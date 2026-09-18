"""Publisher: push fetched comments into the existing Kafka `comments-raw` topic.

Reuses the exact event schema the Spark job already consumes:
    {"id", "source", "author", "text", "label", "ts", "post_id", "post_title"}
"""

from __future__ import annotations

import json
import os

from kafka import KafkaProducer

KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP", "localhost:9092")
TOPIC = os.getenv("KAFKA_TOPIC", "comments-raw")

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


def publish_comments(comments: list[dict]) -> int:
    """Publish fetched comments to Kafka; returns the number sent."""
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
    return sent
