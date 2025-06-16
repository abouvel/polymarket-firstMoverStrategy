from flask import Flask, jsonify, request
from flask_cors import CORS
import json
import time
import random
import requests
from clob import token_name_map, market_name_map, fetch_token_name_map, websocket, threading
from flask_socketio import SocketIO
from functools import lru_cache
from datetime import datetime, timedelta

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Configure Socket.IO with explicit transport settings
socketio = SocketIO(
    app,
    cors_allowed_origins="*",
    async_mode='threading',
    logger=True,
    engineio_logger=True,
    ping_timeout=60,
    ping_interval=25,
    transports=['polling'],  # Use polling only initially
    allow_upgrades=False,  # Disable upgrades initially
    max_http_buffer_size=1e8
)

# Initialize maps
result = fetch_token_name_map()
if isinstance(result, tuple):
    token_map, market_map = result
    token_name_map.update(token_map)
    market_name_map.update(market_map)
else:
    token_name_map.update(result)
    # If we only have token map, create market map from it
    market_name_map.update({name: id for id, name in token_name_map.items()})

# Global queue to store market updates
market_updates = {}

# Market details cache
market_details_cache = {}
market_details_cache_time = {}

# Rate limiting state
rate_limit_state = {
    'last_request': 0,
    'min_delay': 1.0,  # Minimum delay between requests in seconds
    'max_delay': 5.0,  # Maximum delay between requests in seconds
    'current_delay': 1.0,  # Current delay between requests
    'backoff_factor': 1.5,  # Factor to increase delay on rate limit
    'recovery_factor': 0.8,  # Factor to decrease delay on successful request
}

def get_rate_limited_delay():
    """Calculate delay based on rate limit state"""
    current_time = time.time()
    time_since_last = current_time - rate_limit_state['last_request']
    
    if time_since_last < rate_limit_state['current_delay']:
        return rate_limit_state['current_delay'] - time_since_last
    
    return 0

def update_rate_limit_state(success=True):
    """Update rate limit state based on request success"""
    current_time = time.time()
    rate_limit_state['last_request'] = current_time
    
    if success:
        # Gradually decrease delay on successful requests
        rate_limit_state['current_delay'] = max(
            rate_limit_state['min_delay'],
            rate_limit_state['current_delay'] * rate_limit_state['recovery_factor']
        )
    else:
        # Increase delay on rate limit
        rate_limit_state['current_delay'] = min(
            rate_limit_state['max_delay'],
            rate_limit_state['current_delay'] * rate_limit_state['backoff_factor']
        )

def make_api_request(url, headers=None):
    """Make API request with rate limiting protection"""
    delay = get_rate_limited_delay()
    if delay > 0:
        time.sleep(delay)
    
    try:
        print(f"Making API request to: {url}")
        if headers:
            print(f"With headers: {headers}")
        response = requests.get(url, headers=headers)
        print(f"Response status code: {response.status_code}")
        print(f"Response content: {response.text[:500]}")  # Print first 500 chars of response
        
        if response.status_code == 429:
            update_rate_limit_state(success=False)
            raise Exception("Rate limited")
        
        update_rate_limit_state(success=True)
        return response.json()
    except Exception as e:
        print(f"API request error: {e}")
        raise

@lru_cache(maxsize=1000)
def get_market_details(condition_id):
    """Get market details with caching"""
    cache_key = condition_id
    current_time = time.time()
    
    # Check cache
    if cache_key in market_details_cache:
        cache_time = market_details_cache_time.get(cache_key, 0)
        if current_time - cache_time < 300:  # Cache for 5 minutes
            return market_details_cache[cache_key]
    
    try:
        # First try to get the market slug from the market name map
        market_slug = None
        for slug, id in market_name_map.items():
            if id == condition_id:
                market_slug = slug
                break
        
        if not market_slug:
            print(f"Could not find market slug for condition_id: {condition_id}")
            return {'error': 'Market not found'}
        
        # Fetch from CLOB API using the market slug
        url = f"https://clob.polymarket.com/markets/{market_slug}"
        print(f"Fetching market details from: {url}")
        response = make_api_request(url)
        print(f"Market details response: {response}")
        
        if response and not response.get('error'):
            # Update cache
            market_details_cache[cache_key] = response
            market_details_cache_time[cache_key] = current_time
            return response
        return {'error': 'Market not found'}
    except Exception as e:
        print(f"Error fetching market details: {e}")
        return {'error': str(e)}

# WebSocket state
ws_state = {
    'connected': False,
    'reconnect_attempts': 0,
    'last_ping': 0,
    'last_pong': 0,
    'rate_limited': False,
    'rate_limit_reset': 0,
    'subscribed_markets': set()  # Track subscribed markets
}

def update_market_data(market_id, data):
    if market_id not in market_updates:
        market_updates[market_id] = []
    market_updates[market_id].append(data)
    # Keep only last 100 updates
    if len(market_updates[market_id]) > 100:
        market_updates[market_id] = market_updates[market_id][-100:]
    # Emit to connected clients
    socketio.emit('market_update', {
        'market_id': market_id,
        'data': data
    })

def handle_ws_message(ws, message):
    try:
        if message == "PONG":
            ws_state['last_pong'] = time.time()
            return

        msg = json.loads(message)
        if isinstance(msg, list):
            for event in msg:
                if isinstance(event, dict):
                    market_id = event.get("condition_id")
                    if market_id and market_id in ws_state['subscribed_markets']:
                        update_market_data(market_id, event)
        elif isinstance(msg, dict):
            market_id = msg.get("condition_id")
            if market_id and market_id in ws_state['subscribed_markets']:
                update_market_data(market_id, msg)
    except Exception as e:
        print(f"Error handling WebSocket message: {e}")

def handle_ws_open(ws):
    print("WebSocket connected")
    ws_state['connected'] = True
    ws_state['reconnect_attempts'] = 0
    ws_state['last_ping'] = time.time()
    ws_state['last_pong'] = time.time()
    ws_state['rate_limited'] = False
    
    # Start keep-alive ping
    def keep_alive():
        while ws_state['connected']:
            current_time = time.time()
            
            # Check if we're rate limited
            if ws_state['rate_limited']:
                if current_time < ws_state['rate_limit_reset']:
                    time.sleep(1)
                    continue
                ws_state['rate_limited'] = False
            
            # Check if we haven't received a pong in 30 seconds
            if current_time - ws_state['last_pong'] > 30:
                print("No PONG received for 30 seconds, reconnecting...")
                ws.close()
                break
            
            # Send ping every 15 seconds
            if current_time - ws_state['last_ping'] > 15:
                try:
                    ws.send(json.dumps({"type": "ping"}))
                    ws_state['last_ping'] = current_time
                except Exception as e:
                    print(f"Ping failed: {e}")
                    break
            
            time.sleep(1)
    
    threading.Thread(target=keep_alive, daemon=True).start()

def handle_ws_error(ws, error):
    print(f"WebSocket error: {error}")
    ws_state['connected'] = False
    
    # Check if we're being rate limited
    if "429" in str(error):
        ws_state['rate_limited'] = True
        ws_state['rate_limit_reset'] = time.time() + 60  # Wait 1 minute
        print("Rate limited. Waiting 60 seconds before reconnecting...")
        time.sleep(60)
    else:
        # Calculate backoff time with jitter
        backoff = min(30, (2 ** ws_state['reconnect_attempts']) + random.uniform(0, 1))
        ws_state['reconnect_attempts'] += 1
        print(f"Reconnecting in {backoff:.2f} seconds...")
        time.sleep(backoff)
    
    try:
        ws.close()
    except:
        pass
    start_websocket()

def handle_ws_close(ws, close_status_code, close_msg):
    print(f"WebSocket closed: {close_status_code} - {close_msg}")
    ws_state['connected'] = False
    
    # Check if we're being rate limited
    if "429" in str(close_msg):
        ws_state['rate_limited'] = True
        ws_state['rate_limit_reset'] = time.time() + 60  # Wait 1 minute
        print("Rate limited. Waiting 60 seconds before reconnecting...")
        time.sleep(60)
    else:
        # Calculate backoff time with jitter
        backoff = min(30, (2 ** ws_state['reconnect_attempts']) + random.uniform(0, 1))
        ws_state['reconnect_attempts'] += 1
        print(f"Reconnecting in {backoff:.2f} seconds...")
        time.sleep(backoff)
    
    start_websocket()

def start_websocket():
    print("Starting WebSocket connection...")
    
    # WebSocket headers
    headers = {
        'User-Agent': 'Polymarket-Live-Data/1.0',
        'Origin': 'https://polymarket.com',
        'Pragma': 'no-cache',
        'Cache-Control': 'no-cache'
    }
    
    ws = websocket.WebSocketApp(
        "wss://ws-subscriptions-clob.polymarket.com/ws/market",
        header=headers,
        on_message=handle_ws_message,
        on_error=handle_ws_error,
        on_close=handle_ws_close,
        on_open=handle_ws_open
    )
    
    # Start WebSocket in a separate thread
    ws_thread = threading.Thread(target=ws.run_forever)
    ws_thread.daemon = True
    ws_thread.start()
    return ws

def subscribe_to_market(market_id):
    """Subscribe to a specific market"""
    if not ws_state['connected']:
        print("WebSocket not connected, cannot subscribe")
        return False
    
    try:
        ws.send(json.dumps({"type": "MARKET", "condition_ids": [market_id]}))
        ws_state['subscribed_markets'].add(market_id)
        print(f"Subscribed to market: {market_id}")
        return True
    except Exception as e:
        print(f"Error subscribing to market {market_id}: {e}")
        return False

def unsubscribe_from_market(market_id):
    """Unsubscribe from a specific market"""
    if market_id in ws_state['subscribed_markets']:
        ws_state['subscribed_markets'].remove(market_id)
        print(f"Unsubscribed from market: {market_id}")

@app.route('/api/search')
def search():
    query = request.args.get('q', '').lower()
    if len(query) < 2:
        return jsonify([])
    
    # Split query into keywords
    keywords = query.split()
    
    # Search through market names
    results = []
    for name, condition_id in market_name_map.items():
        name_lower = name.lower()
        # Check if all keywords are present in the market name
        if any(keyword in name_lower for keyword in keywords):
            results.append({
                'id': condition_id,
                'name': name,
                'match_score': sum(name_lower.count(keyword) for keyword in keywords)  # Simple relevance score
            })
    
    # Sort by match score and limit to 10 results
    results.sort(key=lambda x: x['match_score'], reverse=True)
    return jsonify(results[:10])

@app.route('/api/market/<market_id>')
def get_market_data(market_id):
    """Get market data and details"""
    # Subscribe to the market when requested
    subscribe_to_market(market_id)
    
    market_data = market_updates.get(market_id, [])
    market_details = get_market_details(market_id)
    
    return jsonify({
        'updates': market_data,
        'details': market_details
    })

if __name__ == '__main__':
    # Start initial WebSocket connection
    ws = start_websocket()
    
    # Run Flask app
    socketio.run(
        app,
        debug=True,
        port=5000,
        host='0.0.0.0',
        use_reloader=False  # Disable reloader to prevent duplicate connections
    ) 