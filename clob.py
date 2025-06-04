import os
import json
import time
import requests
import websocket
import threading
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

# -------------------------------
# Global
# -------------------------------
token_name_map = {}  # token_id -> market_slug
market_name_map = {}  # market_slug -> condition_id

# -------------------------------
# Cache Helpers
# -------------------------------
def load_json_cache(path):
    try:
        if not os.path.exists(path):
            return None
        with open(path, "r") as f:
            data = json.load(f)
            if time.time() - data["timestamp"] < CACHE_TTL_SECONDS:
                return data["data"]
    except Exception as e:
        print(f"⚠️ Failed to load cache from {path}:", e)
    return None

def save_json_cache(path, payload):
    try:
        with open(path, "w") as f:
            json.dump({"timestamp": time.time(), "data": payload}, f)
    except Exception as e:
        print(f"⚠️ Failed to save cache to {path}:", e)

# -------------------------------
# Fetch Token Map with Caching
# -------------------------------
def fetch_token_name_map():
    cached_map = load_json_cache(NAME_MAP_FILE)
    if cached_map:
        print(f"✅ Loaded {len(cached_map)} tokens from cache.")
        return cached_map

    print("🔄 Fetching fresh token name map...")
    token_name_map = {}
    market_name_map = {}
    cursor = ""

    headers = {
        'Accept': 'application/json',
        'User-Agent': 'Polymarket-Live-Data/1.0',
        'Content-Type': 'application/json'
    }

    while True:
        try:
            url = f"{host}/sampling-markets?next_cursor={cursor}"
            print(f"🌐 Requesting: {url}")
            resp = requests.get(url, headers=headers)
            print(f"🔁 Status Code: {resp.status_code}")
            resp.raise_for_status()

            try:
                payload = resp.json()
            except json.JSONDecodeError:
                print("❌ Failed to decode JSON.")
                print("📄 Raw Response:", resp.text[:500])
                break

            markets = payload.get("data", [])
            print(f"📦 Received {len(markets)} markets")

            for market in markets:
                name = market.get("market_slug")
                condition_id = market.get("condition_id")
                if name and condition_id:
                    market_name_map[name] = condition_id
                for token in market.get("tokens", []):
                    tid = token.get("token_id")
                    if tid and name:
                        token_name_map[tid] = name

            cursor = payload.get("next_cursor")
            if not cursor or cursor == "LTE=":
                print("✅ Done fetching all pages.")
                break

        except requests.RequestException as req_err:
            print(f"❌ Request failed: {req_err}")
            print("📄 Response text (truncated):", resp.text[:500] if 'resp' in locals() else "No response")
            break

        except Exception as e:
            print(f"❌ Unexpected error: {e}")
            break

    print(f"🔎 Sample token name map entries: {list(token_name_map.items())[:3]}")
    print(f"🔎 Sample market name map entries: {list(market_name_map.items())[:3]}")
    save_json_cache(NAME_MAP_FILE, token_name_map)
    print(f"💾 Saved {len(token_name_map)} token names to cache.")
    return token_name_map, market_name_map

# -------------------------------
# WebSocket Handlers
# -------------------------------
def handle_book(msg):
    asset_id = msg.get("asset_id", "unknown")
    market_id = msg.get("market", "unknown")
    market_name = token_name_map.get(asset_id, f"Unknown Market ({market_id})")
    timestamp = msg.get("timestamp", "unknown")
    print(f"\n📘 BOOK UPDATE for {market_name} at {timestamp}")
    print("  🟩 BUYS:")
    for b in msg.get("buys", []):
        print(f"    {b.get('price')} x {b.get('size')}")
    print("  🔵 SELLS:")
    for s in msg.get("sells", []):
        print(f"    {s.get('price')} x {s.get('size')}")

def handle_price_change(msg):
    asset_id = msg.get("asset_id", "unknown")
    market_id = msg.get("market", "unknown")
    market_name = token_name_map.get(asset_id, f"Unknown Market ({market_id})")
    timestamp = msg.get("timestamp", "unknown")
    print(f"\n📈 PRICE CHANGES for {market_name} at {timestamp}:")
    for change in msg.get("changes", []):
        side = change.get("side", "UNKNOWN")
        price = change.get("price", "0")
        size = change.get("size", "0")
        print(f"  {side}: {price} x {size}")

def handle_tick_size_change(msg):
    asset_id = msg.get("asset_id", "unknown")
    market_id = msg.get("market", "unknown")
    market_name = token_name_map.get(asset_id, f"Unknown Market ({market_id})")
    old_tick = msg.get("old_tick_size", "unknown")
    new_tick = msg.get("new_tick_size", "unknown")
    timestamp = msg.get("timestamp", "unknown")
    print(f"\n📏 TICK SIZE CHANGE for {market_name} at {timestamp}")
    print(f"  Old: {old_tick} → New: {new_tick}")

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

def on_message(ws, message):
    try:
        if message == "PONG":
            print("🔂 Received PONG")
            return

        print(f"📩 Raw message: {message[:120]}...")
        msg = json.loads(message)

        if isinstance(msg, list):
            for event in msg:
                if isinstance(event, dict):
                    handle_event(event)
                else:
                    print("⚠️ Skipped non-dict item in list:", event)
        elif isinstance(msg, dict):
            handle_event(msg)
        else:
            print(f"⚠️ Unexpected message type: {type(msg)}")

    except json.JSONDecodeError:
        print(f"⚠️ JSON parse error: {repr(message)}")
    except Exception as e:
        print(f"⚠️ Error parsing message: {e}")

def on_open(ws):
    global token_name_map
    print("🟢 WebSocket connected.")

    try:
        token_name_map, market_name_map = fetch_token_name_map()
        token_ids = list(token_name_map.keys())

        if not token_ids:
            print("⚠️ No token IDs found. Skipping subscription.")
            return

        print(f"🧾 First few token IDs: {token_ids[:3]}")

        for i in range(0, len(token_ids), 100):
            batch = token_ids[i:i+100]
            print(f"📨 Subscribing to batch {i//100 + 1}: {batch[:2]}")
            ws.send(json.dumps({"type": "MARKET", "assets_ids": batch}))
            print(f"📱 Subscribed to {len(batch)} tokens.")

    except Exception as e:
        print(f"❌ Error during WebSocket on_open: {e}")

    def keep_alive():
        while True:
            time.sleep(25)
            try:
                ws.send(json.dumps({"type": "ping"}))
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
