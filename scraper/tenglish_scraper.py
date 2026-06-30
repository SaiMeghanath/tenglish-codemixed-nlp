"""
tenglish_scraper.py
====================
Scrapes Telugu-English (Tenglish) tweets from Telugu news accounts on Twitter/X
using Selenium (no API key required).

Usage:
    python tenglish_scraper.py

Output:
    raw_tweets.csv  —  tweet_id, username, text, date, likes, retweets, replies

Requirements:
    pip install selenium webdriver-manager pandas

Notes:
    - You must have Chrome installed on your machine.
    - Twitter may show a login wall after ~20 tweets without an account.
      If it does, set USE_LOGIN = True and fill in your credentials below.
    - Run this on the Lenovo LOQ for speed; works on any machine otherwise.
"""

import time
import csv
import re
import os
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from webdriver_manager.chrome import ChromeDriverManager
import pandas as pd

# ─────────────────────────────────────────────
# CONFIGURATION — edit these before running
# ─────────────────────────────────────────────

# Telugu news accounts to scrape (verified active accounts)
TARGET_ACCOUNTS = [
    "AndhraJyothy",
    "eenaduonline",
    "sakshitv",
    "TV9Telugu",
    "NTV_Telugu",
    "ZeeTelugu",
    "10TVNews",
    "ABNAndhraPrabha",
    "PrimeTime9",
    "ManaTelugu1",
]

# How many tweets to collect per account
TWEETS_PER_ACCOUNT = 300

# Total target (script stops early if reached)
TOTAL_TARGET = 5000

# Output file
OUTPUT_FILE = "raw_tweets.csv"

# Scroll pause — increase if on slow internet
SCROLL_PAUSE = 2.5

# Set to True and fill credentials if Twitter shows a login wall
USE_LOGIN = False
TWITTER_EMAIL = "your_email@example.com"
TWITTER_PASSWORD = "your_password"

# ─────────────────────────────────────────────
# TELUGU UNICODE RANGE — used to detect Tenglish
# ─────────────────────────────────────────────
TELUGU_UNICODE_RANGE = re.compile(r'[\u0C00-\u0C7F]')
ROMAN_TELUGU_PATTERN = re.compile(
    r'\b(meeru|nenu|mee|memu|anni|undi|ayindi|cheppandi|cheyandi|'
    r'antunnaru|chestunnaru|ledu|ikkade|akkade|ela|ento|emiti|'
    r'bagunna|padthundi|vastundi|poindi|okka|okate|oka)\b',
    re.IGNORECASE
)

def is_tenglish(text: str) -> bool:
    """
    Returns True if tweet contains Telugu script OR
    common Romanized Telugu (Tenglish) words.
    """
    has_telugu_script = bool(TELUGU_UNICODE_RANGE.search(text))
    has_roman_telugu = bool(ROMAN_TELUGU_PATTERN.search(text))
    return has_telugu_script or has_roman_telugu

# ─────────────────────────────────────────────
# DRIVER SETUP
# ─────────────────────────────────────────────

def get_driver():
    options = Options()
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    options.add_argument("--window-size=1280,900")
    # Comment out the line below if you want to see the browser window
    # options.add_argument("--headless=new")
    
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    driver.execute_script(
        "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
    )
    return driver


def login(driver):
    """Log into Twitter/X if USE_LOGIN is True."""
    print("[AUTH] Logging in...")
    driver.get("https://x.com/login")
    time.sleep(3)

    try:
        email_field = WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.NAME, "text"))
        )
        email_field.send_keys(TWITTER_EMAIL)
        driver.find_element(By.XPATH, "//span[text()='Next']").click()
        time.sleep(2)

        password_field = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.NAME, "password"))
        )
        password_field.send_keys(TWITTER_PASSWORD)
        driver.find_element(By.XPATH, "//span[text()='Log in']").click()
        time.sleep(4)
        print("[AUTH] Login successful.")
    except Exception as e:
        print(f"[AUTH] Login failed: {e}")


# ─────────────────────────────────────────────
# SCRAPER CORE
# ─────────────────────────────────────────────

def scrape_account(driver, username: str, max_tweets: int) -> list[dict]:
    """Scrape tweets from a single account page."""
    url = f"https://x.com/{username}"
    driver.get(url)
    time.sleep(3)

    collected = []
    seen_ids = set()
    last_height = driver.execute_script("return document.body.scrollHeight")
    stale_scrolls = 0

    print(f"[SCRAPE] @{username} — target: {max_tweets} tweets")

    while len(collected) < max_tweets and stale_scrolls < 6:
        # Find all tweet articles currently in DOM
        try:
            tweets = driver.find_elements(By.CSS_SELECTOR, 'article[data-testid="tweet"]')
        except Exception:
            tweets = []

        for tweet in tweets:
            if len(collected) >= max_tweets:
                break
            try:
                # Tweet text
                try:
                    text_el = tweet.find_element(By.CSS_SELECTOR, '[data-testid="tweetText"]')
                    text = text_el.text.strip()
                except NoSuchElementException:
                    continue

                if not text or len(text) < 10:
                    continue

                # Unique tweet ID via permalink
                try:
                    link_el = tweet.find_element(
                        By.CSS_SELECTOR, 'a[href*="/status/"]'
                    )
                    href = link_el.get_attribute("href")
                    tweet_id = href.split("/status/")[-1].split("?")[0]
                except NoSuchElementException:
                    tweet_id = str(hash(text))

                if tweet_id in seen_ids:
                    continue
                seen_ids.add(tweet_id)

                # Date
                try:
                    time_el = tweet.find_element(By.TAG_NAME, "time")
                    date_str = time_el.get_attribute("datetime")
                except NoSuchElementException:
                    date_str = ""

                # Engagement stats
                def get_stat(testid):
                    try:
                        el = tweet.find_element(
                            By.CSS_SELECTOR, f'[data-testid="{testid}"]'
                        )
                        return el.get_attribute("aria-label") or "0"
                    except NoSuchElementException:
                        return "0"

                likes    = get_stat("like")
                retweets = get_stat("retweet")
                replies  = get_stat("reply")

                row = {
                    "tweet_id":  tweet_id,
                    "username":  username,
                    "text":      text,
                    "date":      date_str,
                    "likes":     likes,
                    "retweets":  retweets,
                    "replies":   replies,
                    "is_tenglish": is_tenglish(text),
                    "scraped_at": datetime.utcnow().isoformat(),
                }
                collected.append(row)

            except Exception:
                continue

        # Scroll down
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(SCROLL_PAUSE)

        new_height = driver.execute_script("return document.body.scrollHeight")
        if new_height == last_height:
            stale_scrolls += 1
        else:
            stale_scrolls = 0
        last_height = new_height

    tenglish_count = sum(1 for r in collected if r["is_tenglish"])
    print(f"[SCRAPE] @{username} — collected {len(collected)} tweets "
          f"({tenglish_count} Tenglish)")
    return collected


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

def main():
    driver = get_driver()
    all_tweets = []

    try:
        if USE_LOGIN:
            login(driver)

        for account in TARGET_ACCOUNTS:
            if len(all_tweets) >= TOTAL_TARGET:
                print(f"[DONE] Reached total target of {TOTAL_TARGET} tweets.")
                break

            remaining = TOTAL_TARGET - len(all_tweets)
            per_account = min(TWEETS_PER_ACCOUNT, remaining)

            try:
                tweets = scrape_account(driver, account, per_account)
                all_tweets.extend(tweets)
                print(f"[TOTAL] {len(all_tweets)} / {TOTAL_TARGET} so far\n")
                time.sleep(2)  # polite pause between accounts
            except Exception as e:
                print(f"[ERROR] Failed on @{account}: {e}")
                continue

    finally:
        driver.quit()

    if not all_tweets:
        print("[WARN] No tweets collected. Check if Twitter showed a login wall.")
        return

    # Save
    df = pd.DataFrame(all_tweets)
    df.to_csv(OUTPUT_FILE, index=False, encoding="utf-8-sig")

    # Stats
    total      = len(df)
    tenglish   = df["is_tenglish"].sum()
    accounts   = df["username"].value_counts().to_dict()

    print("\n" + "="*50)
    print(f"  Saved to      : {OUTPUT_FILE}")
    print(f"  Total tweets  : {total}")
    print(f"  Tenglish hits : {tenglish} ({100*tenglish/total:.1f}%)")
    print(f"  Per account   :")
    for acc, count in accounts.items():
        print(f"    @{acc:<22} {count}")
    print("="*50)


if __name__ == "__main__":
    main()
