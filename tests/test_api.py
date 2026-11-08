"""API tests using FastAPI TestClient — run with:  .venv/bin/pytest tests/ -v

DB-backed endpoint tests skip automatically when PostgreSQL is unreachable
(e.g. inside a bare Jenkins container with no services) — import-level and
/health checks always run.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("PG_HOST", "localhost")

import pytest  # noqa: E402

try:
    import psycopg2  # noqa: E402

    _conn = psycopg2.connect(
        host=os.getenv("PG_HOST", "localhost"),
        port=int(os.getenv("PG_PORT", "5432")),
        dbname=os.getenv("PG_DB", "sentiment"),
        user=os.getenv("PG_USER", "sentiment"),
        password=os.getenv("PG_PASSWORD", "sentiment"),
        connect_timeout=3,
    )
    _conn.close()
    PG_AVAILABLE = True
except Exception:
    PG_AVAILABLE = False

requires_db = pytest.mark.skipif(
    not PG_AVAILABLE, reason="PostgreSQL not reachable (CI/bare container)"
)

from fastapi.testclient import TestClient  # noqa: E402

from api.main import app  # noqa: E402

client = TestClient(app)


def test_health():
    res = client.get("/health")
    assert res.status_code == 200
    assert "status" in res.json()


@requires_db
def test_summary_shape():
    res = client.get("/api/summary")
    assert res.status_code == 200
    body = res.json()
    assert "total" in body and "sentiment" in body and "sources" in body
    assert set(body["sentiment"]) == {"positive", "negative", "neutral", "positive_pct", "negative_pct", "neutral_pct"}



@requires_db
def test_comments_filters():
    res = client.get("/api/comments", params={"limit": 5, "sentiment": "positive"})
    assert res.status_code == 200
    body = res.json()
    assert body["count"] <= 5
    for comment in body["comments"]:
        assert comment["llm_label"] == "positive"



@requires_db
def test_words():
    res = client.get("/api/words", params={"limit": 5})
    assert res.status_code == 200
    assert "words" in res.json()



@requires_db
def test_compare():
    res = client.get("/api/compare", params={"limit": 100})
    assert res.status_code == 200
    assert "compared" in res.json()
