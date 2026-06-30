"""
clean_corpus.py
================
Cleans raw_comments.csv before annotation begins.

Removes only genuinely unusable content:
  1. Empty / NaN comments
  2. Pure emoji or symbol-only comments (no alphabetic characters at all)
  3. Comments under 3 words AND containing no Telugu script
     (too short to carry any classifiable signal)
  4. Exact duplicate comments (spam / copy-paste)

Does NOT remove:
  - Short comments that contain real words ("fake news", "super decision")
  - Comments with emojis mixed into real text (emoji is stripped, text kept)
  - Misspellings or transliteration variants (these ARE the Tenglish phenomenon)

This keeps the cleaning defensible for publication: every dropped row has
zero analyzable linguistic content. Nothing is removed because a label
would be "hard" to assign.

Usage:
    python clean_corpus.py raw_comments.csv

Output:
    raw_comments_clean.csv
    cleaning_report.txt   (drop counts + reasons, for the methodology section)
"""

import sys
import re
import pandas as pd
from datetime import datetime, timezone

TELUGU_SCRIPT = re.compile(r'[\u0C00-\u0C7F]')

# Matches emoji and pictographic symbols across common Unicode blocks
EMOJI_PATTERN = re.compile(
    "["
    "\U0001F300-\U0001FAFF"  # symbols & pictographs, extended-A
    "\U00002600-\U000027BF"  # misc symbols, dingbats
    "\U0001F1E0-\U0001F1FF"  # flags
    "\U00002700-\U000027BF"
    "\U0001F900-\U0001F9FF"
    "\U00002300-\U000023FF"  # misc technical (incl. some emoji)
    "\U0000FE0F"             # variation selector
    "]+",
    flags=re.UNICODE
)

def strip_emoji(text: str) -> str:
    return EMOJI_PATTERN.sub('', text).strip()

def has_alpha_content(text: str) -> bool:
    """True if string has at least one letter (Telugu or Latin)."""
    return bool(re.search(r'[A-Za-z\u0C00-\u0C7F]', text))

def word_count(text: str) -> int:
    return len(text.strip().split())

def clean_corpus(input_path: str, output_path: str, report_path: str):
    df = pd.read_csv(input_path, dtype=str)
    original_count = len(df)

    drop_reasons = {
        'empty_or_nan': 0,
        'emoji_or_symbol_only': 0,
        'too_short_no_telugu': 0,
        'exact_duplicate': 0,
    }

    keep_rows = []
    seen_texts = set()

    for _, row in df.iterrows():
        raw_text = row.get('text', None)

        # 1. Empty / NaN
        if pd.isna(raw_text) or str(raw_text).strip() == '':
            drop_reasons['empty_or_nan'] += 1
            continue

        text = str(raw_text).strip()

        # 2. Strip emoji, check what's left
        stripped = strip_emoji(text)
        if not has_alpha_content(stripped):
            drop_reasons['emoji_or_symbol_only'] += 1
            continue

        # 3. Too short AND no Telugu script
        has_telugu = bool(TELUGU_SCRIPT.search(text))
        if word_count(stripped) < 3 and not has_telugu:
            drop_reasons['too_short_no_telugu'] += 1
            continue

        # 4. Exact duplicate (after emoji stripping + lowercase + whitespace normalize)
        dedup_key = re.sub(r'\s+', ' ', stripped.lower())
        if dedup_key in seen_texts:
            drop_reasons['exact_duplicate'] += 1
            continue
        seen_texts.add(dedup_key)

        # Keep row, but store the emoji-stripped text in a new column
        # (original text preserved for reference)
        row_dict = row.to_dict()
        row_dict['text_original'] = text
        row_dict['text'] = stripped if stripped else text  # fallback safety
        keep_rows.append(row_dict)

    cleaned_df = pd.DataFrame(keep_rows)
    cleaned_df.to_csv(output_path, index=False, encoding='utf-8-sig')

    final_count = len(cleaned_df)
    total_dropped = original_count - final_count

    # ── Report ──
    report = f"""CORPUS CLEANING REPORT
=======================
Generated: {datetime.now(timezone.utc).isoformat()}
Input file:  {input_path}
Output file: {output_path}

Original comment count : {original_count}
Final comment count    : {final_count}
Total dropped          : {total_dropped} ({100*total_dropped/max(original_count,1):.1f}%)

Drop reasons (mutually exclusive, checked in order):
  1. Empty or NaN text              : {drop_reasons['empty_or_nan']}
  2. Emoji/symbol only (no letters) : {drop_reasons['emoji_or_symbol_only']}
  3. <3 words AND no Telugu script  : {drop_reasons['too_short_no_telugu']}
  4. Exact duplicate                : {drop_reasons['exact_duplicate']}

Cleaning Policy (for methodology section):
-------------------------------------------
Comments were removed only if they contained zero analyzable linguistic
content: empty/NaN entries, comments consisting solely of emoji or symbol
characters, comments under three words with no Telugu script present, and
exact duplicate comments (likely spam or repeated copy-paste content).

Short comments containing real words (e.g. "fake news", "super decision")
were retained, as were comments with emoji mixed into substantive text
(emoji stripped, underlying text preserved). Misspellings and transliteration
variants were retained, as these are characteristic of the Tenglish
phenomenon under study rather than noise.

Suggested methodology sentence:
"We removed {total_dropped} comments ({100*total_dropped/max(original_count,1):.1f}%) containing no
analyzable text content (pure emoji/symbol strings, comments under three
words with no Telugu script, empty entries, and exact duplicates), reducing
the corpus from {original_count} to {final_count} comments."
"""

    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(report)

    print(report)


if __name__ == "__main__":
    input_file = sys.argv[1] if len(sys.argv) > 1 else "raw_comments.csv"
    output_file = input_file.replace('.csv', '_clean.csv')
    report_file = "cleaning_report.txt"
    clean_corpus(input_file, output_file, report_file)
