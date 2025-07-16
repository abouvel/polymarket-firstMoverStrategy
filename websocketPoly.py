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
        if self.verbose:
            print(message)
        try:
            data = json.loads(message)
        except json.JSONDecodeError as e:
            logging.error(f"Error parsing message as JSON: {e}. Message: {message}")
            return
        except Exception as e:
            logging.error(f"Unexpected error during JSON parsing: {e}. Message: {message}")
            return

        # Handle if data is a list (batch messages)
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict):
                    await self._process_price_change(item)
                else:
                    logging.warning(f"Received non-dict item in message list: {item}")
            return
        elif isinstance(data, dict):
            await self._process_price_change(data)
        else:
            logging.warning(f"Received message that is neither dict nor list: {data}")

    async def _process_price_change(self, data):
        if data.get("event_type") != "price_change":
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
            except Exception as e:
                logging.warning(f"Invalid price in change: {change}, error: {e}")
                continue
            side = change.get("side")
            if side == "BUY":
                if best_bid is None or price > best_bid:
                    best_bid = price
            elif side == "SELL":
                if best_ask is None or price < best_ask:
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
        async with websockets.connect(self.ws_url) as ws:
            await self.send_subscribe(ws)
            while True:
                message = await ws.recv()
                await self.on_message(message)