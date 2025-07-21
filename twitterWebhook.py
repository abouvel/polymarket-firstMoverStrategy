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

    doc_id = str(uuid.uuid4())

    collection.add(
        documents=[tweet_text],
        metadatas=[{
            "username": username,
            "url": tweet_url
        }],
        ids=[doc_id]
    )

    print(f"✅ Stored tweet from @{username}")
    return {"status": "stored", "id": doc_id}
