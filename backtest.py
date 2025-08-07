import json
from datetime import datetime
from langgraphPipe import graph
from pprint import pprint
import asyncio
import time


def load_tweets(filename):
    """Load tweets from JSON file"""
    with open(filename, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data['tweets']

def prepare_tweet_state(tweet, index):
    """Prepare tweet state for pipeline processing"""
    print(f"\n--- Processing tweet {index} ---")
    print(f"ID: {tweet['id']}")
    print(f"Timestamp: {tweet['timestamp']}")
    print(f"Text: {tweet['text'][:100]}...")
    
    # Handle date - use tweet timestamp if available, otherwise current date
    tweet_date = tweet.get('timestamp')
    if tweet_date:
        # Handle ISO format like "2025-08-01T12:08:01.000Z"
        if 'T' in tweet_date and 'Z' in tweet_date:
            parsed_date = datetime.fromisoformat(tweet_date.replace('Z', '+00:00'))
        else:
            # Try to parse other formats
            try:
                parsed_date = datetime.fromisoformat(tweet_date)
            except:
                parsed_date = datetime.now()
    else:
        parsed_date = datetime.now()
    
    return {
        "headline": f"{tweet}",
        "enriched_headline": "",
        "search_results": "",
        "top_k": [],
        "structured_output": {},
        "selected_id": "",
        "token_id": "",
        "date": parsed_date.isoformat(),
    }

async def process_tweet_batch(tweets_batch, batch_num):
    """Process a batch of tweets concurrently"""
    print(f"\n🚀 Starting batch {batch_num} with {len(tweets_batch)} tweets")
    batch_start = time.time()
    
    # Create tasks for concurrent processing
    tasks = []
    for i, tweet in enumerate(tweets_batch):
        tweet_index = (batch_num - 1) * 10 + i + 1
        initial_state = prepare_tweet_state(tweet, tweet_index)
        task = asyncio.create_task(process_single_tweet(initial_state, tweet_index))
        tasks.append(task)
    
    # Wait for all tweets in batch to complete
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    batch_time = time.time() - batch_start
    success_count = sum(1 for r in results if not isinstance(r, Exception))
    error_count = len(results) - success_count
    
    print(f"✅ Batch {batch_num} completed in {batch_time:.2f}s")
    print(f"   Success: {success_count}, Errors: {error_count}")
    
    return results

async def process_single_tweet(initial_state, tweet_index):
    """Process a single tweet through the pipeline"""
    try:
        result = await graph.ainvoke(initial_state)
        print(f"✅ Tweet {tweet_index} processed successfully")
        return result
    except Exception as e:
        print(f"❌ Tweet {tweet_index} error: {e}")
        return e

async def backtest_tweets():
    """Run backtest on Elon Musk tweets with concurrent batching"""
    tweets = load_tweets('elonmusk_tweets.json')
    
    # Process subset for testing - adjust as needed
    tweets = tweets[:50]  # Process first 50 tweets
    
    print(f"🎯 Starting concurrent backtest with {len(tweets)} tweets")
    print(f"📦 Processing in batches of 10")
    
    total_start = time.time()
    
    # Split tweets into batches of 10
    batch_size = 10
    total_batches = (len(tweets) + batch_size - 1) // batch_size
    
    for batch_num in range(1, total_batches + 1):
        start_idx = (batch_num - 1) * batch_size
        end_idx = min(start_idx + batch_size, len(tweets))
        tweets_batch = tweets[start_idx:end_idx]
        
        # Process batch
        await process_tweet_batch(tweets_batch, batch_num)
        
        # Add small delay between batches to avoid overwhelming the system
        if batch_num < total_batches:
            print("⏸️  2 second pause between batches...")
            await asyncio.sleep(2)
    
    total_time = time.time() - total_start
    print(f"\n🏁 All batches completed in {total_time:.2f}s")
    print(f"📊 Average time per tweet: {total_time/len(tweets):.2f}s")

if __name__ == "__main__":
    asyncio.run(backtest_tweets())

