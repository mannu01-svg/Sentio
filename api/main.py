"""FastAPI service — read endpoints over the processed data in PostgreSQL,
plus the /api/analyze ingestion trigger for link-based analysis.

Run:
    .venv/bin/uvicorn api.main:app --reload --port 8000
Docs:
    http://localhost:8000/docs
"""

import csv
import io
import json
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
# Auth: signup + login backed by the users table in PostgreSQL
# ---------------------------------------------------------------------------

import hashlib
import hmac
import secrets
import time as _time

PBKDF2_ITERATIONS = 120_000


def _hash_password(password: str, salt: str | None = None) -> str:
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), PBKDF2_ITERATIONS)
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${salt}${digest.hex()}"


def _verify_password(password: str, stored: str) -> bool:
    try:
        algo, iters, salt, hexdigest = stored.split("$")
        if algo != "pbkdf2_sha256":
            return False
        digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), int(iters))
        return hmac.compare_digest(digest.hex(), hexdigest)
    except (ValueError, AttributeError):
        return False


def _make_token(email: str) -> str:
    stamp = str(_time.time())
    digest = hashlib.sha256(f"{email}:{stamp}:{secrets.token_hex(8)}".encode()).hexdigest()[:24]
    return f"sentio_{digest}_{int(float(stamp))}"


class SignupRequest(BaseModel):
    name: str
    email: str
    password: str


class LoginRequest(BaseModel):
    email: str
    password: str


def _validate(email: str, password: str, name: str | None = None) -> str | None:
    if name is not None and not (1 <= len(name.strip()) <= 60):
        return "Name must be 1-60 characters"
    if "@" not in email or "." not in email.split("@")[-1]:
        return "Enter a valid email address"
    if len(password) < 6:
        return "Password must be at least 6 characters"
    return None


@app.post("/api/signup")
def signup(req: SignupRequest):
    """Create an account (name + email + password) in the users table."""
    email = req.email.strip().lower()
    name = req.name.strip()
    error = _validate(email, req.password, name)
    if error:
        return {"status": "error", "message": error}
    try:
        with db() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO users (email, name, password_hash)
                VALUES (%s, %s, %s)
                ON CONFLICT (email) DO UPDATE
                SET name = EXCLUDED.name, password_hash = EXCLUDED.password_hash
                RETURNING email, name
                """,
                (email, name, _hash_password(req.password)),
            )
            row = cur.fetchone()
    except psycopg2.Error as exc:
        return {"status": "error", "message": f"Could not create account: {exc}"}
    return {
        "status": "ok",
        "token": _make_token(email),
        "user": {"email": row["email"], "name": row["name"]},
        "note": "Account created and signed in",
    }


@app.post("/api/login")
def login(req: LoginRequest):
    """Verify credentials against the users table."""
    email = req.email.strip().lower()
    error = _validate(email, req.password)
    if error and "email" not in error:
        return {"status": "error", "message": error}
    if "@" not in email:
        return {"status": "error", "message": "Enter a valid email address"}
    try:
        with db() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT email, name, password_hash FROM users WHERE email = %s",
                (email,),
            )
            row = cur.fetchone()
            if not row or not _verify_password(req.password, row["password_hash"]):
                return {"status": "error", "message": "Invalid email or password"}
            cur.execute(
                "UPDATE users SET last_login = NOW() WHERE email = %s", (email,)
            )
    except psycopg2.Error as exc:
        return {"status": "error", "message": f"Login failed: {exc}"}
    return {
        "status": "ok",
        "token": _make_token(email),
        "user": {"email": row["email"], "name": row["name"]},
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


# ---------------------------------------------------------------------------
# Live stream control: the producer idles until a control file asks for a burst
# ---------------------------------------------------------------------------

CONTROL_PATH = os.getenv(
    "LIVE_CONTROL",
    os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "logs", "live-stream.json")),
)


def _control_until() -> tuple[float, int]:
    try:
        with open(CONTROL_PATH) as handle:
            data = json.load(handle)
        return float(data.get("until", 0)), int(data.get("rate", 40))
    except Exception:
        return 0.0, 40


class LiveStreamRequest(BaseModel):
    minutes: float = 3.0   # burst duration
    rate: int = 40         # messages per second


@app.post("/api/stream/live")
def stream_live(req: LiveStreamRequest):
    """Tell the producer to start streaming a high-rate live burst.

    The producer process watches logs/live-stream.json; we write
    {"until": <epoch>, "rate": N} and it streams until that timestamp.
    """
    minutes = min(max(req.minutes, 0.5), 30.0)
    rate = min(max(req.rate, 5), 120)
    until = _time.time() + minutes * 60
    current_until, _ = _control_until()
    os.makedirs(os.path.dirname(CONTROL_PATH), exist_ok=True)
    with open(CONTROL_PATH, "w") as handle:
        json.dump({"until": max(until, current_until), "rate": rate}, handle)
    return {
        "status": "ok",
        "live": True,
        "rate": rate,
        "duration_minutes": minutes,
        "until": until,
        "ends_at": datetime.fromtimestamp(until).strftime("%H:%M:%S"),
        "note": f"Producer is streaming at {rate}/s for {minutes:g} min — counters are climbing",
    }


@app.post("/api/stream/stop")
def stream_stop():
    """End the live burst immediately (producer goes back to idle)."""
    with open(CONTROL_PATH, "w") as handle:
        json.dump({"until": _time.time(), "rate": 0}, handle)
    return {"status": "ok", "live": False, "note": "Live burst stopped — producer is idle"}


@app.get("/api/stream/status")
def stream_status():
    """Whether the producer is currently mid-burst (powers the Go-live button)."""
    until, rate = _control_until()
    live = until > _time.time()
    return {"live": live, "rate": rate, "until": until,
            "seconds_left": round(until - _time.time()) if live else 0}


@app.get("/api/summary")
def summary():
    """KPI cards: totals, sentiment split (LLM — the authoritative score), coverage."""
    with db() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT count(*) AS total,
                   count(*) FILTER (WHERE llm_label = 'positive') AS positive,
                   count(*) FILTER (WHERE llm_label = 'negative') AS negative,
                   count(*) FILTER (WHERE llm_label = 'neutral')  AS neutral,
                   count(*) FILTER (WHERE vader_label IS NOT NULL) AS vader_scored,
                   count(*) FILTER (WHERE bert_label IS NOT NULL) AS bert_scored,
                   count(*) FILTER (WHERE llm_label IS NOT NULL) AS llm_scored,
                   count(*) FILTER (WHERE source = 'reddit')    AS reddit,
                   count(*) FILTER (WHERE source = 'youtube')   AS youtube,
                   count(*) FILTER (WHERE source = 'instagram') AS instagram,
                   count(*) FILTER (WHERE source = 'facebook')  AS facebook,
                   count(*) FILTER (WHERE source = 'x')         AS x,
                   count(*) FILTER (WHERE source = 'threads')   AS threads,
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
        "scorer": "llm",
        "vader_scored": row["vader_scored"] or 0,
        "bert_scored": row["bert_scored"] or 0,
        "llm_scored": row["llm_scored"] or 0,
        "sources": {
            "reddit": row["reddit"] or 0,
            "youtube": row["youtube"] or 0,
            "instagram": row["instagram"] or 0,
            "facebook": row["facebook"] or 0,
            "x": row["x"] or 0,
            "threads": row["threads"] or 0,
        },
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
        clauses.append("llm_label = %s")
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
                   bert_label, bert_score, llm_label, llm_score, ts, post_id
            FROM comments
            WHERE {' AND '.join(clauses)}
            ORDER BY processed_at DESC, ts DESC NULLS LAST
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
        clauses.append("llm_label = %s")
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
    """3-way model comparison: VADER (lexicon) vs DistilBERT (SST-2) vs LLM (tweet-RoBERTa).

    The LLM (cardiffnlp, trained on 124M tweets) is the authoritative score;
    agreement and per-model accuracy are reported against it.
    """
    with db() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT vader_label, bert_label, llm_label, label, vader_score, text
            FROM comments
            WHERE vader_label IS NOT NULL AND llm_label IS NOT NULL
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
        return label

    bert_rows = [r for r in rows if r["bert_label"]]
    bert_agree_llm = sum(1 for r in bert_rows if r["bert_label"] == r["llm_label"])
    vader_agree_llm = sum(1 for r in rows if r["vader_label"] == r["llm_label"])
    all_three = sum(
        1 for r in rows
        if r["bert_label"] and r["vader_label"] == r["bert_label"] == r["llm_label"]
    )
    labeled = [r for r in rows if r["label"]]
    correct_vader = sum(
        1 for r in labeled if r["label"].lower().startswith(r["vader_label"][:4])
    )
    correct_llm = sum(
        1 for r in labeled if r["llm_label"].startswith(r["label"].lower()[:4])
    )
    # examples where the LLM corrects VADER (the strongest demo material)
    corrections = [
        {"text": r["text"][:200], "vader": r["vader_label"], "llm": r["llm_label"],
         "vader_score": r["vader_score"]}
        for r in rows if r["vader_label"] != r["llm_label"]
    ][:10]

    return {
        "compared": total,
        "models": ["vader", "bert", "llm"],
        "vader_vs_llm_agreement_pct": round(vader_agree_llm * 100 / total, 1),
        "bert_vs_llm_agreement_pct": round(bert_agree_llm * 100 / len(bert_rows), 1) if bert_rows else None,
        "all_three_agreement_pct": round(all_three * 100 / total, 1),
        "agree_vader_llm": vader_agree_llm,
        "disagree_vader_llm": total - vader_agree_llm,
        "label_accuracy_vader_pct": round(correct_vader * 100 / len(labeled), 1) if labeled else None,
        "label_accuracy_llm_pct": round(correct_llm * 100 / len(labeled), 1) if labeled else None,
        "labeled_examples": len(labeled),
        "llm_corrections": corrections,
        "note": "LLM = cardiffnlp twitter-roberta (124M tweets) — authoritative social-media score",
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


def _sentiment_select(label_col: str = "llm_label") -> str:
    """Shared aggregate fragment: counts + pcts for one label column."""
    return f"""
            count(*) AS total,
            count(*) FILTER (WHERE {label_col} = 'positive') AS positive,
            count(*) FILTER (WHERE {label_col} = 'negative') AS negative,
            count(*) FILTER (WHERE {label_col} = 'neutral')  AS neutral,
            avg(llm_score) AS avg_score
    """


def _sentiment_payload(row: dict) -> dict:
    total = row["total"] or 0
    return {
        "positive": row["positive"] or 0,
        "negative": row["negative"] or 0,
        "neutral": row["neutral"] or 0,
        "positive_pct": round((row["positive"] or 0) * 100 / total, 1) if total else 0,
        "negative_pct": round((row["negative"] or 0) * 100 / total, 1) if total else 0,
        "neutral_pct": round((row["neutral"] or 0) * 100 / total, 1) if total else 0,
    }


@app.get("/api/posts")
def posts():
    """Analyzed posts (URL/paste ingests) with their live sentiment summary."""
    out = []
    with db() as conn, conn.cursor() as cur:
        for post_id, info in ANALYZED.posts.items():
            cur.execute(
                f"SELECT {_sentiment_select()} FROM comments WHERE post_id = %s",
                (post_id,),
            )
            row = dict(cur.fetchone())
            total = row["total"] or 0
            out.append({
                **info,
                "scored": total,
                "sentiment": _sentiment_payload(row),
                "avg_score": round(float(row["avg_score"]), 3) if row["avg_score"] is not None else None,
            })
    out.sort(key=lambda p: p["analyzed_at"], reverse=True)
    return {"posts": out, "count": len(out)}


# ---------------------------------------------------------------------------
# Account-level analysis (fetch every comment across an account's posts)
# ---------------------------------------------------------------------------

class AnalyzeAccountRequest(BaseModel):
    platform: str            # youtube | reddit
    handle: str
    limit: int = 100         # comments per post
    max_videos: int = 5      # youtube only: how many recent videos


ACCOUNTS = {}  # account_key -> {platform, handle, posts: [post_id...], analyzed_at}


@app.post("/api/analyze-account")
def analyze_account(req: AnalyzeAccountRequest):
    """Fetch every comment across an account's recent posts and push them into the pipeline."""
    import fetchers
    import publisher

    try:
        posts = fetchers.fetch_account(
            req.platform, req.handle,
            limit=min(req.limit, 500), max_videos=min(req.max_videos, 10),
        )
    except ValueError as exc:
        return {"status": "error", "message": str(exc)}
    except Exception as exc:
        return {"status": "error", "message": f"account fetch failed: {exc}"}

    account_key = f"{req.platform.lower()}:{req.handle.strip().lstrip('@').lower()}"
    published_total, post_infos = 0, []
    for post in posts:
        sent = publisher.publish_comments(post["comments"])
        published_total += sent
        info = {
            "post_id": post["post_id"],
            "post_title": post["post_title"],
            "source": post["source"],
            "comments_fetched": len(post["comments"]),
            "comments_published": sent,
        }
        ANALYZED.add(post["post_id"], info)
        post_infos.append(info)

    ACCOUNTS[account_key] = {
        "platform": req.platform.lower(),
        "handle": req.handle,
        "posts": [p["post_id"] for p in post_infos],
        "analyzed_at": datetime.now(timezone.utc).isoformat(),
    }

    return {
        "status": "ok",
        "account_key": account_key,
        "platform": req.platform.lower(),
        "handle": req.handle,
        "posts_analyzed": len(post_infos),
        "comments_fetched": sum(p["comments_fetched"] for p in post_infos),
        "comments_published": published_total,
        "post_ids": [p["post_id"] for p in post_infos],
        "note": "Comments are streaming through Kafka -> Spark; account scores appear in ~30-60s.",
    }


@app.get("/api/accounts")
def accounts():
    """Recently analyzed accounts with aggregate sentiment across all their posts."""
    out = []
    with db() as conn, conn.cursor() as cur:
        for key, info in ACCOUNTS.items():
            if not info["posts"]:
                continue
            placeholders = ",".join(["%s"] * len(info["posts"]))
            cur.execute(
                f"""
                SELECT {_sentiment_select()}
                FROM comments WHERE post_id IN ({placeholders})
                """,
                info["posts"],
            )
            row = dict(cur.fetchone())
            total = row["total"] or 0
            out.append({
                **info,
                "account_key": key,
                "scored": total,
                "posts_count": len(info["posts"]),
                "sentiment": _sentiment_payload(row),
                "avg_score": round(float(row["avg_score"]), 3) if row["avg_score"] is not None else None,
            })
    out.sort(key=lambda a: a["analyzed_at"], reverse=True)
    return {"accounts": out, "count": len(out)}


# ---------------------------------------------------------------------------
# Threads OAuth: consent URL + code exchange + connection status
# ---------------------------------------------------------------------------

def _persist_env(key: str, value: str):
    """Persist KEY=value into .env.local (idempotent, keeps comments/other lines)."""
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".env.local")
    env_path = os.path.normpath(env_path)
    lines = []
    if os.path.exists(env_path):
        with open(env_path) as f:
            lines = f.read().splitlines()
    replaced = False
    for i, line in enumerate(lines):
        if line.strip().startswith(f"{key}="):
            lines[i] = f"{key}={value}"
            replaced = True
            break
    if not replaced:
        if lines and lines[-1].strip():
            lines.append("")
        lines.append(f"{key}={value}")
    with open(env_path, "w") as f:
        f.write("\n".join(lines) + "\n")
    os.environ[key] = value


@app.get("/api/threads/auth-url")
def threads_auth_url():
    """Consent URL for the Threads OAuth flow (future scope — needs app creds)."""
    import fetchers
    try:
        return {"status": "ok", "url": fetchers.threads_auth_url(), "redirect_uri": fetchers.threads_redirect_uri()}
    except ValueError as exc:
        return {"status": "error", "message": f"Threads OAuth not configured: {exc}"}


@app.get("/api/threads/status")
def threads_status():
    """Threads connection state: configured (app creds present) + connected (token valid)."""
    import fetchers
    configured = bool(os.getenv("THREADS_APP_ID") and os.getenv("THREADS_APP_SECRET"))
    if not os.getenv("THREADS_ACCESS_TOKEN"):
        return {"status": "ok", "configured": configured, "connected": False,
                "reason": None if configured else "future scope — THREADS_APP_ID/SECRET not configured"}
    try:
        import requests as _rq
        me = _rq.get(
            f"{fetchers.THREADS_API}/me",
            params={"fields": "id,username", "access_token": os.getenv("THREADS_ACCESS_TOKEN")},
            timeout=15,
        )
        data = me.json() if me.status_code == 200 else {}
        if data.get("id"):
            return {"status": "ok", "configured": True, "connected": True, "username": data.get("username"), "user_id": data.get("id")}
        return {"status": "ok", "configured": configured, "connected": False, "reason": "token invalid/expired — reconnect"}
    except Exception as exc:
        return {"status": "ok", "configured": configured, "connected": False, "reason": str(exc)}


@app.get("/api/threads/callback")
def threads_callback(code: str | None = None, error: str | None = None):
    """OAuth redirect target: exchange ?code= for a long-lived token, persist it."""
    import fetchers
    if error:
        return {"status": "error", "message": f"OAuth denied: {error}"}
    if not code:
        return {"status": "error", "message": "No authorization code in callback"}
    try:
        result = fetchers.threads_exchange_code(code)
        _persist_env("THREADS_ACCESS_TOKEN", result["access_token"])
        return {
            "status": "ok",
            "connected": True,
            "expires_in": result.get("expires_in"),
            "note": "Token persisted to .env.local — account analysis is now unlocked",
        }
    except ValueError as exc:
        return {"status": "error", "message": str(exc)}


@app.post("/api/threads/disconnect")
def threads_disconnect():
    """Remove the stored Threads token."""
    _persist_env("THREADS_ACCESS_TOKEN", "")
    return {"status": "ok", "connected": False}


# ---------------------------------------------------------------------------
# Trending velocity: words + hashtags growing fastest (recent vs previous half)
# ---------------------------------------------------------------------------

HASHTAG_RE = re.compile(r"#\w{2,}")


@app.get("/api/trends")
def trends(limit: int = Query(10, ge=3, le=30), source: str | None = Query(None, description="youtube | x | reddit")):
    """Hashtags/words whose mention velocity is rising (recent window vs before).

    Falls back to a 24h lookback when the stream has been idle, so the tab
    always shows meaningful rising terms instead of going empty.
    """
    clauses, params = ["1=1"], []
    if source and source != "all":
        clauses.append("source = %s")
        params.append(source)
    where = " AND ".join(clauses)

    with db() as conn, conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT cleaned_text, ts,
                   (ts >= now() - interval '30 minutes') AS recent
            FROM comments
            WHERE {where} AND ts >= now() - interval '60 minutes'
            """,
            params,
        )
        rows = [dict(r) for r in cur.fetchall()]
        lookback_minutes = 60
        if len(rows) < 60:  # stream idle — widen to 24h so trends stay alive
            cur.execute(
                f"""
                SELECT cleaned_text, ts,
                       (ts >= now() - interval '12 hours') AS recent
                FROM comments
                WHERE {where} AND ts >= now() - interval '24 hours'
                """,
                params,
            )
            widened = [dict(r) for r in cur.fetchall()]
            if len(widened) > len(rows):
                rows = widened
                lookback_minutes = 1440

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
        "lookback_minutes": lookback_minutes,
        "source": source or "all",
        "total_recent": sum(recent_tags.values()) + sum(recent_words.values()) // 2,
    }


# ---------------------------------------------------------------------------
# Per-source trending topics: top keywords per platform (youtube / x / reddit)
# Powers the Dashboard "Trending topics" cards — click one -> live topic stream.
# ---------------------------------------------------------------------------

@app.get("/api/trending")
def trending(source: str | None = Query(None, description="youtube | x | reddit | all"), limit: int = Query(8, ge=3, le=20)):
    """Top topics per source: keyword frequency over the source's full stored history.

    Real counts (not a sample) + a 2x fresh boost for mentions in the last 30 min,
    so numbers stay meaningful and shift as the stream flows.
    """
    sources = [source] if source and source != "all" else ["youtube", "x", "reddit"]
    out = {}
    with db() as conn, conn.cursor() as cur:
        for src in sources:
            cur.execute(
                """
                SELECT cleaned_text,
                       (ts >= now() - interval '30 minutes') AS fresh
                FROM comments
                WHERE source = %s AND cleaned_text IS NOT NULL
                """,
                (src,),
            )
            rows = cur.fetchall()
            total_comments = len(rows)
            words = Counter()
            fresh_words = Counter()
            for row in rows:
                text, fresh = row["cleaned_text"], row["fresh"]
                for w in set(re.findall(r"[a-z']{4,}", text or "")):
                    if w in STOPWORDS:
                        continue
                    words[w] += 1
                    if fresh:
                        fresh_words[w] += 1
            # score: real volume + fresh boost (recent mentions count double)
            scored = [
                {"topic": w, "count": c, "fresh": fresh_words[w],
                 "share_pct": round(c * 100 / total_comments, 1) if total_comments else 0,
                 "score": round(c + fresh_words[w] * 2, 2)}
                for w, c in words.items() if c >= 3
            ]
            scored.sort(key=lambda x: -x["score"])
            out[src] = scored[:limit]
            out[f"{src}_comments"] = total_comments
    return {"trending": out, "sources": sources}


class TopicStreamRequest(BaseModel):
    topic: str
    source: str = "youtube"   # youtube | x | reddit
    limit: int = 100          # comments to pull per post/video


TOPIC_STREAMS = {}  # topic_key -> {source, topic, posts: [...], started_at}


@app.post("/api/topics/stream")
def topics_stream(req: TopicStreamRequest):
    """Click a trending topic -> fetch a fresh batch of real comments about it -> Kafka.

    youtube: yt-dlp flat search (fast, keyless) -> comments of the top videos
    reddit / x: pick fresh posts about the topic from the dataset replay pool
                (their public APIs are bot-walled / paid), publish matching comments
    """
    import fetchers
    import publisher

    topic = req.topic.strip()
    if not topic or len(topic) < 3:
        return {"status": "error", "message": "Topic must be at least 3 characters"}
    source = (req.source or "youtube").lower()
    if source not in ("youtube", "x", "reddit"):
        return {"status": "error", "message": f"Topic streaming supports youtube, x, reddit (got {source!r})"}

    published_total, post_infos = 0, []
    stream_note = ""

    if source == "youtube":
        # 1) flat-search YouTube for the topic (no API key, ~2-4s)
        ytdlp_bin = fetchers._ytdlp_bin()
        import subprocess
        raw = subprocess.run(
            [ytdlp_bin, "--flat-playlist", "--no-warnings", "--playlist-end", "3",
             "--print", "%(id)s|%(title)s", f"ytsearch3:{topic}"],
            capture_output=True, text=True, timeout=60,
        )
        if raw.returncode != 0:
            return {"status": "error", "message": f"YouTube search failed: {raw.stderr.strip()[:150]}"}
        videos = []
        for line in raw.stdout.splitlines():
            line = line.strip()
            if "|" in line and len(line.split("|", 1)[0]) == 11:
                vid, vtitle = line.split("|", 1)
                videos.append((vid, vtitle))
        if not videos:
            return {"status": "error", "message": f"No YouTube videos found for topic '{topic}'"}

        # 2) fetch comments for the top videos (~5s each)
        for vid, vtitle in videos:
            try:
                post = fetchers.fetch_youtube(f"https://www.youtube.com/watch?v={vid}", limit=min(req.limit, 200))
                if not post["comments"]:
                    continue
                sent = publisher.publish_comments(post["comments"])
                published_total += sent
                info = {"post_id": post["post_id"], "post_title": post["post_title"],
                        "source": "youtube", "comments_fetched": len(post["comments"]),
                        "comments_published": sent}
                ANALYZED.add(post["post_id"], info)
                post_infos.append(info)
            except Exception:
                continue  # skip videos whose comments are off
        stream_note = "fresh YouTube videos + their comments via yt-dlp (keyless)"

    else:
        # reddit / x: their public APIs are bot-walled (403/521) or paid —
        # stream FRESH dataset comments matching the topic (real comments, live-scored)
        topic_words = {w for w in re.findall(r"[a-z']{3,}", topic.lower())}
        with db() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, author, text, post_id, post_title, ts
                FROM comments
                WHERE source = %s
                ORDER BY ts DESC NULLS LAST
                LIMIT 8000
                """,
                (source,),
            )
            rows = cur.fetchall()
        matches = []
        seen_texts = set()
        for row in rows:
            cid, author = row["id"], row["author"]
            text, pid, ptitle, ts = row["text"], row["post_id"], row["post_title"], row["ts"]
            tl = (text or "").lower()
            if not tl or tl in seen_texts:
                continue
            hits = sum(1 for w in topic_words if w in tl)
            if hits >= 1:
                matches.append((cid, author, text, pid, ptitle, ts))
                seen_texts.add(tl)
                if len(matches) >= min(req.limit, 200):
                    break
        if not matches:
            return {"status": "error", "message": f"No {source} comments about '{topic}' in the pool — try another topic"}

        # publish as a fresh live batch under a topic post id
        topic_post_id = f"topic-{source}-{re.sub(r'[^a-z0-9]+', '-', topic.lower())[:40]}-{uuid.uuid4().hex[:6]}"
        now_iso = datetime.now().isoformat(timespec="seconds")
        comments = [
            {
                "id": f"{topic_post_id}-{i}",
                "source": source,
                "author": author or "anonymous",
                "text": text,
                "post_id": topic_post_id,
                "post_title": f"Topic: {topic}",
                "label": None,
                "ts": now_iso,
            }
            for i, (cid, author, text, pid, ptitle, ts) in enumerate(matches)
        ]
        sent = publisher.publish_comments(comments)
        published_total = sent
        info = {"post_id": topic_post_id, "post_title": f"Topic: {topic}",
                "source": source, "comments_fetched": len(comments),
                "comments_published": sent}
        ANALYZED.add(topic_post_id, info)
        post_infos.append(info)
        stream_note = "topic-matched comments from the live replay pool (real comments, re-scored fresh)"

    if not post_infos:
        return {"status": "error", "message": f"Could not fetch comments for topic '{topic}'"}

    topic_key = f"{source}:{topic.lower()}"
    TOPIC_STREAMS[topic_key] = {
        "source": source, "topic": topic,
        "posts": [p["post_id"] for p in post_infos],
        "started_at": datetime.now(timezone.utc).isoformat(),
    }
    return {
        "status": "ok",
        "topic": topic,
        "source": source,
        "posts_analyzed": len(post_infos),
        "comments_published": published_total,
        "post_ids": [p["post_id"] for p in post_infos],
        "stream_note": stream_note,
        "note": "Comments are streaming through Kafka -> Spark; live scores appear in ~30-60s. "
                "Open the topic stream page for the real-time feed.",
    }


@app.get("/api/topics/streams")
def topics_streams():
    """Recently started topic streams with their live sentiment."""
    out = []
    with db() as conn, conn.cursor() as cur:
        for key, info in TOPIC_STREAMS.items():
            if not info["posts"]:
                continue
            placeholders = ",".join(["%s"] * len(info["posts"]))
            cur.execute(
                f"""
                SELECT {_sentiment_select()}
                FROM comments WHERE post_id IN ({placeholders})
                """,
                info["posts"],
            )
            row = dict(cur.fetchone())
            total = row["total"] or 0
            out.append({
                **info,
                "stream_key": key,
                "scored": total,
                "sentiment": _sentiment_payload(row),
                "avg_score": round(float(row["avg_score"]), 3) if row["avg_score"] is not None else None,
            })
    out.sort(key=lambda s: s["started_at"], reverse=True)
    return {"streams": out, "count": len(out)}


# ---------------------------------------------------------------------------
# Keyword search: enter any word -> fetch every matching comment -> analyze
# ---------------------------------------------------------------------------

class KeywordSearchRequest(BaseModel):
    platform: str = "youtube"  # youtube | x | reddit
    keyword: str
    limit: int = 100


@app.post("/api/keyword-search")
def keyword_search(req: KeywordSearchRequest):
    """Search a working platform for a keyword and stream every matching comment.

    youtube: real yt-dlp search for the keyword -> comments of the top videos (live fetch)
    x / reddit: topic-matched fresh batch from the dataset replay pool (APIs bot-walled)
    """
    req_model = TopicStreamRequest(topic=req.keyword, source=req.platform, limit=req.limit)
    return topics_stream(req_model)


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
        clauses.append("llm_label = %s"); params.append(sentiment)
    if q:
        clauses.append("(text ILIKE %s OR cleaned_text ILIKE %s)"); params += [f"%{q}%", f"%{q}%"]
    if post_id:
        clauses.append("post_id = %s"); params.append(post_id)

    with db() as conn, conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT id, source, author, text, label, vader_label, vader_score,
                   vader_positive, vader_negative, vader_neutral, bert_label, bert_score,
                   llm_label, llm_score, ts
            FROM comments WHERE {' AND '.join(clauses)}
            ORDER BY ts DESC NULLS LAST LIMIT %s
            """,
            (*params, limit),
        )
        rows = cur.fetchall()

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["id", "source", "author", "text", "dataset_label", "vader_label", "vader_score",
                     "vader_pos", "vader_neg", "vader_neu", "bert_label", "bert_score",
                     "llm_label", "llm_score", "ts"])
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
