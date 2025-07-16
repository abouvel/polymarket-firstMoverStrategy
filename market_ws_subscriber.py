import asyncio
from newfile import get_asyncpg_connection, fetch_active_markets
from py_clob_client.client import ClobClient
import os
from dotenv import load_dotenv
from websocketPoly import WebSocketOrderBook, createMarketWS


async def subscribeToAll():
    conn = await get_asyncpg_connection()
    try:
        rows = await conn.fetch("SELECT id FROM tokens;")
        asset_ids = [row['id'] for row in rows]
        MarketWS = createMarketWS(asset_ids, None, True)
        await MarketWS.run()
    finally:
        await conn.close()

def connect():
    load_dotenv()
    host: str = "https://clob.polymarket.com"
    key: str = os.getenv("POLY_KEY")  # Loaded from .env
    chain_id: int = 137 # No need to adjust this
    POLYMARKET_PROXY_ADDRESS: str = os.getenv("POLY_ADDRESS")  # Loaded from .env

async def run_all():
        # Scrape all markets and store in DB
    await fetch_active_markets()
        # After scraping, subscribe to all
    await subscribeToAll()


async def load_or_fetch_markets(conn):
    """Load markets from DB, or fetch if none exist."""
    # Check if any markets exist
    result = await conn.fetchrow("SELECT COUNT(*) AS count FROM markets;")
    if result and result['count'] == 0:
        print("No markets found in DB. Fetching from API...")
        await fetch_active_markets(conn=conn)
    else:
        print(f"Markets found in DB: {result['count']}")
    # Load all markets
    rows = await conn.fetch("SELECT id, title FROM markets;")
    return rows

async def main():
    conn = await get_asyncpg_connection()
    try:
        markets = await load_or_fetch_markets(conn)
        print(f"Loaded {len(markets)} markets.")
        connect()
        # Loop through markets and (for now) do nothing in the loop
        # for market in markets:
        #     market_id = market['id']
        #     market_title = market['title']
            # Placeholder for websocket subscription logic
            # e.g., await subscribe_to_market_ws(market_id)
            # pass
    finally:
        await conn.close()

# For testing, you can run this file directly
if __name__ == "__main__":
    asyncio.run(run_all()) 