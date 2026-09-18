#!/usr/bin/env python3
"""Producer: replays a comments CSV file into Kafka as a simulated live stream.

Each CSV row is published to the `comments-raw` topic as JSON:
    {"id", "source", "author", "text", "label", "ts"}

Usage:
    python producer.py                          # default dataset, 20 msgs/sec
    python producer.py --rate 5 --loop          # 5/sec, restart from top when done
    python producer.py --file data/raw/reddit.csv --limit 100
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
        "ts": datetime.now(timezone.utc).isoformat(),
    }
    return json.dumps(payload).encode("utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Replay a comments CSV into Kafka.")
    parser.add_argument("--file", default=os.getenv("DATA_FILE", "data/raw/reddit.csv"))
    parser.add_argument("--rate", type=float, default=20.0, help="messages per second")
    parser.add_argument("--limit", type=int, default=None, help="max rows to send")
    parser.add_argument("--loop", action="store_true", help="restart from the top when finished")
    parser.add_argument("--shuffle", action="store_true", help="shuffle row order")
    parser.add_argument("--source", default=SOURCE_DEFAULT, help="source label for messages")
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

    print(f"Streaming to {KAFKA_BOOTSTRAP}/{TOPIC} at {args.rate} msgs/sec (Ctrl+C to stop)")
    sent = 0
    interval = 1.0 / args.rate if args.rate > 0 else 0
    try:
        while True:
            for index, row in enumerate(rows):
                message = build_message(row, sent, args.source)
                if not message:
                    continue
                producer.send(TOPIC, key=f"{row.get('source') or args.source}-{sent}", value=message)
                sent += 1
                if sent % 100 == 0:
                    print(f"sent {sent} messages")
                time.sleep(interval)
            if not args.loop:
                break
            print("Reached end of file; looping (Ctrl+C to stop)")
    except KeyboardInterrupt:
        print("Stopped by user")
    finally:
        producer.flush()
        producer.close()
        print(f"Done. {sent} messages sent.")


if __name__ == "__main__":
    main()
