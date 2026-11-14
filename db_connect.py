import os
import sys
from pathlib import Path
from dotenv import load_dotenv
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from sqlalchemy import create_engine, text
import pandas as pd

# Load environment variables from .env file in the current directory
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

def get_db_config(target_db: str | None = None) -> dict:
    """
    Get database connection configuration from environment variables.
    """
    return {
        "host": os.getenv("DB_HOST", "localhost"),
        "port": int(os.getenv("DB_PORT", "5433")),
        "database": target_db or os.getenv("DB_NAME", "olist_dw"),
        "user": os.getenv("DB_USER", "postgres"),
        "password": os.getenv("DB_PASSWORD", ""),
    }

def get_connection(target_db: str | None = None, autocommit: bool = False):
    """
    Get a raw psycopg2 database connection.
    """
    config = get_db_config(target_db)
    conn = psycopg2.connect(
        host=config["host"],
        port=config["port"],
        dbname=config["database"],
        user=config["user"],
        password=config["password"]
    )
    if autocommit:
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    return conn

def get_engine(target_db: str | None = None):
    """
    Get a SQLAlchemy engine for the database.
    """
    config = get_db_config(target_db)
    url = f"postgresql+psycopg2://{config['user']}:{config['password']}@{config['host']}:{config['port']}/{config['database']}"
    return create_engine(url)

def ensure_database_exists(target_db: str = "olist_dw") -> bool:
    """
    Checks if target database exists. If not, connects to default 'postgres' database and creates it.
    """
    config = get_db_config("postgres")
    try:
        conn = psycopg2.connect(
            host=config["host"],
            port=config["port"],
            dbname="postgres",
            user=config["user"],
            password=config["password"]
        )
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM pg_database WHERE datname = %s;", (target_db,))
            exists = cur.fetchone()
            if not exists:
                print(f"[*] Database '{target_db}' does not exist. Creating database '{target_db}'...")
                cur.execute(f'CREATE DATABASE "{target_db}";')
                print(f"[+] Database '{target_db}' created successfully.")
            else:
                print(f"[i] Database '{target_db}' already exists.")
        conn.close()
        return True
    except Exception as e:
        print(f"[!] Error ensuring database '{target_db}' exists: {e}")
        return False

def test_connection():
    """
    Test PostgreSQL connectivity and show server / database info.
    """
    config = get_db_config()
    print("=" * 60)
    print("Testing PostgreSQL Connection:")
    print(f"  Host    : {config['host']}")
    print(f"  Port    : {config['port']}")
    print(f"  User    : {config['user']}")
    print(f"  Database: {config['database']}")
    print("=" * 60)

    # First test server access via 'postgres' or target db
    try:
        ensure_database_exists(config["database"])
    except Exception as e:
        print(f"[!] Could not connect to default database: {e}")

    # Now test target database connection
    try:
        conn = get_connection()
        with conn.cursor() as cur:
            cur.execute("SELECT version();")
            ver = cur.fetchone()[0]
            print(f"[+] Connected to '{config['database']}' successfully!")
            print(f"    Version: {ver.split(',')[0]}")
            
            # Check schemas
            cur.execute("SELECT schema_name FROM information_schema.schemata WHERE schema_name IN ('staging', 'dw');")
            schemas = [row[0] for row in cur.fetchall()]
            print(f"    Existing schemas: {schemas if schemas else 'None (run etl_pipeline.py to create)'}")
        conn.close()
        return True
    except psycopg2.OperationalError as e:
        print(f"[-] Connection Failed: {e}")
        print("\n[TIP] Check if:")
        print("  1. PostgreSQL service is running.")
        print("  2. DB_PASSWORD in .env is correct.")
        print("  3. DB_PORT is 5433 (or matches your PostgreSQL installation).")
        return False

def query_df(sql: str, params: tuple | None = None) -> pd.DataFrame:
    """
    Execute SQL and return results as a Pandas DataFrame.
    """
    engine = get_engine()
    return pd.read_sql_query(sql, con=engine, params=params)

if __name__ == "__main__":
    test_connection()
