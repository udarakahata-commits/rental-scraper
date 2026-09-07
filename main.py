"""
main.py
The full daily pipeline:
  1. Scrape ikman.lk house rentals (using ikman_scraper.py)
  2. Filter down to your criteria
  3. Compare against listings we've already seen (seen_urls.json)
  4. Save only the genuinely NEW matches to matches.csv
  5. Send a Telegram alert with the new matches (or a "no new listings" message)
  6. Update seen_urls.json so tomorrow's run doesn't repeat today's results
"""

import csv
import json
import os
import requests
from datetime import datetime

from ikman_scraper import scrape_ikman

# --- Your search criteria ---
MAX_PRICE = 40000
MAX_BEDS = 2
MAX_BATHS = 1
TARGET_LOCATIONS = ["colombo"]  # matched against ikman's district field, lowercase

SEEN_URLS_FILE = "seen_urls.json"
MATCHES_FILE = "matches.csv"
NUM_PAGES_TO_SCRAPE = 5  # ikman shows ~25 listings/page; 5 pages = most recent ~125

# --- Telegram settings (read from environment variables, never hardcoded) ---
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")


def send_telegram_message(text: str) -> None:
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("[telegram] Skipped: TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not set")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "disable_web_page_preview": True,
    }
    response = requests.post(url, json=payload, timeout=15)
    if response.status_code == 200:
        print("[telegram] Message sent successfully")
    else:
        print(f"[telegram] Failed to send message: {response.status_code} {response.text}")


def build_telegram_message(new_matches: list[dict]) -> str:
    lines = [f"🏠 {len(new_matches)} new house(s) matching your criteria:\n"]
    for listing in new_matches:
        lines.append(
            f"• {listing['title']}\n"
            f"  Rs {listing['price']:,} | {listing['beds']}bd/{listing['baths']}ba | {listing['location']}\n"
            f"  {listing['url']}\n"
        )
    return "\n".join(lines)


def load_seen_urls() -> set:
    if not os.path.exists(SEEN_URLS_FILE):
        return set()
    with open(SEEN_URLS_FILE, "r", encoding="utf-8") as f:
        return set(json.load(f))


def save_seen_urls(urls: set) -> None:
    with open(SEEN_URLS_FILE, "w", encoding="utf-8") as f:
        json.dump(sorted(urls), f, indent=2)


def matches_criteria(listing: dict) -> bool:
    if listing["price"] is None or listing["price"] > MAX_PRICE:
        return False
    if listing["beds"] is None or listing["beds"] > MAX_BEDS:
        return False
    if listing["baths"] is None or listing["baths"] > MAX_BATHS:
        return False
    location_lower = (listing["location"] or "").lower()
    if not any(target in location_lower for target in TARGET_LOCATIONS):
        return False
    return True


def run_pipeline():
    print(f"=== Rental scraper run started: {datetime.now().isoformat(timespec='seconds')} ===\n")

    all_listings = scrape_ikman(num_pages=NUM_PAGES_TO_SCRAPE)
    print(f"\nScraped {len(all_listings)} total listings from ikman.lk")

    matching = [l for l in all_listings if matches_criteria(l)]
    print(f"{len(matching)} listings match your criteria "
          f"(<= Rs {MAX_PRICE}, <= {MAX_BEDS} beds, <= {MAX_BATHS} baths, {TARGET_LOCATIONS})")

    seen_urls = load_seen_urls()
    new_matches = [l for l in matching if l["url"] not in seen_urls]
    print(f"{len(new_matches)} of those are NEW (not seen in a previous run)")

    if new_matches:
        scraped_at = datetime.now().isoformat(timespec="seconds")
        fieldnames = ["title", "location", "price", "beds", "baths", "url", "source", "scraped_at"]

        file_exists = os.path.exists(MATCHES_FILE)
        with open(MATCHES_FILE, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            if not file_exists:
                writer.writeheader()
            for listing in new_matches:
                row = {**listing, "scraped_at": scraped_at}
                writer.writerow(row)

        print(f"\nSaved {len(new_matches)} new matches to {MATCHES_FILE}")
        send_telegram_message(build_telegram_message(new_matches))
    else:
        print("\nNo new matches this run — matches.csv unchanged.")
        send_telegram_message("Hey, there are no new rental listings today.")

    all_matching_urls = {l["url"] for l in matching}
    save_seen_urls(seen_urls | all_matching_urls)

    print(f"\n=== Run finished: {datetime.now().isoformat(timespec='seconds')} ===")


if __name__ == "__main__":
    run_pipeline()
