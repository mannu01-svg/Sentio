"""MongoDB document store for Sentio.

PostgreSQL keeps what Spark computes (scored comments, 1-minute windows) and
what the app needs to be relational (users, history list). MongoDB keeps what
is naturally a *document*: the raw data each analysis collected.

Collections (database `sentio` by default):

  raw_comments   one document per fetched comment, exactly as it came from the
                 platform (YouTube / Reddit / X / pasted ...), before cleaning
                 or scoring. _id = comment id, so re-fetches upsert instead of
                 duplicating. Fields: source, author, text, ts, post_id,
                 post_title, label, fetched_at, first_seen_at.

  analyses       one document per analysis a user ran (link / account / topic /
                 keyword / paste), with its request, the posts it covered and
                 how many comments it collected. history_id links it to the
                 PostgreSQL `history` row.

Why both stores: re-scoring ("Re-score" on the History page) republishes the
stored raw comments from MongoDB, so it works even when YouTube or Reddit no
longer return those comments, and the original wording is kept for audit.

Everything here is best-effort: if MongoDB is down, analyses still run and
the app keeps working on PostgreSQL alone (same policy as the history table).
"""

from __future__ import annotations

import os
from datetime import datetime, timezone

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB = os.getenv("MONGO_DB", "sentio")

_client = None
_indexes_ready = False
_down_until = 0.0        # after a failed connect, skip MongoDB for a while instead of waiting each call
RETRY_SECONDS = 30


def _now() -> datetime:
    return datetime.now(timezone.utc)


def get_db():
    """Return the Mongo database handle, or None if MongoDB is unreachable."""
    global _client, _indexes_ready, _down_until
    import time

    if time.time() < _down_until:
        return None
    try:
        if _client is None:
            from pymongo import MongoClient

            _client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=1500, connectTimeoutMS=1500)
        db = _client[MONGO_DB]
        if not _indexes_ready:
            db.raw_comments.create_index("post_id")
            db.raw_comments.create_index([("fetched_at", -1)])
            db.analyses.create_index([("created_at", -1)])
            db.analyses.create_index("history_id")
            db.analyses.create_index("user_email")
            _indexes_ready = True
        return db
    except Exception:
        _client = None
        _down_until = time.time() + RETRY_SECONDS
        return None


def save_raw_comments(comments: list[dict]) -> int:
    """Upsert fetched comments (raw, unscored) by id. Returns how many were written."""
    if not comments:
        return 0
    db = get_db()
    if db is None:
        return 0
    try:
        from pymongo import UpdateOne

        now = _now()
        ops = []
        for c in comments:
            if not c.get("id") or not c.get("text"):
                continue
            doc = {
                "source": c.get("source", "paste"),
                "author": c.get("author", "anonymous"),
                "text": c["text"],
                "label": c.get("label"),
                "ts": c.get("ts"),
                "post_id": c.get("post_id"),
                "post_title": c.get("post_title"),
                "fetched_at": now,
            }
            ops.append(UpdateOne({"_id": c["id"]},
                                 {"$set": doc, "$setOnInsert": {"first_seen_at": now}},
                                 upsert=True))
        if not ops:
            return 0
        result = db.raw_comments.bulk_write(ops, ordered=False)
        return result.upserted_count + result.matched_count
    except Exception:
        return 0


def save_analysis(doc: dict) -> str | None:
    """Store one analysis document. Returns its Mongo id as a string, or None."""
    db = get_db()
    if db is None:
        return None
    try:
        record = {**doc, "created_at": doc.get("created_at") or _now()}
        post_ids = [p for p in (record.get("posts") or []) if p]
        if post_ids:
            record["raw_comments_stored"] = db.raw_comments.count_documents({"post_id": {"$in": post_ids}})
        return str(db.analyses.insert_one(record).inserted_id)
    except Exception:
        return None


def raw_comments_for(post_ids: list[str], limit: int = 2000) -> list[dict]:
    """Stored raw comments for these posts, in the publisher's event shape."""
    ids = [p for p in post_ids if p]
    if not ids:
        return []
    db = get_db()
    if db is None:
        return []
    try:
        cursor = db.raw_comments.find({"post_id": {"$in": ids}}).limit(limit)
        return [
            {
                "id": d["_id"], "source": d.get("source", "paste"), "author": d.get("author", "anonymous"),
                "text": d["text"], "label": d.get("label"), "ts": d.get("ts"),
                "post_id": d.get("post_id"), "post_title": d.get("post_title"),
            }
            for d in cursor
        ]
    except Exception:
        return []


def analysis_for_history(history_id: int) -> dict | None:
    """The analysis document linked to a PostgreSQL history row (JSON-safe)."""
    db = get_db()
    if db is None:
        return None
    try:
        doc = db.analyses.find_one({"history_id": history_id}, sort=[("created_at", -1)])
        return _jsonable(doc) if doc else None
    except Exception:
        return None


def stats() -> dict | None:
    """Collection counts for the Pipeline page; None when MongoDB is unreachable."""
    db = get_db()
    if db is None:
        return None
    try:
        return {
            "raw_comments": db.raw_comments.estimated_document_count(),
            "analyses": db.analyses.estimated_document_count(),
        }
    except Exception:
        return None


def ping() -> bool:
    db = get_db()
    if db is None:
        return False
    try:
        db.command("ping")
        return True
    except Exception:
        return False


def _jsonable(doc: dict) -> dict:
    out = {}
    for k, v in doc.items():
        if k == "_id":
            out["id"] = str(v)
        elif isinstance(v, datetime):
            out[k] = v.isoformat()
        else:
            out[k] = v
    return out
