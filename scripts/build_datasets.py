#!/usr/bin/env python3
"""Merge approved Kaggle datasets into data/raw/facebook.csv + instagram.csv,
then rebuild data/raw/all_sources.csv.

English-only filter (VADER + DistilBERT are English models).
Sources (all downloaded via the Kaggle API with the user's token):
  FB-1 tomthescientist/netflix-facebook-posts-as-sentences-for-llm-input  (~200k comments)
  FB-2 kalashnikov1405/facebook-text-classification  (labeled posts)
  FB-3 annguyennt/singapore-fashion-facebook-posts  (brand posts + sentiment)
  FB-4 ucsmgirl/social-media-public-group-post-dataset  (group posts)
  FB-5 thedevastator/facebook-posts-of-amazon-tourism  (page posts, pt/en mix)
  IG-1 rezaunderfit/what-people-are-talking-about-pfizer-on-instagram  (captions)
  IG-2 colabsss/instagram-service-sentiment-dataset  (service captions)
  IG-3 sohumgokhale/multi-platform-social-sentiment-evolution  (IG rows, labeled)
"""

import csv
import os
import random
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from textlang import is_english  # noqa: E402

P = "/tmp/opencode/kaggle_probe"
OUT = "data/raw"

FB_CAP = int(os.getenv("FB_CAP", "25000"))
IG_CAP = int(os.getenv("IG_CAP", "25000"))


def read_csv(path: str) -> list[dict]:
    with open(path, encoding="utf-8", errors="replace") as fh:
        return list(csv.DictReader(fh))


def build_facebook() -> list[dict]:
    rows, seen = [], set()

    def add(text, label="", author="anonymous", ts="", note=""):
        text = (text or "").strip()
        if not text or len(text) < 5 or text.lower() in seen:
            return
        if not is_english(text):
            return
        seen.add(text.lower())
        rows.append({
            "id": f"fb-{len(rows)}",
            "comment": text,
            "label": (label or "").strip().lower(),
            "author": (author or "anonymous").strip()[:80],
            "ts": (ts or "").strip(),
            "source": "facebook",
            "dataset": note,
        })

    # FB-1: netflix comments (~200k) -> sample
    fb1 = read_csv(f"{P}/tomthescientist__netflix-facebook-posts-as-sentences-for-llm-input/netflix_fb_comments.csv")
    random.seed(42)
    random.shuffle(fb1)
    for r in fb1:
        if len(rows) >= FB_CAP:
            break
        add(r.get("Comment"), label="", author=r.get("UserName"), ts=r.get("Timestamp"), note="FB-1 netflix")

    # FB-2: labeled posts
    for r in read_csv(f"{P}/kalashnikov1405__facebook-text-classification/Facebook_data_txt.csv"):
        add(r.get("text"), label=r.get("sentiment"), author="fb_post", ts=r.get("timestamp"),
            note="FB-2 text-classification")

    # FB-3: singapore fashion brand posts
    for r in read_csv(f"{P}/annguyennt__singapore-fashion-facebook-posts/Facebook posts and sentiments.csv"):
        add(r.get("post_text"), author=r.get("Brand") or "brand_post", ts=r.get("time"),
            note="FB-3 sg-fashion")

    # FB-4: public group posts
    for r in read_csv(f"{P}/ucsmgirl__social-media-public-group-post-dataset/Social Media Public Datasset.csv"):
        add(r.get("Post"), note="FB-4 group-posts")
        # top comment as separate row
        add(r.get("1Comment"), note="FB-4 group-comments")

    # FB-5: amazon tourism page posts (pt/en mix -> english filter handles it)
    for r in read_csv(f"{P}/thedevastator__facebook-posts-of-amazon-tourism/tourism_amazon.csv"):
        add(r.get("status_message"), author="page_post", ts=r.get("status_published"),
            note="FB-5 amazon-tourism")

    return rows


def build_instagram() -> list[dict]:
    rows, seen = [], set()

    def add(text, label="", author="instagram_user", ts="", note=""):
        text = (text or "").strip()
        if not text or len(text) < 5 or text.lower() in seen:
            return
        if not is_english(text):
            return
        seen.add(text.lower())
        rows.append({
            "id": f"ig-{len(rows)}",
            "comment": text,
            "label": (label or "").strip().lower(),
            "author": (author or "instagram_user").strip()[:80],
            "ts": (ts or "").strip(),
            "source": "instagram",
            "dataset": note,
        })

    # IG-1: pfizer captions — unique (text, timestamp) = distinct posts sharing
    # recycled caption templates; keep each timestamp variant as its own row
    for r in read_csv(f"{P}/rezaunderfit__what-people-are-talking-about-pfizer-on-instagram/pfizer.csv"):
        ts = r.get("taken_at_timestamp")
        if ts and ts.strip().isdigit():
            from datetime import datetime, timezone
            ts = datetime.fromtimestamp(int(ts), tz=timezone.utc).isoformat()
        text = (r.get("text") or "").strip()
        likes = (r.get("edge_media_preview_like") or "").strip()
        add(text, author="ig_caption", ts=ts, note="IG-1 pfizer")
        if not text:
            continue
        # accessibility captions are descriptive text of the image — also usable signal
        acc = (r.get("accessibility_caption") or "").strip()
        add(acc, author="ig_media", ts=ts, note="IG-1 pfizer-alt") if acc and len(acc) > 25 else None

    # IG-2: service captions (15k rows = template captions × service domains;
    # dedup by (text, service_domain) keeps one row per unique combination)
    for r in read_csv(f"{P}/colabsss__instagram-service-sentiment-dataset/Instagram_Service_Marketing_Sentiment_Dataset.csv"):
        cap = (r.get("caption") or "").strip()
        domain = (r.get("service_domain") or "").strip().lower()
        add(f"{cap}", author=f"ig_{domain}" if domain else "ig_service", note=f"IG-2 {domain or 'service'}")

    # IG-3: multi-platform evolution — NO text column (metadata only), skipped.
    # IG-4: citynet (already cached from the first build) — 1301 real IG comments
    # with labels. This is the volume backbone for instagram.
    kaggle_cache = os.path.join(os.path.expanduser("~"), ".cache", "kagglehub", "datasets")
    citynet = os.path.join(kaggle_cache, "vrashad/citynet-instagram-comments-sentiment-analysis/versions/1/citynet_denormalized_dataset_with_comment.csv")
    for r in read_csv(citynet):
        add(r.get("Comment"), label=r.get("Label"), author="citynet_user", note="IG-4 citynet")

    # IG-5: kashishparmar02 social-media sentiments — the Instagram slice (249 rows)
    kash = os.path.join(kaggle_cache, "kashishparmar02/social-media-sentiments-analysis-dataset/versions/3/sentimentdataset.csv")
    for r in read_csv(kash):
        if (r.get("Platform") or "").strip().lower() != "instagram":
            continue
        add(r.get("Text"), label=r.get("Sentiment"), author=(r.get("User") or "ig_user"),
            ts=r.get("Timestamp"), note="IG-5 kashish")

    return rows


def rebuild_all_sources(fb: list[dict], ig: list[dict]) -> None:
    fields = ["id", "source", "text", "comment", "label", "author", "ts", "post_id", "post_title"]
    all_rows = []
    for fname in ["reddit.csv", "youtube.csv", "x.csv"]:
        path = f"{OUT}/{fname}"
        if not os.path.exists(path):
            print(f"  !! missing {path}")
            continue
        for r in read_csv(path):
            text = (r.get("text") or r.get("comment") or r.get("clean_text") or "").strip()
            if not text:
                continue
            all_rows.append({
                "id": r.get("id") or "", "source": r.get("source") or fname.replace(".csv", ""),
                "text": text, "comment": text,
                "label": r.get("label") or "", "author": r.get("author") or "",
                "ts": r.get("ts") or "", "post_id": r.get("post_id") or "",
                "post_title": r.get("post_title") or "",
            })
    for r in fb + ig:
        all_rows.append({
            "id": r["id"], "source": r["source"], "text": r["comment"], "comment": r["comment"],
            "label": r["label"], "author": r["author"], "ts": r["ts"],
            "post_id": "", "post_title": "",
        })
    with open(f"{OUT}/all_sources.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(all_rows)
    print(f"all_sources.csv: {len(all_rows)} rows")


def main():
    from collections import Counter

    fb = build_facebook()
    ig = build_instagram()

    for name, rows in [("facebook", fb), ("instagram", ig)]:
        with open(f"{OUT}/{name}.csv", "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=["id", "comment", "label", "author", "ts", "source", "dataset"])
            w.writeheader()
            w.writerows(rows)
        print(f"{name}.csv: {len(rows)} rows | per-dataset: {dict(Counter(r['dataset'] for r in rows))}"
              + (f" | labels: {dict(Counter(r['label'] for r in rows if r['label']))}" if name == 'facebook' else ""))

    rebuild_all_sources(fb, ig)
    with open(f"{OUT}/all_sources.csv", encoding="utf-8", errors="replace") as fh:
        split = Counter(r["source"] for r in csv.DictReader(fh))
    print("final split:", dict(split))


if __name__ == "__main__":
    main()
