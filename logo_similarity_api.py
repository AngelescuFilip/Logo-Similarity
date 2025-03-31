from fastapi import FastAPI
from fastapi import BackgroundTasks
from pydantic import BaseModel
from typing import List
import os
from dotenv import load_dotenv
import torch
from transformers import AutoProcessor, AutoModel

from clustering import clustering
from web_scraping import get_logos


load_dotenv()
LOGODEV_API_KEY = os.getenv("LOGODEV_API_KEY")

app = FastAPI()

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
processor = AutoProcessor.from_pretrained("facebook/dinov2-base")
model = AutoModel.from_pretrained("facebook/dinov2-base").eval().to(device)

# Lock processor to 224x224 resolution, disable cropping
processor.size = {"height": 224, "width": 224}
processor.do_center_crop = False


class DomainList(BaseModel):
    domains: List[str]


@app.post("/extract-logos")
def process_logos(data: DomainList):
    domains = data.domains
    with open("domains.txt", "w") as f:
        for domain in domains:
            f.write(domain + "\n")

    ## Download Logos
    get_logos(domains)

    if not os.listdir("logos"):
        return {"error": "No logos downloaded. Clustering aborted."}

    ## Cluster Logos
    clusters = clustering(device, processor, model, domains)

    return clusters


@app.post("/run-scraper")
def run_scraper_endpoint(data: DomainList, background_tasks: BackgroundTasks):
    # Save domains to file
    with open("domains.txt", "w", encoding="utf-8") as f:
        for domain in data.domains:
            f.write(domain + "\n")

    # Trigger the scraper in background
    def run_scraper():
        os.system("python scraper_crawl.py")

    background_tasks.add_task(run_scraper)

    return "Scraping is over!!"
