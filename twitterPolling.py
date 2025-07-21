from playwright.sync_api import sync_playwright
import time
import os
import requests

USERNAME = "ABouvel16870"
WEBHOOK_URL = "http://localhost:8000/receive"
SESSION_FILE = "twitter_session.json"

def build_injected_script(username):
    return f"""
    const observer = new MutationObserver((mutationsList) => {{
        for (const mutation of mutationsList) {{
            for (const node of mutation.addedNodes) {{
                if (node.nodeType === 1 && node.querySelector("a[href*='/{username}/status/']")) {{
                    const text = node.innerText;
                    const linkNode = node.querySelector("a[href*='/{username}/status/']");
                    const tweetUrl = linkNode ? "https://twitter.com" + linkNode.getAttribute("href") : "";

                    console.log("TWEET_DETECTED|" + text + "|URL|" + tweetUrl);
                }}
            }}
        }}
    }});
    observer.observe(document.body, {{ childList: true, subtree: true }});
    """


import requests  # Ensure this is at the top of your file

def run_watcher():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(storage_state="twitter_session.json")
        page = context.new_page()
        page.goto(f"https://twitter.com/{USERNAME}", timeout=20000)
        print(f"📡 Watching @{USERNAME} (polling every 10s)...")

        last_seen = ""

        try:
            while True:
                page.reload()
                time.sleep(3)  # Wait for DOM to update
                tweets = page.locator(f"a[href*='/{USERNAME}/status/']").all()

                if tweets:
                    text = tweets[0].inner_text()
                    url = tweets[0].get_attribute("href")
                    full_url = f"https://twitter.com{url}"

                    if text != last_seen:
                        last_seen = text
                        print(f"📢 New tweet detected: {text}")

                        # ✅ Send to FastAPI webhook using Python requests
                        try:
                            response = requests.post(WEBHOOK_URL, json={
                                "username": USERNAME,
                                "tweet_text": text,
                                "url": full_url
                            }, timeout=5)
                            print(f"✅ Webhook sent: {response.status_code}")
                        except Exception as e:
                            print(f"❌ Failed to send webhook: {e}")

                time.sleep(10)
        except KeyboardInterrupt:
            print("👋 Stopping...")
            browser.close()



if __name__ == "__main__":
    run_watcher()
