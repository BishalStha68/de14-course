import os
from sqlalchemy import create_engine
from dotenv import load_dotenv


def get_database_engine():
    """
    Creates and returns a SQLAlchemy database engine.

    The database connection details are loaded from environment variables.
    This avoids hardcoding credentials directly inside the code.
    """

    load_dotenv()

    postgres_host = os.getenv("POSTGRES_HOST")
    postgres_port = os.getenv("POSTGRES_PORT")
    postgres_db = os.getenv("POSTGRES_DB")
    postgres_user = os.getenv("POSTGRES_USER")
    postgres_password = os.getenv("POSTGRES_PASSWORD")

    database_url = (
        f"postgresql+psycopg2://{postgres_user}:{postgres_password}"
        f"@{postgres_host}:{postgres_port}/{postgres_db}"
    )

    engine = create_engine(database_url)

    return engine