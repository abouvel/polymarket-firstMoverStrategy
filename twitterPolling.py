import snscrape.modules.twitter as sntwitter
import aiohttp
import asyncio
import certifi
import os

os.environ['SSL_CERT_FILE'] = certifi.where()

# ==== CONFIG ====
ACCOUNTS = ["ABouvel16870", "unusual_whales"]  # Twitter usernames
WEBHOOK_URL = "http://localhost:8000/receive"
POLL_INTERVAL = 10  # seconds

# ==== STATE ====
last_seen_ids = {}

# ==== FETCH LATEST TWEET ====
async def get_latest_tweet(username):
    try:
        return next(sntwitter.TwitterUserScraper(username).get_items())
    except Exception as e:
        print(f"❌ Error fetching @{username}: {e}")
        return None

# ==== SEND WEBHOOK ====
async def send_webhook(session, tweet, username):
    payload = {
        "username": username,
        "tweet_id": tweet.id,
        "tweet_text": tweet.content,
        "url": f"https://x.com/{username}/status/{tweet.id}"
    }
    try:
        async with session.post(WEBHOOK_URL, json=payload, timeout=5) as resp:
            print(f"✅ Sent @{username}: {tweet.content[:40]}... ({resp.status})")
    except Exception as e:
        print(f"❌ Webhook error for @{username}: {e}")

# ==== PER-USER TASK ====
async def monitor_user(session, username):
    tweet = await get_latest_tweet(username)
    if not tweet:
        return
    if last_seen_ids.get(username) != tweet.id:
        last_seen_ids[username] = tweet.id
        await send_webhook(session, tweet, username)
    else:
        print(f"⏸️ No new tweet from @{username}")

# ==== SIMPLE SYNC TEST ====
def test_single_user(username):
    print(f"🔍 Checking latest tweet from @{username}")
    tweet = next(sntwitter.TwitterUserScraper(username).get_items())
    print(f"🟢 Latest tweet:\n{tweet.content}\n→ {tweet.date} — https://x.com/{username}/status/{tweet.id}")

# ==== MAIN LOOP ====
async def main():
    async with aiohttp.ClientSession() as session:
        while True:
            tasks = [monitor_user(session, user) for user in ACCOUNTS]
            await asyncio.gather(*tasks)
            await asyncio.sleep(POLL_INTERVAL)

if __name__ == "__main__":
    # asyncio.run(main())  # Commented out async polling

    # Run a one-time sync scrape for ABouvel16870
    test_single_user("ABouvel16870")
