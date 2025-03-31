import os
import imghdr
import io
import cairosvg
import pillow_avif
from PIL import Image, ImageOps
import numpy as np
import networkx as nx
import networkx.algorithms.components.connected as nx_conn
from tqdm import tqdm
from transformers import AutoProcessor, AutoModel
import community as community_louvain
import hnswlib
import torch
import igraph as ig
import leidenalg
import csv

def is_avif(path):
    try:
        with open(path, "rb") as f:
            return b"ftypavif" in f.read(32)
    except:
        return False

def load_image(path):
    ext = os.path.splitext(path)[1].lower()
    try:
        if ext == '.svg':
            png_data = cairosvg.svg2png(url=path)
            return Image.open(io.BytesIO(png_data)).convert("RGB")
        elif ext in ['.jpg', '.jpeg', '.png', '.webp', '.avif']:
            return Image.open(path).convert("RGB")
        elif ext == '.img':
            if is_avif(path):
                try:
                    return Image.open(path).convert("RGB")
                except Exception as e:
                    print(f"⚠️ Skipping unreadable AVIF: {path} — {e}")
                    return None
            else:
                real_ext = imghdr.what(path)
                if real_ext in ['jpeg', 'png', 'webp']:
                    return Image.open(path).convert("RGB")
                else:
                    print(f"⚠️ Skipping unknown .img: {path} (detected: {real_ext})")
                    return None
        else:
            print(f"⚠️ Skipping unsupported extension: {path}")
            return None
    except Exception as e:
        print(f"❌ Skipping unreadable file: {path} — Reason: {e}")
        return None

def pad_to_square(image, fill=(255, 255, 255)):
    w, h = image.size
    max_dim = max(w, h)
    delta_w = max_dim - w
    delta_h = max_dim - h
    padding = (delta_w // 2, delta_h // 2, delta_w - delta_w // 2, delta_h - delta_h // 2)
    return ImageOps.expand(image, padding, fill=fill)

def extract_features_with_padding(image_paths, domains, device, processor, model, batch_size=32):
    all_embeddings = []
    valid_domains = []
    with torch.inference_mode():
        for i in tqdm(range(0, len(image_paths), batch_size), desc="Extracting features"):
            batch_imgs = []
            batch_domains = []
            for p, domain in zip(image_paths[i:i+batch_size], domains[i:i+batch_size]):
                img = load_image(p)
                if img is None:
                    continue
                img = pad_to_square(img)
                batch_imgs.append(img)
                batch_domains.append(domain)
            if not batch_imgs:
                continue
            inputs = processor(images=batch_imgs, return_tensors="pt").to(device)
            outputs = model(**inputs).last_hidden_state.mean(dim=1)
            all_embeddings.append(outputs.cpu().numpy())
            valid_domains.extend(batch_domains)
    if not all_embeddings:
        return np.array([]), []
    return np.vstack(all_embeddings), valid_domains

def build_hnsw_index(embeddings, ef=100, ef_construction=200, M=64, save_path=None):
    dim = embeddings.shape[1]
    index = hnswlib.Index(space='l2', dim=dim)
    index.init_index(max_elements=len(embeddings), ef_construction=ef_construction, M=M)
    index.add_items(embeddings)
    index.set_ef(ef)
    if save_path:
        index.save_index(save_path)
    return index

def build_similarity_graph(index, embeddings, k=10, threshold=0.75):
    labels, distances = index.knn_query(embeddings, k=k)
    G = nx.Graph()
    for i in range(len(embeddings)):
        for j, neighbor in enumerate(labels[i]):
            if i != neighbor:
                similarity = 1 - distances[i][j]
                if similarity >= threshold:
                    G.add_edge(i, neighbor, weight=similarity)
    return G

def graph_to_igraph(G_nx):
    mapping = {node: idx for idx, node in enumerate(G_nx.nodes())}
    reverse_mapping = {idx: node for node, idx in mapping.items()}
    edges = [(mapping[u], mapping[v]) for u, v in G_nx.edges()]
    G_ig = ig.Graph(edges=edges, directed=False)
    return G_ig, reverse_mapping

def cluster_with_leiden(G_nx):
    G_ig, reverse_map = graph_to_igraph(G_nx)
    partition = leidenalg.find_partition(G_ig, leidenalg.ModularityVertexPartition)
    clusters = {}
    for cluster_id, nodes in enumerate(partition):
        clusters[cluster_id] = [reverse_map[n] for n in nodes]
    return clusters

def split_clusters(G):
    components = list(nx_conn.connected_components(G))
    final_clusters = []
    unique_logos = []
    for comp in components:
        if len(comp) > 1:
            final_clusters.append(list(comp))
        else:
            unique_logos.append(list(comp)[0])
    return final_clusters, unique_logos

def cluster_indices_to_domains(cluster_dict, valid_domains):
    cluster_domains = {}
    for cluster_id, logo_indices in cluster_dict.items():
        cluster_domains[cluster_id] = [valid_domains[i] for i in logo_indices]
    return cluster_domains

def get_logo_paths(folder, domain_names):
    supported_exts = ['.jpg', '.jpeg', '.png', '.webp', '.svg', '.img']
    logo_paths = []
    valid_domains = []
    all_files = set(os.listdir(folder))
    seen_domains = set()
    for domain in domain_names:
        if domain in seen_domains:
            continue
        for ext in supported_exts:
            filename = f"{domain}{ext}"
            if filename in all_files:
                path = os.path.join(folder, filename)
                logo_paths.append(path)
                valid_domains.append(domain)
                seen_domains.add(domain)
                break
    return logo_paths, valid_domains

# def save_clusters_to_csv(cluster_dict, domains, output_file="clusters.csv"):
#     with open(output_file, mode="w", newline="", encoding="utf-8") as f:
#         writer = csv.writer(f)
#         writer.writerow(["cluster_id", "domain"])
#         for cluster_id, indices in cluster_dict.items():
#             for idx in indices:
#                 writer.writerow([cluster_id, domains[idx]])
#     print(f"✅ Clusters saved to {output_file}")

def clustering(device, processor, model, domains):
    domains = list(dict.fromkeys(domains))
    print("🔍 Domains passed in:", domains)
    print("📂 Files in 'logos/' folder:", os.listdir("logos"))
    logo_paths, valid_domains = get_logo_paths("logos", domains)
    if not logo_paths:
        print("❌ No matching logo files found.")
        return {}
    embeddings, valid_domains = extract_features_with_padding(logo_paths, valid_domains, device, processor, model, batch_size=32)
    index = build_hnsw_index(embeddings, save_path="hnsw_index.bin")
    G = build_similarity_graph(index, embeddings, k=3, threshold=0.92)
    clusters_dict = cluster_with_leiden(G)
    domain_clusters = cluster_indices_to_domains(clusters_dict, valid_domains)
    return domain_clusters
