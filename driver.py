import nodriver as uc
from nodriver.cdp.page import FrameStoppedLoading
from nodriver.core.connection import ProtocolException
import asyncio
import aiohttp
import json
import os
from newfile import fetch_active_markets

USERNAME = "your_proxy_username"
PASSWORD = "your_proxy_password"
LOGGED_IN_USER = "ABouvel16870"
MONITORED_USERS = ["ABouvel16870", "elonmusk", "unusual_whales"]
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "http://twitter-webhook:8000")
POLL_INTERVAL = 10  # seconds

# Global set to track processed tweet IDs
processed_tweet_ids = set()

async def load_existing_tweet_ids():
    """Load existing tweet IDs from ChromaDB via webhook API"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{WEBHOOK_URL}/tweet-ids", timeout=10) as response:
                if response.status == 200:
                    data = await response.json()
                    existing_ids = data.get("tweet_ids", [])
                    processed_tweet_ids.update(existing_ids)
                    print(f"✅ Loaded {len(existing_ids)} existing tweet IDs from ChromaDB")
                    return len(existing_ids)
                else:
                    print(f"⚠️ Failed to load existing tweet IDs: HTTP {response.status}")
                    return 0
    except Exception as e:
        print(f"❌ Error loading existing tweet IDs: {e}")
        return 0

class TwitterTabMonitor:
    def __init__(self, browser, user):
        self.browser = browser
        self.user = user
        self.tab = None

    async def get_tab(self,tab, url):
        try:
            print(f"moving to{url} ")
            return await tab.get(url)
        except KeyError as e:
            print(f"couldn't load{url}")
            # nodriver tried to remove a handler for FrameStoppedLoading that wasn't there
            if e.args and e.args[0] is FrameStoppedLoading:
                return
            raise
    async def setup(self):
        # open a fresh tab and enable fetch handling
        self.tab = await self.browser.get("draft:,")
        self.tab.add_handler(uc.cdp.fetch.RequestPaused, self._req_paused)
        self.tab.add_handler(uc.cdp.fetch.AuthRequired, self._auth_challenge)
        await self.tab.send(uc.cdp.fetch.enable(handle_auth_requests=True))

        # visit logged-in account to load cookies, then target profile
        
        await self.get_tab(self.tab, f"https://x.com/{self.user}")
        await asyncio.sleep(3)

    async def poll(self):
        while True:
            await asyncio.sleep(3)

            await self._extract_and_send()
            await asyncio.sleep(POLL_INTERVAL)

    async def _extract_and_send(self):
    # reload the profile once
        await self.tab.get(f"https://x.com/{self.user}")
        await asyncio.sleep(3)

        js = f"""
        (() => {{
        const els = Array.from(
            document.querySelectorAll("article[data-testid='tweet']")
        ).slice(0, 3);

        return els
            .map(el => {{
            const td = el.querySelector("[data-testid='tweetText']");
            if (!td) return null;
            const text = Array.from(td.querySelectorAll("span"))
                .map(s => s.textContent.trim())
                .filter(t => t)
                .join(" ");
            return td.id && text ? {{ id: td.id, text }} : null;
            }})
            .filter(x => x);
        }})()
        """

        # evaluate the JS and get a Python list back
        raw = await self.tab.evaluate(js, return_by_value=True)
# If it’s still a RemoteObject, extract the deep value
        if not isinstance(raw, list) and hasattr(raw, "deep_serialized_value"):
            raw = raw.deep_serialized_value.value or []

        if not isinstance(raw, list) or not raw:
            print(f"⚠️ @{self.user}: no tweets extracted (raw={raw})")
            return
        clean = []
        for obj in raw:
            # obj['value'] is a list of [key, desc] pairs
            entry = { key: desc['value'] for key, desc in obj['value'] }
            # entry now is {'id': 'id__bkd5qzqsc5b', 'text': 'Next I’m buying Coca-Cola…'}
            clean.append(entry)

        # `clean` is now a list of simple dicts:
        # [
        #   {
        #     'id': 'id__bkd5qzqsc5b',
        #     'text': 'Next I’m buying Coca-Cola…'
        #   }
        # ]

        # Filter out already processed tweets and send new ones
        async with aiohttp.ClientSession() as session:
            tasks = []
            new_tweets = []
            
            for t in clean:
                tweet_id = t['id']
                
                # Check local cache first
                if tweet_id in processed_tweet_ids:
                    print(f"⚠️ Skipping already processed tweet: {tweet_id}")
                    continue
                
                # Add to local cache immediately to prevent race conditions
                processed_tweet_ids.add(tweet_id)
                new_tweets.append(t)
                
                print(f"🆕 New tweet: {tweet_id}, {t['text'][:50]}..., @{self.user}")
                tasks.append(
                    session.post(
                        f"{WEBHOOK_URL}/receive",
                        json={
                            "username":   self.user,
                            "tweet_id":   tweet_id,
                            "tweet_text": t["text"],
                            "url":        f"https://x.com/{self.user}/status/{tweet_id}"
                        },
                        timeout=30
                    )
                )
            
            if not tasks:
                print(f"📭 No new tweets found for @{self.user}")
                return []
            
            # Run all requests concurrently
            responses = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Handle failed requests by removing from local cache
            for i, response in enumerate(responses):
                if isinstance(response, Exception):
                    failed_tweet_id = new_tweets[i]['id']
                    processed_tweet_ids.discard(failed_tweet_id)
                    print(f"❌ Failed to send tweet {failed_tweet_id}: {response}")
                
            return responses




    async def _auth_challenge(self, event):
        await self.tab.send(uc.cdp.fetch.continue_with_auth(
            request_id=event.request_id,
            auth_challenge_response=uc.cdp.fetch.AuthChallengeResponse(
                response="ProvideCredentials",
                username=USERNAME,
                password=PASSWORD
            )
        ))

    async def _req_paused(self, event):
        try:
            await self.tab.send(uc.cdp.fetch.continue_request(request_id=event.request_id))
        except:
            pass  # ignore invalid‑state errors

async def main():
    # Initialize database with all markets from Polymarket
    print("🔄 Initializing database with Polymarket data...")
    try:
        result = await fetch_active_markets()
        print(f"✅ Database initialization completed: {result}")
    except Exception as e:
        print(f"❌ Database initialization failed: {e}")
    
    # Load existing tweet IDs from ChromaDB at startup
    print("🔄 Loading existing tweet IDs from ChromaDB...")
    await load_existing_tweet_ids()
    
    browser = await uc.start(
        browser_executable_path="/usr/bin/chromium",
        browser_args=["--no-sandbox", "--disable-dev-shm-usage"],
        headless=True, 
        no_sandbox=True,
        sandbox=False
    )
    try:
        await browser.cookies.load()
        print("✅ Cookies loaded, skipping manual login")
    except FileNotFoundError:
        print("⚠️ No cookies found, logging in now")

    # launch one monitor per user
    monitors = []
    for u in MONITORED_USERS:
        m = TwitterTabMonitor(browser, u)
        await m.setup()
        monitors.append(asyncio.create_task(m.poll()))

    await asyncio.gather(*monitors)
    
    

    

if __name__ == "__main__":
    asyncio.run(main())
