from fastapi import FastAPI, Request
import chromadb
import uuid
import os
import getpass
import psycopg2
import asyncpg
from dotenv import load_dotenv
from langgraphTester import runcom


# 📁 Set path to "./chroma" relative to the script location
base_dir = os.path.dirname(os.path.abspath(__file__))
chroma_path = os.path.join(base_dir, "chroma")


# 🚀 Initialize Chroma client with local persistence
client = chromadb.PersistentClient(path=chroma_path)

# 🔁 Create (or get) the collection
collection = client.get_or_create_collection(name="tweets")

polymarketCollection = client.get_or_create_collection(name="events")




app = FastAPI()

@app.get("/db")
def db():
    return collection

@app.get("/tweet-ids")
def get_tweet_ids():
    """Get all existing tweet IDs from ChromaDB"""
    try:
        result = collection.get()
        return {"tweet_ids": result["ids"] or []}
    except Exception as e:
        print(f"❌ Error getting tweet IDs: {e}")
        return {"tweet_ids": []}

@app.post("/poly")
async def push_markets(request: Request):
    data = await request.json()
    event_id = data.get("id")
    event_name = data.get("name") or data.get("slug")

    if not event_id or not event_name:
        return {"error": "Missing id or name/slug"}

    # Check if event already exists in polymarketCollection
    try:
        result = polymarketCollection.get(ids=[event_id])
        if result and result.get("ids") and event_id in result["ids"]:
            return {"status": "already_exists", "id": event_id}
    except Exception:
        pass  # If not found, proceed to add

    # Store event in polymarketCollection (id as id, name/slug as document)
    polymarketCollection.add(
        documents=[event_name],
        metadatas=[{"name": event_name}],
        ids=[event_id]
    )

    print(f"✅ Stored event: {event_name} (id: {event_id}) in polymarketCollection")
    return {"status": "stored", "id": event_id}

@app.post("/connect")
async def connect():
    load_dotenv()  # Load environment variables from .env
    try:
        conn = psycopg2.connect(
            user=os.getenv("POSTGRES_USER"),
            password=os.getenv("POSTGRES_PASSWORD"),
            host=os.getenv("POSTGRES_HOST"),
            port=os.getenv("POSTGRES_PORT"),
            dbname=os.getenv("POSTGRES_DB")
        )
        conn.autocommit = True
        print("✅ DB Connection successful")
        return conn
    except Exception as e:
        print(f"❌ DB Connection failed: {e}")
        return None

@app.post("/receive")
async def receive_tweet(request: Request):
    print("tweet received")
    data = await request.json()
    tweet_text = data.get("tweet_text")
    tweet_url = data.get("url")
    username = data.get("username")
    tweet_id = data.get("tweet_id")

    if not tweet_text or not tweet_id:
        return {"error": "Missing tweet_text or tweet_id"}

    try:
        # Check if tweet already exists
        existing = collection.get(ids=[tweet_id])
        if existing['ids']:
            print(f"⚠️ Tweet {tweet_id} already stored, skipping")
            return {"status": "already_exists", "tweet_id": tweet_id}
        
        # Try to add tweet - ChromaDB will handle duplicates gracefully
        collection.add(
            documents=[tweet_text],
            metadatas=[{
                "username": username,
                "url": tweet_url
            }],
            ids=[tweet_id]
        )
        print(f"✅ Stored tweet from @{username}")
        print(f"tweet id: {tweet_id}")
        
        # Only run AI pipeline for new tweets
        runcom(tweet_text)
        return {"status": "stored", "tweet_id": tweet_id}
        
    except Exception as e:
        # Handle ChromaDB duplicate errors gracefully
        if "already exists" in str(e).lower() or "duplicate" in str(e).lower():
            print(f"⚠️ Tweet {tweet_id} already exists (caught exception)")
            return {"status": "already_exists", "tweet_id": tweet_id}
        else:
            print(f"❌ Error storing tweet: {e}")
            return {"error": f"Failed to store tweet: {str(e)}"}