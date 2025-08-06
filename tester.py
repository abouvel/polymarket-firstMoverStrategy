import nodriver as uc
from nodriver.cdp.page import FrameStoppedLoading
from nodriver.core.connection import ProtocolException
import asyncio
import aiohttp
import os
from datetime import datetime

USERNAME = "your_proxy_username"
PASSWORD = "your_proxy_password"
MONITORED_USER = "elonmusk"
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "http://twitter-webhook:8000")
POLL_INTERVAL = 10  # seconds

processed_tweet_ids = set()

def log(msg):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {msg}")

class TwitterMonitor:
    def __init__(self, browser):
        self.browser = browser
        self.tab = None
        self.user = MONITORED_USER

    async def get_tab(self, tab, url):
        try:
            log(f"[@{self.user}] Navigating to {url}")
            return await tab.get(url)
        except KeyError as e:
            log(f"ERROR: [@{self.user}] Couldn't load {url}")
            # nodriver tried to remove a handler for FrameStoppedLoading that wasn't there
            if e.args and e.args[0] is FrameStoppedLoading:
                return
            raise

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
            pass

    async def setup(self):
        self.tab = await self.browser.get("draft:,")
        self.tab.add_handler(uc.cdp.fetch.RequestPaused, self._req_paused)
        self.tab.add_handler(uc.cdp.fetch.AuthRequired, self._auth_challenge)
        await self.tab.send(uc.cdp.fetch.enable(handle_auth_requests=True))
        await self.get_tab(self.tab, f"https://x.com/{self.user}")
        await asyncio.sleep(3)
        log(f"[{self.user}] Setup complete")

    async def poll(self):
        while True:
            await self.scrape_and_send()
            await asyncio.sleep(POLL_INTERVAL)

    async def scrape_and_send(self):
        await self.tab.get(f"https://x.com/{self.user}")
        await asyncio.sleep(3)

        js = """
        (() => {
            const els = Array.from(document.querySelectorAll("article[data-testid='tweet']")).slice(0, 3);
            return els.map(el => {
                const td = el.querySelector("[data-testid='tweetText']");
                if (!td) return null;
                const text = Array.from(td.querySelectorAll("span"))
                    .map(s => s.textContent.trim())
                    .filter(t => t)
                    .join(" ");
                return td.id && text ? { id: td.id, text } : null;
            }).filter(x => x);
        })()
        """

        raw = await self.tab.evaluate(js, return_by_value=True)
        
        # If it's still a RemoteObject, extract the deep value
        if not isinstance(raw, list) and hasattr(raw, "deep_serialized_value"):
            raw = raw.deep_serialized_value.value or []

        if not isinstance(raw, list) or not raw:
            log(f"[{self.user}] No tweets extracted (raw={raw})")
            return
        
        # Process the complex nested structure from nodriver
        clean = []
        for obj in raw:
            # obj['value'] is a list of [key, desc] pairs
            entry = { key: desc['value'] for key, desc in obj['value'] }
            clean.append(entry)

        new_tweets = []
        for tweet in clean:
            tweet_id = tweet['id']
            if tweet_id in processed_tweet_ids:
                continue
            processed_tweet_ids.add(tweet_id)
            new_tweets.append(tweet)

        if not new_tweets:
            log(f"[{self.user}] No new tweets")
            return

        async with aiohttp.ClientSession() as session:
            tasks = [
                session.post(
                    f"{WEBHOOK_URL}/receive",
                    json={
                        "username": self.user,
                        "tweet_id": t['id'],
                        "tweet_text": t['text'],
                        "url": f"https://x.com/{self.user}/status/{t['id']}"
                    },
                    timeout=30
                ) for t in new_tweets
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for i, res in enumerate(results):
                if isinstance(res, Exception):
                    log(f"ERROR sending tweet {new_tweets[i]['id']}: {res}")

async def main():
    browser = await uc.start(
        browser_executable_path="/usr/bin/chromium-browser",
        browser_args=[
            "--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu",
            "--disable-software-rasterizer", "--disable-background-timer-throttling",
            "--disable-backgrounding-occluded-windows", "--disable-renderer-backgrounding",
            "--remote-debugging-port=9222"
        ],
        headless=True,
        no_sandbox=True
    )

    try:
        await browser.cookies.load()
        log("Cookies loaded")
    except FileNotFoundError:
        log("No cookies found")

    monitor = TwitterMonitor(browser)
    await monitor.setup()
    await monitor.poll()

if __name__ == "__main__":
    asyncio.run(main())