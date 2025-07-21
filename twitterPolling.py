from playwright.sync_api import sync_playwright
import time
import os
import requests
from twitterWebhook import collection

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




def run_watcher():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(storage_state=SESSION_FILE)
        page = context.new_page()
        page.goto(f"https://twitter.com/{USERNAME}", timeout=20000)
        print(f"📡 Watching @{USERNAME} (polling every 10s)...")

        try:
            while True:
                page.reload()
                time.sleep(3)

                tweets = page.locator(f"a[href*='/{USERNAME}/status/']").all()

                if tweets:
                    url = tweets[0].get_attribute("href")
                    if not url:
                        time.sleep(10)
                        continue

                    tweet_id = url.split("/")[-1]
                    full_url = f"https://twitter.com{url}"

                    # ✅ Get full tweet text, not just timestamp
                    tweet_container = tweets[0].locator("xpath=ancestor::article")
                    text = tweet_container.inner_text()

                    # Check if tweet is already in Chroma
                    try:
                        result = collection.get(ids=[tweet_id])
                        if tweet_id in result["ids"]:
                            print(f"🔁 Already processed tweet ID {tweet_id}, skipping.")
                            time.sleep(10)
                            continue
                    except Exception as e:
                        print(f"⚠️ Error checking Chroma for ID {tweet_id}: {e}")


                    print(f"📢 New tweet detected: {text}")
                    try:
                        response = requests.post(WEBHOOK_URL, json={
                            "username": USERNAME,
                            "tweet_text": text,
                            "url": full_url,
                            "tweet_id": tweet_id
                        }, timeout=5)
                        print(f"✅ Webhook sent: {response.status_code} and Text: {text}")
                    except Exception as e:
                        print(f"❌ Failed to send webhook: {e}")

                time.sleep(10)
        except KeyboardInterrupt:
            print("👋 Stopping...")
            browser.close()





if __name__ == "__main__":
    run_watcher()
