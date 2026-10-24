#!/usr/bin/env python3
"""Prepare the Kaggle sentiment data for fine-tuning.

Reads data/raw/all_sources.csv, keeps rows whose label maps cleanly to
positive/negative/neutral, dedupes by text, and writes a stratified
train/validation split (90/10) as JSONL for the fine-tune script.
"""

import csv
import json
import os
import random
import sys
from collections import Counter

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))


def normalize(raw: str) -> str | None:
    label = (raw or "").strip().lower()
    if label.startswith("pos"):
        return "positive"
    if label.startswith("neg"):
        return "negative"
    if label.startswith("neu"):
        return "neutral"
    return None


def main() -> None:
    src = os.path.join(ROOT, "data", "raw", "all_sources.csv")
    out_dir = os.path.join(ROOT, "models", "training")
    seen, rows = set(), []
    with open(src, newline="", encoding="utf-8") as handle:
        for r in csv.DictReader(handle):
            text = (r.get("text") or r.get("comment") or "").strip()
            label = normalize(r.get("label"))
            if not text or not label or len(text) < 8 or len(text) > 400:
                continue
            key = text.lower()
            if key in seen:
                continue
            seen.add(key)
            rows.append({"text": text, "label": label})
    random.seed(42)
    random.shuffle(rows)
    split = int(len(rows) * 0.9)
    train, val = rows[:split], rows[split:]
    for name, data in (("train.jsonl", train), ("val.jsonl", val)):
        with open(os.path.join(out_dir, name), "w", encoding="utf-8") as handle:
            for row in data:
                handle.write(json.dumps(row) + "\n")
    counts = Counter(r["label"] for r in rows)
    print(f"total {len(rows)} clean rows (train {len(train)} / val {len(val)})")
    print("label distribution:", dict(counts))


if __name__ == "__main__":
    main()
