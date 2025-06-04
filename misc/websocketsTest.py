import websocket
import json
import threading
import time
import csv
import logging
import requests
from collections import defaultdict


logging.basicConfig(level=logging.INFO)

def on_open(ws):
    listOfTokens = []  # Add token IDs here
    subscribe_message = {
        "type": "Market",
        "assets_ids": listOfTokens[:1]
    }
    ws.send(json.dumps(subscribe_message))
    logging.info("Sent subscribe message")

    def keep_alive():
        while True:
            time.sleep(30)
            if not ws.sock or not ws.sock.connected:
                logging.info("WebSocket not connected. Stopping ping loop.")
                break
            try:
                ws.send(json.dumps({"type": "ping"}))
                logging.info("Ping sent")
            except Exception as e:
                logging.error(f"Ping failed: {e}")
                break


    threading.Thread(target=keep_alive).start()

def print_message_keys(message):
    try:
        data = json.loads(message)
        print("\n🧩 Available keys in this message:")
        for key in data:
            print(f"  - {key}")
        print(f"Total fields: {len(data)}\n")
    except Exception as e:
        print("Failed to parse message:", e)

def on_message(ws, message):
    logging.info("Raw Message:")
    logging.info(message)
    print_message_keys(message)

    try:
        converted_message = json.loads(message)
    except json.JSONDecodeError:
        logging.info(f"Received non-JSON message: {message}")
        return

    event_type = converted_message.get('event_type', 'Unknown')
    if event_type == 'book':
        logging.info(f"Book: {message}")
        # handle_book_message(converted_message)
    elif event_type == 'price_change':
        logging.info(f"Price Change: {message}")
        # handle_price_change_message(converted_message)
    elif event_type == 'last_trade_price':
        logging.info(f"Last Trade Price: {message}")
        # handle_last_trade_price_message(converted_message)
    else:
        logging.info(f"Received unknown message type: {event_type}")
        logging.info(json.dumps(converted_message, indent=4))
    logging.info("\n" + "_" * 50 + "\n")

def handle_book_message(message):
    logging.info("Book Message Received")
    print("\n📊 Message Fields:")
    for key in message.keys():
        print(f"  - {key}")
    print(f"Total fields: {len(message)}")

    asset_id = message.get('asset_id', 'Unknown')
    market = message.get('market', 'Unknown')
    neg_risk = message.get('neg_risk', False)
    market_title = message.get('market_title', "Unknown Market Title")
    outcome = message.get('outcome', "Unknown Outcome")

    logging.info(f"Market Title: {market_title}")
    logging.info(f"Outcome: {outcome}")
    logging.info(f"Asset ID: {asset_id}")
    logging.info(f"Market: {market}")
    logging.info(f"Neg Risk: {neg_risk}")

    logging.info("Buys (Bids):")
    bids = message.get('bids', [])
    if not bids:
        logging.info("  No buy orders")
    for bid in bids:
        logging.info(f"  Price: {bid['price']}, Size: {bid['size']}")

    logging.info("Sells (Asks):")
    asks = message.get('asks', [])
    if not asks:
        logging.info("  No sell orders")
    for ask in asks:
        logging.info(f"  Price: {ask['price']}, Size: {ask['size']}")

def handle_price_change_message(message):
    logging.info("Price Change Message Received")
    asset_id = message.get('asset_id', 'Unknown')
    market = message.get('market', 'Unknown')
    price = message.get('price', 'Unknown')
    size = message.get('size', 'Unknown')
    side = message.get('side', 'Unknown')
    time = message.get('time', 'Unknown')
    # neg_risk = neg_risk_status.get(asset_id, False)
    # market_title = dictOfTitles.get(asset_id, "Unknown Market Title")
    # outcome = outcome_context.get(asset_id, "Unknown Outcome")

    logging.info(f"Asset ID: {asset_id}")
    logging.info(f"Market: {market}")
    logging.info(f"Price: {price}")
    logging.info(f"Size: {size}")
    logging.info(f"Side: {side}")
    logging.info(f"Time: {time}")

def handle_last_trade_price_message(message):
    logging.info("Last Trade Price Message Received")
    asset_id = message.get('asset_id', 'Unknown')
    market = message.get('market', 'Unknown')
    fee_rate_bps = message.get('fee_rate_bps', 'Unknown')
    price = message.get('price', 'Unknown')
    side = message.get('side', 'Unknown')
    size = message.get('size', 'Unknown')
    timestamp = message.get('timestamp', 'Unknown')
    # neg_risk = neg_risk_status.get(asset_id, False)
    # market_title = dictOfTitles.get(asset_id, "Unknown Market Title")
    # outcome = outcome_context.get(asset_id, "Unknown Outcome")

    logging.info(f"Asset ID: {asset_id}")
    logging.info(f"Market: {market}")
    logging.info(f"Fee Rate BPS: {fee_rate_bps}")
    logging.info(f"Price: {price}")
    logging.info(f"Side: {side}")
    logging.info(f"Size: {size}")
    logging.info(f"Timestamp: {timestamp}")

def on_error(ws, error):
    logging.error("Error: %s", error)

def on_close(ws, close_status_code, close_msg):
    logging.info("Connection closed")


def findIds():
    base_url = "https://gamma-api.polymarket.com"

    # Step 1: Get all events
    try:
        events = requests.get(f"{base_url}/events").json()
        event_lookup = {str(event["id"]): event.get("title") or event.get("slug") for event in events}
    except Exception as e:
        print("Failed to fetch events:", e)
        return

    # Step 2: Get all markets
    try:
        markets = requests.get(f"{base_url}/markets?closed=false&active=true&limit=10").json()
        print(markets)

    except Exception as e:
        print("Failed to fetch markets:", e)
        return

    # Step 3: Group markets by eventId
    grouped_markets = defaultdict(list)

    for market in markets:
        event_title= str(market.get("title"))
        market_title = market.get("slug") or "Unnamed Market"
        end_date = market.get("endDate", "Unknown End Date")
        grouped_markets[event_title].append((market_title, end_date))

    # Step 4: Print grouped output
    for event_title, markets in grouped_markets.items():
        event_name = event_lookup.get(event_title, "Unknown Event")
        print(f"\n📅 Event: {event_name}")
        for market_title, end_date in markets:
            print(f"    📈 {market_title} (ends {end_date})")





if __name__ == "__main__":
    findIds()
    # ws = websocket.WebSocketApp(
    #     "wss://ws-subscriptions-clob.polymarket.com/ws/market",
    #     on_open=on_open,
    #     on_message=on_message,
    #     on_error=on_error,
    #     on_close=on_close
    # )
    # ws.run_forever(ping_interval=30, ping_timeout=10)
