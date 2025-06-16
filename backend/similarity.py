from clob import NAME_MAP_FILE
import json
import requests
import hashlib
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.cluster import DBSCAN
from sklearn.metrics.pairwise import cosine_distances
import subprocess
import concurrent.futures
import os
import csv
from datetime import datetime

def get_unique_titles():
    with open(NAME_MAP_FILE, 'r') as f:
        data = json.load(f)
        # Get all values from token_map and convert to set to get unique titles
        titles = set(data['token_map'].values())
        return sorted(list(titles))

def get_embedding(text):
    response = requests.post("http://localhost:11434/api/embeddings", json={
        "model": "bge-large:latest",
        "prompt": text
    })
    return response.json()["embedding"]

def cluster_events( event_embeddings, eps=0.1, min_samples=2):
    event_titles = get_unique_titles()
    """
    Cluster similar events based on their embeddings using DBSCAN.

    Parameters:
        event_titles (List[str]): List of event names (same order as embeddings).
        event_embeddings (List[List[float]]): List of vector embeddings.
        eps (float): Distance threshold for clustering (smaller = stricter).
        min_samples (int): Minimum events per cluster.

    Returns:
        Dict[int, List[str]]: A dictionary mapping cluster ID to event names.
    """
    # Step 1: Compute cosine distance matrix
    distance_matrix = cosine_distances(event_embeddings)

    # Step 2: Run DBSCAN clustering
    db = DBSCAN(eps=eps, metric='precomputed', min_samples=min_samples)
    db.fit(distance_matrix)

    # Step 3: Group events by cluster label
    clusters = {}
    for label, event in zip(db.labels_, event_titles):
        clusters.setdefault(label, []).append(event)

    return clusters

def generate_embeddings():
    """Generate embeddings for all unique titles and save them to a JSON file."""
    titles = get_unique_titles()
    embeddings_dict = {}
    for text in titles:
        text_hash = hashlib.sha256(text.encode()).hexdigest()
        embedding = get_embedding(text)
        embeddings_dict[text_hash] = {
            "text": text,
            "embedding": embedding
        }
    
    # Save to JSON
    with open("event_embeddings.json", "w") as f:
        json.dump(embeddings_dict, f, indent=2)
    return embeddings_dict

def load_embeddings():
    """Load pre-generated embeddings from JSON file or generate new ones if file doesn't exist."""
    embeddings_file = "event_embeddings.json"
    if not os.path.exists(embeddings_file):
        print("Embeddings file not found. Generating new embeddings...")
        return generate_embeddings()
    
    with open(embeddings_file, "r") as f:
        return json.load(f)

def get_similar_events(texts, similarities, threshold=0.85):
    """Find and return similar event pairs based on cosine similarity threshold."""
    similar_pairs = []
    print(f"🧠 Similar event pairs (cosine similarity > {threshold}):")
    for i in range(len(texts)):
        for j in range(i + 1, len(texts)):
            sim = similarities[i][j]
            if sim > threshold:
                print(f"\n🔗 {texts[i]}\n🔗 {texts[j]}\n   → Similarity: {sim:.2f}")
                similar_pairs.append((texts[i], texts[j], sim))
    return similar_pairs

def analyze_similarities(embeddings_dict):
    """Analyze similarities between events using pre-generated embeddings."""
    hashes = list(embeddings_dict.keys())
    vectors = [embeddings_dict[h]["embedding"] for h in hashes]
    texts = [embeddings_dict[h]["text"] for h in hashes]
    similarities = cosine_similarity(vectors)
    return get_similar_events(texts, similarities)

def classify_pair(event_a, event_b, model="gemma3:12b"):
    prompt = f"""
            Consider whether these two events are logically linked — even if they are phrased differently or focus on different aspects of the same topic.

            Event A: "{event_a}"
            Event B: "{event_b}"

            Could the outcome of one event reasonably influence, imply, or change the probability of the other? Think beyond exact phrasing.

            Choose the best answer:

            Dependent — One event implies, affects, or is contextually tied to the other (even indirectly)

            Independent — The two events are unrelated in logic, context, or impact

            Uncertain — There's not enough context to determine a relationship

            Respond with only the number (1, 2, or 3).
            """.strip()

    try:
        result = subprocess.run(
            ["ollama", "run", model, "-p", prompt],
            capture_output=True, text=True, timeout=60
        )
        response = result.stdout.strip()
        return (event_a, event_b, response.startswith("1"))
    except Exception as e:
        print(f"⚠️ Error on pair: ({event_a}, {event_b}) → {e}")
        return (event_a, event_b, False)

def find_dependent_pairs(pairs):
    max_workers=4
    model="gemma3:12b"
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(classify_pair, a, b, model) for a, b, _ in pairs]
        for future in concurrent.futures.as_completed(futures):
            a, b, is_dependent = future.result()
            if is_dependent:
                results.append((a, b))
    return results

def save_clusters_to_json(clusters, filename=None):
    """Save clusters to a JSON file with timestamp."""
    if filename is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"clusters_{timestamp}.json"
    
    # Convert numpy.int64 keys to regular Python integers
    clusters_dict = {int(k): v for k, v in clusters.items()}
    
    with open(filename, 'w') as f:
        json.dump(clusters_dict, f, indent=2)
    print(f"Clusters saved to {filename}")

def save_clusters_to_csv(clusters, filename=None):
    """Save clusters to a CSV file with timestamp."""
    if filename is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"clusters_{timestamp}.csv"
    
    with open(filename, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['Cluster ID', 'Event'])
        for cluster_id, events in clusters.items():
            # Convert numpy.int64 to regular Python integer
            cluster_id = int(cluster_id)
            for event in events:
                writer.writerow([cluster_id, event])
    print(f"Clusters saved to {filename}")

def main():
    # Load pre-generated embeddings or generate new ones if needed
    embeddings_dict = load_embeddings()
    
    # Analyze similarities
    similar_pairs = analyze_similarities(embeddings_dict)

    # Extract just the embeddings from the dictionary values
    embeddings = [data["embedding"] for data in embeddings_dict.values()]
    clusters = cluster_events(embeddings, eps=0.1, min_samples=2)
    
    # Print clusters in a readable format
    print("\n=== Clusters Found ===")
    for cluster_id, events in clusters.items():
        if cluster_id != -1:  # Skip noise points
            print(f"\nCluster {cluster_id}:")
            for event in events:
                print(f"  • {event}")
        else:
            print(f"\nNoise Points (Cluster -1):")
            for event in events:
                print(f"  • {event}")
    
    # Save clusters to files
    save_clusters_to_json(clusters, "clusters.json")
    save_clusters_to_csv(clusters, "clusters.csv")
    
    #dependent_pairs = find_dependent_pairs(similar_pairs)
    # print(f"\nFound {len(dependent_pairs)} dependent pairs")
    # for pair in dependent_pairs:
    #     print(f"  • {pair[0]} and {pair[1]}")
    
    return clusters

if __name__ == "__main__":
    main()
