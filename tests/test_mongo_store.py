"""MongoDB document store tests (fetcher/mongo_store.py).

Uses mongomock (an in-memory MongoDB), so these run anywhere, including
Jenkins containers without a MongoDB server. Run:  pytest tests/test_mongo_store.py -v
"""

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "fetcher"))
sys.path.insert(0, ROOT)

import mongomock  # noqa: E402
import pytest  # noqa: E402

import mongo_store  # noqa: E402


@pytest.fixture(autouse=True)
def fake_mongo(monkeypatch):
    """Point mongo_store at a fresh in-memory MongoDB for every test."""
    monkeypatch.setattr(mongo_store, "_client", mongomock.MongoClient())
    monkeypatch.setattr(mongo_store, "_indexes_ready", False)
    monkeypatch.setattr(mongo_store, "_down_until", 0.0)
    yield mongo_store.get_db()


def comment(i, post="vid123", text=None):
    return {"id": f"yt-{post}-{i}", "source": "youtube", "author": f"@u{i}",
            "text": text or f"comment number {i}", "ts": "2026-11-20T10:00:00",
            "post_id": post, "post_title": "Lec-20 DBMS"}


def test_raw_comments_are_stored_as_documents(fake_mongo):
    written = mongo_store.save_raw_comments([comment(1), comment(2)])
    assert written == 2
    doc = fake_mongo.raw_comments.find_one({"_id": "yt-vid123-1"})
    assert doc["text"] == "comment number 1"
    assert doc["source"] == "youtube" and doc["post_id"] == "vid123"
    assert doc["fetched_at"] and doc["first_seen_at"]


def test_refetch_upserts_instead_of_duplicating(fake_mongo):
    mongo_store.save_raw_comments([comment(1)])
    first_seen = fake_mongo.raw_comments.find_one({"_id": "yt-vid123-1"})["first_seen_at"]
    mongo_store.save_raw_comments([comment(1, text="edited text")])
    assert fake_mongo.raw_comments.count_documents({}) == 1
    doc = fake_mongo.raw_comments.find_one({"_id": "yt-vid123-1"})
    assert doc["text"] == "edited text"
    assert doc["first_seen_at"] == first_seen      # $setOnInsert keeps the first time we saw it


def test_comments_without_id_or_text_are_skipped(fake_mongo):
    assert mongo_store.save_raw_comments([{"id": "", "text": "x"}, {"id": "a", "text": ""}]) == 0
    assert fake_mongo.raw_comments.count_documents({}) == 0


def test_raw_comments_for_returns_publisher_event_shape():
    mongo_store.save_raw_comments([comment(1), comment(2), comment(3, post="other")])
    events = mongo_store.raw_comments_for(["vid123"])
    assert len(events) == 2
    assert set(events[0]) == {"id", "source", "author", "text", "label", "ts", "post_id", "post_title"}
    assert {e["id"] for e in events} == {"yt-vid123-1", "yt-vid123-2"}
    assert mongo_store.raw_comments_for([]) == []


def test_analysis_document_links_history_and_counts_raw_comments(fake_mongo):
    mongo_store.save_raw_comments([comment(i) for i in range(5)])
    oid = mongo_store.save_analysis({"history_id": 42, "kind": "post", "platform": "youtube",
                                     "posts": ["vid123"], "comments_published": 5,
                                     "user_email": "admin@sentio.app",
                                     "request": {"url": "https://youtu.be/vid123"}})
    assert oid
    doc = mongo_store.analysis_for_history(42)
    assert doc["id"] == oid and doc["raw_comments_stored"] == 5
    assert doc["request"]["url"] == "https://youtu.be/vid123"
    assert isinstance(doc["created_at"], str)      # JSON-safe for the API


def test_stats_and_ping():
    mongo_store.save_raw_comments([comment(1)])
    mongo_store.save_analysis({"history_id": 1, "posts": []})
    assert mongo_store.stats() == {"raw_comments": 1, "analyses": 1}
    assert mongo_store.ping() is True


def test_unreachable_mongodb_is_best_effort(monkeypatch):
    """No MongoDB: every call returns quickly with an empty result, never raises."""
    monkeypatch.setattr(mongo_store, "_client", None)
    monkeypatch.setattr(mongo_store, "MONGO_URI", "mongodb://127.0.0.1:1")   # nothing listens here
    assert mongo_store.save_raw_comments([comment(1)]) == 0
    assert mongo_store.save_analysis({"history_id": 1}) is None
    assert mongo_store.raw_comments_for(["vid123"]) == []
    assert mongo_store.stats() is None
    assert mongo_store.ping() is False
