import os
from dataclasses import dataclass
from dotenv import load_dotenv

@dataclass
class AppConfig:
    app_name: str
    environment: str
    raw_data_path: str
    cleaned_data_path: str
    log_file_path: str
    date_format: str
    
    db_host: str
    db_port: int
    db_name: str
    db_user: str
    db_password: str
    db_schema: str
    db_table: str

def load_config() -> AppConfig:
    load_dotenv()
    
    config = AppConfig(
        app_name=os.getenv('APP_NAME', 'Sales Orders ETL Pipeline'),
        environment=os.getenv('ENVIRONMENT', 'Development'),
        raw_data_path=os.getenv('RAW_DATA_PATH', 'data/raw/sales_orders_raw.csv'),
        cleaned_data_path=os.getenv('CLEANED_DATA_PATH', 'data/cleaned/sales_orders_cleaned.csv'),
        log_file_path=os.getenv('LOG_FILE_PATH', 'logs/pipeline.log'),
        date_format=os.getenv('DATE_FORMAT', '%Y-%m-%d'),
        db_host=os.getenv('DB_HOST', 'localhost'),
        db_port=int(os.getenv('DB_PORT', 5432)),
        db_name=os.getenv('DB_NAME', 'de_db'),
        db_user=os.getenv('DB_USER', 'de_user'),
        db_password=os.getenv('DB_PASSWORD', 'de_password'),
        db_schema=os.getenv('DB_SCHEMA', 'public'),
        db_table=os.getenv('DB_TABLE', 'sales_orders_cleaned')
    )
    return config