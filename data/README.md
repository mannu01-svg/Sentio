# Data

## Bundled (committed to the repo, ~54MB total)
- `raw/all_sources.csv` — 35MB merged dataset (reddit · youtube · x · facebook · instagram), used by the producer for the live replay
- `raw/reddit.csv`, `raw/youtube.csv`, `raw/x.csv`, `raw/facebook.csv`, `raw/instagram.csv` — per-source intermediates (kept for `evaluation/evaluate.py --csv` demos and re-merging)
- `sample_comments.csv` — 50 labeled YouTube-style comments (works out of the box with the producer)

A fresh `git clone` has everything — no downloads, no extraction, no zip. `startup/*/start.sh` uses `raw/all_sources.csv` directly.

## Want more data?
Recommended Kaggle dataset (labels included):
- **Twitter and Reddit Sentimental Analysis Dataset** — kaggle.com/datasets/cosmos98/twitter-and-reddit-sentimental-analysis-dataset
  - ~49k Reddit comments with `label` (positive/negative/neutral)
  - download → place as `data/raw/reddit.csv` (keep the `clean_text`/`label` columns)

Optional second source:
- UCI **YouTube Spam Collection** (CC BY 4.0) — archive.ics.uci.edu/dataset/380 — 1,956 comments, `CONTENT` + `CLASS`.
- or any Kaggle YouTube comments CSV → `data/raw/youtube.csv`

The producer auto-detects common column names:
- text: `comment`, `text`, `CONTENT`, `content`, `body`, `clean_text`
- label: `label`, `sentiment`, `category`, `CLASS`
- id/author: `id`, `comment_id`, `COMMENT_ID`, `author`, `AUTHOR`

`data/raw/*.csv` are committed (54MB total); only spark-side artifacts (`.crc`, `_SUCCESS`) are gitignored.

> The one-off dataset-builder scripts (`build_datasets.py`, `textlang.py`,
> Kaggle probes, the legacy llm_label backfill) were removed after the final
> `all_sources.csv` was built — recover them from git history if you ever
> need to re-merge raw CSVs from scratch.
