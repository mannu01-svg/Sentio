#!/usr/bin/env python3
"""Producer: replays a comments CSV file into Kafka as a simulated live stream.

Two phases:
  1. seed (optional): one fast pass through the dataset so the dashboard has data
  2. live-idle: sit idle watching a control file (logs/live-stream.json); when the
     API writes {"until": <epoch>, "rate": N} into it, stream a high-rate burst
     until that timestamp, then idle again. This keeps headline counters stable
     during a demo until someone hits "Go live".

Usage:
    python producer.py --file data/raw/all_sources.csv --seed 6000
    python producer.py --no-seed                 # idle-only, bursts on demand
Control:
    echo '{"until": 1799999999, "rate": 40}' > logs/live-stream.json
"""

import argparse
import csv
import json
import os
import random
import sys
import time
from datetime import datetime, timezone

from kafka import KafkaProducer

KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP", "localhost:9092")
TOPIC = os.getenv("KAFKA_TOPIC", "comments-raw")
ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
CONTROL_PATH = os.getenv("LIVE_CONTROL", os.path.join(ROOT, "logs", "live-stream.json"))

# Columns we accept for the text/label fields across the datasets we use.
TEXT_COLUMNS = ["comment", "text", "CONTENT", "content", "body", "clean_text"]
LABEL_COLUMNS = ["label", "sentiment", "category", "CLASS"]
ID_COLUMNS = ["id", "comment_id", "COMMENT_ID"]
AUTHOR_COLUMNS = ["author", "AUTHOR", "user", "username"]
SOURCE_DEFAULT = os.getenv("SOURCE_NAME", "reddit")


def pick(row: dict, candidates: list[str]) -> str:
    """Return the first non-empty value among candidate column names."""
    for col in candidates:
        value = row.get(col)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def load_rows(path: str, limit: int | None) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
    if limit:
        rows = rows[:limit]
    if not rows:
        sys.exit(f"No rows found in {path}")
    print(f"Loaded {len(rows)} rows from {path}")
    return rows


def build_message(row: dict, index: int, source: str) -> bytes:
    text = pick(row, TEXT_COLUMNS)
    if not text:
        return b""
    # per-row source (combined datasets carry a `source` column); CLI flag is fallback
    row_source = pick(row, ["source"]) or source
    payload = {
        # unique per send: replaying the same dataset must not collide in the sink
        "id": f"{pick(row, ID_COLUMNS) or row_source}-{index}",
        "source": row_source,
        "author": pick(row, AUTHOR_COLUMNS) or "anonymous",
        "text": text,
        "label": pick(row, LABEL_COLUMNS) or None,
        # naive local time: the sink's `ts` column is compared as a plain timestamp,
        # mixing tz-aware and naive strings breaks feed ordering
        "ts": datetime.now().isoformat(timespec="seconds"),
        "post_id": pick(row, ["post_id", "POST_ID"]) or None,
        "post_title": pick(row, ["post_title", "POST_TITLE", "title"]) or None,
    }
    return json.dumps(payload).encode("utf-8")


def read_control() -> tuple[float, int]:
    """Read {"until": epoch, "rate": n} from the control file (0 = idle)."""
    try:
        with open(CONTROL_PATH) as handle:
            data = json.load(handle)
        return float(data.get("until", 0)), int(data.get("rate", 40))
    except Exception:
        return 0.0, 40


def stream_rows(rows, producer, until, rate, sent) -> int:
    """Publish rows at `rate`/sec until `until` (epoch); reshuffle between passes."""
    interval = 1.0 / rate if rate > 0 else 0
    order = list(rows)
    random.shuffle(order)
    checks = 0
    while time.time() < until:
        for row in order:
            message = build_message(row, sent, "")
            if message:
                row_source = pick(row, ["source"]) or SOURCE_DEFAULT
                producer.send(TOPIC, key=f"{row_source}-{sent}", value=message)
                sent += 1
                if sent % 500 == 0:
                    print(f"sent {sent} messages", flush=True)
            time.sleep(interval)
            checks += 1
            if checks % 50 == 0 and time.time() >= until:
                break
        random.shuffle(order)
        # honor control-file extensions mid-burst
        new_until, _ = read_control()
        until = max(until, new_until)
    return sent


def main() -> None:
    parser = argparse.ArgumentParser(description="Replay a comments CSV into Kafka (seed + live bursts).")
    parser.add_argument("--file", default=os.getenv("DATA_FILE", "data/raw/all_sources.csv"))
    parser.add_argument("--seed", type=int, default=6000, help="rows to stream once at startup (0/--no-seed skips)")
    parser.add_argument("--seed-rate", type=float, default=150.0, help="seed pass messages per second")
    parser.add_argument("--rate", type=float, default=15.0, help="legacy continuous rate (with --loop)")
    parser.add_argument("--limit", type=int, default=None, help="max rows loaded from the file")
    parser.add_argument("--loop", action="store_true", help="legacy: loop the dataset forever (no idle)")
    parser.add_argument("--shuffle", action="store_true", help="shuffle row order")
    parser.add_argument("--source", default=SOURCE_DEFAULT, help="source label fallback")
    parser.add_argument("--no-seed", action="store_true", help="skip the startup seed pass")
    args = parser.parse_args()

    rows = load_rows(args.file, args.limit)
    if args.shuffle:
        random.shuffle(rows)

    producer = KafkaProducer(
        bootstrap_servers=KAFKA_BOOTSTRAP,
        value_serializer=lambda v: v,
        key_serializer=lambda k: k.encode("utf-8") if k else None,
        linger_ms=5,
        retries=3,
    )

    sent = 0
    try:
        # phase 1: seed pass (fills the dashboard so it never starts empty)
        if args.seed and not args.no_seed:
            seed_rows = rows[: args.seed]
            print(f"Seeding {len(seed_rows)} rows at {args.seed_rate}/s …")
            sent = stream_rows(seed_rows, producer, time.time() + len(seed_rows) / max(args.seed_rate, 1), int(args.seed_rate), sent)
            print(f"Seed done ({sent} sent). Going idle — waiting for a live burst.")

        # phase 2: live-idle loop (legacy --loop keeps the old forever behaviour)
        if args.loop:
            interval = 1.0 / args.rate if args.rate > 0 else 0
            print(f"Streaming to {KAFKA_BOOTSTRAP}/{TOPIC} at {args.rate} msgs/sec (Ctrl+C to stop)")
            while True:
                for row in rows:
                    message = build_message(row, sent, args.source)
                    if not message:
                        continue
                    row_source = pick(row, ["source"]) or args.source
                    producer.send(TOPIC, key=f"{row_source}-{sent}", value=message)
                    sent += 1
                    if sent % 100 == 0:
                        print(f"sent {sent} messages")
                    time.sleep(interval)
                print("Reached end of file; looping (Ctrl+C to stop)")
        else:
            print(f"Idle mode — watching {CONTROL_PATH} for live bursts (Ctrl+C to stop)")
            while True:
                until, rate = read_control()
                if until > time.time():
                    print(f"🔴 LIVE burst until {datetime.fromtimestamp(until).strftime('%H:%M:%S')} at {rate}/s")
                    sent = stream_rows(rows, producer, until, rate, sent)
                    print("🟢 Burst over — idling.")
                time.sleep(2)
    except KeyboardInterrupt:
        print("Stopped by user")
    finally:
        producer.flush()
        producer.close()
        print(f"Done. {sent} messages sent.")


if __name__ == "__main__":
    main()
