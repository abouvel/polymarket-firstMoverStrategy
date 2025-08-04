from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
import chromadb
import os
import psycopg2
import asyncio
import json
from datetime import datetime
from dotenv import load_dotenv
from langgraphTester import runcom

app = FastAPI()

# Add CORS middleware for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 📁 Set path to "./chroma" relative to the script location
base_dir = os.path.dirname(os.path.abspath(__file__))
chroma_path = os.path.join(base_dir, "chroma")


# 🚀 Initialize Chroma client with local persistence
client = chromadb.PersistentClient(path=chroma_path)

# 🔁 Create (or get) the collection
collection = client.get_or_create_collection(name="tweets")

polymarketCollection = client.get_or_create_collection(name="events")

# Dashboard event system - simple single user
current_dashboard = None

def get_db_connection():
    load_dotenv()
    return psycopg2.connect(
        user=os.getenv("POSTGRES_USER"),
        password=os.getenv("POSTGRES_PASSWORD"),
        host=os.getenv("POSTGRES_HOST"),
        port=os.getenv("POSTGRES_PORT"),
        dbname=os.getenv("POSTGRES_DB")
    )

async def run_langgraph_async(tweet_text: str):
    """Run LangGraph pipeline asynchronously without blocking the webhook response"""
    try:
        print("🚀 Running LangGraph...")
        await runcom(tweet_text)
        print("✅ LangGraph pipeline completed successfully")
    except Exception as langgraph_error:
        print(f"❌ LangGraph pipeline failed: {langgraph_error}")
        print(f"🔍 Error type: {type(langgraph_error).__name__}")

async def broadcast_event(event_type: str, data: dict):
    global current_dashboard
    if current_dashboard:
        event = {
            "timestamp": datetime.now().isoformat(),
            "type": event_type,
            "data": data
        }
        try:
            await current_dashboard.put(event)
        except:
            current_dashboard = None  # Dashboard disconnected

@app.post("/api/broadcast")
async def broadcast_endpoint(request: Request):
    """Endpoint for LangGraph pipeline to send trade events"""
    try:
        data = await request.json()
        await broadcast_event(data["type"], data["data"])
        return {"status": "broadcasted"}
    except Exception as e:
        print(f"❌ Broadcast error: {e}")
        return {"error": str(e)}


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
        print(f"🔍 Storing tweet {tweet_id}: '{tweet_text[:100]}...'")
        collection.add(
            documents=[tweet_text],
            metadatas=[{
                "username": username,
                "url": tweet_url
            }],
            ids=[tweet_id]
        )
        print(f"✅ Successfully stored tweet {tweet_id} in ChromaDB")
        print(f"✅ Stored tweet from @{username}")
        print(f"tweet id: {tweet_id}")
        
        # Broadcast tweet event to dashboard
        await broadcast_event("tweet_received", {
            "tweet_id": tweet_id,
            "username": username,
            "text": tweet_text[:100] + "..." if len(tweet_text) > 100 else tweet_text,
            "url": tweet_url
        })
        
        # Only run AI pipeline for new tweets (fire-and-forget to avoid blocking)
        asyncio.create_task(run_langgraph_async(tweet_text))
        
        return {"status": "stored", "tweet_id": tweet_id}
        
    except Exception as e:
        # Handle ChromaDB duplicate errors gracefully
        if "already exists" in str(e).lower() or "duplicate" in str(e).lower():
            print(f"⚠️ Tweet {tweet_id} already exists (caught exception)")
            return {"status": "already_exists", "tweet_id": tweet_id}
        else:
            print(f"❌ Error storing tweet: {e}")
            return {"error": f"Failed to store tweet: {str(e)}"}

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard():
    with open("static/dashboard.html", "r") as f:
        return HTMLResponse(content=f.read())

@app.get("/events")
async def events():
    global current_dashboard
    async def event_stream():
        client_queue = asyncio.Queue()
        current_dashboard = client_queue  # Simple - just store the one connection
        
        try:
            while True:
                event = await client_queue.get()
                yield f"data: {json.dumps(event)}\\n\\n"
        except asyncio.CancelledError:
            pass
        finally:
            current_dashboard = None  # Clear when disconnected
    
    return StreamingResponse(
        event_stream(), 
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Cache-Control"
        }
    )

@app.get("/api/recent")
async def get_recent_events():
    try:
        # Get recent tweets from ChromaDB metadata (this should work)
        tweets_result = collection.get(limit=50)
        tweets = []
        if tweets_result and tweets_result.get('ids'):
            print(tweets_result)
            for i, tweet_id in enumerate(tweets_result['ids']):
                metadata = tweets_result['metadatas'][i] if tweets_result.get('metadatas') else {}
                document = tweets_result['documents'][i] if i < len(tweets_result['documents']) else ""
                # Skip old tweets - we only want live ones via SSE
                # Old tweets from ChromaDB don't have proper timestamps
                pass
        
        # Try to get trades from PostgreSQL (might fail)
        trades = []
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT TokenID, Tweet, Event, Date 
                FROM bought 
                ORDER BY Date DESC 
                LIMIT 10
            """)
            
            for row in cursor.fetchall():
                token_id, tweet, event, date = row
                # Parse event text to extract market and token info
                if "Executing trade on token" in event:
                    parts = event.split('"')
                    token_name = parts[1] if len(parts) > 1 else "Unknown"
                    market_name = parts[3] if len(parts) > 3 else "Unknown Market"
                    
                    trades.append({
                        "timestamp": date.isoformat(),
                        "type": "trade_executed",
                        "data": {
                            "token_id": token_id,
                            "token_name": token_name,
                            "market_name": market_name
                        }
                    })
            
            cursor.close()
            conn.close()
        except Exception as db_error:
            print(f"⚠️ Database error (continuing with tweets only): {db_error}")
        
        # Combine and sort by timestamp
        all_events = tweets + trades
        all_events.sort(key=lambda x: x['timestamp'], reverse=True)
        
        return all_events[:20]
        
    except Exception as e:
        print(f"❌ Error getting recent events: {e}")
        return []