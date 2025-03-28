import os
import re
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
import tldextract

BOOST_KEYWORDS = ["logo"]
PENALTY_KEYWORDS = ["icon", "favicon", "payment", "visa", "mastercard", "amex", "badge", "banner", "ads", "social", "heritage"]
EXT_PRIORITY = ['.svg', '.png', '.jpg', '.jpeg', '.ico']

def extract_brand_name(domain_name):
    extracted = tldextract.extract(domain_name)
    return extracted.domain.lower()

def normalize_url(base_url, relative_url):
    if relative_url.startswith("//"):
        return "https:" + relative_url
    if relative_url.startswith("http://") or relative_url.startswith("https://"):
        return relative_url
    return urljoin(base_url, relative_url)

def get_extension_score(url):
    url = url.lower()
    for i, ext in enumerate(EXT_PRIORITY):
        if url.endswith(ext):
            return i
    return len(EXT_PRIORITY) + 1

def is_in_preferred_section(tag):
    for parent in tag.parents:
        if parent.name in ['header', 'nav']:
            return True
    return False

def is_in_logo_wrapper(tag):
    for parent in tag.parents:
        if not parent or not getattr(parent, "attrs", None):
            continue
        classes = parent.get("class", [])
        id_attr = parent.get("id", "")
        combined = " ".join(classes + [id_attr]).lower()
        if "logo" in combined or "brand" in combined:
            return True
    return False

def extract_background_image(tag, base_url):
    style = tag.get("style", "")
    match = re.search(r'background-image:\s*url\(["\']?(.*?)["\']?\)', style)
    if match:
        return normalize_url(base_url, match.group(1))
    return None

def candidate_score(tag, base_url, brand_name):
    score = 100
    candidate_url = None

    src = (
        tag.get("src") or
        tag.get("data-src") or
        tag.get("data-srcset") or
        tag.get("srcset")
    )

    if not src:
        src = tag.get("href") or tag.get("content")
    if not src:
        candidate_url = extract_background_image(tag, base_url)
        if not candidate_url:
            return None, score
    else:
        candidate_url = normalize_url(base_url, src)

    lower_url = candidate_url.lower()
    attr_text = " ".join([str(tag.get(attr, "")) for attr in ["src", "alt", "title", "class", "id"]]).lower()

    for word in BOOST_KEYWORDS:
        if word in attr_text or word in lower_url:
            score -= 30
    for word in PENALTY_KEYWORDS:
        if word in attr_text or word in lower_url:
            score += 30
    if is_in_preferred_section(tag):
        score -= 20
    if is_in_logo_wrapper(tag):  # ✅ new logic
        score -= 40
    if brand_name in lower_url:
        score -= 10

    score += get_extension_score(candidate_url)

    return candidate_url, score

def has_inline_logo_svg(soup, brand_name):
    svg_tags = soup.find_all("svg")
    for svg in svg_tags:
        class_attr = " ".join(svg.get("class", [])).lower()
        title = svg.find("title")
        title_text = title.get_text().lower() if title else ""

        if "logo" in class_attr or brand_name in title_text:
            return True

        for parent in svg.parents:
            if not parent or not getattr(parent, "attrs", None):
                continue
            class_id = " ".join(parent.get("class", []) + [parent.get("id", "")]).lower()
            if "logo" in class_id or "brand" in class_id:
                return True

    return False

def find_logos_in_html(html, base_url):
    soup = BeautifulSoup(html, "html.parser")
    brand_name = extract_brand_name(urlparse(base_url).netloc)

    if has_inline_logo_svg(soup, brand_name):
        return []

    candidates = []

    img_and_source_tags = soup.find_all(["img", "source"])
    icons = soup.find_all("link", rel=lambda x: x and "icon" in x.lower())
    og_images = soup.find_all("meta", property="og:image")
    divs_with_bg = soup.find_all("div", style=lambda x: x and "background-image" in x.lower())

    all_candidates = img_and_source_tags + icons + og_images + divs_with_bg

    for tag in all_candidates:
        candidate_url, score = candidate_score(tag, base_url, brand_name)
        if candidate_url:
            candidates.append((candidate_url, score))

    best = {}
    for url, score in candidates:
        if url not in best or score < best[url]:
            best[url] = score

    sorted_candidates = sorted(best.items(), key=lambda x: x[1])
    return [url for url, score in sorted_candidates]

def is_valid_logo(logo_url, domain_name):
    test_url = logo_url.strip().lower()
    brand_name = extract_brand_name(domain_name)
    file_name = os.path.basename(urlparse(test_url).path)

    if "logo" in test_url or brand_name in file_name:
        return logo_url
    else:
        return "NO_LOGO_FOUND"

def extract_logo_url_from_html(folder_path):
    logo_data = []
    for file in os.listdir(folder_path):
        if file.endswith(".html"):
            domain = file.replace(".html", "")
            path = os.path.join(folder_path, file)

            with open(path, "r", encoding="utf-8") as f:
                html = f.read()
                candidates = find_logos_in_html(html, f"https://{domain}")
                if candidates:
                    logo_url = candidates[0]
                    logo_url = is_valid_logo(logo_url, domain)
                    logo_data.append({"domain": domain, "logo_url": logo_url})
                else:
                    logo_data.append({"domain": domain, "logo_url": "NO_LOGO_FOUND"})
    return logo_data
