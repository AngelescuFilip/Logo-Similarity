from fastapi import FastAPI
from pydantic import BaseModel
from typing import List
import os
import json
import pandas as pd
import requests
from dotenv import load_dotenv
from io import BytesIO
from PIL import Image, ImageOps
import time
import io
import imghdr
import cairosvg
import torch
import hnswlib
import numpy as np
import networkx as nx
import networkx.algorithms.components.connected as nx_conn
from tqdm import tqdm
from transformers import AutoProcessor, AutoModel
import pillow_avif
import community as community_louvain
import igraph as ig
import leidenalg
import csv
from logo_extractor import extract_logo_url_from_html

load_dotenv()
LOGODEV_API_KEY = os.getenv("LOGODEV_API_KEY")

app = FastAPI()


class DomainList(BaseModel):
    domains: List[str]


def run_scraper():
    os.system('python scraper_crawl.py')

def download_logos_from_url():
    # Use FlareSolverr-based script instead of requests-based download
    os.system('python flaresolverr_logo_download.py')

def save_logo_paths(logos, filename="logos_image_paths.json"):
    with open(filename, "w") as f:
        json.dump(logos, f)


def clean_html_folder(folder_path: str):
    for filename in os.listdir(folder_path):
        if filename.startswith('www.'):
            new_name = filename.replace('www.', '', 1)
            old_path = os.path.join(folder_path, filename)
            new_path = os.path.join(folder_path, new_name)
            os.rename(old_path, new_path)

def remove_url_prefixes(logos):
    for entry in logos:
        if entry['logo_url'].startswith("https://"):
            entry['logo_url'] = entry['logo_url'].replace("https://", "", 1)
        if entry['logo_url'].startswith("http://"):
            entry['logo_url'] = entry['logo_url'].replace("http://", "", 1)
    return logos

def get_failed_domains(domains, downloaded_folder="logos"):
    downloaded = {os.path.splitext(f)[0] for f in os.listdir(downloaded_folder)}
    return [d for d in domains if d not in downloaded]


def is_valid_image_url(url, content=None):
    try:
        if content is None:
            response = requests.get(url, timeout=5)
            if response.status_code != 200:
                return False
            content = response.content
        img = Image.open(BytesIO(content))
        return img.width > 1 and img.height > 1
    except Exception as e:
        print(f"⚠️ Image validation failed for {url}: {e}")
        return False


def get_logo_logodev(domain):
    url = f"https://img.logo.dev/{domain}?token={LOGODEV_API_KEY}&fallback=404"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200 and response.headers["Content-Type"].startswith("image"):
            return url, 200
        elif response.status_code == 202:
            print(f"🕒 Logo.dev is processing {domain} (202)")
            return None, 202
        elif response.status_code == 404:
            print(f"🚫 Logo.dev: No logo for {domain} (404)")
            return None, 404
        else:
            print(f"🟥 Logo.dev failed for {domain} (status {response.status_code})")
            return None, response.status_code
    except Exception as e:
        print(f"⚠️ Logo.dev request error for {domain}: {e}")
        return None, None


def get_logo_clearbit(domain):
    url = f"https://logo.clearbit.com/{domain}"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200 and response.headers["Content-Type"].startswith("image"):
            if is_valid_image_url(url, response.content):
                return url, 200
            else:
                print(f"🟥 Clearbit returned invalid image for {domain}")
                return None, 200
        else:
            print(f"🟥 Clearbit failed for {domain} (status {response.status_code})")
            return None, response.status_code
    except Exception as e:
        print(f"⚠️ Clearbit error for {domain}: {e}")
        return None, None


def fetch_logos_from_apis(domains, use_logodev=True, use_clearbit=True):
    results = []
    pending_logos = []

    for domain in domains:
        print(f"🔍 Looking for logo for: {domain}")
        logo_url = None

        if use_logodev:
            logo_url_dev, status = get_logo_logodev(domain)
            if logo_url_dev:
                logo_url = logo_url_dev
            elif status == 202:
                print(f"⏳ Logo.dev is processing {domain}")
                pending_logos.append(domain)

        if not logo_url and use_clearbit:
            logo_url_clearbit, status = get_logo_clearbit(domain)
            if logo_url_clearbit:
                logo_url = logo_url_clearbit

        results.append({
            "domain": domain,
            "logo_url": logo_url
        })

    if pending_logos:
        print(f"\n🔁 Waiting to recheck {len(pending_logos)} pending logos from Logo.dev...")
        time.sleep(240)
        for domain in pending_logos:
            logo_url, status = get_logo_logodev(domain)
            if logo_url:
                print(f"✅ Logo now available for {domain}")
                for entry in results:
                    if entry["domain"] == domain and not entry["logo_url"]:
                        entry["logo_url"] = logo_url

    for entry in results:
        if not entry["logo_url"]:
            entry["logo_url"] = 'NO_LOGO_FOUND'

    return results


def clean_logo_urls(logos):
    for entry in logos:
        if entry['logo_url'].startswith("https://"):
            entry['logo_url'] = entry['logo_url'].replace("https://", "", 1)
        if entry['logo_url'].startswith("http://"):
            entry['logo_url'] = entry['logo_url'].replace("http://", "", 1)
    return [entry for entry in logos if entry['logo_url'] != 'NO_LOGO_FOUND']


def save_logos_to_json(logos, filename="logos.json"):
    with open(filename, "w") as f:
        json.dump(logos, f)


def download_logos(logo_data, save_dir='logos'):
    os.makedirs(save_dir, exist_ok=True)
    for item in logo_data:
        domain = item['domain']
        logo_url = item['logo_url']
        if logo_url == 'NO_LOGO_FOUND':
            print(f"❌ Skipping {domain} — no logo found.")
            continue
        try:
            response = requests.get(logo_url, timeout=10)
            if response.status_code == 200:
                file_path = os.path.join(save_dir, f"{domain}.png")
                with open(file_path, 'wb') as f:
                    f.write(response.content)
                print(f"✅ Saved logo for {domain}")
            else:
                print(f"⚠️ Failed to download logo for {domain} (status {response.status_code})")
        except Exception as e:
            print(f"⚠️ Error downloading logo for {domain}: {e}")


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


processor = AutoProcessor.from_pretrained("facebook/dinov2-base")
model = AutoModel.from_pretrained("facebook/dinov2-base").eval().to(torch.device("cuda" if torch.cuda.is_available() else "cpu"))
processor.size = {"height": 224, "width": 224}
processor.do_center_crop = False


def extract_features_with_padding(image_paths, domains, batch_size=32):
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
            inputs = processor(images=batch_imgs, return_tensors="pt").to(model.device)
            outputs = model(**inputs).last_hidden_state.mean(dim=1)
            all_embeddings.append(outputs.cpu().numpy())
            valid_domains.extend(batch_domains)
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


def cluster_indices_to_domains(cluster_dict, domains):
    cluster_domains = {}
    for cluster_id, logo_indices in cluster_dict.items():
        cluster_domains[cluster_id] = [domains[i] for i in logo_indices]
    return cluster_domains


def get_logo_paths_from_folder(folder, domains):
    supported_exts = ['.jpg', '.jpeg', '.png', '.webp', '.svg', '.img']
    logo_paths = []
    valid_domains = []
    for domain in domains:
        for ext in supported_exts:
            candidate = os.path.join(folder, f"{domain}{ext}")
            if os.path.isfile(candidate):
                logo_paths.append(candidate)
                valid_domains.append(domain)
                break
    return logo_paths, valid_domains


def save_clusters_to_csv(cluster_dict, domains, output_file="clusters.csv"):
    with open(output_file, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["cluster_id", "domain"])
        for cluster_id, indices in cluster_dict.items():
            for idx in indices:
                writer.writerow([cluster_id, domains[idx]])
    print(f"✅ Clusters saved to {output_file}")


@app.post("/process-logos")
def process_logos(data: DomainList, html_folder: str = "scraped_domains_html"):
    domains = data.domains
    with open("domains.txt", "w") as f:
        for domain in domains:
            f.write(domain + "\n")

    run_scraper()
    clean_html_folder(html_folder)

    # Step 2: Extract logo URLs from HTML
    logos = extract_logo_url_from_html(html_folder)

    # Step 3: Clean logo URLs
    logos = remove_url_prefixes(logos)
    filtered_logos = filter_valid_logos(logos)
    save_logo_paths(filtered_logos)

    # Step 4: Download logos
    download_logos_from_url()

    # Step 5: Identify failed downloads and fetch via APIs
    failed = get_failed_domains(domains)
    fallback_logos = fetch_logos_from_apis(failed)
    fallback_logos = filter_valid_logos(remove_url_prefixes(fallback_logos))

    # Combine everything
    all_logos = filtered_logos + fallback_logos
    save_logo_paths(all_logos)

    # Step 6: Clustering
    df_logos = pd.DataFrame(all_logos)
    clusters = cluster_logos(df_logos)
    save_clusters_to_csv(clusters_dict, valid_domains, output_file="clusters.csv")

    return {
        "logos": cleaned_logos,
        "clusters": domain_clusters,
        "num_clusters": len(final_clusters),
        "num_unique": len(unique_logos)
    }
