import os
import mimetypes
import asyncio
from pathlib import Path
from urllib.parse import urlparse
from playwright.async_api import async_playwright
import random
import requests
import json
import time

# Load proxy pool
with open('proxies.json') as f:
    PROXY_POOL = json.load(f)

# Rotating user agents
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:115.0) Gecko/20100101 Firefox/115.0",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 16_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.4 Mobile/15E148 Safari/604.1"
]

TLD_COUNTRY_OVERRIDES = {
    "co.uk": "GB",
    "org.uk": "GB",
    "ac.uk": "GB",
    "com.au": "AU",
    "net.au": "AU",
    "org.au": "AU",
}

def get_country_from_domain(domain: str) -> str:
    domain = domain.lower()
    for suffix, country in TLD_COUNTRY_OVERRIDES.items():
        if domain.endswith(suffix):
            return country
    parts = domain.split(".")
    return parts[-1].upper() if len(parts) >= 2 else "US"

def get_proxy_by_country(country_code: str):
    return [p for p in PROXY_POOL if p["country"].upper() == country_code.upper()]

def get_backup_proxies(exclude_country: str):
    return [p for p in PROXY_POOL if p["country"].upper() != exclude_country.upper()]

def download_direct_image(url: str, domain: str, output_dir: str) -> bool:
    try:
        headers = {
            "User-Agent": random.choice(USER_AGENTS),
            "Referer": f"https://{urlparse(url).netloc}/"
        }
        resp = requests.get(url, headers=headers, stream=True, timeout=10, allow_redirects=True)

        if resp.url != url:
            print(f"⚠️ Redirected to {resp.url}, skipping.")
            return False

        first_chunk = next(resp.iter_content(512), b"")
        if b"<html" in first_chunk.lower() or b"<!doctype" in first_chunk.lower():
            print("⚠️ Looks like HTML, not an image.")
            return False

        if resp.status_code == 200:
            file_path = os.path.join(output_dir, f"{domain}.png")
            os.makedirs(output_dir, exist_ok=True)
            with open(file_path, "wb") as f:
                f.write(first_chunk)
                for chunk in resp.iter_content(1024):
                    f.write(chunk)
            print(f"✅ Saved directly: {file_path}")
            return True
    except Exception as e:
        print(f"❌ Direct download error: {e}")
    return False

async def playwright_image_download(url: str, domain: str, output_dir: str, proxies: list) -> bool:
    random.shuffle(proxies)
    max_retries = min(2, len(proxies))
    tried = 0

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)

        for proxy in proxies:
            if tried >= max_retries:
                print("🔁 Max retries reached.")
                break

            print(f"🌍 Trying proxy {proxy['server']} ({proxy['country']})")

            try:
                context = await browser.new_context(
                    user_agent=random.choice(USER_AGENTS),
                    proxy={
                        "server": proxy["server"],
                        "username": proxy["username"],
                        "password": proxy["password"]
                    }
                )
                await context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => false});")
                page = await context.new_page()
                response = await page.goto(url, timeout=15000, wait_until="load")

                if not response:
                    print("❌ No response from page.")
                    await context.close()
                    tried += 1
                    time.sleep(2 ** tried)  # Exponential backoff
                    continue

                final_url = page.url
                content_type = response.headers.get("content-type", "")

                print("🔍 Status:", response.status)
                print("🔍 Content-Type:", content_type)

                ext = os.path.splitext(urlparse(url).path)[-1].lower()
                image_like = ext in [".png", ".jpg", ".jpeg", ".svg", ".gif", ".webp", ".bmp"]

                if final_url != url:
                    print(f"⚠️ Redirected to {final_url}, skipping.")
                    await context.close()
                    tried += 1
                    time.sleep(2 ** tried)
                    continue

                body = await response.body()

                if b"<html" in body.lower() or b"<!doctype" in body.lower():
                    print("⚠️ HTML content detected.")
                    await context.close()
                    tried += 1
                    time.sleep(2 ** tried)
                    continue

                if response.status == 200 and (content_type.startswith("image/") or image_like):
                    ext = mimetypes.guess_extension(content_type.split(";")[0]) or ext or ".img"
                    file_path = os.path.join(output_dir, f"{domain}{ext}")
                    os.makedirs(output_dir, exist_ok=True)
                    with open(file_path, "wb") as f:
                        f.write(body)
                    print(f"✅ Playwright saved: {file_path}")
                    await context.close()
                    await browser.close()
                    return True

                print("❌ Not an image response.")
                await context.close()
                tried += 1
                time.sleep(2 ** tried)

            except Exception as e:
                print(f"❌ Proxy failed: {e}")
                tried += 1
                time.sleep(2 ** tried)

        await browser.close()

    print("🚫 All proxies failed.")
    return False

def download_playwright_fallback(url: str, domain: str, output_dir: str, country_code: str = "US") -> bool:
    proxies = get_proxy_by_country(country_code) + get_backup_proxies(country_code)
    return asyncio.run(playwright_image_download(url, domain, output_dir, proxies))

# # Example usage for testing
# if __name__ == "__main__":
#     domain = "aamco-bellevue.com"
#     url = "www.aamco-bellevue.com/wp-content/uploads/2018/09/logo.png"
#     country_code = get_country_from_domain(domain)
#     download_playwright_fallback(url, domain, "logos", country_code)
