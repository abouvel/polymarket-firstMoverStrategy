import streamlit as st
import numpy as np
import plotly.graph_objects as go
from sklearn.manifold import TSNE
from sklearn.cluster import KMeans, DBSCAN, AgglomerativeClustering
from scipy.spatial import ConvexHull
import threading
import asyncio
from ollama import AsyncClient
from similarity import load_embeddings
import time

# --- Initialize persistent cache in session_state ------------------------
if 'cluster_labels_cache' not in st.session_state:
    st.session_state['cluster_labels_cache'] = {}
if 'cluster_labels_cache_lock' not in st.session_state:
    st.session_state['cluster_labels_cache_lock'] = threading.Lock()
cluster_labels_cache = st.session_state['cluster_labels_cache']
cluster_labels_cache_lock = st.session_state['cluster_labels_cache_lock']

# --- Load embeddings ------------------------------------------------------
def get_embeddings():
    embeddings_dict = load_embeddings()
    embeddings = [data['embedding'] for data in embeddings_dict.values()]
    texts = [data['text'] for data in embeddings_dict.values()]
    return np.array(embeddings), texts

# --- TSNE and Clustering -------------------------------------------------
def get_tsne_coords(embeddings, perplexity=30, random_state=42):
    tsne = TSNE(n_components=2,
                perplexity=min(perplexity, len(embeddings)-1),
                random_state=random_state)
    return tsne.fit_transform(embeddings)

def get_cluster_labels(coords, method='kmeans', n_clusters=10, eps=0.1, min_samples=2):
    """Get cluster labels using specified method and parameters."""
    if method == 'kmeans':
        model = KMeans(n_clusters=n_clusters, random_state=42)
        return model.fit_predict(coords)
    elif method == 'dbscan':
        model = DBSCAN(eps=eps, min_samples=min_samples)
        return model.fit_predict(coords)
    elif method == 'agglomerative':
        model = AgglomerativeClustering(n_clusters=n_clusters)
        return model.fit_predict(coords)
    else:
        raise ValueError(f"Unknown clustering method: {method}")

# --- Asynchronous summarization -----------------------------------------
async def summarize_cluster_async(events, model="gemma3:1b", max_events=12):
    prompt = (
        "Here is a list of event titles:\n"
        + "\n".join(f"- {e}" for e in events[:max_events])
        + "\n\nIdentify one concise theme. Return only a short phrase."
    )
    try:
        client = AsyncClient()
        resp = await client.chat(model=model, messages=[{'role':'user','content':prompt}])
        return resp.message.content.strip() or "(No summary)"
    except Exception as e:
        return f"(Error: {e})"

# --- Run summarization in background ------------------------------------
def start_summarization(clusters):
    async def worker():
        for cid, events in clusters.items():
            if cid == -1:
                continue
            summary = await summarize_cluster_async(events)
            with cluster_labels_cache_lock:
                cluster_labels_cache[cid] = summary
        with cluster_labels_cache_lock:
            cluster_labels_cache['summaries_ready'] = True
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(worker())

# --- Plotting helper -----------------------------------------------------
def plot_clusters(coords, labels, texts, summaries, selected):
    fig = go.Figure()
    clusters = {}
    for lbl, txt in zip(labels, texts): clusters.setdefault(lbl,[]).append(txt)
    ids = sorted([cid for cid in clusters if cid != -1])

    def draw(cid, items):
        idx = [i for i,t in enumerate(texts) if t in items]
        pts = coords[idx]
        theme = summaries.get(cid, 'Loading...')
        if len(pts) >= 3:
            hull = ConvexHull(pts)
            pts_hull = np.vstack((pts[hull.vertices], pts[hull.vertices][0]))
            fig.add_trace(go.Scatter(x=pts_hull[:,0], y=pts_hull[:,1], mode='lines',
                                     line=dict(color='rgba(0,0,255,0.5)',width=2),
                                     fill='toself', fillcolor='rgba(100,100,255,0.1)',
                                     name=theme, hoverinfo='text',
                                     text=[f"{theme} ({len(items)})"]*len(pts_hull)))
        fig.add_trace(go.Scatter(x=pts[:,0], y=pts[:,1], mode='markers',
                                 marker=dict(size=8, line=dict(color='white',width=1)),
                                 name=theme,
                                 text=[f"{theme}\n{it}" for it in items], hoverinfo='text'))

    if selected == 'all':
        for cid in ids: draw(cid, clusters[cid])
    else:
        draw(int(selected), clusters[int(selected)])

    fig.update_layout(title='Event Clusters (t-SNE)', hovermode='closest',
                      xaxis=dict(showline=True,showgrid=True,gridcolor='lightgray'),
                      yaxis=dict(showline=True,showgrid=True,gridcolor='lightgray'),
                      plot_bgcolor='white', legend_title_text='Themes')
    return fig, ids

# --- Modular Clustering Pipeline -----------------------------------------
def run_clustering_pipeline(n_clusters, clustering_method, force_recompute=False):
    """
    Modular function to run the entire clustering pipeline.
    Returns: (coords, labels, clusters, nids, texts)
    """
    # Load embeddings
    embeddings, texts = get_embeddings()
    
    # Get t-SNE coordinates
    coords = get_tsne_coords(embeddings)
    
    # Get cluster labels with current parameters
    labels = get_cluster_labels(
        coords, 
        method=clustering_method, 
        n_clusters=n_clusters
    )
    
    # Build cluster->events map
    clusters = {}
    for lbl, txt in zip(labels, texts): 
        clusters.setdefault(lbl,[]).append(txt)
    
    # Get cluster IDs (excluding noise cluster -1)
    nids = sorted([cid for cid in clusters if cid != -1])
    
    return coords, labels, clusters, nids, texts

# --- Streamlit UI --------------------------------------------------------
st.set_page_config(layout='wide')
st.title('Polymarket Event Clusters')

# Controls
col1, col2 = st.columns([2, 1])

with col1:
    n_clusters = st.slider('Number of clusters', 2, 20, 10)

with col2:
    clustering_method = st.selectbox(
        'Clustering Method',
        ['kmeans', 'agglomerative', 'dbscan'],
        format_func=lambda x: x.title()
    )

# Show current parameters
st.info(f"**Current Settings:** {clustering_method.title()} clustering with {n_clusters} clusters")

# Check if parameters changed
current_params = (n_clusters, clustering_method)
if ('last_params' not in st.session_state
    or st.session_state['last_params'] != current_params):
    st.session_state.update({
        'last_params': current_params,
        'summarizing': False
    })
    # Clear cache when parameters change
    with cluster_labels_cache_lock:
        cluster_labels_cache.clear()

# Run clustering pipeline with current parameters
with st.spinner(f"Computing {clustering_method} clusters..."):
    coords, labels, clusters, nids, texts = run_clustering_pipeline(n_clusters, clustering_method)

# Launch summarization thread exactly once and block
if not st.session_state.get('summarizing', False):
    st.session_state['summarizing'] = True
    threading.Thread(target=lambda: start_summarization(clusters), daemon=True).start()
    with st.spinner("🤖 Generating cluster summaries…"):
        while not cluster_labels_cache.get('summaries_ready', False):
            time.sleep(0.5)

# Select and plot
opts = ['all'] + [str(i) for i in nids]
selected = st.selectbox('Select cluster', opts,
                        format_func=lambda x: 'All' if x=='all' else cluster_labels_cache.get(int(x), f'Cluster {x}'))
fig, _ = plot_clusters(coords, labels, texts, cluster_labels_cache, selected)
st.plotly_chart(fig, use_container_width=True)

# Show summaries
st.subheader('Cluster Summaries')
for cid in nids:
    summ = cluster_labels_cache.get(cid, 'Loading...')
    st.write(f"**Cluster {cid}:** {summ} ({len(clusters[cid])} events)")
    if selected in ['all', str(cid)]:
        with st.expander(f'Events in cluster {cid}'):
            for ev in clusters[cid][:10]: st.write(f"- {ev}")
