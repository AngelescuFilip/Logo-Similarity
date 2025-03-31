import requests
import os
import mimetypes
import json
import base64
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor
from playwright_logo_fallback import download_playwright_fallback, get_country_from_domain

FLARESOLVERR_URL = "http://localhost:8191/v1"
output_dir = "logos"
os.makedirs(output_dir, exist_ok=True)

# Load input
with open("logos_image_paths.json", "r", encoding="utf-8") as f:
    json_input = json.load(f)

prefixes = ["https://", "http://", "https://www.", "http://www."]

# Track already downloaded files
already_downloaded = {os.path.splitext(f)[0].lower() for f in os.listdir(output_dir)}

def get_extension(url, content_type):
    ext_from_url = os.path.splitext(url)[-1]
    if ext_from_url and len(ext_from_url) <= 5:
        return ext_from_url
    ext_from_type = mimetypes.guess_extension(content_type)
    return ext_from_type or ".img"

def download_direct_image(url: str, domain: str) -> bool:
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        }
        resp = requests.get(url, headers=headers, stream=True, timeout=10)
        if resp.status_code == 200:
            file_path = os.path.join(output_dir, f"{domain}.png")
            with open(file_path, "wb") as f:
                for chunk in resp.iter_content(1024):
                    f.write(chunk)
            print(f"✅ Direct image: {file_path}")
            return True
    except Exception as e:
        print(f"❌ Direct download error: {e}")
    return False

def download_image(url, domain):
    if "logo.clearbit.com" in url:
        return download_direct_image(url, domain)

    payload = {
        "cmd": "request.get",
        "url": url,
        "maxTimeout": 30000,
        "download": True
    }

    try:
        resp = requests.post(FLARESOLVERR_URL, json=payload, timeout=30)
        data = resp.json()
        if data.get("status") == "ok":
            content_type = data["solution"].get("headers", {}).get("Content-Type", "")
            body = data["solution"].get("response")

            if body and "image" in content_type:
                ext = get_extension(url, content_type)
                file_path = os.path.join(output_dir, f"{domain}{ext}")
                with open(file_path, "wb") as f:
                    f.write(base64.b64decode(body))
                print(f"✅ FlareSolverr: {file_path}")
                return True
        else:
            print(f"❌ FlareSolverr error: {data.get('message')}")
    except Exception as e:
        print(f"❌ FlareSolverr exception: {e}")

    print(f"🔁 Falling back to Playwright for: {url}")
    country = get_country_from_domain(urlparse(url).netloc)
    return download_playwright_fallback(url, domain, output_dir, country)

def process_entry(entry):
    domain = entry.get("domain")
    raw_url = entry.get("logo_url")

    if not domain or not raw_url or domain.lower() in already_downloaded:
        return

    print(f"\n🔍 Processing: {domain}")
    for prefix in prefixes:
        full_url = prefix + raw_url.lstrip("/")
        if download_image(full_url, domain):
            return
    print(f"❌ All attempts failed for: {domain}")

# Run in parallel
with ThreadPoolExecutor(max_workers=5) as executor:
    executor.map(process_entry, json_input)