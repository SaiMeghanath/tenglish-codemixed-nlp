# tenglish-codemixed-nlp

**Multi-Task Explainable Analysis of Telugu-English Code-Mixed News Comments**

Sentiment, toxicity, and stance detection on Telugu-English (Tenglish) code-mixed YouTube news comments, using multilingual transformer models with explainability analysis.

> Research project supervised by **Dr. Thushara M.G.**, Amrita School of Computing, Amrita Vishwa Vidyapeetham (Amritapuri Campus).

---

## Overview

Telugu-English code-mixed text — informally called *Tenglish* — is pervasive in YouTube comments on Telugu news content, but remains severely underrepresented in NLP research compared to Hindi-English or Tamil-English code-mixing. This project builds:

1. A new dataset of Telugu-English code-mixed YouTube news comments, collected via the YouTube Data API and annotated for **sentiment**, **toxicity**, and **stance**.
2. A transliteration-aware preprocessing pipeline for mixed-script (Telugu Unicode + Romanized Telugu) text.
3. A comparative evaluation of multilingual transformer baselines — **mBERT**, **XLM-R**, **IndicBERT**, and **MuRIL** — across all three tasks, including a multi-task learning setup with a shared encoder.
4. An explainability analysis (SHAP / attention) of model predictions on Tenglish text.

## Repository Structure

```
tenglish-codemixed-nlp/
├── README.md
├── LICENSE
├── requirements.txt
├── .gitignore
│
├── scraper/
│   └── tenglish_youtube_scraper.py     # YouTube Data API comment collection
│
├── annotation/
│   ├── annotation_tool.html            # Browser-based multi-task annotation tool
│   └── annotation_guidelines.md        # Label definitions + annotator protocol
│
├── preprocessing/
│   └── clean_corpus.py                 # Corpus cleaning (removes unusable noise)
│
├── docs/
│   ├── problem_statement.md            # Research problem, gaps, RQs
│   ├── data_collection_pipeline.md     # Channels, dates, collection parameters
│   ├── literature_review.md            # Related work survey
│   └── dataset_card.txt                # Auto-generated per scraper run
│
├── data/
│   ├── raw/                            # comment_id + metadata (no full author PII)
│   ├── processed/                      # Cleaned corpus after preprocessing
│   └── annotations/                    # Annotated subsets, IAA evaluation files
│
└── models/                             # Trained model artifacts (tracked via Git LFS / HF Hub)
```

## Tasks and Labels

| Task | Labels |
|---|---|
| **Sentiment** | Positive · Negative · Neutral |
| **Toxicity** | Toxic · Not Toxic · Ambiguous |
| **Stance** | Support · Oppose · Neutral (relative to the news topic in the video title) |

Full label definitions and edge-case rules are in [`annotation/annotation_guidelines.md`](annotation/annotation_guidelines.md).

## Dataset

- **Source:** YouTube comments from major Telugu news channels (TV9, NTV, Sakshi TV, ABN, 10TV, T News)
- **Collection method:** YouTube Data API v3 (see [`docs/data_collection_pipeline.md`](docs/data_collection_pipeline.md) for channel IDs, dates, and parameters)
- **Current size:** ~2,700 raw comments, expanding toward 8,000–10,000 across diverse categories (politics, social issues, crime, entertainment, sports)
- **Privacy:**Raw datasets are currently withheld during active research and may be released in accordance with platform policies and publication requirements. Full comment text can be rehydrated via the YouTube API using the published comment IDs, in compliance with YouTube's Terms of Service.

## Annotation

Annotation is performed using a custom browser-based tool ([`annotation/annotation_tool.html`](annotation/annotation_tool.html)) supporting all three tasks with keyboard shortcuts, live distribution tracking, and progress save/restore.

Inter-annotator agreement is measured via Cohen's κ on a shared subset, annotated independently by two annotators using a locked, fixed corpus snapshot.

## Setup

```bash
git clone https://github.com/SaiMeghanath/tenglish-codemixed-nlp.git
cd tenglish-codemixed-nlp
pip install -r requirements.txt
```

To scrape new data, create a .env file and add your YouTube Data API v3 key (do not commit your key — see `.gitignore`):

```bash
python scraper/tenglish_youtube_scraper.py
```

To clean a raw corpus:

```bash
python preprocessing/clean_corpus.py data/raw/raw_comments.csv
```

To annotate, open `annotation/annotation_tool.html` in a browser and load a cleaned CSV.

## Status

🔄 **Active research project** — dataset collection and annotation in progress. Model training and explainability analysis to follow.

## Citation

If you use this dataset or code, please cite (citation details to be added upon publication):

```
@misc{aladurthi2026tenglish,
  author    = {Aladurthi Sai Meghanath and Thushara M.G.},
  title     = {Multi-Task Explainable Analysis of Telugu-English Code-Mixed News Comments},
  year      = {2026},
  institution = {Amrita Vishwa Vidyapeetham},
  note      = {Work in progress}
}
```

## Author

**Aladurthi Sai Meghanath**
MCA (Artificial Intelligence)
Amrita School of Computing, Amrita Vishwa Vidyapeetham
GitHub: [@SaiMeghanath](https://github.com/SaiMeghanath)

**Supervisor:** Dr. Thushara M.G., Assistant Professor (Sel. Grd.), Amrita School of Computing

## License

MIT License — see [`LICENSE`](LICENSE) for details.
