import requests
import os
import mimetypes
import json
from urllib.parse import urlparse
import base64
from playwright_logo_fallback import download_playwright_fallback, get_country_from_domain

FLARESOLVERR_URL = "http://localhost:8191/v1"
output_dir = "logos"
os.makedirs(output_dir, exist_ok=True)

# Load from logos.json
with open("logos_image_paths.json", "r", encoding="utf-8") as f:
    json_input = json.load(f)

prefixes = ["https://", "http://", "https://www.", "http://www."]

def get_extension(url, content_type):
    ext_from_url = os.path.splitext(url)[-1]
    if ext_from_url and len(ext_from_url) <= 5:
        return ext_from_url
    ext_from_type = mimetypes.guess_extension(content_type)
    return ext_from_type or ".img"

def download_direct_image(url: str, domain: str, output_dir: str) -> bool:
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        }
        resp = requests.get(url, headers=headers, stream=True, timeout=15)
        if resp.status_code == 200:
            os.makedirs(output_dir, exist_ok=True)
            file_path = os.path.join(output_dir, f"{domain}.png")
            with open(file_path, "wb") as f:
                for chunk in resp.iter_content(1024):
                    f.write(chunk)
            print(f"✅ Image saved directly as PNG: {file_path}")
            return True
        else:
            print(f"❌ Failed direct image download: {url} (Status {resp.status_code})")
    except Exception as e:
        print(f"❌ Exception in direct image download: {e}")
    return False

def download_image(url, filename_base):
    if "logo.clearbit.com" in url:
        print(f"🔁 Bypassing FlareSolverr for Clearbit logo: {url}")
        return download_direct_image(url, filename_base, output_dir)

    payload = {
        "cmd": "request.get",
        "url": url,
        "maxTimeout": 60000,
        "download": True
    }

    try:
        resp = requests.post(FLARESOLVERR_URL, json=payload)
        data = resp.json()

        if data.get("status") == "ok":
            content_type = data["solution"].get("headers", {}).get("Content-Type", "")
            body = data["solution"].get("response")

            print(f"📥 FlareSolverr content-type: {content_type}")
            print(f"🔗 FlareSolverr resolved URL: {data['solution'].get('url')}")

            if body and "image" in content_type:
                ext = get_extension(url, content_type)
                filename = os.path.join(output_dir, f"{filename_base}{ext}")
                with open(filename, "wb") as f:
                    f.write(base64.b64decode(body))
                print(f"✅ Saved from FlareSolverr: {filename}")
                return True
            else:
                print(f"❌ Not an image or missing content: {url}")

        else:
            print(f"❌ FlareSolverr error for {url}: {data.get('message')}")

    except Exception as e:
        print(f"❌ Exception for {url}: {e}")

    print(f"🔁 Trying Playwright fallback for: {url}")
    country_code = get_country_from_domain(urlparse(url).netloc)
    return download_playwright_fallback(url, filename_base, output_dir, country_code)

# Get already downloaded logos (without extension)
downloaded = set()
for file in os.listdir(output_dir):
    name, _ = os.path.splitext(file)
    downloaded.add(name.lower())

for entry in json_input:
    domain = entry.get("domain")
    raw_url = entry.get("logo_url")
    if not domain or not raw_url:
        print(f"⚠️ Skipping invalid entry: {entry}")
        continue

    if domain.lower() in downloaded:
        print(f"⏭️  Already downloaded: {domain}")
        continue

    print(f"\n🔍 Trying variants for: {domain} -> {raw_url}")

    success = False
    for prefix in prefixes:
        full_url = prefix + raw_url.lstrip("/")
        if download_image(full_url, filename_base=domain):
            success = True
            break

    if not success:
        print(f"❌ All variants failed for: {domain}")