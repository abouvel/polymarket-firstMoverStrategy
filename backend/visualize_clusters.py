import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np
from similarity import load_embeddings, cluster_events, get_unique_titles
import dash
from dash import dcc, html
from dash.dependencies import Input, Output
import json
from scipy.spatial import ConvexHull
from sklearn.metrics.pairwise import cosine_distances
from sklearn.cluster import DBSCAN, KMeans, AgglomerativeClustering
from sklearn.manifold import TSNE
from dash import ctx
import os
import hashlib
import joblib
import concurrent.futures
import threading
import time
from ollama import chat, ResponseError


# Set up joblib cache directory
memory = joblib.Memory(location=".cache", verbose=0)

# Global cache for cluster summaries
cluster_summaries_cache = {}
cluster_summaries_lock = threading.Lock()

# Global state for cluster summaries
summaries_ready = False
cluster_labels = {}
last_n_clusters = None

def get_embeddings():
    """Load and return embeddings and texts."""
    embeddings_dict = load_embeddings()
    embeddings = [data["embedding"] for data in embeddings_dict.values()]
    texts = [data["text"] for data in embeddings_dict.values()]
    return np.array(embeddings), texts

@memory.cache
def get_tsne_coords(embeddings, tsne_perplexity=30, tsne_random_state=42):
    """
    Compute (or load cached) t-SNE coordinates for embeddings.
    Uses joblib caching based on embeddings hash and t-SNE params.
    """
    tsne = TSNE(n_components=2, random_state=tsne_random_state, perplexity=min(tsne_perplexity, len(embeddings)-1))
    return tsne.fit_transform(embeddings)

@memory.cache
def get_cluster_labels(coords_2d, method='kmeans', n_clusters=10, dbscan_eps=5, dbscan_min_samples=5, agglom_distance_threshold=None):
    """
    Compute (or load cached) cluster labels for 2D coordinates.
    Uses joblib caching based on coordinates and clustering params.
    """
    if method == 'kmeans':
        model = KMeans(n_clusters=n_clusters, random_state=42)
        labels = model.fit_predict(coords_2d)
    elif method == 'dbscan':
        model = DBSCAN(eps=dbscan_eps, min_samples=dbscan_min_samples)
        labels = model.fit_predict(coords_2d)
    elif method == 'agglomerative':
        if agglom_distance_threshold is not None:
            model = AgglomerativeClustering(distance_threshold=agglom_distance_threshold, n_clusters=None)
        else:
            model = AgglomerativeClustering(n_clusters=n_clusters)
        labels = model.fit_predict(coords_2d)
    else:
        raise ValueError(f"Unknown clustering method: {method}")
    return labels

# Cleaned up summarization function using only the Ollama Python SDK
def summarize_cluster(events, model="gemma3:1b", max_events=12):
    selected = events[:max_events]
    prompt = (
        "Here is a list of current Polymarket event titles:\n"
        + "\n".join(f"- {e}" for e in selected)
        + "\n\nYou are an expert in global current events, with deep knowledge across domains like Politics, Sports, Crypto, Tech, Culture, World Affairs, the Economy, U.S. Elections, and public figures such as Donald Trump.\n\n"
        "Your task is to identify a single, clear theme that connects these events. Focus on the underlying subject matter—not the fact that these are prediction markets or betting events.\n\n"
        "Return one short, creative, and specific phrase that best captures the shared topic. Do not include any explanation or reasoning—just the phrase.\n\n"
        "Some examples of good outputs (for reference only):\n"
        "- “AI Policy Debates”\n"
        "- “2024 Senate Races”\n"
        "- “Crypto Drama”\n"
        "- “European Geopolitics”\n\n"
        "These are just illustrative. Your output should reflect the unique theme of the provided list."
    )

    print(f"[Summarize] Sending prompt to Ollama for cluster of {len(events)} events.")
    try:
        response = chat(
            model=model,
            messages=[{"role": "user", "content": prompt}]
        )
        summary = response.message.content.strip()
        if not summary:
            print("[Summarize] WARNING: Ollama returned an empty summary. Using fallback.")
            summary = "(No summary generated)"
        print(f"[Summarize] Ollama returned: {summary}")
        return summary
    except ResponseError as e:
        print(f"[Summarize] Ollama error: {e.error}")
        return "(AI summary error)"
    except Exception as e:
        print(f"[Summarize] General error: {e}")
        return "(AI summary error)"

# Parallel summarization using the SDK
def start_parallel_summarization(clusters, model="gemma3:1b", max_events=12):
    global summaries_ready, cluster_labels, last_n_clusters
    def summarize_and_store(cid, events):
        print(f"[Summarize] Starting summary for cluster {cid}...")
        summary = summarize_cluster(events, model=model, max_events=max_events)
        with cluster_summaries_lock:
            cluster_labels[cid] = summary
        print(f"[Summarize] Stored summary for cluster {cid}.")
    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = []
        for cid, events in clusters.items():
            if cid == -1:
                continue
            futures.append(executor.submit(summarize_and_store, cid, events))
        # Wait for all to finish
        for f in futures:
            f.result()
    summaries_ready = True



def get_cluster_summary(cid):
    with cluster_summaries_lock:
        return cluster_summaries_cache.get(cid, "Loading...")

def create_cluster_visualization_with_metadata(
    eps=0.1, min_samples=2, clustering_method='agglomerative', n_clusters=10, selected_cluster='all', tsne_perplexity=30, tsne_random_state=42):
    """
    Returns (fig, cluster_ids, cluster_labels) for use in Dash callback.
    If selected_cluster is not 'all', only that cluster is shown and zoomed.
    Uses cached t-SNE and clustering for speed.
    """
    global summaries_ready, cluster_labels, last_n_clusters
    embeddings, texts = get_embeddings()
    coords_2d = get_tsne_coords(embeddings, tsne_perplexity=tsne_perplexity, tsne_random_state=tsne_random_state)
    labels = get_cluster_labels(
        coords_2d,
        method=clustering_method,
        n_clusters=n_clusters,
        dbscan_eps=eps,
        dbscan_min_samples=min_samples
    )
    clusters = {}
    for label, text in zip(labels, texts):
        clusters.setdefault(label, []).append(text)
    cluster_ids = sorted([cid for cid in clusters.keys() if cid != -1])

    # Only start summarization if n_clusters changed or first load
    if last_n_clusters != n_clusters:
        
        print(f"[Summarize] n_clusters changed from {last_n_clusters} to {n_clusters}, starting summarization.")
        summaries_ready = False
        last_n_clusters = n_clusters
        cluster_labels.clear()
        last_n_clusters = n_clusters
        threading.Thread(target=start_parallel_summarization, args=(clusters,), daemon=True).start()

    fig = go.Figure()
    if not summaries_ready:
        fig.update_layout(title='Loading cluster summaries...', xaxis={'visible': False}, yaxis={'visible': False})
        return fig, cluster_ids, {}
    # Otherwise, plot with real cluster_labels
    if selected_cluster != 'all':
        cid = int(selected_cluster)
        events = clusters[cid]
        cluster_indices = [i for i, text in enumerate(texts) if text in events]
        cluster_coords = coords_2d[cluster_indices]
        label = cluster_labels.get(cid, '')
        if len(cluster_coords) >= 3:
            try:
                hull = ConvexHull(cluster_coords)
                hull_points = cluster_coords[hull.vertices]
                hull_points = np.vstack((hull_points, hull_points[0]))
                fig.add_trace(go.Scatter(
                    x=hull_points[:, 0],
                    y=hull_points[:, 1],
                    mode='lines',
                    line=dict(color='rgba(0, 0, 255, 0.5)', width=2, dash='solid'),
                    fill='toself',
                    fillcolor='rgba(100, 100, 255, 0.05)',
                    name=f'{label}',
                    hoverinfo='text',
                    text=[f"{label}<br>Events: {len(events)}"] * len(hull_points)
                ))
            except Exception as e:
                print(f"Error creating hull for cluster {cid}: {e}")
        fig.add_trace(go.Scatter(
            x=cluster_coords[:, 0],
            y=cluster_coords[:, 1],
            mode='markers',
            marker=dict(size=10, color='rgba(0, 0, 255, 0.7)', symbol='circle', line=dict(color='white', width=1)),
            name=f'{label}',
            text=[f"{label}<br>{texts[i]}" for i in cluster_indices],
            hoverinfo='text'
        ))
        # Zoom to cluster
        x_margin, y_margin = 10, 10
        x0, x1 = cluster_coords[:,0].min()-x_margin, cluster_coords[:,0].max()+x_margin
        y0, y1 = cluster_coords[:,1].min()-y_margin, cluster_coords[:,1].max()+y_margin
        fig.update_xaxes(range=[x0, x1])
        fig.update_yaxes(range=[y0, y1])
    else:
        for cluster_id, events in clusters.items():
            if cluster_id == -1:
                continue
            cluster_indices = [i for i, text in enumerate(texts) if text in events]
            cluster_coords = coords_2d[cluster_indices]
            label = cluster_labels.get(cluster_id, '')
            if len(cluster_coords) >= 3:
                try:
                    hull = ConvexHull(cluster_coords)
                    hull_points = cluster_coords[hull.vertices]
                    hull_points = np.vstack((hull_points, hull_points[0]))
                    fig.add_trace(go.Scatter(
                        x=hull_points[:, 0],
                        y=hull_points[:, 1],
                        mode='lines',
                        line=dict(color='rgba(0, 0, 255, 0.5)', width=2, dash='solid'),
                        fill='toself',
                        fillcolor='rgba(100, 100, 255, 0.05)',
                        name=f'{label}',
                        hoverinfo='text',
                        text=[f"{label}<br>Events: {len(events)}"] * len(hull_points)
                    ))
                except Exception as e:
                    print(f"Error creating hull for cluster {cluster_id}: {e}")
            fig.add_trace(go.Scatter(
                x=cluster_coords[:, 0],
                y=cluster_coords[:, 1],
                mode='markers',
                marker=dict(size=10, color='rgba(0, 0, 255, 0.7)', symbol='circle', line=dict(color='white', width=1)),
                name=f'{label}',
                text=[f"{label}<br>{texts[i]}" for i in cluster_indices],
                hoverinfo='text'
            ))
        # Add noise points (for DBSCAN)
        noise_indices = [i for i, label in enumerate(labels) if label == -1]
        if noise_indices:
            noise_coords = coords_2d[noise_indices]
            fig.add_trace(go.Scatter(
                x=noise_coords[:, 0],
                y=noise_coords[:, 1],
                mode='markers',
                marker=dict(size=8, color='rgba(128, 128, 128, 0.5)', symbol='circle', line=dict(color='white', width=1)),
                name='Noise Points',
                text=['Noise']*len(noise_indices),
                hoverinfo='text'
            ))
    fig.update_layout(
        title='Event Clusters Visualization (t-SNE)',
        hovermode='closest',
        showlegend=True,
        xaxis_title='t-SNE Dimension 1',
        yaxis_title='t-SNE Dimension 2',
        plot_bgcolor='white',
        hoverdistance=2,
        spikedistance=1000,
        xaxis=dict(showspikes=True, spikecolor='gray', spikesnap='cursor', showline=True, showgrid=True, gridcolor='lightgray', zeroline=False),
        yaxis=dict(showspikes=True, spikecolor='gray', spikesnap='cursor', showline=True, showgrid=True, gridcolor='lightgray', zeroline=False)
    )
    return fig, cluster_ids, cluster_labels

# Initialize Dash app
app = dash.Dash(__name__)

# Define app layout with improved styling
app.layout = html.Div([
    html.H1('Interactive Cluster Visualization', style={'textAlign': 'center', 'color': '#2c3e50', 'margin': '20px'}),
    html.Div([
        html.Label('Number of Clusters:', style={'fontSize': '16px', 'marginRight': '10px'}),
        dcc.Slider(
            id='n-clusters-slider',
            min=2,
            max=30,
            step=1,
            value=10,
            marks={i: str(i) for i in range(2, 31, 2)},
            tooltip={"placement": "bottom", "always_visible": True}
        ),
        html.Label('Select Cluster:', style={'fontSize': '16px', 'marginLeft': '40px', 'marginRight': '10px'}),
        dcc.Dropdown(
            id='cluster-dropdown',
            options=[{'label': 'All', 'value': 'all'}],
            value='all',
            clearable=False,
            style={'width': '200px', 'display': 'inline-block'}
        ),
    ], style={'width': '90%', 'margin': '20px auto', 'padding': '20px'}),
    dcc.Graph(id='cluster-graph', style={'height': '80vh'}),
    dcc.Interval(id='interval-component', interval=2000, n_intervals=0)  # 2 seconds
], style={'backgroundColor': '#f8f9fa', 'padding': '20px'})

# Define callback
@app.callback(
    [Output('cluster-graph', 'figure'), Output('cluster-dropdown', 'options')],
    [Input('n-clusters-slider', 'value'), Input('cluster-dropdown', 'value'), Input('interval-component', 'n_intervals')]
)
def update_graph(n_clusters, selected_cluster, n_intervals):
    fig, cluster_ids, cluster_labels = create_cluster_visualization_with_metadata(n_clusters=n_clusters, selected_cluster=selected_cluster)
    options = [{'label': 'All', 'value': 'all'}] + [
        {'label': cluster_labels.get(cid, 'Loading...'), 'value': str(cid)} for cid in cluster_ids
    ]
    return fig, options

if __name__ == '__main__':
    app.run(debug=True) 