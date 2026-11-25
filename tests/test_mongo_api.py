"""End-to-end API tests for the MongoDB + analyze-topic flow.

analyze a YouTube link -> raw comments + analysis document land in MongoDB,
comments go to the `comments-analyze` Kafka topic -> the history entry's
document is readable -> "Re-score" republishes from MongoDB without
re-fetching from YouTube -> /api/pipeline and /health report MongoDB.

YouTube and Kafka are replaced by fakes; MongoDB by mongomock. Needs
PostgreSQL (skips without it, like test_api.py).
"""

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "fetcher"))
os.environ.setdefault("PG_HOST", "localhost")

import mongomock  # noqa: E402
import pytest  # noqa: E402

try:
    import psycopg2

    psycopg2.connect(host=os.getenv("PG_HOST", "localhost"), port=int(os.getenv("PG_PORT", "5432")),
                     dbname="sentiment", user="sentiment", password="sentiment", connect_timeout=3).close()
    PG_AVAILABLE = True
except Exception:
    PG_AVAILABLE = False

pytestmark = pytest.mark.skipif(not PG_AVAILABLE, reason="PostgreSQL not reachable")

from fastapi.testclient import TestClient  # noqa: E402

import fetchers  # noqa: E402
import mongo_store  # noqa: E402
import publisher  # noqa: E402
from api.main import app  # noqa: E402

client = TestClient(app)
VIDEO = "dQw4w9WgXcQ"


class FakeProducer:
    def __init__(self):
        self.sent = []

    def send(self, topic, key=None, value=None):
        self.sent.append((topic, key))

    def flush(self):
        pass


@pytest.fixture()
def env(monkeypatch):
    monkeypatch.setattr(mongo_store, "_client", mongomock.MongoClient())
    monkeypatch.setattr(mongo_store, "_indexes_ready", False)
    monkeypatch.setattr(mongo_store, "_down_until", 0.0)
    producer = FakeProducer()
    monkeypatch.setattr(publisher, "_producer", producer)

    def fake_fetch(url, mode="auto", limit=100):
        return {"post_id": VIDEO, "post_title": "Lec-20: Many to Many Relationship in DBMS", "source": "youtube",
                "comments": [{"id": f"yt-{VIDEO}-{i}", "source": "youtube", "author": f"@s{i}", "text": t,
                              "ts": "2026-11-20T10:00:00", "post_id": VIDEO,
                              "post_title": "Lec-20: Many to Many Relationship in DBMS"}
                             for i, t in enumerate(["Best DBMS explanation!", "Audio is low", "Thanks sir"])]}

    monkeypatch.setattr(fetchers, "fetch", fake_fetch)
    login = client.post("/api/login", json={"email": "admin@sentio.app", "password": "admin123"}).json()
    assert login.get("token"), f"seed the admin first (scripts/seed_admin.py): {login}"
    return {"producer": producer, "headers": {"Authorization": f"Bearer {login['token']}"},
            "db": mongo_store.get_db()}


def test_analyze_stores_raw_comments_and_analysis_in_mongodb(env):
    res = client.post("/api/analyze", headers=env["headers"],
                      json={"url": f"https://www.youtube.com/watch?v={VIDEO}", "user_email": "admin@sentio.app"}).json()
    assert res["status"] == "ok" and res["comments_published"] == 3
    # comments went to the priority topic, not the replay topic
    assert {topic for topic, _ in env["producer"].sent} == {"comments-analyze"}
    # raw comments as documents
    assert env["db"].raw_comments.count_documents({"post_id": VIDEO}) == 3
    # one analysis document, linked to the PostgreSQL history row
    doc = env["db"].analyses.find_one({"posts": VIDEO})
    assert doc["kind"] == "post" and doc["platform"] == "youtube" and doc["history_id"]
    assert doc["request"]["url"].endswith(VIDEO) and doc["raw_comments_stored"] == 3


def test_history_document_and_rescore_from_mongodb(env, monkeypatch):
    client.post("/api/analyze", headers=env["headers"],
                json={"url": f"https://youtu.be/{VIDEO}", "user_email": "admin@sentio.app"})
    entry = client.get("/api/history", headers=env["headers"],
                       params={"user": "admin@sentio.app", "limit": 1}).json()["history"][0]

    document = client.get(f"/api/history/{entry['id']}/document", headers=env["headers"]).json()
    assert document["mongodb"] is True
    assert document["analysis"]["history_id"] == entry["id"]
    assert document["raw_count"] == 3 and document["raw_comments"][0]["text"]

    # re-score must not touch YouTube: make any re-fetch fail loudly
    def no_fetch(*a, **k):
        raise AssertionError("re-score should republish from MongoDB, not re-fetch")

    monkeypatch.setattr(fetchers, "fetch_youtube", no_fetch)
    env["producer"].sent.clear()
    res = client.post(f"/api/history/{entry['id']}/rehydrate", headers=env["headers"]).json()
    assert res["status"] == "ok" and res["source"] == "mongodb"
    assert res["comments_published"] == 3 and res["healed_ids"] == [VIDEO]
    assert len(env["producer"].sent) == 3


def test_pipeline_and_health_report_mongodb(env):
    mongo_store.save_raw_comments([{"id": "x1", "text": "hello", "post_id": "p"}])
    stages = {s["name"]: s for s in client.get("/api/pipeline").json()["stages"]}
    assert stages["MongoDB · raw_comments"]["value"] == 1
    assert "MongoDB · analyses" in stages and "Kafka · comments-analyze" in stages
    # the names the Pipeline page looks up are unchanged
    assert {"Kafka · comments-raw", "Kafka · comments-scored", "PostgreSQL · comments"} <= set(stages)
    assert client.get("/health").json()["mongodb"] == "up"
