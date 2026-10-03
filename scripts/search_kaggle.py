#!/usr/bin/env python3
"""Search Kaggle for Facebook / Instagram comment & post datasets with sentiment labels.

Uses the datasets/list endpoint with the KAGGLE_API_TOKEN (read-only).
Prints every candidate: ref, size, title — no downloads.
"""

import os
import sys

import requests

TOK = None
for line in open(".env"):
    if line.strip().startswith("Kaggle API token"):
        TOK = line.split("=", 1)[1].strip()
if not TOK:
    sys.exit("no token in .env")

H = {"Authorization": f"Bearer {TOK}"}
BASE = "https://www.kaggle.com/api/v1"

QUERIES = [
    "facebook comments sentiment",
    "facebook posts sentiment",
    "facebook status updates",
    "instagram comments sentiment",
    "instagram comments",
    "instagram caption sentiment",
    "social media comments sentiment facebook instagram",
]


def search(q: str) -> list[dict]:
    out, seen = [], set()
    after = None
    for _ in range(3):  # up to 3 pages
        url = f"{BASE}/datasets/list?search={q.replace(' ', '+')}&maxSize=200000000"
        if after:
            url += f"&page={after}"
        try:
            r = requests.get(url, headers=H, timeout=25)
        except Exception as exc:
            print(f"  !! {q}: {exc}", file=sys.stderr)
            break
        if r.status_code != 200:
            print(f"  !! {q}: HTTP {r.status_code}", file=sys.stderr)
            break
        items = r.json() if isinstance(r.json(), list) else []
        if not items:
            break
        for it in items:
            ref = it.get("ref")
            if ref and ref not in seen:
                seen.add(ref)
                out.append(it)
        after = len(out) // 20 + 1
    return out


def main():
    all_hits: dict[str, dict] = {}
    for q in QUERIES:
        hits = search(q)
        print(f"\n### {q}  ({len(hits)} unique)")
        for it in hits:
            ref = it.get("ref")
            all_hits[ref] = it
            size = it.get("totalBytes") or 0
            print(f"  {ref}  |  {size/1024:.0f} KB  |  {(it.get('title') or '')[:60]}")

    print(f"\n=== TOTAL unique candidates: {len(all_hits)} ===")
    # save full list for the probe step
    import json
    with open("/tmp/opencode/kaggle_candidates.json", "w") as f:
        json.dump(sorted(all_hits.values(), key=lambda x: x.get("totalBytes") or 0), f, indent=1)
    print("saved -> /tmp/opencode/kaggle_candidates.json")


if __name__ == "__main__":
    main()
