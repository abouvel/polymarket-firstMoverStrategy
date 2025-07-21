from fastapi import FastAPI, Request
import chromadb
import uuid
import os

# 📁 Set path to "./chroma" relative to the script location
base_dir = os.path.dirname(os.path.abspath(__file__))
chroma_path = os.path.join(base_dir, "chroma")

# 🚀 Initialize Chroma client with local persistence
client = chromadb.PersistentClient(path=chroma_path)

# 🔁 Create (or get) the collection
collection = client.get_or_create_collection(name="tweets")
def get_collection():
    return collection
app = FastAPI()

@app.post("/receive")
async def receive_tweet(request: Request):
    print("tweet recieved")
    data = await request.json()
    tweet_text = data.get("tweet_text")
    tweet_url = data.get("url")
    username = data.get("username")

    if not tweet_text:
        return {"error": "No tweet text provided"}

    tweet_id = data.get("tweet_id")

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
    return {"status": "stored", "id": tweet_id}
