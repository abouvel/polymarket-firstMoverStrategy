# cb_connect.py

import os
import psycopg2
import asyncpg
from dotenv import load_dotenv

load_dotenv()  # Load environment variables from .env

def get_db_connection():
    try:
        conn = psycopg2.connect(
            user=os.getenv("POSTGRES_USER"),
            password=os.getenv("POSTGRES_PASSWORD"),
            host=os.getenv("POSTGRES_HOST"),
            port=os.getenv("POSTGRES_PORT"),
            dbname=os.getenv("POSTGRES_DB")
        )
        conn.autocommit = True
        print("✅ DB Connection successful")
        create_markets_and_tokens_tables(conn)
        return conn
    except Exception as e:
        print(f"❌ DB Connection failed: {e}")
        return None

async def create_tables_async(conn):
    """Create the markets and tokens tables if they do not exist (async version)."""
    try:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS markets (
                id TEXT PRIMARY KEY,
                title TEXT,
                expiry_date TIMESTAMP
            );
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS tokens (
                id TEXT PRIMARY KEY,
                market_id TEXT NOT NULL,
                name TEXT,
                bid_price DECIMAL,
                ask_price DECIMAL,
                FOREIGN KEY (market_id) REFERENCES markets(id) ON DELETE CASCADE
            );
        """)
        print("✅ Tables 'markets' and 'tokens' created or already exist.")
    except Exception as e:
        print(f"❌ Failed to create tables: {e}")

def create_markets_and_tokens_tables(conn):
    """Create the markets and tokens tables if they do not exist."""
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS markets (
                    id TEXT PRIMARY KEY,
                    title TEXT,
                    expiry_date TIMESTAMP
                );
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS tokens (
                    id TEXT PRIMARY KEY,
                    market_id TEXT NOT NULL,
                    name TEXT,
                    bid_price DECIMAL,
                    ask_price DECIMAL,
                    FOREIGN KEY (market_id) REFERENCES markets(id) ON DELETE CASCADE
                );
            """)
        print("✅ Tables 'markets' and 'tokens' created or already exist.")
    except Exception as e:
        print(f"❌ Failed to create tables: {e}")