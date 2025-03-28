# playwright_logo_fallback.py

import os
import mimetypes
import asyncio
from pathlib import Path
from urllib.parse import urlparse
from playwright.async_api import async_playwright
import random
import requests
import json

# Example proxy pool
with open('proxies.json') as f:
    PROXY_POOL = json.load(f)


# Improved domain to country code extractor
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
            "User-Agent": "Mozilla/5.0",
            "Referer": f"https://{urlparse(url).netloc}/"
        }
        resp = requests.get(url, headers=headers, stream=True, timeout=15, allow_redirects=True)

        # Check redirect
        if resp.url != url:
            print(f"⚠️ Redirected to {resp.url}, skipping.")
            return False

        # Check for HTML
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
        else:
            print(f"❌ Failed with status {resp.status_code}")
    except Exception as e:
        print(f"❌ Exception: {e}")
    return False

def download_playwright_fallback(url: str, domain: str, output_dir: str, country_code: str = "US") -> bool:
    async def inner():
        HEADERS = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
        }

        proxy_list = get_proxy_by_country(country_code) + get_backup_proxies(country_code)
        random.shuffle(proxy_list)
        max_retries = min(3, len(proxy_list))
        tried_proxies = 0

        async with async_playwright() as p:
            for proxy in proxy_list:
                if tried_proxies >= max_retries:
                    print("🔁 Max retries reached.")
                    break

                print(f"🌍 Trying proxy {proxy['server']} ({proxy['country']})")

                try:
                    browser = await p.chromium.launch(headless=True)
                    context = await browser.new_context(
                        user_agent=HEADERS["User-Agent"],
                        proxy={
                            "server": proxy["server"],
                            "username": proxy["username"],
                            "password": proxy["password"]
                        }
                    )
                    await context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => false});")
                    page = await context.new_page()

                    response = await page.goto(url, timeout=20000, wait_until="load")
                    final_url = page.url
                    content_type = response.headers.get("content-type", "")

                    print("🔍 Status:", response.status)
                    print("🔍 Content-Type:", content_type)

                    ext = os.path.splitext(urlparse(url).path)[-1].lower()
                    image_like = ext in [".png", ".jpg", ".jpeg", ".svg", ".gif", ".webp", ".bmp"]

                    if final_url != url:
                        print(f"⚠️ Redirected to {final_url}, skipping.")
                        tried_proxies += 1
                        await browser.close()
                        await asyncio.sleep(3)
                        continue

                    body = await response.body()

                    if b"<html" in body.lower() or b"<!doctype" in body.lower():
                        print("⚠️ Response is HTML, not image.")
                        tried_proxies += 1
                        await browser.close()
                        await asyncio.sleep(3)
                        continue

                    if response.status == 200 and (content_type.startswith("image/") or image_like):
                        ext = mimetypes.guess_extension(content_type.split(";")[0]) or ext or ".img"
                        file_path = os.path.join(output_dir, f"{domain}{ext}")
                        os.makedirs(output_dir, exist_ok=True)
                        with open(file_path, "wb") as f:
                            f.write(body)
                        print(f"✅ Saved with Playwright: {file_path}")
                        await browser.close()
                        return True

                    print("❌ Not an image.")
                    tried_proxies += 1
                    await browser.close()
                    await asyncio.sleep(3)

                except Exception as e:
                    print(f"❌ Proxy {proxy['server']} failed: {e}")
                    tried_proxies += 1
                    await asyncio.sleep(3)

        print("🚫 All proxies failed.")
        return False

    return asyncio.run(inner())

# Example usage
if __name__ == "__main__":
    domain = "aamco-bellevue.com"
    url = "www.aamco-bellevue.com/wp-content/uploads/2018/09/logo.png"
    country_code = get_country_from_domain(domain)

    download_playwright_fallback(url, domain, "logos", country_code)