import os
import asyncio
from crawl4ai import AsyncWebCrawler, CrawlerRunConfig, CacheMode

# ✅ Step 1: Input URLs to crawl
with open("domains.txt", "r", encoding="utf-8") as f:
    urls = [line.strip() for line in f if line.strip()]

# ✅ Step 2: Utility to clean filename
def sanitize_filename(url):
    return url.replace("https://", "").replace("http://", "").replace("/", "_")

# ✅ Step 3: Load already scraped domains into a set
def load_scraped_domains():
    scraped_domains = set()
    if os.path.exists("scraped_domains_html"):
        for file in os.listdir("scraped_domains_html"):
            if file.endswith(".html"):
                domain = file.replace(".html", "").replace("www.", "")
                scraped_domains.add(domain)
    return scraped_domains

# ✅ Step 4: Create URL variants (4 possibilities)
def generate_url_variants(domain):
    return [
        f"https://{domain}",
        f"http://{domain}",
        f"https://www.{domain}",
        f"http://www.{domain}",
    ]

# ✅ Step 5: Crawl one URL, return HTML (try variants until one works)
async def crawl_url(url, crawler, scraped_domains):
    domain = sanitize_filename(url)

    # Check if this domain has already been scraped
    if domain in scraped_domains:
        print(f"⚡ Skipping {url} — already scraped!")
        return None

    variants = generate_url_variants(url)
    for variant in variants:
        try:
            print(f"🌐 Crawling: {variant}")
            result = await crawler.arun(
                url=variant,
                config=CrawlerRunConfig(
                    cache_mode=CacheMode.BYPASS,
                    session_id="html_batch_session"
                )
            )

            html = result.html
            if not html.strip():
                print(f"⚠️ No HTML returned for {variant}")
                continue  # Skip to the next variant if no HTML returned

            # Save HTML to file
            filename = sanitize_filename(variant) + ".html"
            path = f"scraped_domains_html/{filename}"
            os.makedirs(os.path.dirname(path), exist_ok=True)

            with open(path, "w", encoding="utf-8") as f:
                f.write(html)
            print(f"✅ Saved: {path}")

            return path  # Return the path once successful
        except Exception as e:
            print(f"❌ Error scraping {variant}: {e}")
            continue  # Try the next variant if error occurs
    return None  # If no variant works

# ✅ Step 6: Run it all
async def run_all():
    scraped_domains = load_scraped_domains()  # Load the existing scraped domains
    async with AsyncWebCrawler() as crawler:
        for url in urls:
            html_path = await crawl_url(url, crawler, scraped_domains)
            if html_path:
                print(f"✅ Scraped {url} and saved HTML to {html_path}")
            else:
                print(f"🔍 No valid results for {url}")

# ✅ Step 7: Run the async main
asyncio.run(run_all())
