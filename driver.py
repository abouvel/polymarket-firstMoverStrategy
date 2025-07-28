import nodriver as uc
import asyncio
import os
import sys
import aiohttp


USERNAME = "your_proxy_username"
PASSWORD = "your_proxy_password"
TWITTER_USER = "ABouvel16870"
WEBHOOK_URL = "http://localhost:8000/receive"

class Scraper:
    main_tab: uc.Tab

    def __init__(self):
        try:
            uc.loop().run_until_complete(self.run())
        except Exception as e:
            print(f"❌ Fatal error: {e}")
            sys.exit(1)

    async def run(self):
        browser = None
        try:
            print("🚀 Starting browser...")
            
            # Use the working config 3
            browser = await uc.start(
                browser_args=["--no-sandbox", "--disable-dev-shm-usage"],
                headless=True,
                no_sandbox=True
            )
            
            print("✅ Browser started successfully")

            # Get the main tab
            self.main_tab = await browser.get("draft:,")
            
            # Set up handlers
            self.main_tab.add_handler(uc.cdp.fetch.RequestPaused, self.req_paused)
            self.main_tab.add_handler(uc.cdp.fetch.AuthRequired, self.auth_challenge_handler)
            await self.main_tab.send(uc.cdp.fetch.enable(handle_auth_requests=True))

            # Load cookies
            try:
                await browser.cookies.load()
                print("✅ Cookies loaded.")
            except FileNotFoundError:
                print("⚠️ No cookies found.")

            # Navigate to Twitter
            print(f"📱 Navigating to https://x.com/{TWITTER_USER}")
            page = await browser.get(f"https://x.com/{TWITTER_USER}")
            
            print("⏳ Waiting for tweets to load...")

            await browser.get(f"https://x.com/{TWITTER_USER}")
            # Extract tweets
            await self.extract_tweets(page)

            # Save cookies
            try:
                await browser.cookies.save()
                print("✅ Cookies saved.")
            except Exception as e:
                print(f"⚠️ Failed to save cookies: {e}")

        except Exception as e:
            print(f"❌ Error in main execution: {e}")
            import traceback
            traceback.print_exc()
        
        finally:
            if browser:
                try:
                    await asyncio.sleep(2)
                    browser.stop()
                    print("✅ Browser closed successfully")
                except Exception as e:
                    print(f"⚠️ Error closing browser: {e}")

    async def send_webhook(self, tweet_id: str, tweet_text: str, username: str):
        """POST tweet data to webhook"""
        payload = {
            "username": username,
            "tweet_id": tweet_id,
            "tweet_text": tweet_text,
            "url": f"https://x.com/{username}/status/{tweet_id}"
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(WEBHOOK_URL, json=payload, timeout=60) as resp:
                    print(f"✅ Webhook sent for @{username} ({tweet_id}): {resp.status}")
        except Exception as e:
            print(f"❌ Webhook error for @{username} ({tweet_id}): {e}")

    async def extract_tweets(self, page):
        """Extract all tweets using span.text.strip()"""
        try:
            print("🔍 Looking for tweets...")
            
            # Find tweet containers
            tweets = await page.select_all("article[data-testid='tweet']")
            if not tweets:
                print("❌ No tweet containers found")
                return

            print(f"✅ Found {len(tweets)} tweet containers")
            
            extracted_count = 0
            
            # Process all tweets
            for i, tweet in enumerate(tweets):
                try:
                    print(f"\n--- Processing Tweet {i+1} ---")
                    
                    # Look for tweetText container
                    text_div = await tweet.query_selector("[data-testid='tweetText']")
                    id  = await tweet.query_selector("id")
                    if not text_div:
                        print(f"⚠️ No tweetText container in tweet {i+1}")
                        continue
                    
                    # Get all spans in the tweetText
                    spans = await text_div.query_selector_all("span")
                    print(f"Found {len(spans)} spans")
                    
                    tweet_parts = []
                    
                    for j, span in enumerate(spans):
                        try:
                            # Use span.text.strip() - simple and direct
                            text = span.text.strip()
                            
                            if text and len(text) > 1:  # Only keep non-empty text
                                tweet_parts.append(text)
                                print(f"  Span {j+1}: '{text}'")
                        
                        except Exception as span_error:
                            print(f"  Error with span {j+1}: {span_error}")
                            continue
                    
                    # Combine all text parts
                    if tweet_parts:
                        full_tweet = " ".join(tweet_parts)
                        await self.send_webhook(id, full_tweet,TWITTER_USER)
                        break
                        print(f"✅ Tweet {i+1}: {full_tweet}")
                        extracted_count += 1
                    else:
                        print(f"⚠️ No text found in tweet {i+1}")
                        
                except Exception as e:
                    print(f"⚠️ Error processing tweet {i+1}: {e}")
                    continue
            
            print(f"\n🎯 Successfully extracted {extracted_count} tweets out of {len(tweets)} total")

        except Exception as e:
            print(f"❌ Error in extract_tweets: {e}")
            import traceback
            traceback.print_exc()

    async def auth_challenge_handler(self, event: uc.cdp.fetch.AuthRequired):
        """Handle proxy authentication"""
        try:
            asyncio.create_task(
                self.main_tab.send(
                    uc.cdp.fetch.continue_with_auth(
                        request_id=event.request_id,
                        auth_challenge_response=uc.cdp.fetch.AuthChallengeResponse(
                            response="ProvideCredentials",
                            username=USERNAME,
                            password=PASSWORD,
                        ),
                    )
                )
            )
        except Exception as e:
            print(f"❌ Auth challenge error: {e}")

    async def req_paused(self, event: uc.cdp.fetch.RequestPaused):
        """Handle paused requests"""
        try:
            asyncio.create_task(
                self.main_tab.send(
                    uc.cdp.fetch.continue_request(request_id=event.request_id)
                )
            )
        except Exception as e:
            print(f"❌ Request pause error: {e}")

    
if __name__ == "__main__":
    print("🚀 Starting Twitter scraper...")
    Scraper()