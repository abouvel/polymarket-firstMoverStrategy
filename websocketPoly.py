import asyncio
import json
import os
from dotenv import load_dotenv
from newfile import get_asyncpg_connection
import websockets
import logging
MARKET_CHANNEL = "market"
USER_CHANNEL = "user"

def createMarketWS(asset_ids, call_back, verbose):
    url = "wss://ws-subscriptions-clob.polymarket.com"
    load_dotenv()
    auth = {"apiKey": os.getenv('API_KEY'), "secret": os.getenv('API_SECRET'), "passphrase": os.getenv('API_PASSPHRASE')}
    return WebSocketOrderBook(MARKET_CHANNEL, url, asset_ids, auth, call_back, verbose)

class WebSocketOrderBook:
    def __init__(self, channel_type, url, asset_ids, auth, message_callback, verbose):
        self.channel_type = channel_type
        self.url = url
        self.asset_ids = asset_ids
        self.auth = auth
        self.message_callback = message_callback
        self.verbose = verbose
        self.ws_url = url + "/ws/" + channel_type

    async def send_subscribe(self, ws):
        if self.channel_type == MARKET_CHANNEL:
            await ws.send(json.dumps({"assets_ids": self.asset_ids, "type": MARKET_CHANNEL}))
        elif self.channel_type == USER_CHANNEL and self.auth:
            await ws.send(json.dumps({"markets": self.asset_ids, "type": USER_CHANNEL, "auth": self.auth}))
        else:
            raise Exception("Invalid channel type or missing auth for user channel.")

    async def on_message(self, message):
        try:
            data = json.loads(message)
        except json.JSONDecodeError as e:
            logging.error(f"Error parsing message as JSON: {e}. Message: {message}")
            return
        except Exception as e:
            logging.error(f"Unexpected error during JSON parsing: {e}. Message: {message}")
            return

    # Handle batched messages
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict):
                    await self._handle_event_dict(item)
                else:
                    logging.warning(f"Received non-dict item in message list: {item}")
            return

    # Handle single message
        elif isinstance(data, dict):
            await self._handle_event_dict(data)
        else:
            logging.warning(f"Received message that is neither dict nor list: {data}")
    async def _handle_event_dict(self, data: dict):
        event_type = data.get("event_type")

        if event_type == "book":
            await self._handle_book_event(data)
        elif event_type == "price_change":
            await self._handle_price_change_event(data)
        else:
            logging.info(f"Unhandled event_type: {event_type}")


    async def _handle_book_event(self, data: dict):
        asset_id = data.get("asset_id")
        best_bid = float(data["bids"][0]["price"]) if data.get("bids") else None
        best_ask = float(data["asks"][0]["price"]) if data.get("asks") else None

        if asset_id and (best_bid is not None or best_ask is not None):
            try:
                conn = await get_asyncpg_connection()
                if best_bid is not None:
                    await conn.execute(
                        "UPDATE tokens SET bid_price = $1 WHERE id = $2",
                        best_bid, asset_id
                    )
                if best_ask is not None:
                    await conn.execute(
                        "UPDATE tokens SET ask_price = $1 WHERE id = $2",
                        best_ask, asset_id
                    )
                await conn.close()
            except Exception as e:
                logging.error(f"DB error while writing book event for {asset_id}: {e}")


    async def _handle_price_change_event(self, data: dict):
        try:
            await self._process_price_change(data)
        except Exception as e:
            logging.error(f"Error in price change processing: {e}")


    async def _process_price_change(self, data):
        if data.get("event_type") != "price_change" and data.get("event_type") != "book":
            return
        

        asset_id = data.get("asset_id")
        if not asset_id:
            logging.warning(f"No asset_id in price_change event: {data}")
            return

        best_bid = None
        best_ask = None
        for change in data.get("changes", []):
            try:
                price = float(change.get("price", 0))
                size = float(change.get("size", 0))
            except Exception as e:
                logging.warning(f"Invalid price/size in change: {change}, error: {e}")
                continue

            side = change.get("side")

            if side == "BUY":
                if size == 0 and price == best_bid:
                    best_bid = None  # best bid removed, mark for rebuild
                elif size > 0 and (best_bid is None or price > best_bid):
                    best_bid = price

            elif side == "SELL":
                if size == 0 and price == best_ask:
                    best_ask = None  # best ask removed, mark for rebuild
                elif size > 0 and (best_ask is None or price < best_ask):
                    best_ask = price


        try:
            conn = await get_asyncpg_connection()
            try:
                if best_bid is not None:
                    await conn.execute(
                        "UPDATE tokens SET bid_price = $1 WHERE id = $2",
                        best_bid, asset_id
                    )
                if best_ask is not None:
                    await conn.execute(
                        "UPDATE tokens SET ask_price = $1 WHERE id = $2",
                        best_ask, asset_id
                    )
                # Fetch updated bid and ask from the database
                row = await conn.fetchrow(
                    "SELECT bid_price, ask_price, market_id, name FROM tokens WHERE id = $1",
                    asset_id
                )
                if row is not None:
                    bid = row["bid_price"]
                    ask = row["ask_price"]
                    marketType = row["name"]
                    market_id = row["market_id"]
                    if bid is not None and ask is not None:
                        spread = ask - bid
                        if 0.1 < spread < 0.3 and bid != 0 and ask != 0:
                            slug = None
                            if market_id is not None:
                                market_row = await conn.fetchrow(
                                    "SELECT title FROM markets WHERE id = $1",
                                    market_id
                                )
                                if market_row is not None:
                                    title = market_row["title"]
                            if title:
                                print(f"Spread for market '{title}' and type '{marketType}' is {spread:.4f}, which is between 0.05 and 0.1. Spread is {ask} - {bid}")
                            else:
                                print(f"Spread for asset_id {asset_id} (market slug not found) is {spread:.4f}, which is between 0.05 and 0.1")
            except Exception as db_exc:
                logging.error(f"Database error updating best bid/ask for asset_id {asset_id}: {db_exc}")
            finally:
                await conn.close()
        except Exception as conn_exc:
            logging.error(f"Error getting DB connection for asset_id {asset_id}: {conn_exc}")

        # If a callback is provided, call it (can be async or sync)
        if self.message_callback:
            try:
                if asyncio.iscoroutinefunction(self.message_callback):
                    await self.message_callback(data)
                else:
                    self.message_callback(data)
            except Exception as cb_exc:
                logging.error(f"Error in message_callback: {cb_exc}")

    async def run(self):
        async with websockets.connect(
            self.ws_url, 
            ping_interval=30,  # Send ping every 30 seconds
            ping_timeout=10,   # Wait 10 seconds for pong response
            close_timeout=10   # Wait 10 seconds for close frame
        ) as ws:
            await self.send_subscribe(ws)
            while True:
                message = await ws.recv()
                await self.on_message(message)