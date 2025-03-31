import os
import asyncio
from crawl4ai import AsyncWebCrawler, CrawlerRunConfig, CacheMode
import random
from urllib.parse import urlparse

# ✅ Input URLs
with open("domains.txt", "r", encoding="utf-8") as f:
    urls = [line.strip() for line in f if line.strip()]

# ✅ Clean filename
def sanitize_filename(url):
    return url.replace("https://", "").replace("http://", "").replace("/", "_")

# ✅ Load already scraped domains
def load_scraped_domains():
    scraped = set()
    if os.path.exists("scraped_domains_html"):
        for file in os.listdir("scraped_domains_html"):
            if file.endswith(".html"):
                domain = file.replace(".html", "").replace("www.", "")
                scraped.add(domain)
    return scraped

# ✅ Generate variants
def generate_url_variants(domain):
    return [
        f"https://{domain}",
        f"http://{domain}",
        f"https://www.{domain}",
        f"http://www.{domain}",
    ]

# ✅ Crawl one domain
async def crawl_url_variants(domain, crawler, scraped_domains, sem):
    sanitized = sanitize_filename(domain)
    if sanitized in scraped_domains:
        print(f"⚡ Skipping {domain} — already scraped!")
        return True

    variants = generate_url_variants(domain)

    async with sem:
        for variant in variants:
            try:
                print(f"🌐 Crawling: {variant}")
                result = await crawler.arun(
                    url=variant,
                    config=CrawlerRunConfig(
                        cache_mode=CacheMode.BYPASS,
                        session_id="html_batch_session",
                        wait_until="load",
                        page_timeout=15000
                    )
                )
                html = result.html
                if not html.strip():
                    print(f"⚠️ No HTML returned for {variant}")
                    await asyncio.sleep(random.uniform(1, 2))
                    continue

                base_domain = urlparse(variant).netloc.replace("www.", "")
                filename = sanitize_filename(base_domain) + ".html"

                path = os.path.join("scraped_domains_html", filename)
                os.makedirs("scraped_domains_html", exist_ok=True)

                with open(path, "w", encoding="utf-8") as f:
                    f.write(html)
                print(f"✅ Saved: {path}")

                await asyncio.sleep(random.uniform(0.5, 1.5))
                return True

            except Exception as e:
                print(f"❌ Error scraping {variant}: {e}")
                await asyncio.sleep(random.uniform(2, 4))
                continue

    print(f"🔍 No valid result for {domain}")
    return False

# ✅ Run all crawls in parallel
async def run_all():
    scraped = load_scraped_domains()
    sem = asyncio.Semaphore(5)  # Max 10 concurrent crawls

    failed_domains = []

    async with AsyncWebCrawler() as crawler:
        print("🚀 Running initial crawl...")
        tasks = [crawl_url_variants(url, crawler, scraped, sem) for url in urls]
        results = await asyncio.gather(*tasks)

        for url, success in zip(urls, results):
            if not success:
                failed_domains.append(url)

        # Retry pass
        if failed_domains:
            print(f"\n🔁 Retrying {len(failed_domains)} failed domains...\n")
            retry_tasks = [crawl_url_variants(domain, crawler, scraped, sem) for domain in failed_domains]
            await asyncio.gather(*retry_tasks)

# ✅ Go!
asyncio.run(run_all())
