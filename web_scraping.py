import os
import json
from logo_extractor import extract_logo_url_from_html
from dotenv import load_dotenv
import requests
from io import BytesIO
from PIL import Image
import time

load_dotenv()
LOGODEV_API_KEY = os.getenv("LOGODEV_API_KEY")

def run_scraper():
  os.system('python scraper_crawl.py')

def extract_logo_paths_from_html(folder_path, domains):
    # Normalize domain list
    domains = set(d.strip().lower() for d in domains)

    # Rename www-prefixed files
    for filename in os.listdir(folder_path):
        if filename.startswith('www.'):
            new_name = filename.replace('www.', '', 1)
            old_path = os.path.join(folder_path, filename)
            new_path = os.path.join(folder_path, new_name)
            os.rename(old_path, new_path)
            print(f'Renamed: {filename} -> {new_name}')

    logos = extract_logo_url_from_html(folder_path, domains)

    # Normalize and filter logos
    filtered_logos = []
    for entry in logos:
        logo = entry['logo_url'].replace("https://", "").replace("http://", "")
        if logo != 'NO_LOGO_FOUND' and entry['domain'] in domains:
            entry['logo_url'] = logo
            filtered_logos.append(entry)

    with open("logos_image_paths.json", "w") as f:
        json.dump(filtered_logos, f)


def download_logos_from_logo_paths():
  os.system('python flaresolverr_logo_download.py')

def get_failed_domains(domains):
   downloaded_domains = [os.path.splitext(f)[0] for f in os.listdir('logos') if os.path.isfile(os.path.join('logos', f))]
   failed_domains = [domain for domain in domains if domain not in downloaded_domains]
   return failed_domains


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

def fetch_logos_for_domains(domains, use_logodev=True, use_clearbit=True):
    results = []
    pending_logos = []

    # Initial lookup
    for domain in domains:
        print(f"🔍 Looking for logo for: {domain}")
        logo_url = None

        # Try Logo.dev
        if use_logodev:
            logo_url_dev, status = get_logo_logodev(domain)
            if logo_url_dev:
                logo_url = logo_url_dev
            elif status == 202:
                print(f"⏳ Logo.dev is processing {domain}")
                pending_logos.append(domain)

        # Try Clearbit if no logo yet
        if not logo_url and use_clearbit:
            logo_url_clearbit, status = get_logo_clearbit(domain)
            if logo_url_clearbit:
                logo_url = logo_url_clearbit

        results.append({
            "domain": domain,
            "logo_url": logo_url  # might still be None here
        })

    # Retry pending domains from Logo.dev
    if pending_logos:
        print(f"\n🔁 Waiting to recheck {len(pending_logos)} pending logos from Logo.dev...")
        time.sleep(240)  # wait 4 minutes
        for domain in pending_logos:
            logo_url, status = get_logo_logodev(domain)
            if logo_url:
                print(f"✅ Logo now available for {domain}")
                # Update the entry in results
                for entry in results:
                    if entry["domain"] == domain and not entry["logo_url"]:
                        entry["logo_url"] = logo_url

    # Final fallback: set "LOGO_NOT_FOUND" if nothing was found
    for entry in results:
        if not entry["logo_url"]:
            entry["logo_url"] = 'NO_LOGO_FOUND'

    return results

def download_logos(logo_data, save_dir='logos'):

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


def get_logos(domains):
    with open("domains.txt", "w") as f:
        for domain in domains:
            f.write(domain + "\n")

    ## Scrape domains using crawl4ai
    run_scraper()

    ## Extract logo paths from html
    extract_logo_paths_from_html('scraped_domains_html', domains)

    ## Download logos 
    download_logos_from_logo_paths()

    ## Get failed domains
    failed_domains = get_failed_domains(domains)

    ## Fallback to Logo.dev and Clearbit for failed domains
    failed_domains = fetch_logos_for_domains(failed_domains)
 
    download_logos(failed_domains)

