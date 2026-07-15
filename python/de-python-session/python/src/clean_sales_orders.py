import os
import pandas as pd

from config import load_config
from logger import setup_logger

def read_csv_files(file_path: str, logger) -> pd.DataFrame:
    logger.info("starting csv read step")
    logger.info(f"reading data from {file_path}")
    
    if not os.path.exists(file_path):
        logger.error(f"file not found: {file_path}")
        raise FileNotFoundError(f"file not found: {file_path}")
    df = pd.read_csv(file_path)
    
    logger.info(f"successfully read {len(df)} rows and {len(df.columns)} columns")
    return df

def clean_column_names(df: pd.DataFrame, logger) -> pd.DataFrame:
    logger.info("starrting column name cleaning step")
    
    original_columns = list(df.columns)
    
    df.columns = (
        df.columns
        .str.strip()
        .str.lower()
        .str.replace(" ", "_")
    )
    
    logger.info(f"original columns: {original_columns}")
    logger.info(f"cleaned columns: {list(df.columns)}")

    return df

def clean_string_columns(df: pd.DataFrame, logger) -> pd.DataFrame:
    logger.info("starting string column cleaning step")
    
    string_columns = df.select_dtypes(include='object').columns
    
    for column in string_columns:
        df[column] = df[column].astype(str).str.strip()
        
    logger.info(f"cleaned string columns: {list(string_columns)}")
    
    return df

def parse_dates(df: pd.DataFrame, date_format: str, logger) -> pd.DataFrame:
    logger.info("starting date parsing step")
    
    logger.info(f"sample order_date values before parsing: {df['order_date'].head(5).tolist()}")
    logger.info(f"expected date format: {date_format}")
    invalid_dates_before = df["order_date"].isna().sum()
    
    df["order_date"] = pd.to_datetime(
        df["order_date"], 
        format=date_format, 
        errors='coerce'
    )
    
    invalid_dates_after = df["order_date"].isna().sum()
    logger.info(f"missing dates before parsing: {invalid_dates_before}")
    logger.info(f"invalid or missing dates after parsing: {invalid_dates_after}")
    
    return df

def handle_nulls(df: pd.DataFrame, logger) -> pd.DataFrame:
    logger.info("starting null handling step")
    
    rows_before = len(df)
    
    df["customer_name"] = df["customer_name"].replace("nan", pd.NA)
    df["customer_name"] = df["customer_name"].fillna("Unknown Customer")
    
    df["quantity"] = pd.to_numeric(df["quantity"], errors='coerce').fillna(0)
    df["unit_price"] = pd.to_numeric(df["unit_price"], errors='coerce').fillna(0)
    
    df = df.dropna(subset=["order_date"])
    
    rows_after =  len(df)
    rows_removed = rows_before - rows_after
    
    logger.info(f"rows before null handling: {rows_before}")
    logger.info(f"rows after null handling: {rows_after}")
    logger.info(f"rows removed due to null handling: {rows_removed}")
    
    return df

def add_business_columns(df: pd.DataFrame, logger) -> pd.DataFrame:
    logger.info("starting business column addition step")
    
    df["total_amount"] = df["quantity"] * df["unit_price"]
    
    logger.info("added total_amount column")
    
    return df
    

def save_cleaned_csv(df: pd.DataFrame, output_path: str, logger) -> None:
    logger.info("starting csv save step")
    logger.info(f"saving cleaned data to {output_path}")
    
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    df.to_csv(output_path, index=False)
    
    logger.info(f"successfully saved cleaned data with {len(df)} rows and {len(df.columns)} columns")

def run_pipeline() -> None:
    """
    1. load configuration
    2. set up logging
    3. read raw data
    4. clean and transform data
    5. save cleaned data
    """
    config = load_config()
    logger = setup_logger(config.log_file_path)
    
    logger.info("=" * 80)
    logger.info(f"Starting pipeline: {config.app_name}")
    logger.info(f"Environment: {config.environment}")
    logger.info("=" * 80)
    
    try:
        df = read_csv_files(config.raw_data_path, logger)
        df = clean_column_names(df, logger)
        df = clean_string_columns(df, logger)
        df = parse_dates(df, config.date_format, logger)
        df = handle_nulls(df, logger)
        df = add_business_columns(df, logger)
        save_cleaned_csv(df, config.processed_data_path, logger)
        
        logger.info("Pipeline completed successfully.")
    except Exception as e:
        logger.exception(f"Pipeline failed with an error: {e}")
        raise
    finally:
        logger.info("=" * 80)
        logger.info(f"Ending pipeline: {config.app_name}")
        logger.info("=" * 80)

    
if __name__ == "__main__":
    run_pipeline()