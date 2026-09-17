"""FastAPI service — read endpoints over the processed data in PostgreSQL.

Run:
    .venv/bin/uvicorn api.main:app --reload --port 8000
Docs:
    http://localhost:8000/docs
"""

import os
import re
from collections import Counter

import psycopg2
import psycopg2.extras
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware

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
                   count(*) FILTER (WHERE source = 'reddit')   AS reddit,
                   count(*) FILTER (WHERE source = 'youtube')  AS youtube,
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
        "sources": {"reddit": row["reddit"] or 0, "youtube": row["youtube"] or 0},
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
    source: str | None = Query(None, description="reddit | youtube"),
    sentiment: str | None = Query(None, description="positive | negative | neutral"),
    q: str | None = Query(None, description="substring search in text"),
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

    with db() as conn, conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT id, source, author, text, label, vader_label, vader_score,
                   bert_label, bert_score, ts
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
