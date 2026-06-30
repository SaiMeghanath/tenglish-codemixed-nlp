"""
tenglish_youtube_scraper.py
============================
Collects Telugu-English (Tenglish) code-mixed comments from Telugu news
channel videos on YouTube using the YouTube Data API v3.

Dataset structure collected:
    channel → video → top-level comment → replies

Output files:
    raw_comments.csv     — all collected comments with metadata
    dataset_card.txt     — reproducibility log for publication

Usage:
    python tenglish_youtube_scraper.py

Requirements:
    pip install google-api-python-client pandas

Quota note:
    YouTube Data API v3 free quota = 10,000 units/day.
    This script uses ~3 units per comment page (100 comments).
    At 5000 comments target → ~150 units. Well within free tier.

Author: Aladurthi Sai Meghanath (AA.SC.P2MCA24074053)
Project: Explainable Transformer-Based Analysis of Telugu-English
         Code-Mixed News Comments
Supervisor: Dr. Thushara M.G., Amrita Vishwa Vidyapeetham
"""

import os
import csv
import time
import re
import json
from datetime import datetime, timezone
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import pandas as pd

# ─────────────────────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────────────────────

API_KEY = "YOUR_YOUTUBE_API_KEY"   # ← paste your key here

# Telugu news channels: (channel_name, channel_id)
TARGET_CHANNELS = [
    ("TV9 Telugu Digital", "UCg6JyAGrskayg14qJP3598g"),
    ("TV9 Telugu Live",    "UCPXTXMecYqnRKNdqdVOGSFg"),
    ("NTV Telugu",         "UCumtYpCY26F6Jr3satUgMvA"),
    ("Sakshi TV",          "UCZ9m4KOh8Ei60428xeGYDCQ"),
    ("Sakshi TV Live",     "UCQ_FATLW83q-4xJ2fsi8qAw"),
    ("ABN Telugu",         "UC_2irx_BQR7RsBKmUV9fePQ"),
    ("10TV News Telugu",   "UCfymZbh17_3T_UhgjkQ9fRQ"),
    ("T News Telugu",      "UCu6edg8_eu3-A8ylgaWereA"),
    ("NTV Live",           "UCtzYV2L-m8ew93mZb3qhf5w"),
]

# How many videos to pull per channel
VIDEOS_PER_CHANNEL = 50

# Max top-level comments per video
COMMENTS_PER_VIDEO = 200

# Include replies to top-level comments?
COLLECT_REPLIES = True

# Total comment target (script stops when reached)
TOTAL_TARGET = 5000

# Output
OUTPUT_CSV  = "raw_comments.csv"
DATASET_LOG = "dataset_card.txt"

# ─────────────────────────────────────────────────────────────
# TENGLISH DETECTION
# ─────────────────────────────────────────────────────────────
# Strategy: a comment is Tenglish if it contains Telugu Unicode script
# OR has a script-mixing ratio ≥ 0.05 (5% Telugu chars) OR matches
# an expanded Romanized Telugu vocabulary.
# This is conservative — better to over-include at collection stage
# and filter during annotation than miss real Tenglish.

TELUGU_SCRIPT = re.compile(r'[\u0C00-\u0C7F]')

# Expanded Romanized Telugu word list
# Covers common spellings and regional variations
ROMAN_TELUGU_WORDS = {
    # Pronouns / address
    "nenu", "meeru", "memu", "mee", "nee", "nenu", "meeru", "vallaki",
    "vadiki", "akka", "anna", "bro", "andi", "garu",
    # Common verbs
    "undi", "undhi", "ledu", "ledhu", "oka", "okka", "okate",
    "cheyandi", "cheppandi", "chustunnaru", "antunnaru", "chestunnaru",
    "vastundi", "vastundhi", "poindi", "poindhi", "padthundi",
    "ayindi", "ayindhi", "avutundi", "avutundhi", "ivvandi",
    "cheyaledu", "cheyaledhu", "telusu", "telusindi",
    # Adverbs / connectors
    "ikkade", "akkade", "enti", "emiti", "ela", "elanti", "enduku",
    "chala", "chaala", "chaalaa", "anni", "anni", "inkaa", "inka",
    "kuda", "kooda", "kaadu", "kadu", "kadhu", "ante", "ayite",
    "appudu", "ippudu", "epudu", "kani", "kaani",
    # Adjectives / reactions
    "bagundi", "bagundhi", "baagundi", "super", "worst", "correct",
    "incorrect", "nijam", "nijame", "abadham", "fake", "asalu",
    "meeru", "manchidi", "manchidi", "pedda", "chinna",
    # Nouns / common
    "news", "vishayam", "government", "sarkar", "raajyam",
    "janalu", "praja", "desam", "ooru", "uur",
    # Exclamations
    "ayyo", "arey", "arrey", "haha", "lol", "ra", "raa", "le",
    "em", "emo", "emoo", "avunu", "avunuu",
}

ROMAN_PATTERN = re.compile(
    r'\b(' + '|'.join(re.escape(w) for w in ROMAN_TELUGU_WORDS) + r')\b',
    re.IGNORECASE
)

def tenglish_score(text: str) -> dict:
    """
    Returns a dict with:
        has_telugu_script  : bool
        script_mix_ratio   : float  (Telugu chars / total chars)
        roman_telugu_hits  : int    (matched Romanized Telugu words)
        is_tenglish        : bool
    """
    total_chars = max(len(text.replace(" ", "")), 1)
    telugu_chars = len(TELUGU_SCRIPT.findall(text))
    mix_ratio = telugu_chars / total_chars

    roman_hits = len(ROMAN_PATTERN.findall(text))

    is_tenglish = (
        telugu_chars > 0 or
        mix_ratio >= 0.05 or
        roman_hits >= 1
    )

    return {
        "has_telugu_script": telugu_chars > 0,
        "script_mix_ratio":  round(mix_ratio, 4),
        "roman_telugu_hits": roman_hits,
        "is_tenglish":       is_tenglish,
    }


# ─────────────────────────────────────────────────────────────
# YOUTUBE API HELPERS
# ─────────────────────────────────────────────────────────────

def get_youtube_client(api_key: str):
    return build("youtube", "v3", developerKey=api_key)


def get_recent_videos(yt, channel_id: str, max_results: int) -> list[dict]:
    """Return recent video IDs and titles from a channel."""
    videos = []
    try:
        response = yt.search().list(
            part="id,snippet",
            channelId=channel_id,
            maxResults=max_results,
            order="date",
            type="video",
        ).execute()

        for item in response.get("items", []):
            videos.append({
                "video_id":    item["id"]["videoId"],
                "video_title": item["snippet"]["title"],
                "published_at": item["snippet"]["publishedAt"],
                "channel_name": item["snippet"]["channelTitle"],
            })
    except HttpError as e:
        print(f"  [ERROR] Videos fetch failed for {channel_id}: {e}")
    return videos


def get_comments(yt, video_id: str, max_comments: int,
                 collect_replies: bool) -> list[dict]:
    """
    Fetch top-level comments + optional replies for a video.
    Returns flat list of comment dicts.
    """
    comments = []
    next_page_token = None

    try:
        while len(comments) < max_comments:
            request = yt.commentThreads().list(
                part="snippet,replies",
                videoId=video_id,
                maxResults=min(100, max_comments - len(comments)),
                pageToken=next_page_token,
                textFormat="plainText",
                order="relevance",
            )
            response = request.execute()

            for item in response.get("items", []):
                top = item["snippet"]["topLevelComment"]["snippet"]
                top_id = item["snippet"]["topLevelComment"]["id"]

                comments.append({
                    "comment_id":   top_id,
                    "parent_id":    None,
                    "video_id":     video_id,
                    "text":         top["textDisplay"],
                    "author":       top["authorDisplayName"],
                    "like_count":   top["likeCount"],
                    "published_at": top["publishedAt"],
                    "reply_count":  item["snippet"]["totalReplyCount"],
                })

                # Collect replies if present
                if collect_replies and item["snippet"]["totalReplyCount"] > 0:
                    for reply in item.get("replies", {}).get("comments", []):
                        rs = reply["snippet"]
                        comments.append({
                            "comment_id":   reply["id"],
                            "parent_id":    top_id,
                            "video_id":     video_id,
                            "text":         rs["textDisplay"],
                            "author":       rs["authorDisplayName"],
                            "like_count":   rs["likeCount"],
                            "published_at": rs["publishedAt"],
                            "reply_count":  0,
                        })

            next_page_token = response.get("nextPageToken")
            if not next_page_token:
                break

            time.sleep(0.3)  # polite pause

    except HttpError as e:
        if "commentsDisabled" in str(e):
            print(f"  [SKIP] Comments disabled on video {video_id}")
        else:
            print(f"  [ERROR] Comments fetch failed for {video_id}: {e}")

    return comments


# ─────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────

def main():
    print("="*60)
    print("  Tenglish YouTube Comment Scraper")
    print("  Project: Thushara NLP Research — Amrita AHEAD")
    print("="*60)

    yt = get_youtube_client(API_KEY)
    all_comments = []
    collection_log = []   # for dataset card

    scrape_start = datetime.now(timezone.utc).isoformat()

    for channel_name, channel_id in TARGET_CHANNELS:
        if len(all_comments) >= TOTAL_TARGET:
            break

        print(f"\n[CHANNEL] {channel_name}")
        videos = get_recent_videos(yt, channel_id, VIDEOS_PER_CHANNEL)
        print(f"  Found {len(videos)} videos")
        if not videos:
            print(f"  [SKIP] No videos found — channel ID may be wrong for '{channel_name}'")
            print(f"         Verify at: https://www.youtube.com/@{channel_name.replace(' ','')}")
            continue

        for video in videos:
            if len(all_comments) >= TOTAL_TARGET:
                break

            vid_id    = video["video_id"]
            vid_title = video["video_title"]
            print(f"  → {vid_title[:60]}...")

            raw_comments = get_comments(
                yt, vid_id, COMMENTS_PER_VIDEO, COLLECT_REPLIES
            )

            # Enrich with video metadata + Tenglish score
            enriched = []
            for c in raw_comments:
                score = tenglish_score(c["text"])
                enriched.append({
                    **c,
                    "channel_name":      channel_name,
                    "channel_id":        channel_id,
                    "video_title":       vid_title,
                    "video_published_at": video["published_at"],
                    **score,
                })

            tenglish_count = sum(1 for c in enriched if c["is_tenglish"])
            print(f"     {len(enriched)} comments · "
                  f"{tenglish_count} Tenglish")

            all_comments.extend(enriched)
            collection_log.append({
                "channel":       channel_name,
                "video_id":      vid_id,
                "video_title":   vid_title[:80],
                "total_comments": len(enriched),
                "tenglish":      tenglish_count,
            })

            time.sleep(0.5)

        print(f"  [TOTAL SO FAR] {len(all_comments)}")

    # ── Save CSV ──────────────────────────────────────────────
    if not all_comments:
        print("\n[WARN] No comments collected.")
        print("  Possible reasons:")
        print("  1. Channel IDs may have changed — verify them at youtube.com/@ChannelName")
        print("  2. API quota exhausted for today")
        print("  3. Videos on these channels have comments disabled")
        print("  4. API key not enabled for YouTube Data API v3")
        return

    df = pd.DataFrame(all_comments)

    # Ensure Tenglish columns exist even if enrichment partially failed
    for col in ("is_tenglish", "has_telugu_script", "roman_telugu_hits", "script_mix_ratio"):
        if col not in df.columns:
            df[col] = False if "is" in col or "has" in col else 0

    df.to_csv(OUTPUT_CSV, index=False, encoding="utf-8-sig")

    # ── Stats ─────────────────────────────────────────────────
    total      = len(df)
    tenglish   = df["is_tenglish"].sum()
    has_script = df["has_telugu_script"].sum()
    roman_only = tenglish - has_script

    print("\n" + "="*60)
    print(f"  Saved            : {OUTPUT_CSV}")
    print(f"  Total comments   : {total}")
    print(f"  Tenglish         : {tenglish} ({100*tenglish/max(total,1):.1f}%)")
    print(f"    ↳ Telugu script : {has_script}")
    print(f"    ↳ Roman only    : {roman_only}")
    print("="*60)

    # ── Dataset card (publication reproducibility) ────────────
    scrape_end = datetime.now(timezone.utc).isoformat()

    card = f"""DATASET CARD
============
Title       : Telugu-English Code-Mixed News Comments Dataset
Task        : Toxicity Detection + Fake News Detection
Paper       : Explainable Transformer-Based Analysis of Telugu-English
              Code-Mixed News Comments
Author      : Aladurthi Sai Meghanath (AA.SC.P2MCA24074053)
Supervisor  : Dr. Thushara M.G., Amrita Vishwa Vidyapeetham (Amrita AHEAD)

Collection method   : YouTube Data API v3
Collection date     : {scrape_start[:10]} to {scrape_end[:10]}
API version         : youtube/v3
Comment order       : relevance (YouTube default)
Replies collected   : {COLLECT_REPLIES}

Sources
-------
"""
    for entry in collection_log:
        card += (f"  {entry['channel']:<25} video:{entry['video_id']}  "
                 f"comments:{entry['total_comments']}  "
                 f"tenglish:{entry['tenglish']}\n")

    card += f"""
Statistics
----------
Total comments   : {total}
Tenglish hits    : {int(tenglish)} ({100*tenglish/max(total,1):.1f}%)
  Telugu script  : {int(has_script)}
  Roman Telugu   : {int(roman_only)}

Tenglish Detection Method
--------------------------
A comment is flagged as Tenglish if any of the following:
  1. Contains Telugu Unicode characters (U+0C00–U+0C7F)
  2. Script-mix ratio >= 0.05 (Telugu chars / total chars)
  3. Matches >= 1 word from a {len(ROMAN_TELUGU_WORDS)}-word
     Romanized Telugu vocabulary

Note: Detection is intentionally permissive at collection stage.
Final language identification will use a dedicated LangID model
(e.g. IndicLID or langdetect with Telugu support) during preprocessing.

Annotation Protocol
-------------------
Labels        : toxicity (binary), fake_news (binary)
Annotators    : 2 (student + advisor review)
Agreement     : Cohen's kappa (target >= 0.7)
Tool          : annotation_tool.py (included in repo)

License / Ethics
----------------
Data source    : Public YouTube comments (publicly visible content)
PII handling   : Author display names retained for reproducibility;
                 will be anonymized in final released dataset.
Intended use   : Academic NLP research only
"""

    with open(DATASET_LOG, "w", encoding="utf-8") as f:
        f.write(card)

    print(f"  Dataset card     : {DATASET_LOG}")
    print("\nDone. Next step: run annotation_tool.py on raw_comments.csv")


if __name__ == "__main__":
    main()
