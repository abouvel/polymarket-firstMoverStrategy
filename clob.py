import os
from py_clob_client.client import ClobClient
import websocket
import json
import threading
import time
import requests

# Initialize client
host = "https://clob.polymarket.com"
key = os.getenv("POLYMARKET_API_KEY")  # Make sure to set this in your environment
chain_id = 137
client = ClobClient(host, key=key, chain_id=chain_id)

WS_URL = "wss://ws-subscriptions-clob.polymarket.com/ws/market"

# -------------------------------
# Fetch Token IDs from Sampling Markets
# -------------------------------
def fetch_sampling_market_token_ids():
    token_ids = set()
    cursor = ""
    
    while True:
        try:
            response = requests.get(f"{host}/sampling-markets?next_cursor={cursor}")
            response.raise_for_status()
            payload = response.json()

            for market in payload.get("data", []):
                for token in market.get("tokens", []):
                    token_id = token.get("token_id")
                    if token_id:
                        token_ids.add(token_id)

            cursor = payload.get("next_cursor")
            if not cursor or cursor == "LTE=":
                break  # done paginating

        except Exception as e:
            print("❌ Error fetching sampling markets:", e)
            break

    return list(token_ids)


# -------------------------------
# WebSocket Handlers
# -------------------------------
def handle_book(msg):
    print(f"\n📘 BOOK: {msg['market']}")
    for b in msg.get("buys", []):
        print(f"🟩 Buy: {b['price']} x {b['size']}")
    for s in msg.get("sells", []):
        print(f"🟥 Sell: {s['price']} x {s['size']}")

def handle_event(msg):
    event_type = msg.get("event_type")
    if event_type == "book":
        #handle_book(msg)
        print("book")
    elif event_type == "price_change":
        #handle_price_change(msg)
        print("price_change")
    elif event_type == "tick_size_change":
        #handle_tick_size_change(msg)
        print("tick_size_change")
    else:
        print(f"⚠️ Unknown event_type: {event_type}")

def on_message(ws, message):
    try:
        msg = json.loads(message)

        # Case 1: message is a list of event dicts
        if isinstance(msg, list):
            for event in msg:
                if isinstance(event, dict):
                    handle_event(event)
                else:
                    print("⚠️ Skipped non-dict item in list:", event)
            return

        # Case 2: single event dict
        elif isinstance(msg, dict):
            handle_event(msg)

        # Case 3: unexpected message type
        else:
            print(f"⚠️ Unexpected message type: {type(msg)}")

    except json.JSONDecodeError:
        print(f"⚠️ JSON parse error: {repr(message)}")
    except Exception as e:
        print(f"⚠️ Error parsing message: {e}")


def on_open(ws):
    print("🟢 WebSocket connected.")
    assets = fetch_sampling_market_token_ids()
    for i in range(0, len(assets), 100):
        batch = assets[i:i+100]
        ws.send(json.dumps({"type": "MARKET", "assets_ids": batch}))
        print(f"📡 Subscribed to {len(batch)} tokens.")

    def keep_alive():
        while True:
            time.sleep(25)
            try:
                ws.send(json.dumps({"type": "ping"}))
                print("📶 Ping sent")
            except:
                break

    threading.Thread(target=keep_alive, daemon=True).start()

def on_error(ws, err): print("❌ WebSocket error:", err)
def on_close(ws, code, reason): print("🔌 WebSocket closed:", reason)

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
