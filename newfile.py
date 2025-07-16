# fetch_markets.py

import os
import json
import httpx
import asyncio
from dotenv import load_dotenv
from dbConnect import get_db_connection, create_markets_and_tokens_tables, create_tables_async  # Import connection function
from datetime import datetime, timezone
import asyncpg
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import BookParams

# Load environment variables
load_dotenv()
host = "https://clob.polymarket.com"

def connect_clob_client():
    load_dotenv()

    """Create and return a ClobClient using environment variables."""
    key = os.getenv("POLY_KEY")
    POLYMARKET_PROXY_ADDRESS = os.getenv("POLY_ADDRESS")
    chain_id = 137
    return ClobClient(host, key=key, chain_id=chain_id, signature_type=1, funder=POLYMARKET_PROXY_ADDRESS)

def get_db_config():
    """Return DB config from environment variables."""
    return {
        "host": os.getenv('POSTGRES_HOST'),
        "port": os.getenv('POSTGRES_PORT'),
        "user": os.getenv('POSTGRES_USER'),
        "password": os.getenv('POSTGRES_PASSWORD'),
        "database": os.getenv('POSTGRES_DB')
    }

async def get_asyncpg_connection():
    """Create and return an asyncpg connection using environment variables."""
    config = get_db_config()
    return await asyncpg.connect(**config)

async def fetch_active_markets(limit=None, batch_size=50, conn=None, clob_client=None):
    """Fetch and return all active Polymarket markets. Optionally accept an existing DB connection."""
    stored = 0
    skipped = 0
    processed = 0
    cursor_id = ""
    close_conn = False

    # Use asyncpg for better async database performance
    if conn is None:
        conn = await get_asyncpg_connection()
        close_conn = True
    if clob_client is None:
        clob_client = connect_clob_client()
    
    # Create tables if they don't exist
    await create_tables_async(conn)

    async with httpx.AsyncClient(timeout=30.0) as client:
        while True:
            try:
                url = f"{host}/markets?active=true&closed=false&next_cursor={cursor_id}"
                resp = await client.get(url)
                resp.raise_for_status()

                payload = resp.json()
                markets = payload.get("data", [])

                print(f"📦 Received {len(markets)} markets")
                
                # Process markets in batches for better performance
                batch = []
                for market in markets:
                    processed += 1
                    if not market.get("active", False):
                        skipped += 1
                        continue

                    batch.append(market)
                    
                    # Process batch when it reaches batch_size or at the end
                    if len(batch) >= batch_size:
                        batch_stored = await process_market_batch(batch, conn, clob_client)
                        stored += batch_stored
                        batch = []

                    if limit and processed >= limit:
                        break

                # Process remaining markets in the last batch
                if batch:
                    batch_stored = await process_market_batch(batch, conn, clob_client)
                    stored += batch_stored

                if limit and processed >= limit:
                    break

                cursor_id = payload.get("next_cursor", "")
                if not cursor_id or cursor_id == "LTE=":
                    break

            except Exception as e:
                print(f"❌ Error fetching markets: {e}")
                break

    if close_conn:
        await conn.close()
    print("\n📈 Summary:")
    print(f"Processed: {processed}, Stored: {stored}, Skipped: {skipped}")
    return {"processed": processed, "stored": stored, "skipped": skipped}

async def process_market_batch(markets, conn, clob_client):
    """Process a batch of markets concurrently"""
    now = datetime.now(timezone.utc)
    valid_markets = []
    
    # Counters for debugging
    expired_count = 0
    invalid_date_count = 0
    inactive_count = 0
    missing_condition_count = 0
    
    # Filter markets first
    for market in markets:
        # Check end_date_iso for expiration
        end_date_str = market.get("end_date_iso")
        expiry_date = None
        
        if end_date_str:
            try:
                # Handle different date formats
                if end_date_str.endswith('Z'):
                    end_date_str = end_date_str.replace('Z', '+00:00')
                elif 'T' in end_date_str and '+' not in end_date_str and 'Z' not in end_date_str:
                    # If it's ISO format without timezone, assume UTC
                    end_date_str = end_date_str + '+00:00'
                
                # Debug: show first few date strings
                if invalid_date_count < 3:
                    print(f"🔍 Sample date: '{market.get('end_date_iso')}' -> '{end_date_str}'")
                
                expiry_date = datetime.fromisoformat(end_date_str)
                # Convert to timezone-naive datetime for PostgreSQL
                if expiry_date.tzinfo is not None:
                    expiry_date = expiry_date.replace(tzinfo=None)
                
                # Compare timezone-naive datetimes
                if expiry_date < now.replace(tzinfo=None):
                    expired_count += 1
                    continue  # Skip expired markets
            except Exception as e:
                invalid_date_count += 1
                print(f"⚠️ Invalid date format: {end_date_str} - {e}")
                continue  # Skip markets with invalid dates
        
        # Additional checks
        if not market.get("active", False) or market.get("closed", False):
            inactive_count += 1
            continue

        condition_id = market.get("condition_id")
        if not condition_id:
            missing_condition_count += 1
            continue

        valid_markets.append((market, expiry_date))
    
    # Print batch filtering summary
    if expired_count > 0 or invalid_date_count > 0 or inactive_count > 0 or missing_condition_count > 0:
        print(f"🔍 Batch filtered: {len(markets)} total, {len(valid_markets)} valid")
        print(f"   - Expired: {expired_count}, Invalid dates: {invalid_date_count}")
        print(f"   - Inactive/closed: {inactive_count}, Missing condition_id: {missing_condition_count}")
    
    if not valid_markets:
        return 0
    
    try:
        # Prepare batch data
        market_data = []
        token_data = []
        price_params = []
        token_id_to_info = {}
        for market, expiry_date in valid_markets:
            condition_id = market.get("condition_id")
            title = market.get("question", "")
            tokens = market.get("tokens", [])
            market_data.append((condition_id, title, expiry_date))
            for token in tokens:
                token_id = token.get("token_id")
                token_name = token.get("outcome")
                if token_id:
                    price_params.append(BookParams(token_id=token_id, side="BUY"))
                    price_params.append(BookParams(token_id=token_id, side="SELL"))
                    token_id_to_info[token_id] = (condition_id, token_name)
        # Fetch prices for all tokens in the batch
        if price_params:
            resp = clob_client.get_prices(params=price_params)
            # resp: {token_id: {"BUY": price, "SELL": price}}
            for token_id, (condition_id, token_name) in token_id_to_info.items():
                prices = resp.get(token_id, {})
                bid_price = prices.get("BUY")
                ask_price = prices.get("SELL")
                token_data.append((token_id, condition_id, token_name, bid_price, ask_price))
        # Batch insert markets
        if market_data:
            await conn.executemany("""
                INSERT INTO markets (id, title, expiry_date)
                VALUES ($1, $2, $3)
                ON CONFLICT (id) DO UPDATE SET 
                    title = EXCLUDED.title,
                    expiry_date = EXCLUDED.expiry_date;
            """, market_data)
        # Batch insert tokens (with bid/ask)
        if token_data:
            await conn.executemany("""
                INSERT INTO tokens (id, market_id, name, bid_price, ask_price)
                VALUES ($1, $2, $3, $4, $5)
                ON CONFLICT (id) DO NOTHING;
            """, token_data)
        print(f"✅ Batch stored: {len(valid_markets)} markets | {len(token_data)} tokens")
        return len(valid_markets)
    except Exception as e:
        print(f"⚠️ Error storing batch: {e}")
        return 0

def main():
    """CLI entrypoint for fetching active markets."""
    import argparse
    parser = argparse.ArgumentParser(description="Fetch and store active Polymarket markets.")
    parser.add_argument('--limit', type=int, default=None, help='Limit the number of markets to process')
    parser.add_argument('--batch-size', type=int, default=50, help='Batch size for DB inserts')
    args = parser.parse_args()
    asyncio.run(fetch_active_markets(limit=args.limit, batch_size=args.batch_size))

if __name__ == "__main__":
    main()
