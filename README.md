Hey there! 👋

Welcome to this project focused on **logo scraping, similarity clustering, and analysis**. This repo is meant to serve as both a useful tool and a solid foundation for further development in logo-related scraping and ML tasks. Below is a quick guide and overview of what’s going on here, what we learned along the way, and how you can get started.

---

## Getting Started

💡 **Start with `logo_similarity.ipynb`**  
That notebook walks you through the entire process step-by-step — it’s the best place to begin. Once you're familiar, you can check out:
- `clusters.csv` – the final clustering results
- `logos/` – all downloaded logos

---

## The Journey

Originally, we thought favicons and logos were the same. Spoiler: they’re not.  
We went through several tools — Logo.dev, Clearbit, stealth playwright — but none alone could get the job done reliably.

Eventually, we landed on a combo of:
- **crawl4ai** – to fetch raw HTML
- **flaresolverr + async playwright with proxies** – to download logos
- **Logo.dev & Clearbit** – as fallback options

---

## Key Features
You can explore the API in action via the test_api.ipynb notebook. The API exposes two endpoints:
- /run-scraper — for logo scraping only
- /extract-logos — for scraping + logo clustering


### ⚡ Efficiency
- Smart **caching** (via JSON file) to reduce API calls
- **async scraping and downloading** to maximize speed
- JSON was used for simplicity during rapid iteration, but the system is adaptable to SQLite/MySQL if scaling up
- Concurrent scraping and logo downloading have been implemented for significantly faster runtime and better performance.

### 🎯 Accuracy
- Many websites require testing multiple domain formats: `http`, `https`, `www.`, etc.
- A **scoring system** is used to choose the most probable logo from all image candidates
- Handled many common issues like:
  - Inline SVGs
  - Fake HTML/text responses
  - Latency
  - Ambiguous logo choices
However, **false positives still happen**.  
To improve further, consider using AI tools (OpenAI, Gemini, Claude, etc.) for smarter HTML parsing and content filtering.

### 🌍 Why You Can’t Rely on Just One Logo Source
- Services like logo.dev and Clearbit can return different logos for the same brand, depending on the regional domain — for example, vans.com, vans.fr, and vans.ro might each give a different logo.
- That’s why using only these APIs isn't enough — they have limited and inconsistent datasets.
- Our scraping method aims to directly extract the actual logo from the company’s site to improve accuracy and consistency.

### 🌍 Proxies and targeted servers
- We use **rotating proxies** with configurable country targeting
- The algorithm attempts to **match the website’s country** to the proxy’s region
- If no match is found, it defaults to using a US-based proxy
- The more country diversity you add to your proxy list, the better the scraping success rate

---

## 🔒 API Limitations & Logo Source Issues

- **Logo.dev**  
  - Excellent resolution and hit rate  
  - Limited to **5,000 requests/day** (free tier)  
- **Clearbit**  
  - No request cap, but **database is outdated**  
  - Will be **shut down at the end of 2025**

## 🚀 Deployment

We used **FastAPI** to build an API layer.  
A sample `.service` file is included to help you auto-restart on crash when deploying to a Linux server.
Update file paths as needed and run it using systemctl

---

## 🔧 Setup

1. Create a `.env` file with:
LOGODEV_API_KEY="your_api_key_here"

css
Copy
Edit

2. Create a JSON proxy config like this:
```json
[
  {
    "server": "http://255.00.00.00:8000",
    "username": "user",
    "password": "pass",
    "country": "US"
  },
  ...
]
(Windows only) Install GTK3 Runtime


## 📊 Results
- Logos successfully downloaded: 3400 / 3416 => 99.53% accuracy 
- False positives are possible (some websites intentionally block scraping or serve decoy content)
- Our model treats any unique logo as its own entity, so false positives generally won’t corrupt cluster logic


## 🛠️ Known Limitations
- Proxies are essential — scraping without them was only ~10% effective
We tried stealth plugins, spoofed headers, and various tricks, but scraping HTML without a proxy just didn’t scale
- crawl4ai is an excellent free choice for HTML scraping but can’t download media files
- We ended up using a one-week trial from proxyscrape to hit our scraping targets, with logo.dev and clearbit as final fallbacks (we used playwright with proxies for downloading the logos after retrieving the logo url using crawl4ai)


## 📌 For the Hiring Team

This project was built in just **one week** — that was the timeframe we had, and I wanted to push as much as I could into it.  
While it's already showing strong results in terms of accuracy, speed, and scraping success, there’s still plenty of room to grow.

At its core, this is a **skeleton framework** — a solid base with working logic and a proven pipeline, ready to be scaled and refined further.  
With the right resources, more development time, and technical guidance, this project could evolve into a robust system with production-level performance.
The code is modular and adaptable, leaving a clear path for future improvements in latency, accuracy, and resilience.

Thanks again for taking the time to review this project — it’s been a challenging and exciting technical deep dive, and I hope it gives you a good sense of how I think, build, and iterate under pressure.




