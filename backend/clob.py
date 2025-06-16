import os
import json
import time
import requests
import websocket
import threading
import datetime
from py_clob_client.client import ClobClient

# -------------------------------
# Constants
# -------------------------------
host = "https://clob.polymarket.com"
key = os.getenv("POLYMARKET_API_KEY")
chain_id = 137
client = ClobClient(host, key=key, chain_id=chain_id)

WS_URL = "wss://ws-subscriptions-clob.polymarket.com/ws/market"
NAME_MAP_FILE = "token_name_map.json"
CACHE_TTL_SECONDS = 60 * 60  # 1 hour
token_map, market_map ={}, {}   

# -------------------------------
# Cache Helpers
# -------------------------------
def load_json_cache():
    global token_map, market_map

    try:
        if not os.path.exists(NAME_MAP_FILE):
            return {}, {}
        with open(NAME_MAP_FILE, "r") as f:
            data = json.load(f)
            if time.time() - data["timestamp"] < CACHE_TTL_SECONDS:
                return data.get("token_map", {}), data.get("market_map", {})
    except Exception as e:
        print(f"⚠️ Failed to load cache from {NAME_MAP_FILE}:", e)
    return {}, {}

def save_json_cache():
    global token_map, market_map

    try:
        with open(NAME_MAP_FILE, "w") as f:
            json.dump({
                "timestamp": time.time(),
                "token_map": token_map,
                "market_map": market_map
            }, f)
    except Exception as e:
        print(f"⚠️ Failed to save cache to {NAME_MAP_FILE}:", e)

# -------------------------------
# Fetch Token Map with Caching
# -------------------------------
def fetch_and_cache_token_maps():
    global token_map, market_map
    token_map, market_map = load_json_cache()
    if token_map and market_map:
        print(f"✅ Loaded {len(token_map)} tokens from cache.")
        return

    print("🔄 Fetching fresh token/market name map...")
    cursor = ""
    headers = {
        'Accept': 'application/json',
        'User-Agent': 'Polymarket-Live-Data/1.0',
        'Content-Type': 'application/json'
    }

    while True:
        try:
            url = f"{host}/sampling-markets?next_cursor={cursor}"
            resp = requests.get(url, headers=headers)
            resp.raise_for_status()
            payload = resp.json()
            markets = payload.get("data", [])
            print(f"📦 Received {len(markets)} markets")

            for market in markets:
                name = market.get("market_slug")
                condition_id = market.get("condition_id")
                if name and condition_id:
                    market_map[name] = condition_id
                for token in market.get("tokens", []):
                    tid = token.get("token_id")
                    if tid and name:
                        token_map[tid] = name

            cursor = payload.get("next_cursor")
            if not cursor or cursor == "LTE=":
                break

        except Exception as e:
            print(f"❌ Error while fetching token map: {e}")
            break

    save_json_cache()
    print(f"💾 Saved {len(token_map)} tokens and {len(market_map)} markets to cache.")

# -------------------------------
# WebSocket Handlers
# -------------------------------
def get_market_name(asset_id):
    global token_map, market_map

    token_map, _ = load_json_cache()
    return token_map.get(asset_id, f"Unknown Token ({asset_id})")

def timestamp_to_datetime(timestamp):
    ts_ms = int(timestamp)
    ts_s  = ts_ms / 1000

    # build a datetime in your local timezone
    dt = datetime.datetime.fromtimestamp(ts_s)

    # format as "MM/DD, HH:MM:SS"
    pretty = dt.strftime('%m/%d, %H:%M:%S')
    return pretty
def handle_book(msg):
    global token_map, market_map

    asset_id = msg.get("asset_id", "unknown")
    market_name = get_market_name(asset_id)
    t = msg.get("timestamp", "unknown")
    timestamp = timestamp_to_datetime(t)
    print(f"\n📘 BOOK UPDATE for {market_name} at {timestamp}")
    print("  🟩 BUYS:")
    for b in msg.get("buys", []):
        print(f"    {b.get('price')} x {b.get('size')}")
    print("  🔵 SELLS:")
    for s in msg.get("sells", []):
        print(f"    {s.get('price')} x {s.get('size')}")

def handle_price_change(msg):
    asset_id = msg.get("asset_id", "unknown")
    market_name = get_market_name(asset_id)
    t = msg.get("timestamp", "unknown")
    timestamp = timestamp_to_datetime(t)    
    print(f"\n📈 PRICE CHANGES for {market_name} at {timestamp}:")
    for change in msg.get("changes", []):
        print(f"  {change.get('side')}: {change.get('price')} x {change.get('size')}")

def handle_tick_size_change(msg):
    asset_id = msg.get("asset_id", "unknown")
    market_name = get_market_name(asset_id)
    t = msg.get("timestamp", "unknown")
    timestamp = timestamp_to_datetime(t)
    print(f"\n📏 TICK SIZE CHANGE for {market_name} at {timestamp}")
    print(f"  Old: {msg.get('old_tick_size')} → New: {msg.get('new_tick_size')}")

def handle_event(msg):
    event_type = msg.get("event_type")
    if event_type == "book":
        handle_book(msg)
    elif event_type == "price_change":
        handle_price_change(msg)
    elif event_type == "tick_size_change":
        handle_tick_size_change(msg)
    else:
        print(f"⚠️ Unknown event_type: {event_type}")
        print(json.dumps(msg, indent=2))

# -------------------------------
# WebSocket Lifecycle
# -------------------------------
def on_message(ws, message):
    try:
        if message == "PONG":
            print("🔂 Received PONG")
            return

        msg = json.loads(message)
        if isinstance(msg, list):
            for event in msg:
                if isinstance(event, dict):
                    handle_event(event)
        elif isinstance(msg, dict):
            handle_event(msg)
        else:
            print(f"⚠️ Unexpected message type: {type(msg)}")
    except Exception as e:
        print(f"⚠️ Error parsing message: {e}")

def on_open(ws):
    global token_map, market_map

    print("🟢 WebSocket connected.")
    fetch_and_cache_token_maps()

    tokenList = list(token_map.keys())
    # ✅ Send subscription to 'market' channel
    subscribe_msg = {
        "type": "MARKET", 
        "assets_ids": tokenList
    }
    ws.send(json.dumps(subscribe_msg))
    print("📡 Subscribed to market channel")

    # 🔁 Keep-alive pings
    def keep_alive():
        while True:
            time.sleep(25)
            try:
                ws.send("PING")
                print("📶 Ping sent")
            except Exception as e:
                print(f"❌ Ping failed: {e}")
                break

    threading.Thread(target=keep_alive, daemon=True).start()

def on_error(ws, err):
    print("❌ WebSocket error:", err)

def on_close(ws, code, reason):
    print(f"🔌 WebSocket closed (code={code}): {reason}")

# -------------------------------
# Run it
# -------------------------------
if __name__ == "__main__":
    ws = websocket.WebSocketApp(
        WS_URL,
        on_open=on_open,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close
    )
    ws.run_forever()
