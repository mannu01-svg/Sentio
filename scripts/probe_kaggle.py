#!/usr/bin/env python3
"""Probe each shortlisted dataset: is it downloadable with the token (200 vs 403)?
Downloads to /tmp/opencode/kaggle_probe/<ref>, unzips, shows file list + CSV headers.
Read-only wrt the repo."""

import io
import json
import os
import sys
import zipfile

import requests

TOK = os.getenv("KAGGLE_API_TOKEN")
if not TOK:
    for env_file in (".env.local", ".env"):
        if os.path.exists(env_file):
            for line in open(env_file):
                line = line.strip()
                if line.startswith("KAGGLE_API_TOKEN="):
                    TOK = line.split("=", 1)[1].strip()
                    break
        if TOK:
            break
if not TOK:
    sys.exit("KAGGLE_API_TOKEN not set — add it to .env.local or export it")
H = {"Authorization": f"Bearer {TOK}"}
BASE = "https://www.kaggle.com/api/v1"
OUT = "/tmp/opencode/kaggle_probe"

SHORTLIST = [
    # facebook
    "tomthescientist/netflix-facebook-posts-as-sentences-for-llm-input",
    "samwash94/netflix-facebook-user-comments-dataset-for-llms",
    "kalashnikov1405/facebook-text-classification",
    "thanaphumsaywonin/thai-nba-fans-facebook-comments-sentiment-dataset",
    "annguyennt/singapore-fashion-facebook-posts",
    "abdullahusmani86/facebook-posts-of-khaadi-brand",
    "thedevastator/facebook-posts-of-amazon-tourism",
    "anhndo/facebook-posts-transport-for-nsw",
    "ucsmgirl/social-media-public-group-post-dataset",
    "rayhankazi/facebook-political-comments-dataset-bangladesh",
    # instagram
    "ireddragonicy/nadiem-chromebook-instagram-comments",
    "krpurba/im-instagram-70k",
    "dhamothrans/instagram-cosmetic-product-comments",
    "egeeker/cleaned-instagram-comments",
    "imanuloh1922/indonesian-silat-comments-sentiment",
    "colabsss/instagram-service-sentiment-dataset",
    "husseimstuck/queer-community-sentiment-analysis-using-vader",
    "sohumgokhale/multi-platform-social-sentiment-evolution",
    "rezaunderfit/what-people-are-talking-about-pfizer-on-instagram",
    "prajapatisuraj/instagram-media-metadata-and-engagement-metrics",
]


def probe(ref: str) -> None:
    safe = ref.replace("/", "__")
    dest = os.path.join(OUT, safe)
    zip_path = dest + ".zip"
    print(f"\n=== {ref} ===")
    try:
        r = requests.get(f"{BASE}/datasets/download/{ref}", headers=H, timeout=120, stream=True)
    except Exception as exc:
        print(f"  ERR: {str(exc)[:100]}")
        return
    if r.status_code != 200:
        print(f"  DENIED: HTTP {r.status_code} {r.text[:80]}")
        r.close()
        return
    size = int(r.headers.get("content-length") or 0)
    print(f"  HTTP 200, {size/1024:.0f} KB")
    os.makedirs(dest, exist_ok=True)
    with open(zip_path, "wb") as f:
        for chunk in r.iter_content(1 << 16):
            f.write(chunk)
    r.close()
    # unzip
    try:
        with zipfile.ZipFile(zip_path) as z:
            z.extractall(dest)
        os.remove(zip_path)
    except zipfile.BadZipFile:
        print("  !! not a zip — skipped unzip")
        return
    # show files + headers
    for root, _, files in os.walk(dest):
        for fname in files:
            fpath = os.path.join(root, fname)
            rel = os.path.relpath(fpath, dest)
            fsize = os.path.getsize(fpath) / 1024
            print(f"  file: {rel}  ({fsize:.0f} KB)")
            if fname.lower().endswith((".csv", ".tsv")) and fsize < 40000:
                try:
                    with open(fpath, encoding="utf-8", errors="replace") as fh:
                        header = fh.readline().strip()
                        row1 = fh.readline().strip()
                    print(f"    header: {header[:220]}")
                    print(f"    sample: {row1[:180]}")
                except Exception as exc:
                    print(f"    !! {str(exc)[:80]}")


def main():
    os.makedirs(OUT, exist_ok=True)
    for ref in sys.argv[1:] or SHORTLIST:
        probe(ref)


if __name__ == "__main__":
    main()
