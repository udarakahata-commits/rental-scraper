"""
ikman_scraper.py
Scrapes house-for-rent listings from ikman.lk and returns them as a list of
dictionaries. Designed to be imported by main.py, but you can also run it
directly to see raw results printed to the screen.
"""

import re
import time
import requests
from bs4 import BeautifulSoup

BASE_URL = "https://ikman.lk/en/ads/sri-lanka/house-rentals"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
    )
}


def fetch_page(page_num: int) -> str:
    url = f"{BASE_URL}?page={page_num}"
    response = requests.get(url, headers=HEADERS, timeout=15)
    response.raise_for_status()
    return response.text


def parse_listings(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    ad_cards = soup.find_all("a", class_="gtm-ad-item")

    listings = []
    for ad in ad_cards:
        try:
            title_tag = ad.find("h2")
            title = title_tag.get_text(strip=True) if title_tag else "Untitled"

            link = ad.get("href", "")
            if link and not link.startswith("http"):
                link = "https://ikman.lk" + link

            full_text = ad.get_text(" ", strip=True)

            beds_match = re.search(r"Beds:\s*(\d+)", full_text)
            baths_match = re.search(r"Baths:\s*(\d+)", full_text)
            beds = int(beds_match.group(1)) if beds_match else None
            baths = int(baths_match.group(1)) if baths_match else None

            price_match = re.search(r"Rs\s*([\d,]+)\s*/month", full_text)
            price = int(price_match.group(1).replace(",", "")) if price_match else None

            if price is not None and price < 5000:
                price = None

            desc_div = ad.find("div", class_=re.compile(r"^description"))
            location = desc_div.get_text(strip=True).split(",")[0] if desc_div else ""

            listings.append({
                "title": title,
                "location": location,
                "price": price,
                "beds": beds,
                "baths": baths,
                "url": link,
                "source": "ikman.lk",
            })
        except Exception as e:
            print(f"Skipped one ad due to error: {e}")
            continue

    return listings


def scrape_ikman(num_pages: int = 3) -> list[dict]:
    all_listings = []
    for page in range(1, num_pages + 1):
        print(f"[ikman.lk] Fetching page {page}...")
        html = fetch_page(page)
        page_listings = parse_listings(html)
        print(f"[ikman.lk] Found {len(page_listings)} listings on page {page}")
        all_listings.extend(page_listings)
        time.sleep(1)
    return all_listings


if __name__ == "__main__":
    results = scrape_ikman(num_pages=1)
    print(f"\nTotal listings scraped: {len(results)}\n")
    for r in results[:5]:
        print(r)
