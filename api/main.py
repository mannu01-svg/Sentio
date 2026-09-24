"""FastAPI service — read endpoints over the processed data in PostgreSQL,
plus the /api/analyze ingestion trigger for link-based analysis.

Run:
    .venv/bin/uvicorn api.main:app --reload --port 8000
Docs:
    http://localhost:8000/docs
"""

import csv
import io
import os
import re
import sys
import uuid
from collections import Counter
from datetime import datetime, timezone

import psycopg2
import psycopg2.extras
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "fetcher"))

PG_CONFIG = {
    "host": os.getenv("PG_HOST", "localhost"),
    "port": int(os.getenv("PG_PORT", "5432")),
    "dbname": os.getenv("PG_DB", "sentiment"),
    "user": os.getenv("PG_USER", "sentiment"),
    "password": os.getenv("PG_PASSWORD", "sentiment"),
}

STOPWORDS = set(
    """a an the and or but if then so as at by for in of on to with is are was were be been
    being this that these those it its i you he she we they me my your his her our their
    do does did doing done have has had having not no yes can could should would will just
    about from what when where who whom which why how all any both each few more most other
    some such than too very s t d ll m o re ve y ain aren couldn didn doesn hadn hasn haven
    isn ma mightn mustn needn shan shouldn wasn weren won wouldn get got like really one
    also im dont its ive youre wouldnt couldnt""".split()
)

app = FastAPI(
    title="Social Media Sentiment Analysis API",
    description="Serves aggregated sentiment analytics produced by the Kafka + Spark pipeline.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # college project: open for the dev dashboard
    allow_methods=["*"],
    allow_headers=["*"],
)


def db():
    return psycopg2.connect(**PG_CONFIG, cursor_factory=psycopg2.extras.RealDictCursor)


# ---------------------------------------------------------------------------
# Demo auth (college project: any email+password accepted, signed-lite token)
# ---------------------------------------------------------------------------

import hashlib
import time as _time


def _make_token(email: str) -> str:
    stamp = str(_time.time())
    digest = hashlib.sha256(f"{email}:{stamp}:sentio-demo".encode()).hexdigest()[:24]
    return f"sentio_{digest}_{int(float(stamp))}"


class LoginRequest(BaseModel):
    email: str
    password: str
    name: str | None = None


@app.post("/api/login")
def login(req: LoginRequest):
    """Demo auth: accepts any email/password, returns a session token."""
    email = req.email.strip().lower()
    if "@" not in email or len(req.password) < 1:
        return {"status": "error", "message": "Enter a valid email and any password"}
    name = req.name or email.split("@")[0].replace(".", " ").replace("_", " ").title()
    return {
        "status": "ok",
        "token": _make_token(email),
        "user": {"email": email, "name": name},
        "note": "demo authentication — any email/password combination works",
    }


# ---------------------------------------------------------------------------
# Pipeline monitor: what is streaming right now (powers /pipeline page)
# ---------------------------------------------------------------------------

@app.get("/api/pipeline")
def pipeline():
    """Live pipeline counters: kafka offsets, spark window rate, db rows."""
    out: dict = {"stages": []}

    # kafka offsets (raw in / scored out)
    kafka_raw = kafka_scored = None
    try:
        import subprocess

        def offset_sum(topic: str) -> int | None:
            bins = "/opt/kafka/bin"
            cmd = (
                f"docker exec sma-kafka {bins}/kafka-get-offsets.sh "
                f"--bootstrap-server localhost:9092 --topic {topic}"
            )
            res = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
            if res.returncode != 0:
                return None
            total = 0
            for line in res.stdout.strip().splitlines():
                try:
                    total += int(line.rsplit(":", 1)[1])
                except (ValueError, IndexError):
                    continue
            return total

        kafka_raw = offset_sum("comments-raw")
        kafka_scored = offset_sum("comments-scored")
    except Exception:
        pass

    with db() as conn, conn.cursor() as cur:
        cur.execute("SELECT count(*) AS total FROM comments")
        db_total = cur.fetchone()["total"]
        cur.execute(
            """
            SELECT count(*) AS windows,
                   coalesce(sum(total), 0) AS windowed_comments,
                   coalesce(max(total), 0) AS max_window
            FROM window_stats
            WHERE window_start >= now() - interval '30 minutes'
            """
        )
        w = dict(cur.fetchone())
        cur.execute(
            """
            SELECT count(*) AS recent FROM comments
            WHERE processed_at >= now() - interval '1 minute'
            """
        )
        per_min = cur.fetchone()["recent"]

    out["stages"] = [
        {"name": "Kafka · comments-raw", "detail": "ingestion topic", "value": kafka_raw, "unit": "messages"},
        {"name": "Kafka · comments-scored", "detail": "scored feed topic", "value": kafka_scored, "unit": "messages"},
        {"name": "Spark · throughput", "detail": "comments processed last minute", "value": per_min, "unit": "comments/min"},
        {"name": "Spark · windows", "detail": "1-min windows in last 30 min", "value": w["windows"], "unit": "windows"},
        {"name": "PostgreSQL · comments", "detail": "scored rows stored", "value": db_total, "unit": "rows"},
        {"name": "PostgreSQL · windowed", "detail": "comments in recent windows", "value": w["windowed_comments"], "unit": "comments"},
    ]
    out["flow_per_min"] = per_min
    out["max_window"] = w["max_window"]
    return out


@app.get("/health")
def health():
    try:
        with db() as conn, conn.cursor() as cur:
            cur.execute("SELECT 1")
        return {"status": "ok", "database": "up"}
    except Exception as exc:
        return {"status": "degraded", "database": f"down: {exc}"}


@app.get("/api/summary")
def summary():
    """KPI cards: totals, sentiment split (VADER), BERT coverage, throughput."""
    with db() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT count(*) AS total,
                   count(*) FILTER (WHERE vader_label = 'positive') AS positive,
                   count(*) FILTER (WHERE vader_label = 'negative') AS negative,
                   count(*) FILTER (WHERE vader_label = 'neutral')  AS neutral,
                   avg(vader_score) AS avg_score,
                   count(*) FILTER (WHERE bert_label IS NOT NULL) AS bert_scored,
                   count(*) FILTER (WHERE source = 'reddit')    AS reddit,
                   count(*) FILTER (WHERE source = 'youtube')   AS youtube,
                   count(*) FILTER (WHERE source = 'instagram') AS instagram,
                   max(processed_at) AS last_processed
            FROM comments
            """
        )
        row = dict(cur.fetchone())

    total = row["total"] or 0
    return {
        "total": total,
        "sentiment": {
            "positive": row["positive"] or 0,
            "negative": row["negative"] or 0,
            "neutral": row["neutral"] or 0,
            "positive_pct": round((row["positive"] or 0) * 100 / total, 1) if total else 0,
            "negative_pct": round((row["negative"] or 0) * 100 / total, 1) if total else 0,
            "neutral_pct": round((row["neutral"] or 0) * 100 / total, 1) if total else 0,
        },
        "avg_vader_score": round(float(row["avg_score"]), 4) if row["avg_score"] is not None else None,
        "bert_scored": row["bert_scored"] or 0,
        "sources": {"reddit": row["reddit"] or 0, "youtube": row["youtube"] or 0, "instagram": row["instagram"] or 0},
        "last_processed": row["last_processed"].isoformat() if row["last_processed"] else None,
    }


@app.get("/api/timeline")
def timeline(minutes: int = Query(60, ge=5, le=1440, description="lookback window in minutes")):
    """Per-window aggregates for the sentiment-over-time chart."""
    with db() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT window_start, window_end, total, positive, negative, neutral,
                   pos_pct, neg_pct, neu_pct, avg_score, top_words
            FROM window_stats
            WHERE window_start >= now() - interval '%s minutes'
            ORDER BY window_start
            """,
            (minutes,),
        )
        rows = [dict(r) for r in cur.fetchall()]
    for row in rows:
        for key in ("window_start", "window_end"):
            row[key] = row[key].isoformat() if row[key] else None
    return {"windows": rows, "count": len(rows)}


@app.get("/api/comments")
def comments(
    limit: int = Query(50, ge=1, le=500),
    source: str | None = Query(None, description="reddit | youtube | instagram | paste"),
    sentiment: str | None = Query(None, description="positive | negative | neutral"),
    q: str | None = Query(None, description="substring search in text"),
    post_id: str | None = Query(None, description="filter comments of one analyzed post"),
):
    """Latest scored comments (live feed) with optional filters."""
    clauses, params = ["1=1"], []
    if source:
        clauses.append("source = %s")
        params.append(source)
    if sentiment:
        clauses.append("vader_label = %s")
        params.append(sentiment)
    if q:
        clauses.append("(text ILIKE %s OR cleaned_text ILIKE %s)")
        params += [f"%{q}%", f"%{q}%"]
    if post_id:
        clauses.append("post_id = %s")
        params.append(post_id)

    with db() as conn, conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT id, source, author, text, label, vader_label, vader_score,
                   bert_label, bert_score, ts, post_id
            FROM comments
            WHERE {' AND '.join(clauses)}
            ORDER BY ts DESC NULLS LAST
            LIMIT %s
            """,
            (*params, limit),
        )
        rows = [dict(r) for r in cur.fetchall()]
    for row in rows:
        row["ts"] = row["ts"].isoformat() if row["ts"] else None
    return {"comments": rows, "count": len(rows)}


@app.get("/api/words")
def words(limit: int = Query(15, ge=3, le=50), sentiment: str | None = None):
    """Top words across recent comments (simple frequency count)."""
    clauses, params = ["1=1"], []
    if sentiment:
        clauses.append("vader_label = %s")
        params.append(sentiment)
    with db() as conn, conn.cursor() as cur:
        cur.execute(
            f"SELECT cleaned_text FROM comments WHERE {' AND '.join(clauses)} "
            "ORDER BY ts DESC NULLS LAST LIMIT 2000",
            params,
        )
        texts = [r["cleaned_text"] or "" for r in cur.fetchall()]

    counter = Counter()
    for text in texts:
        counter.update(w for w in re.findall(r"[a-z']{3,}", text) if w not in STOPWORDS)
    top = counter.most_common(limit)
    max_count = top[0][1] if top else 1
    return {
        "words": [
            {"word": w, "count": c, "weight": round(c / max_count, 3)} for w, c in top
        ]
    }


@app.get("/api/compare")
def compare(limit: int = Query(500, ge=10, le=5000)):
    """VADER (lexicon) vs DistilBERT (transformer) agreement + label accuracy."""
    with db() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT vader_label, bert_label, label, vader_score, text
            FROM comments
            WHERE vader_label IS NOT NULL AND bert_label IS NOT NULL
            ORDER BY ts DESC NULLS LAST
            LIMIT %s
            """,
            (limit,),
        )
        rows = [dict(r) for r in cur.fetchall()]

    total = len(rows)
    if not total:
        return {"compared": 0}

    def norm_bert(label: str | None) -> str | None:
        # BERT SST-2 has no neutral; treat low-confidence negative as neutral-ish
        return label

    agreement = sum(1 for r in rows if r["vader_label"] == norm_bert(r["bert_label"]))
    labeled = [r for r in rows if r["label"]]
    correct_vader = sum(
        1 for r in labeled if r["label"].lower().startswith(r["vader_label"][:4])
    )
    disagreements = [
        {
            "text": r["text"][:200],
            "vader": r["vader_label"],
            "bert": r["bert_label"],
            "vader_score": r["vader_score"],
        }
        for r in rows
        if r["vader_label"] != norm_bert(r["bert_label"])
    ][:10]

    return {
        "compared": total,
        "agreement_pct": round(agreement * 100 / total, 1),
        "agree": agreement,
        "disagree": total - agreement,
        "label_accuracy_vader_pct": round(correct_vader * 100 / len(labeled), 1) if labeled else None,
        "labeled_examples": len(labeled),
        "disagreement_examples": disagreements,
    }


# ---------------------------------------------------------------------------
# Link analysis (paste a YouTube/Reddit URL -> fetch its comments -> Kafka)
# ---------------------------------------------------------------------------

class AnalyzeRequest(BaseModel):
    url: str
    mode: str = "auto"        # auto | paste
    limit: int = 100
    title: str | None = None  # only for paste mode


class AnalyzeStatus:
    """In-memory registry of analyzed posts (last 100)."""

    def __init__(self):
        self.posts: dict[str, dict] = {}

    def add(self, post_id: str, info: dict):
        self.posts[post_id] = {**info, "analyzed_at": datetime.now(timezone.utc).isoformat()}
        if len(self.posts) > 100:
            oldest = min(self.posts, key=lambda k: self.posts[k]["analyzed_at"])
            del self.posts[oldest]


ANALYZED = AnalyzeStatus()


@app.post("/api/analyze")
def analyze(req: AnalyzeRequest):
    """Fetch comments for a post URL (or pasted text) and push them into the pipeline."""
    import fetchers
    import publisher

    try:
        result = fetchers.fetch(req.url, mode=req.mode, limit=min(req.limit, 500))
    except ValueError as exc:
        return {"status": "error", "message": str(exc)}
    except Exception as exc:
        return {"status": "error", "message": f"fetch failed: {exc}"}

    if not result["comments"]:
        return {"status": "error", "message": "No comments found for that post"}

    sent = publisher.publish_comments(result["comments"])
    ANALYZED.add(result["post_id"], {
        "post_id": result["post_id"],
        "post_title": result["post_title"],
        "source": result["source"],
        "requested_url": req.url if req.mode != "paste" else None,
        "comments_fetched": len(result["comments"]),
        "comments_published": sent,
    })
    return {
        "status": "ok",
        "post_id": result["post_id"],
        "post_title": result["post_title"],
        "source": result["source"],
        "comments_fetched": len(result["comments"]),
        "comments_published": sent,
        "note": "Comments are streaming through Kafka -> Spark; scores appear in ~30-60s. "
                "Filter the live feed by this post, or check GET /api/posts.",
    }


@app.get("/api/posts")
def posts():
    """Analyzed posts (URL/paste ingests) with their live sentiment summary."""
    out = []
    with db() as conn, conn.cursor() as cur:
        for post_id, info in ANALYZED.posts.items():
            cur.execute(
                """
                SELECT count(*) AS total,
                       count(*) FILTER (WHERE vader_label = 'positive') AS positive,
                       count(*) FILTER (WHERE vader_label = 'negative') AS negative,
                       count(*) FILTER (WHERE vader_label = 'neutral')  AS neutral,
                       avg(vader_score) AS avg_score
                FROM comments WHERE post_id = %s
                """,
                (post_id,),
            )
            row = dict(cur.fetchone())
            total = row["total"] or 0
            out.append({
                **info,
                "scored": total,
                "sentiment": {
                    "positive": row["positive"] or 0,
                    "negative": row["negative"] or 0,
                    "neutral": row["neutral"] or 0,
                    "positive_pct": round((row["positive"] or 0) * 100 / total, 1) if total else 0,
                    "negative_pct": round((row["negative"] or 0) * 100 / total, 1) if total else 0,
                    "neutral_pct": round((row["neutral"] or 0) * 100 / total, 1) if total else 0,
                },
                "avg_vader_score": round(float(row["avg_score"]), 3) if row["avg_score"] is not None else None,
            })
    out.sort(key=lambda p: p["analyzed_at"], reverse=True)
    return {"posts": out, "count": len(out)}


# ---------------------------------------------------------------------------
# Trending velocity: words + hashtags growing fastest (recent vs previous half)
# ---------------------------------------------------------------------------

HASHTAG_RE = re.compile(r"#\w{2,}")


@app.get("/api/trends")
def trends(limit: int = Query(10, ge=3, le=30)):
    """Hashtags/words whose mention velocity is rising (recent window vs before)."""
    with db() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT cleaned_text, ts,
                   (ts >= now() - interval '30 minutes') AS recent
            FROM comments
            WHERE ts >= now() - interval '60 minutes'
            """
        )
        rows = [dict(r) for r in cur.fetchall()]

    recent_tags, older_tags = Counter(), Counter()
    recent_words, older_words = Counter(), Counter()
    for row in rows:
        text = row["cleaned_text"] or ""
        tags = set(HASHTAG_RE.findall(text))
        words_set = {w for w in re.findall(r"[a-z']{3,}", text) if w not in STOPWORDS}
        if row["recent"]:
            recent_tags.update(tags)
            recent_words.update(words_set)
        else:
            older_tags.update(tags)
            older_words.update(words_set)

    def velocity(recent: Counter, older: Counter) -> list[dict]:
        all_terms = set(recent) | set(older)
        scored = []
        for term in all_terms:
            r, o = recent[term], older[term]
            growth = (r - o) / max(o, 1)
            score = r * (1 + max(growth, 0))  # volume-weighted growth
            scored.append({"term": term, "recent": r, "previous": o, "growth_pct": round(growth * 100, 1), "score": round(score, 2)})
        scored.sort(key=lambda x: -x["score"])
        return scored[:limit]

    return {
        "hashtags": velocity(recent_tags, older_tags),
        "words": velocity(recent_words, older_words),
        "recent_window_minutes": 30,
        "total_recent": sum(recent_tags.values()) + sum(recent_words.values()) // 2,
    }


# ---------------------------------------------------------------------------
# Negative-spike alert
# ---------------------------------------------------------------------------

@app.get("/api/alerts")
def alerts():
    """Detect a negative-sentiment spike: latest window vs trailing average."""
    with db() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT window_start, total, negative, pos_pct, neg_pct, neu_pct
            FROM window_stats ORDER BY window_start DESC LIMIT 6
            """
        )
        rows = [dict(r) for r in cur.fetchall()]

    if len(rows) < 2:
        return {"alert": False, "reason": "not enough windows yet"}

    latest, baseline_rows = rows[0], rows[1:]
    baseline_neg = sum(r["neg_pct"] or 0 for r in baseline_rows) / len(baseline_rows)
    latest_neg = latest["neg_pct"] or 0
    jump = latest_neg - baseline_neg

    alert = jump >= 10 and latest["total"] >= 5
    return {
        "alert": alert,
        "latest_window": latest["window_start"].isoformat(),
        "latest_neg_pct": latest_neg,
        "baseline_neg_pct": round(baseline_neg, 1),
        "jump_pct": round(jump, 1),
        "threshold": "+10 points vs trailing average, min 5 comments",
        "message": (
            f"Negative sentiment spiked to {latest_neg}% (baseline {round(baseline_neg, 1)}%, +{round(jump, 1)} pts)"
            if alert else None
        ),
    }


# ---------------------------------------------------------------------------
# CSV export of filtered comments
# ---------------------------------------------------------------------------

@app.get("/api/export")
def export_csv(
    source: str | None = None,
    sentiment: str | None = None,
    q: str | None = None,
    post_id: str | None = None,
    limit: int = Query(1000, ge=1, le=10000),
):
    """Download scored comments (current filters) as CSV."""
    clauses, params = ["1=1"], []
    if source:
        clauses.append("source = %s"); params.append(source)
    if sentiment:
        clauses.append("vader_label = %s"); params.append(sentiment)
    if q:
        clauses.append("(text ILIKE %s OR cleaned_text ILIKE %s)"); params += [f"%{q}%", f"%{q}%"]
    if post_id:
        clauses.append("post_id = %s"); params.append(post_id)

    with db() as conn, conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT id, source, author, text, label, vader_label, vader_score,
                   vader_positive, vader_negative, vader_neutral, bert_label, bert_score, ts
            FROM comments WHERE {' AND '.join(clauses)}
            ORDER BY ts DESC NULLS LAST LIMIT %s
            """,
            (*params, limit),
        )
        rows = cur.fetchall()

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["id", "source", "author", "text", "dataset_label", "vader_label", "vader_score",
                     "vader_pos", "vader_neg", "vader_neu", "bert_label", "bert_score", "ts"])
    for row in rows:
        writer.writerow([c.isoformat() if hasattr(c, "isoformat") else c for c in row])
    buffer.seek(0)

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=sentiment-export-{stamp}.csv"},
    )


# ---------------------------------------------------------------------------
# Spam/junk heuristic (cheap, explainable — flags promotional junk)
# ---------------------------------------------------------------------------

SPAM_MARKERS = ("http", "www.", "subscribe", "sub for", "check my", "follow me", "free ",
                "giveaway", "promo", "discount", "click link", "earn money", "crypto", "dm me")
URL_RE = re.compile(r"(https?://|www\.)\S+")
REPEAT_RE = re.compile(r"(.)\1{4,}")  # aaaaa


def spam_score(text: str) -> dict:
    """0..1 heuristic spam likelihood + the reason it was flagged."""
    t = (text or "").lower()
    score, reasons = 0.0, []
    urls = len(URL_RE.findall(t))
    if urls >= 2:
        score += 0.4; reasons.append("multiple links")
    elif urls == 1:
        score += 0.15; reasons.append("contains link")
    hits = sum(1 for m in SPAM_MARKERS if m in t)
    if hits >= 2:
        score += 0.4; reasons.append("promo phrases")
    elif hits == 1:
        score += 0.2; reasons.append("promo phrase")
    if len(t) > 0 and sum(c.isdigit() for c in t) / len(t) > 0.4:
        score += 0.2; reasons.append("digit-heavy")
    if REPEAT_RE.search(t):
        score += 0.2; reasons.append("repeated chars")
    if t.isupper() and len(t) > 20:
        score += 0.2; reasons.append("all caps")
    return {"spam_score": round(min(score, 1.0), 2), "spam_reasons": reasons, "is_spam": score >= 0.5}


@app.get("/api/comments/{comment_id}/spam")
def comment_spam(comment_id: str):
    """Spam check for a single stored comment."""
    with db() as conn, conn.cursor() as cur:
        cur.execute("SELECT text FROM comments WHERE id = %s", (comment_id,))
        row = cur.fetchone()
    if not row:
        return {"error": "not found"}
    return {"id": comment_id, **spam_score(row["text"])}


@app.get("/api/spam")
def spam_summary(limit: int = Query(500, ge=10, le=5000)):
    """Spam breakdown across recent comments."""
    with db() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT id, text, source, vader_label FROM comments ORDER BY ts DESC NULLS LAST LIMIT %s",
            (limit,),
        )
        rows = [dict(r) for r in cur.fetchall()]

    flagged = []
    per_source = Counter()
    for row in rows:
        check = spam_score(row["text"])
        if check["is_spam"]:
            per_source[row["source"]] += 1
            flagged.append({"id": row["id"], "source": row["source"], "text": row["text"][:120],
                            "spam_score": check["spam_score"], "reasons": check["spam_reasons"]})

    return {
        "checked": len(rows),
        "spam_count": len(flagged),
        "spam_pct": round(len(flagged) * 100 / len(rows), 1) if rows else 0,
        "per_source": dict(per_source),
        "examples": flagged[:10],
    }
