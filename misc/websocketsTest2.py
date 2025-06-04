import websocket
import json
import requests
import time
import threading

API_URL = "https://gamma-api.polymarket.com"
WS_URL = "wss://ws-subscriptions-clob.polymarket.com/ws/market"

# -------------------------------
# Fetch Active Market Asset IDs
# -------------------------------
def fetch_active_markets():
    try:
        response = requests.get(f"{API_URL}/markets?active=true&closed=false")
        response.raise_for_status()

        markets = response.json()

        market_ids = []
        for market in markets[:50]:
            market_id = market.get("id")
            if market_id:
                market_ids.append(market_id)

        print(f"✅ Found {len(market_ids)} active market IDs.")
        return market_ids

    except Exception as e:
        print("❌ Failed to fetch markets:", e)
        return []



# -------------------------------
# WebSocket Message Handlers
# -------------------------------
def handle_book(message):
    asset = message.get("asset_id")
    market = message.get("market")
    print(f"\n📘 BOOK for {asset} | Market: {market}")
    for buy in message.get("buys", []):
        print(f"  🟩 Buy: {buy['price']} x {buy['size']}")
    for sell in message.get("sells", []):
        print(f"  🟥 Sell: {sell['price']} x {sell['size']}")

def handle_price_change(message):
    asset = message.get("asset_id")
    market = message.get("market")
    print(f"\n💹 PRICE CHANGE for {asset} | Market: {market}")
    for change in message.get("changes", []):
        print(f"  {change['side']} {change['price']} x {change['size']}")

def handle_tick_size_change(message):
    print(f"\n🔧 TICK SIZE CHANGE for {message.get('asset_id')}")
    print(f"  Old: {message.get('old_tick_size')} → New: {message.get('new_tick_size')}")

# -------------------------------
# Robust WebSocket Message Parser
# -------------------------------
def on_message(ws, message):
    if not message or not message.strip():
        print("⚠️ Empty or whitespace message received")
        return

    try:
        msg = json.loads(message)

        # Skip batch/list messages
        if isinstance(msg, list):
            print("⚠️ Received unexpected list message. Skipping.")
            return

        if not isinstance(msg, dict):
            print("⚠️ Unexpected message type:", type(msg))
            return

        event_type = msg.get("event_type")

        if event_type == "book":
            handle_book(msg)
        elif event_type == "price_change":
            handle_price_change(msg)
        elif event_type == "tick_size_change":
            handle_tick_size_change(msg)
        else:
            print(f"⚠️ Unknown event_type: {event_type}")
    except json.JSONDecodeError:
        print("⚠️ Could not parse JSON message:", message)
    except Exception as e:
        print("⚠️ Error parsing message:", e)

# -------------------------------
# WebSocket Lifecycle
# -------------------------------
def on_open(ws):
    print("🟢 WebSocket connected.")
    assets = fetch_active_markets()

    for i in range(0, len(assets), 100):
        batch = assets[i:i + 100]
        sub_msg = {
            "type": "MARKET",
            "assets_ids": batch
        }
        ws.send(json.dumps(sub_msg))
        print(f"📡 Subscribed to {len(batch)} assets.")

    def keep_alive():
        while True:
            time.sleep(25)
            try:
                ws.send(json.dumps({"type": "ping"}))
                print("📶 Ping sent")
            except Exception as e:
                print("⚠️ Ping failed:", e)
                break

    threading.Thread(target=keep_alive, daemon=True).start()

def on_error(ws, err): print("❌ WebSocket error:", err)
def on_close(ws, code, reason): print("🔌 WebSocket closed:", reason)

# -------------------------------
# Entry Point
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
