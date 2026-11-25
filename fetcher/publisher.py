"""Publisher: push fetched comments into Kafka for Spark to score.

Reuses the exact event schema the Spark job already consumes:
    {"id", "source", "author", "text", "label", "ts", "post_id", "post_title"}

User-triggered analyses (links, accounts, topics, re-score) go to their own
topic, `comments-analyze` by default. Spark runs a separate streaming query on
it, so these comments are scored straight away instead of queuing behind the
thousands of seed/live-replay comments on `comments-raw` (that queue is why
analyses used to sit at "scoring pending").

Every published comment is also stored, raw and unscored, in MongoDB
(fetcher/mongo_store.py) so it can be re-scored later without re-fetching.
"""

from __future__ import annotations

import json
import os

from kafka import KafkaProducer

KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP", "localhost:9092")
TOPIC = os.getenv("KAFKA_ANALYZE_TOPIC", "comments-analyze")

_producer: KafkaProducer | None = None


def get_producer() -> KafkaProducer:
    global _producer
    if _producer is None:
        _producer = KafkaProducer(
            bootstrap_servers=KAFKA_BOOTSTRAP,
            linger_ms=5,
            retries=3,
        )
    return _producer


def publish_comments(comments: list[dict], store_raw: bool = True) -> int:
    """Publish fetched comments to Kafka (and keep a raw copy in MongoDB); returns the number sent."""
    producer = get_producer()
    sent = 0
    for comment in comments:
        payload = {
            "id": comment["id"],
            "source": comment.get("source", "paste"),
            "author": comment.get("author", "anonymous"),
            "text": comment["text"],
            "label": comment.get("label"),
            "ts": comment.get("ts"),
            "post_id": comment.get("post_id"),
            "post_title": comment.get("post_title"),
        }
        producer.send(TOPIC, key=comment["id"].encode("utf-8"), value=json.dumps(payload).encode("utf-8"))
        sent += 1
    producer.flush()
    if store_raw:
        try:
            import mongo_store

            mongo_store.save_raw_comments(comments)
        except Exception:
            pass  # MongoDB is best-effort: scoring must never depend on it
    return sent
