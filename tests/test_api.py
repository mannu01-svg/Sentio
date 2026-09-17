"""API tests using FastAPI TestClient — run with:  .venv/bin/pytest tests/ -v"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("PG_HOST", "localhost")

from fastapi.testclient import TestClient  # noqa: E402

from api.main import app  # noqa: E402

client = TestClient(app)


def test_health():
    res = client.get("/health")
    assert res.status_code == 200
    assert "status" in res.json()


def test_summary_shape():
    res = client.get("/api/summary")
    assert res.status_code == 200
    body = res.json()
    assert "total" in body and "sentiment" in body and "sources" in body
    assert set(body["sentiment"]) == {"positive", "negative", "neutral", "positive_pct", "negative_pct", "neutral_pct"}


def test_comments_filters():
    res = client.get("/api/comments", params={"limit": 5, "sentiment": "positive"})
    assert res.status_code == 200
    body = res.json()
    assert body["count"] <= 5
    for comment in body["comments"]:
        assert comment["vader_label"] == "positive"


def test_words():
    res = client.get("/api/words", params={"limit": 5})
    assert res.status_code == 200
    assert "words" in res.json()


def test_compare():
    res = client.get("/api/compare", params={"limit": 100})
    assert res.status_code == 200
    assert "compared" in res.json()
