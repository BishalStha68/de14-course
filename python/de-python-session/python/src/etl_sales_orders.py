import os
from typing import List, Tuple

import pandas as pd
import psycopg2
from psycopg2.extras import execute_values

from config import load_config
from logger import setup_logger

def extract_csv(file_path: str, logger) -> pd.DataFrame:
    logger.info("starting csv read step")
    logger.info(f"reading data from {file_path}")
    
    if not os.path.exists(file_path):
        logger.error(f"file not found: {file_path}")
        raise FileNotFoundError(f"file not found: {file_path}")
    df = pd.read_csv(file_path)
    
    logger.info(f"successfully read {len(df)} rows and {len(df.columns)} columns")
    return df

def transform_sales_orders(df: pd.DataFrame, date_format: str, logger) -> pd.DataFrame:
    logger.info("starting data transformation step")
    
    rows_before_transform = len(df)
    
    logger.info("cleaning column names")
    df.columns = (
        df.columns
        .str.strip()
        .str.lower()
        .str.replace(" ", "_")
    )
    
    required_columns = [
        "order_id","customer_name","customer_email","order_date","product","quantity","unit_price","country",
    ]
    
    missing_columns = [col for col in required_columns if col not in df.columns]
    
    if missing_columns:
        logger.error(f"missing required columns: {missing_columns}")
        raise ValueError(f"missing required columns: {missing_columns}")
    
    logger.info("cleaning string columns")
    string_columns = df.select_dtypes(include='object').columns
    
    for column in string_columns:
        df[column] = df[column].astype(str).str.strip()
    
    logger.info("parsing order_date column")
    df["order_date"] = pd.to_datetime(
        df["order_date"], 
        format=date_format, 
        errors='coerce'
    )
    
    invalid_date_count =df["order_date"].isna().sum()
    logger.info(f"number of invalid order_date entries after parsing: {invalid_date_count}")
    
    logger.info("handling missing values")
    
    df["customer_name"] = df["customer_name"].replace("nan",pd.NA)
    df["customer_name"] = df["customer_name"].fillna("Unknown Customer")
    
    df["product"] = df["product"].replace("nan",pd.NA)
    df["product"] = df["product"].fillna("Unknown Product")
    
    df["quantity"] = pd.to_numeric(df["quantity"], errors='coerce').fillna(0)
    df["unit_price"] = pd.to_numeric(df["unit_price"], errors='coerce').fillna(0.0)
    
    logger.info("Removing rows with missing order_date")
    df = df.dropna(subset=["order_date"])
    
    logger.info("creating total_amount column")
    df["total_amount"] = df["quantity"] * df["unit_price"]  
    
    zero_amount_count = len(df[df["total_amount"] == 0])
    
    if zero_amount_count > 0:
        logger.warning(f"found {zero_amount_count} rows with total_amount equal to 0")
        
    logger.info("converting order_date to date-only value for database loading")
    df["order_date"] = df["order_date"].dt.date
    
    final_columns = [
        "order_id","customer_name","customer_email","order_date","product","quantity","unit_price","country","total_amount",
    ]
    
    df = df[final_columns]
    
    rows_after_transform = len(df)
    rows_removed = rows_before_transform - rows_after_transform
    
    logger.info("transform step completed")
    logger.info(f"rows before transformation: {rows_before_transform}")
    logger.info(f"rows after transformation: {rows_after_transform}")
    logger.info(f"rows removed: {rows_removed}")
    
    return df

def save_cleaned_csv(df: pd.DataFrame, file_path: str, logger) -> None:
    logger.info("starting cleaned csv save step")
    logger.info(f"saving cleaned data to {file_path}")
    
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    
    df.to_csv(file_path, index=False)
    
    logger.info(f"successfully saved cleaned data to {file_path}")
    
def get_database_connection(config, logger):
    logger.info("establishing database connection")
    
    connection = psycopg2.connect(
        host=config.db_host,
        port=config.db_port,
        dbname=config.db_name,
        user=config.db_user,
        password=config.db_password
    )
    
    logger.info("database connection established")
    
    return connection

def create_target_table(connection, config, logger) -> None:
    logger.info("checking or creating target table in database")
    
    create_table_sql = f"""
    CREATE TABLE IF NOT EXISTS {config.db_schema}.{config.db_table} (
        order_id INTEGER PRIMARY KEY,
        customer_name TEXT NOT NULL,
        customer_email TEXT,
        order_date DATE NOT NULL,
        product TEXT NOT NULL,
        quantity NUMERIC(10,2) NOT NULL,
        unit_price NUMERIC(12,2) NOT NULL,
        country TEXT,
        total_amount NUMERIC(14, 2) NOT NULL,
        etl_loaded_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    """
    
    with connection.cursor() as cursor:
        cursor.execute(create_table_sql)
    
    logger.info(f"target table {config.db_schema}.{config.db_table} is ready")
    
def dataframe_to_records(df: pd.DataFrame) -> List[Tuple]:
    records = list(df.itertuples(index=False, name=None))
    return records

def load_sales_orders(connection, df: pd.DataFrame, config, logger) -> None:
    logger.info("starting data load step")
    
    records = dataframe_to_records(df)
    
    if not records:
        logger.warning("no records available to load. skipping database load step.")
        return
    
    insert_sql = f"""
    INSERT INTO {config.db_schema}.{config.db_table} (
        order_id, customer_name, customer_email, order_date, product, quantity, unit_price, country, total_amount
    ) VALUES %s
    ON CONFLICT (order_id)
    DO UPDATE SET
        customer_name = EXCLUDED.customer_name,
        customer_email = EXCLUDED.customer_email,
        order_date = EXCLUDED.order_date,
        product = EXCLUDED.product,
        quantity = EXCLUDED.quantity,
        unit_price = EXCLUDED.unit_price,
        country = EXCLUDED.country,
        total_amount = EXCLUDED.total_amount,
        etl_loaded_at = CURRENT_TIMESTAMP;
    """
    
    with connection.cursor() as cursor:
        execute_values(cursor, insert_sql, records)
    
    logger.info("load step completed successfully")
    logger.info(f"loaded {len(records)} records into database table {config.db_schema}.{config.db_table}")
    
def run_etl_pipeline() -> None:
    """
    1. load configuration
    2. set up logging
    3. extract raw data from csv
    4. transform and clean data
    5. save cleaned data to new csv
    6. connect to postgres
    7. start transaction
    8. create target table if not exists
    9. load transformed data into postgres with upsert logic
    10. commit transaction if successful
    11. roll back transaction if any errors occur
    """
    config = load_config()
    logger = setup_logger(config.log_file_path)
    
    logger.info("=" * 80)
    logger.info(f"Starting pipeline: {config.app_name}")
    logger.info(f"Environment: {config.environment}")
    logger.info("=" * 80)
    
    connection = None
    
    try:
        raw_df = extract_csv(config.raw_data_path, logger)
        transformed_df = transform_sales_orders(raw_df, config.date_format, logger)
        save_cleaned_csv(transformed_df, config.cleaned_data_path, logger)
        
        connection = get_database_connection(config, logger)
        
        logger.info("beginning database transaction")
        
        create_target_table(connection, config, logger)
        load_sales_orders(connection, transformed_df, config, logger)
        
        connection.commit()
        
        logger.info("transaction committed successfully")
        logger.info("Pipeline completed successfully.")
    
    except Exception as e:
        logger.error(f"an error occurred: {e}")
        if connection is not None:
            logger.info("rolling back database transaction")
            connection.rollback()
            logger.info("transaction rolled back due to error")
            
        raise
    finally:
        if connection is not None:
            connection.close()
            logger.info("database connection closed")
            
        logger.info("=" * 80)
        logger.info(f"Finished pipeline: {config.app_name}")
        logger.info("=" * 80)

if __name__ == "__main__":
    run_etl_pipeline()
    