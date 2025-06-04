import requests
from collections import defaultdict

def fetch_all_markets(limit=100):
    """
    Fetches all active Polymarket markets using pagination.
    """
    all_markets = []
    offset = 0

    while True:
        url = f"https://gamma-api.polymarket.com/markets?active=true&closed=false&limit={limit}&offset={offset}"
        r = requests.get(url)
        data = r.json()  # API returns a list directly
        markets = data  # <-- FIXED: it's already a list

        if offset >= 1000:
            break

        all_markets.extend(markets)
        offset += limit

    return all_markets

def group_markets_by_event(markets):
    """
    Groups markets by their eventTitle.
    """
    grouped = defaultdict(list)
    for market in markets:
        event_title = market.get('eventTitle', 'Unknown Event')
        grouped[event_title].append(market)
    return grouped

def print_top_markets_by_event(grouped_markets, key_func, reverse=True):
    """
    Prints the top N markets by a sorting key for each event.
    """
    for event, markets in grouped_markets.items():
        print(f"\n📌 Event: {event}")
        sorted_markets = sorted(markets, key=key_func, reverse=reverse)
        for market in sorted_markets:
            title = market.get('slug', 'No title')
            volume = market.get('volume24hr', 0)
            print(f"  - Market: {title} | 24h Volume: {volume}")

# Run the pipeline
if __name__ == "__main__":
    all_markets = fetch_all_markets()
    grouped = group_markets_by_event(all_markets)
    print_top_markets_by_event(grouped, key_func=lambda m: ((m.get('volume7d')/7) - m.get('volume24hr', 0))/m.get('volume7d')/7)
