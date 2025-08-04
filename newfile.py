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
gamma_host = "https://gamma-api.polymarket.com"

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
        #os.getenv('POSTGRES_HOST')
        "host": "localhost",
        "port": os.getenv('POSTGRES_PORT'),
        "user": os.getenv('POSTGRES_USER'),
        "password": os.getenv('POSTGRES_PASSWORD'),
        "database": os.getenv('POSTGRES_DB')
    }

async def get_asyncpg_connection():
    """Create and return an asyncpg connection using environment variables."""
    config = get_db_config()
    return await asyncpg.connect(**config)

async def fetch_active_events_optimized(limit=None, batch_size=50, conn=None, clob_client=None):
    """Fetch active events using Gamma API with server-side filtering for better performance."""
    print("Starting fetch_active_events_optimized...")
    stored = 0
    skipped = 0
    processed = 0
    close_conn = False
    
    # Use asyncpg for better async database performance
    print("Setting up database connection...")
    if conn is None:
        conn = await get_asyncpg_connection()
        close_conn = True
        print("Database connection established")
    if clob_client is None:
        clob_client = connect_clob_client()
        print("CLOB client connected")
    
    # Create tables if they don't exist
    print("Creating database tables if they don't exist...")
    await create_tables_async(conn)
    print("Database tables ready")
    
    # Use Gamma API for better filtering - get active events that end in the future
    now = datetime.now(timezone.utc)
    print(f"Current time: {now.isoformat()}")
    
    limit_param = min(limit, batch_size) if limit else batch_size
    
    async with httpx.AsyncClient(timeout=30.0, verify=False) as client:
        offset = 0
        while True:
            try:
                url = f"{gamma_host}/events?active=true&closed=false&limit={limit_param}&offset={offset}"
                print(f"Making API request to: {url}")
                resp = await client.get(url)
                print(f"API response status: {resp.status_code}")
                resp.raise_for_status()
                
                payload = resp.json()
                # API returns list directly, not wrapped in 'data'
                events = payload if isinstance(payload, list) else payload.get("data", [])
                
                if not events:
                    print("No more events to process")
                    break
                
                print(f"Received {len(events)} active events (offset: {offset})")
                print(f"Processing events...")
                
                # Filter and prepare events for concurrent processing
                active_events = []
                for event in events:
                    processed += 1
                    if not event.get('active', True) or event.get('closed', False):
                        print(f"WARNING: Skipping inactive/closed event: {event.get('id')}")
                        skipped += 1
                        continue
                    active_events.append(event)
                
                print(f"Processing {len(active_events)} active events concurrently...")
                
                # Process events concurrently
                async def process_single_event(event):
                    try:
                        # Convert event to market-like structure
                        market_data = {
                            'condition_id': event.get('id'),
                            'question': event.get('title', ''),
                            'end_date_iso': event.get('end_date'),
                            'active': event.get('active', True),
                            'closed': event.get('closed', False),
                            'tokens': []
                        }
                        
                        # Get markets for this event to populate tokens
                        markets_url = f"{host}/markets?event_id={event.get('id')}"
                        markets_resp = await client.get(markets_url)
                        
                        if markets_resp.status_code == 200:
                            markets_data = markets_resp.json()
                            if markets_data.get('data'):
                                first_market = markets_data['data'][0]
                                market_data['tokens'] = first_market.get('tokens', [])
                            
                        return market_data
                    except Exception as e:
                        print(f"ERROR: Error processing event {event.get('id')}: {e}")
                        return None
                
                # Run all event processing concurrently
                event_tasks = [process_single_event(event) for event in active_events]
                event_results = await asyncio.gather(*event_tasks, return_exceptions=True)
                
                # Filter out None results and exceptions
                valid_events = [result for result in event_results if result is not None and not isinstance(result, Exception)]
                print(f"Successfully processed {len(valid_events)} events")
                    
                if limit and processed >= limit:
                    break
                
                # Process events concurrently in smaller batches
                if valid_events:
                    print(f"Processing {len(valid_events)} valid events...")
                    # Process in parallel batches for better performance
                    concurrent_batches = [valid_events[i:i+batch_size] for i in range(0, len(valid_events), batch_size)]
                    print(f"Split into {len(concurrent_batches)} batches for processing")
                    batch_tasks = [process_market_batch(batch, conn, clob_client) for batch in concurrent_batches]
                    batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)
                    
                    for i, result in enumerate(batch_results):
                        if isinstance(result, Exception):
                            print(f"ERROR: Batch {i+1} processing error: {result}")
                        else:
                            print(f"Batch {i+1} completed: {result} events processed")
                            stored += result
                else:
                    print("WARNING: No valid events to process in this batch")
                
                if limit and processed >= limit:
                    break
                
                # Pagination - move to next batch
                offset += len(events)
                if len(events) < batch_size:
                    break  # No more results
                    
            except Exception as e:
                print(f"ERROR: Error fetching events: {e}")
                print(f"Exception details: {type(e).__name__}: {str(e)}")
                break
    
    if close_conn:
        print("Closing database connection...")
        await conn.close()
        print("Database connection closed")
    
    print("\nFinal Summary:")
    print(f"Processed: {processed}")
    print(f"Stored: {stored}")
    print(f"Skipped: {skipped}")
    return {"processed": processed, "stored": stored, "skipped": skipped}

async def fetch_active_markets(limit=None, batch_size=50, conn=None, clob_client=None):
    """Wrapper to maintain backward compatibility - uses optimized event fetching."""
    return await fetch_active_events_optimized(limit, batch_size, conn, clob_client)

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
                    print(f"Sample date: '{market.get('end_date_iso')}' -> '{end_date_str}'")
                
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
                print(f"WARNING: Invalid date format: {end_date_str} - {e}")
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
        print(f"Batch filtered: {len(markets)} total, {len(valid_markets)} valid")
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
        # Optimize database operations with concurrent processing
        if market_data:
            # Concurrent database operations for better performance
            db_tasks = []
            
            # Task 1: Check existing markets in PostgreSQL
            async def check_existing_markets():
                if not market_data:
                    return set()
                market_ids = [market_id for market_id, _, _ in market_data]
                placeholders = ','.join(['$' + str(i+1) for i in range(len(market_ids))])
                check_query = f"SELECT id FROM markets WHERE id IN ({placeholders})"
                existing_records = await conn.fetch(check_query, *market_ids)
                return {record['id'] for record in existing_records}
            
            # Task 2: Push to ChromaDB sequentially (simpler, more reliable)
            async def push_to_chromadb():
                poly_url = os.getenv("WEBHOOK_URL", "http://twitter-webhook:8000") + "/poly"
                successful_pushes = 0
                
                async with httpx.AsyncClient(timeout=30.0, verify=False) as client:
                    for market_id, market_name, _ in market_data:
                        try:
                            payload = {"id": str(market_id), "name": str(market_name)}
                            resp = await client.post(poly_url, json=payload)
                            if resp.status_code == 200:
                                result = await resp.json()
                                if result.get("status") == "already_exists":
                                    continue  # Skip already existing
                                else:
                                    successful_pushes += 1
                            else:
                                print(f"ERROR: ChromaDB push failed for {market_id}: HTTP {resp.status_code}")
                        except Exception as e:
                            print(f"ERROR: ChromaDB exception for {market_id}: {e}")
                            continue
                
                print(f"ChromaDB: {successful_pushes}/{len(market_data)} new events stored")
            
            # Execute database check and ChromaDB push concurrently
            existing_market_ids, _ = await asyncio.gather(
                check_existing_markets(),
                push_to_chromadb(),
                return_exceptions=True
            )
            
            # Handle potential errors from gather
            if isinstance(existing_market_ids, Exception):
                print(f"ERROR: Error checking existing markets: {existing_market_ids}")
                existing_market_ids = set()
            
            # Filter out existing markets and insert new ones
            new_market_data = [(market_id, title, expiry_date) 
                              for market_id, title, expiry_date in market_data 
                              if market_id not in existing_market_ids]
            
            # Batch insert new markets to PostgreSQL
            if new_market_data:
                await conn.executemany("""
                    INSERT INTO markets (id, title, expiry_date)
                    VALUES ($1, $2, $3)
                    ON CONFLICT (id) DO UPDATE SET 
                        title = EXCLUDED.title,
                        expiry_date = EXCLUDED.expiry_date;
                """, new_market_data)
                print(f"[PostgreSQL] Inserted {len(new_market_data)} new markets")
            else:
                print(f"[PostgreSQL] All {len(market_data)} markets already exist")
        # Check for duplicates in tokens table before inserting
        if token_data:
            # Check existing tokens in PostgreSQL
            existing_token_ids = set()
            if token_data:
                token_ids = [token_id for token_id, _, _, _, _ in token_data]
                placeholders = ','.join(['$' + str(i+1) for i in range(len(token_ids))])
                check_query = f"SELECT id FROM tokens WHERE id IN ({placeholders})"
                existing_records = await conn.fetch(check_query, *token_ids)
                existing_token_ids = {record['id'] for record in existing_records}
            
            # Filter out existing tokens
            new_token_data = [(token_id, market_id, name, bid_price, ask_price) 
                             for token_id, market_id, name, bid_price, ask_price in token_data 
                             if token_id not in existing_token_ids]
            
            # Batch insert new tokens with prices
            if new_token_data:
                await conn.executemany("""
                    INSERT INTO tokens (id, market_id, name, bid_price, ask_price)
                    VALUES ($1, $2, $3, $4, $5)
                    ON CONFLICT (id) DO UPDATE SET
                        bid_price = EXCLUDED.bid_price,
                        ask_price = EXCLUDED.ask_price;
                """, new_token_data)
                print(f"[PostgreSQL] Inserted {len(new_token_data)} new tokens")
            else:
                print(f"[PostgreSQL] All {len(token_data)} tokens already exist")
        
        print(f"Batch processed: {len(valid_markets)} markets | {len(token_data)} tokens")
        return len(valid_markets)
    except Exception as e:
        print(f"WARNING: Error storing batch: {e}")
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
