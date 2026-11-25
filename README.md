# Sentio — Real-Time Social Media Sentiment Analysis

**Kafka → Spark Structured Streaming → VADER + DistilBERT + RoBERTa → PostgreSQL → FastAPI → React**

Sentio ingests social-media comments (Reddit, YouTube, X/Twitter, Instagram, Facebook, Threads),
scores their sentiment with three models side-by-side, aggregates live trends, and serves it all
through an interactive dashboard — entirely on your localhost.

![stack](https://img.shields.io/badge/kafka-3.9-black) ![spark](https://img.shields.io/badge/spark-3.5.4-orange) ![python](https://img.shields.io/badge/python-3.12-blue) ![react](https://img.shields.io/badge/react-19-cyan) ![fastapi](https://img.shields.io/badge/fastapi-0.115-green)

---

## Contents

1. [What is Sentio?](#what-is-sentio)
2. [Requirements](#requirements)
3. [Quickstart — Mac & Windows & Linux](#quickstart)
4. [First tour — what to click](#first-tour)
5. [Every tab explained](#every-tab-explained)
6. [The three sentiment models](#the-three-sentiment-models)
7. [Where the data comes from (Kaggle & sources)](#where-the-data-comes-from)
8. [Architecture](#architecture)
9. [API reference](#api-reference)
10. [Configuration reference](#configuration-reference)
11. [Troubleshooting](#troubleshooting)
12. [Tests & docs](#tests--docs)
13. [Project structure](#project-structure)

---

## What is Sentio?

Eight services work together, all in Docker:

| Service | What it does |
|---|---|
| **Producer** | Replays real comment datasets into Kafka as a simulated live stream (seed + on-demand bursts). |
| **Kafka** | Message bus: `comments-raw` (replay stream), `comments-analyze` (your analyses, scored first) and `comments-scored` (live feed). |
| **Spark Streaming** | Consumes raw comments, cleans text, scores sentiment with **VADER + DistilBERT + RoBERTa**, builds 1-minute aggregates. |
| **PostgreSQL** | Stores every scored comment + window stats + users + analysis history. |
| **MongoDB** | Document store for raw data: every fetched comment exactly as the platform returned it (`raw_comments`) and one document per analysis (`analyses`). "Re-score" republishes from here without re-fetching. |
| **FastAPI** | 30+ REST endpoints: summaries, timelines, trends, keyword search, URL analysis, CSV export. |
| **React dashboard** | The app you interact with: 8 tabs, live charts, KPIs, deep links. |

You can also **paste any YouTube video or Reddit thread URL** into the dashboard and Sentio
will fetch its real comments (via `yt-dlp` / PullPush) and push them through the same pipeline.

---

## Requirements

| Requirement | Version | Where to get it |
|---|---|---|
| **Docker Desktop** | any recent (WSL 2 backend on Windows) | [docker.com/products/docker-desktop](https://www.docker.com/products/docker-desktop/) |
| ~8 GB RAM for Docker | — | Kafka + PostgreSQL + MongoDB + Spark with two transformer models |
| ~10 GB disk | — | images (~4 GB), models (~750 MB), data |

That's all. **Python, Java, Node.js and the ML models run inside containers**, so the same
command works on Windows, macOS (Intel and Apple Silicon) and Linux.

> **Windows:** Docker Desktop gives containers half your RAM by default. On a 16 GB PC that is
> enough. With 8 GB, start in `--fast` mode, or raise the limit in `%UserProfile%\.wslconfig`:
> `[wsl2]` then `memory=6GB`, then `wsl --shutdown` and restart Docker Desktop.

---

## Quickstart

| Platform | Command |
|---|---|
| **Windows** | double-click **`startup\windows\start.bat`** (or run it from a terminal) |
| **macOS** | `bash startup/mac/start.sh` |
| **Linux** | `bash startup/linux/start.sh` |
| **Any** | `docker compose up -d --build` |

The first run builds the images and downloads the sentiment models (**~4 GB, 15–25 min**);
later starts take under a minute. `setup.sh` / `setup.bat` do the same and then also start
**Jenkins CI** (see [Jenkins CI](#jenkins-ci-one-command-demo-on-your-own-machine)).

### No machine? Run the live demo from GitHub Actions

The repo ships a **Public demo** workflow (`.github/workflows/public-demo.yml`) that boots the
stack on a GitHub runner and prints a **live public URL + demo credentials** in the job summary:

> **Actions tab → "Public demo" → Run workflow** (~10 min to boot, live for up to ~6h)

### 1. Clone

```bash
git clone https://github.com/mannu01-svg/Sentio.git
cd Sentio
```

### 2. Start

```bash
startup/windows/start.bat          # Windows
bash startup/mac/start.sh          # macOS (same script in startup/linux/)
```

What runs (`docker compose ps`):

| Container | Role |
|---|---|
| `kafka`, `kafka-init` | broker + one-shot topic creation |
| `postgres` | scored comments, windows, users, history |
| `mongodb` | raw comments + analysis documents |
| `models` | one-shot download of DistilBERT + RoBERTa into a volume (first run only) |
| `spark` | streaming job: replay query + analyze query |
| `api` | FastAPI on :8000 (also seeds the demo/admin logins) |
| `producer` | seeds 6,000 comments, then waits for "Go live" bursts |
| `frontend` | React dashboard served by nginx on :5173 (proxies `/api` and `/docs`) |

**Variants:**

```bash
start.bat --fast        |  start.sh --fast       # VADER only: lighter, quicker demo
start.bat --fresh       |  start.sh --fresh      # wipe all data for a clean demo state
stop.bat                |  stop.sh               # stop (data kept)
docker compose logs -f spark                     # watch comments being scored
```

**Bigger machine (Docker has 10+ GB):** score faster with more Spark workers:

```bash
set SPARK_MASTER=local[4]& set NLP_TORCH_THREADS=4& startup\windows\start.bat   # Windows
SPARK_MASTER=local[4] NLP_TORCH_THREADS=4 bash startup/mac/start.sh            # macOS/Linux
```

**Without Docker** (development only): `startup/*/run_spark.sh` and the old native flow still
work with Python 3.12 + Java 17 installed, plus a local MongoDB (optional: Sentio runs without it).

### 3. Open the app

When the start script finishes it prints a status box. Then open:

| URL | What |
|---|---|
| **http://localhost:5173** | the dashboard (login first) |
| http://localhost:8000/docs | interactive API docs (Swagger) |
| http://localhost:4040 | Spark streaming UI (while Spark runs) |

**Logins:** `admin@sentio.app` / `admin123` (admin) or `ada@sentio.app` / `secret123` (demo user),
or create an account on the login page (an admin approves it in Settings).

| More URLs | What |
|---|---|
| http://localhost:5173/docs | Swagger through the nginx proxy |
| mongodb://localhost:27017 | MongoDB (open with MongoDB Compass; database `sentio`) |
| localhost:5432 | PostgreSQL (`sentiment` / `sentiment`) |

### What you should see within a minute

- KPI cards at the top of the Dashboard (total comments, % positive, etc.)
- a sentiment timeline chart filling in
- comments scrolling into the live feed
- trending words updating every few seconds

If anything shows red in the status box, jump to [Troubleshooting](#troubleshooting).

---

## First tour

Log in and you land on the **Dashboard**. There is a sidebar on the left with 8 tabs:

```
Dashboard  ·  Live Feed  ·  Analyze  ·  History  ·  Trends  ·  Models  ·  Pipeline  ·  Sources
```

A 60-second script to see everything:

1. **Dashboard** — KPIs, sentiment timeline, distribution donut, trending words, live comment feed, spike alerts. Hit the red **Go Live** button: the producer floods Kafka at high rate and you watch the charts move in real time.
2. **Live Feed** — a full-page, auto-refreshing wall of scored comments with model labels and confidence chips. Filter by source (reddit/youtube/x/…).
3. **Analyze** — paste a **YouTube video URL** or **Reddit thread URL** → Sentio fetches the real comments and scores them. Also: analyze a whole account/handle, or search a keyword across sources.
4. **History** — every analysis you've ever run (URL, account, keyword, topic stream), with live sentiment re-computed per entry. Survives restarts. Click an entry to jump back to it.
5. **Trends** — trending topics over your full history with % share, keyword search with platform breakdown, topic streams (per-topic deep dives), timeline + sentiment-over-time for any lookback window.
6. **Models** — side-by-side comparison of the three sentiment models (VADER vs DistilBERT vs RoBERTa): agreement, accuracy against dataset labels, per-model confidence, plus the **fine-tuned DistilBERT card** trained on our own 70k-row Kaggle corpus.
7. **Pipeline** — plain-English live status of every stage (producer → Kafka → Spark → DB → API), with throughputs and counts. Great for demos and debugging.
8. **Sources** — every dataset behind the app, with real row counts per platform.

---

## Every tab explained

### 1. Dashboard (`/dashboard`)
The command center. Shows: **KPI cards** (total comments, positive %, negative %, neutral %),
**sentiment timeline** (stacked area, 1-minute buckets), **distribution donut**,
**trending words** with velocity arrows, **live feed** of the most recently scored comments,
**VADER-vs-BERT disagreement** panel, **spike alerts** (comment volume bursts), and the
**Go Live** button (control the simulated firehose: minutes × rate, e.g. 3 min at 40 comments/s).

### 2. Live Feed (`/live`)
Infinite scrollable wall of every scored comment, newest first, with per-model sentiment chips
(VADER / DistilBERT / RoBERTa) and confidence scores. Filter by platform. This is the raw
output of the Spark stream — what you see here is exactly what's in Postgres.

### 3. Analyze (`/analyze`)
Four ways to analyze something not in the stream:
- **Paste URL** — a YouTube video or Reddit thread link. Sentio fetches its comments
  (yt-dlp for YouTube, PullPush for Reddit) and pushes them through the live pipeline.
  You get a full sentiment report and a persistent post record.
- **Platform analyze** — per-platform forms (YouTube / Reddit / X / Instagram / Facebook).
- **Account analyze** — give a handle (`@nasa`, etc.); the pool is matched for that author's
  comments and scored as one body of work.
- **Keyword search** — a term (" IPL", " election", " AI") across all sources with
  per-platform sentiment splits.
Every result is recorded in **History** automatically.

### 4. History (`/history`)
Your analysis log. Each entry: kind (URL / account / keyword / topic), title, platform,
timestamp, and **live sentiment bars re-computed from the DB right now** — so an old entry's
numbers stay current as new data flows in. Filter chips per kind. Deep-links back into the
original view. Survives API restarts (it's a table, not state).

### 5. Trends (`/trends`)
- **Trending topics** — the biggest topics across the **full DB history** with % share of all comments.
- **Keyword search** — any term with sentiment split and per-platform breakdown.
- **Topic streams** — click a topic to open a dedicated stream page for it (`/topics/:source/:topic`).
- **Timeline** — comment volume + sentiment over any lookback window (falls back gracefully
  when you request more history than exists).

### 6. Models (`/models`)
Everything about the three sentiment engines plus our own fine-tune:
- **VADER** card — lexicon-based, transparent, ~28k comments/s, tuned for social media.
- **DistilBERT** card — SST-2 transformer, context-aware, binary pos/neg.
- **RoBERTa** card — cardiffnlp, trained on **124M tweets**, understands slang/emojis/sarcasm;
  this is the **authoritative headline score** everywhere in the app.
- **Fine-tuned DistilBERT** card — trained on our own cleaned **70,671-row Kaggle corpus**
  (110 noisy emotion labels normalized to pos/neg/neu), with validation accuracy and epoch config.
- **Model comparison** — agreement matrix, per-model accuracy against dataset labels,
  and disagreement analysis (where VADER and BERT disagree, RoBERTa arbitrates).

### 7. Pipeline (`/pipeline`)
The "how it works" tab, in plain English, with live numbers: producer rate, Kafka offsets,
Spark micro-batch stats (rows in/out, trigger), DB row counts, API health. Each stage has an
explanation of *what* it does and *why* it exists. If something is stuck, this tab shows where.

### 8. Sources (`/sources`)
Honest accounting of the data: every CSV dataset, its real row count, and what portion of the
DB each platform covers (e.g. reddit 38k rows, youtube 18k, x 20k, facebook 49k, instagram 1.4k,
threads 1.5k). Producer auto-detects column names (`comment`/`text`/`CONTENT`, `label`/`CLASS`, …).

---

## The three sentiment models

Every comment is scored by **all three** models simultaneously:

| | VADER | DistilBERT | RoBERTa (cardiffnlp) |
|---|---|---|---|
| Type | rule/lexicon-based | transformer (SST-2) | transformer (124M tweets) |
| Output | compound −1..1 + pos/neg/neu proportions | positive/negative + confidence | positive/neutral/negative + confidence |
| Speed | ~28,000/s | ~500/s batched | ~290/s batched per worker |
| Strength | transparent, instant, great on short social text | context-aware classification | slang, emojis, sarcasm patterns |
| Role in app | baseline + fast mode | comparison + fine-tune base | **headline score** |

**Headline logic:** the sentiment shown everywhere (KPIs, timeline, trending) is the
**RoBERTa label**, falling back to VADER in `--fast` mode. VADER and DistilBERT run
alongside so the Models tab can show agreement/disagreement analytics.

**Our own fine-tune:** `models/training/` contains a full training pipeline —
`prepare_data.py` (cleans + dedupes the Kaggle corpus, normalizes 110 noisy emotion labels
to pos/neg/neu, 90/10 split), `finetune.py` (HF Trainer, 3 epochs, warmup), and the result
ships in `models/sentiment-finetuned/` (weights stored as GitHub-friendly chunks, auto-rejoined
on first run). Retrain it yourself:

```bash
.venv/bin/python models/training/prepare_data.py     # builds the 70k-row corpus
.venv/bin/python models/training/finetune.py         # fine-tunes DistilBERT (~2-3 h CPU)
```

---

## Where the data comes from

### Bundled (works out of the box, committed to the repo ~54MB)
- `data/sample_comments.csv` — 50 labeled comments, zero setup.
- `data/raw/all_sources.csv` — a **144,800-row** merged dataset across 6 platforms
  (this is what the start script seeds from by default).
- `data/raw/` per-source CSVs — committed too; a fresh `git clone` has every dataset,
  no downloads or extraction needed.

### Kaggle datasets (already merged into `data/raw/`)
| Platform | Rows | Source dataset |
|---|---|---|
| Reddit | 38,206 | [Twitter and Reddit Sentimental Analysis](https://www.kaggle.com/datasets/cosmos98/twitter-and-reddit-sentimental-analysis-dataset) (cosmos98) |
| X / Twitter | 20,001 | Kaggle Twitter sentiment sets |
| Facebook | 49,454 | Kaggle Facebook comments set |
| YouTube | 18,365 | Kaggle YouTube comments / UCI YouTube Spam Collection |
| Instagram | 1,450 | Kaggle Instagram comment set |
| Threads | 1,526 | preview dataset (the pipeline treats it as a first-class source) |

**Adding your own dataset:** drop any CSV at `data/raw/<name>.csv` with a text column and
(optionally) a label column — the producer auto-detects common column names
(`comment`/`text`/`CONTENT`, `label`/`sentiment`/`CLASS`, …). See `data/README.md`.

**Real-time ingestion:** X and Reddit block anonymous real-time access (HTTP 403/521), so
real-time streams are **pool-matched**: live bursts replay rows whose author/topic matches the
requested handle or keyword. YouTube works fully in real time via `yt-dlp`.

---

## Architecture

```
 datasets (Kaggle CSVs, 274k rows)              Analyze page / accounts / topics / Re-score
        │                                                 │  (FastAPI fetches YouTube / Reddit ...)
        ▼                                                 ├──────────────► MongoDB
 producer ──seed + live bursts──► Kafka comments-raw      │                raw_comments · analyses
                                          │               ▼
                                          │       Kafka comments-analyze
                                          ▼               ▼
                     Spark Structured Streaming — two queries, FAIR scheduler pools
                     ├── replay query  (comments-raw, trigger 10 s, feeds live windows)
                     └── analyze query (comments-analyze, trigger 3 s, scored first)
                         clean text → VADER → DistilBERT + RoBERTa
                                          │
                ┌─────────────────────────┴──────────────────────┐
                ▼                                                ▼
     Kafka comments-scored                        PostgreSQL (idempotent upserts)
     (live feed topic)                            comments · window_stats · users · history
                │                                                │
                └───────────────────────┬────────────────────────┘
                                        ▼
                     FastAPI :8000 (30+ endpoints, Swagger at /docs)
                                        ▲
                     nginx :5173 ── React dashboard
```

**Why two stores:** PostgreSQL holds what Spark computes and what must be relational (scores,
windows, users, the history list). MongoDB holds documents: raw comments exactly as fetched and
one record per analysis (request, posts, counts, `history_id` link). `GET /api/history/{id}/document`
returns both sides of an analysis; "Re-score" republishes the stored raw comments.

**Why two Spark queries:** user analyses used to share `comments-raw` with the 6,000-comment
seed, so they waited minutes behind it ("scoring pending…"). Their own topic and query, in their
own FAIR scheduler pool, gets them scored within seconds.

**Delivery semantics:** every sink upserts by primary key (`comments.id`, `window_stats.window_start`),
so producer replays and Spark restarts are always safe — no duplicates, ever.

---

## API reference

Full interactive docs at **http://localhost:8000/docs**. Highlights:

| Endpoint | What |
|---|---|
| `POST /api/signup` · `POST /api/login` | auth (PBKDF2-hashed passwords) |
| `GET /api/summary` | KPIs: totals, % split, avg score |
| `GET /api/timeline?minutes=60` | 1-minute bucketed sentiment history |
| `GET /api/comments?source=reddit&limit=50` | scored comments, filterable |
| `GET /api/words` | trending words + velocity |
| `GET /api/compare` | VADER vs DistilBERT vs RoBERTa agreement stats |
| `GET /api/history` | your analysis log with live sentiment per entry |
| `GET /api/history/{id}/document` | the MongoDB side of an analysis: stored document + raw comments as fetched |
| `POST /api/history/{id}/rehydrate` | Re-score: republish stored raw comments from MongoDB (re-fetch only if none) |
| `POST /api/analyze` | fetch + score a YouTube/Reddit URL |
| `POST /api/analyze-account` | analyze an account/handle |
| `POST /api/keyword-search` | search a keyword across all sources |
| `GET /api/trends` · `GET /api/trending` | topics, % share, velocity |
| `POST /api/topics/stream` | start a live topic stream |
| `POST /api/stream/live` · `POST /api/stream/stop` | control the simulated firehose (rate 5–120/s) |
| `GET /api/alerts` | volume-spike alerts |
| `GET /api/export` | CSV export of scored comments |
| `GET /api/spam` · `/api/comments/{id}/spam` | spam analysis |
| `GET /api/pipeline` | stage counters: Kafka topics, Spark throughput, PostgreSQL, MongoDB |
| `GET /health` | liveness probe (PostgreSQL + MongoDB status) |

---

## Configuration reference

Everything works with defaults. Optional overrides (create `.env.local` — gitignored — or export env vars):

| Variable | Default | Meaning |
|---|---|---|
| `SEED_ROWS` | `6000` | comments seeded on startup |
| `NLP_BATCH_SIZE` | `64` | transformer batch size inside Spark workers |
| `NLP_TORCH_THREADS` | `6` | torch threads per Spark worker (8 workers × 6 = 48 cores) |
| `SPARK_MASTER` | `local[8]` | Spark parallelism |
| `TRIGGER_SECONDS` | `10` | streaming micro-batch interval |
| `WINDOW_SECONDS` | `60` | aggregation window size |
| `KAFKA_BOOTSTRAP` | `localhost:9092` | Kafka address |
| `PG_DSN` | `localhost:5432/sentiment` | Postgres connection (user/pass `sentiment`) |
| `CHECKPOINT_DIR` | `checkpoints/` | Spark checkpoint location |
| `SKIP_BERT` | unset | `1` = transformers skipped (fast mode) |

`.env.local` uses plain `KEY=VALUE` lines and is loaded by `start.sh` automatically.

---

## Troubleshooting

**History says "scoring pending…" for a long time** → Spark isn't scoring. Check
`docker compose logs --tail 80 spark`. The Pipeline tab shows whether `Kafka · comments-analyze`
grows while `PostgreSQL · comments` doesn't. Spark restarts automatically; after a crash loop:

```bash
docker compose rm -sf spark && docker volume rm sentio_checkpoints && docker compose up -d spark
```

**`spark` container keeps restarting / exit code 137** → Docker is out of memory: start with
`--fast`, or give Docker more RAM (see [Requirements](#requirements)).

**First build fails with a network error** (`no such host`, `timeout`) → re-run the same command;
finished layers are kept. On flaky Wi-Fi set Docker Desktop → Settings → Docker Engine →
`"dns": ["8.8.8.8", "1.1.1.1"]`.

**Port already in use** (5173, 8000, 5432, 27017, 9092, 4040) → another program uses it. Change the
left-hand number in `docker-compose.yml`, e.g. `"5433:5432"`.

**Model download failed** → Spark still scores with VADER. Fix the network, then
`docker compose up models` and `docker compose restart spark`.

**MongoDB down** → analyses still run (MongoDB is best-effort); Re-score falls back to re-fetching.
`/health` shows `"mongodb": "down"`.

**Fresh demo state** → `start.bat --fresh` / `start.sh --fresh` (deletes all data volumes).

---

## Tests & docs

```bash
.venv/bin/pytest tests/ -v        # 42 tests: NLP, API, features, threads
cd frontend && npm run build      # production build check
cd frontend && npm run lint       # oxlint
```

### Jenkins CI (one command, demo on your own machine)

```bash
./run_jenkins.sh          # manual mode: Jenkins up + click-path printed
AUTO=1 ./run_jenkins.sh   # zero-click: admin sentio/sentio123 + sentio-ci job + first build queued
```

`startup/*/setup.sh` (and `setup.bat`) already runs Jenkins in AUTO mode —
the flow above is for when you want Jenkins on its own. Five stages:
Setup Python → Lint → Unit Tests → Frontend Build → Compose Config.
Full details in `docs/06_Jenkins_Guide.md`. Selenium, Postman and the GitHub webhook: `docs/08_Testing_Guide.md`.

`docs/` contains the full academic/documentation set:

| Doc | Content |
|---|---|
| `01_SRS.md` | IEEE-style requirements (FR-1..40, NFR-1..8, use cases, acceptance criteria) |
| `02_SDD.md` | architecture, DFDs, component design, DB schema, sequence diagram, error matrix |
| `03_Final_Report.md` | SDLC report: abstract → process/timeline → implementation → results (84.2%, ~59 rec/s) |
| `04_Work_Division.md` | 3-member workstreams, 17 Sep → 21 Nov phase plan, RACI matrix |
| `05_Docker_Guide.md` | every container/env var explained + troubleshooting |
| `06_Jenkins_Guide.md` | CI pipeline stages + zero-click Jenkins (AUTO mode) |
| `07_Jira_Guide.md` | full board setup, 9-sprint plan, CSV import, GitHub for Jira |
| `08_Testing_Guide.md` | unit tests, Selenium UI tests, Postman/Newman collection, Jenkins test stages, GitHub webhook |
| `08_GitHub_Guide.md` | branching, PRs, issues, commit convention, large-file policy |
| `09_Demo_and_Viva.md` | 10-min demo script + 16 viva Q&As |

---

## Project structure

```
producer/producer.py        CSV → Kafka replay (seed + live bursts, control-file driven)
spark/nlp.py                VADER + DistilBERT + RoBERTa scoring (unit tested, warm models)
spark/streaming_job.py      Kafka → clean → score → windows → sinks (single-pass foreachBatch)
fetcher/fetchers.py         yt-dlp (YouTube) + PullPush (Reddit) real-comment fetchers
api/main.py                 FastAPI: 30+ endpoints (auth, summary, analyze, trends, history…)
frontend/                   React 19 + Vite + Tailwind + Recharts (8 tabs)
  src/pages/                Dashboard · Live · Analyze · History · Trends · Models · Pipeline · Sources
  src/components/UI.jsx     app shell, sidebar nav, sentiment chips
models/sentiment-finetuned/ our fine-tuned DistilBERT (chunked weights + meta)
models/training/            prepare_data.py · finetune.py · split_weights.py
evaluation/evaluate.py      accuracy / F1 / confusion matrices vs dataset labels
data/raw/                   7 Kaggle datasets, 274k rows total
db/init.sql                 Postgres schema (comments · users · history · window_stats)
docker-compose.yml          whole stack: Kafka, PostgreSQL, MongoDB, Spark, API, producer, nginx
docker/                     Dockerfile.app (Python 3.12 + Java 17), Dockerfile.frontend, nginx.conf
fetcher/mongo_store.py      MongoDB document store (raw comments, analyses)
startup/linux/               setup.sh · start.sh · stop.sh · run_spark.sh · bootstrap.sh
startup/mac/                 same scripts (identical, macOS-safe)
startup/windows/             setup.bat · start.bat · stop.bat · run_spark.bat (double-click)
jenkins/                     plugins.txt + init.groovy.d (zero-click Jenkins AUTO mode)
scripts/seed_demo_user.py   cross-platform demo-user seed (all OSes)
run_jenkins.sh              Jenkins CI setup (manual or AUTO=1 zero-click)
Dockerfile.jenkins          Jenkins LTS + python3 + node + docker CLI + baked plugins
Jenkinsfile                 CI: lint → tests → frontend build → compose check
tests/                      42 pytest cases
```

---

## Tech stack

Python 3.12 · PySpark 3.5.4 · Kafka 3.9 (KRaft) · PostgreSQL 16 · FastAPI ·
Transformers (DistilBERT, RoBERTa) · VADER · React 19 · Vite · Tailwind 4 · Recharts ·
Docker · pytest · Jenkins CI
