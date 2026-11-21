# Software Requirements Specification (SRS)
## Sentio — Real-Time Social Media Sentiment Analysis Platform

| | |
|---|---|
| **Project** | Sentio — Social Media Sentiment Analysis using Kafka, Spark & NLP |
| **Version** | 2.0 (final) |
| **Status** | Delivered |
| **Team** | Mannat Muthreja · Member B · Member C |
| **Timeline** | August – November (mid-term evaluation: October) |
| **Repository** | github.com/mannu01-svg/Sentio |

---

## 1. Introduction

### 1.1 Purpose
This document specifies the functional and non-functional requirements of
**Sentio**, a real-time social media sentiment analysis platform. Sentio
ingests social media comments (bundled Kaggle datasets replayed as a live
stream, plus live YouTube/Reddit/X ingestion by link, account, keyword and
topic), processes them with Apache Spark Structured Streaming, classifies
sentiment with three scorers (VADER lexicon, DistilBERT-SST2, and a
fine-tuned DistilBERT + tweet-RoBERTa LLM), aggregates statistics in time
windows, persists everything in PostgreSQL, and visualizes results on an
8-tab interactive dashboard with per-account history.

Intended readers: project team members, faculty evaluators, and future
maintainers.

### 1.2 Scope
**The system does:**
- Ingest comment data into Apache Kafka (KRaft) as a simulated live stream
  (seed pass + on-demand high-rate bursts controlled by the dashboard)
- Process the stream with Spark Structured Streaming (clean → score →
  windowed aggregation) through a single fault-tolerant `foreachBatch` sink
- Classify sentiment with VADER (lexicon), DistilBERT-SST2 (transformer) and
  our **fine-tuned DistilBERT (84.2% validation accuracy)** + cardiffnlp
  tweet-RoBERTa (the authoritative live score)
- Persist scored comments, per-minute aggregates, users and analysis history
  in PostgreSQL
- Serve 30+ REST endpoints over FastAPI: analytics, link/account analysis,
  keyword & topic search, trends, alerts, spam, CSV export, auth, history
- Provide an 8-tab React dashboard: Dashboard, Live, Analyze, Trends, Models,
  Pipeline, Sources, Settings — with per-account isolation
- Tie every analysis to the logged-in account (`user_email`) and persist it
  across API restarts

**The system does not (explicitly out of scope):**
- OAuth ingestion from Instagram/Facebook/Threads (flow built; needs Meta app
  credentials — listed as future work)
- Multi-language sentiment analysis (English only)
- Production deployment, clustering, or horizontal scaling

### 1.3 Definitions & Acronyms
| Term | Meaning |
|---|---|
| **Kafka** | Distributed event streaming platform used as the pipeline's message backbone (KRaft mode — no Zookeeper) |
| **Topic** | Named Kafka channel; this system uses `comments-raw` and `comments-scored` (3 partitions each) |
| **Producer** | Program that writes events to a Kafka topic |
| **Spark Structured Streaming** | Spark's micro-batch stream processing engine (DataFrame API) |
| **Watermark** | Threshold bounding how late data may arrive and still update a window |
| **Tumbling window** | Fixed, non-overlapping time window (here: 1 minute) |
| **VADER** | Valence Aware Dictionary and sEntiment Reasoner — lexicon/rule sentiment analyzer tuned for social media |
| **DistilBERT-SST2** | Compressed BERT transformer fine-tuned on SST-2 (binary: positive/negative) |
| **Fine-tuned DistilBERT** | Our DistilBERT further trained on 63.6k social-media rows — 3-class, 84.2% validation accuracy |
| **LLM score** | cardiffnlp/twitter-roberta-base-sentiment-latest — the authoritative 3-class live score |
| **Pool-matched stream** | X/Reddit real-time analysis replays dataset rows matching the requested keyword/handle (their public APIs are bot-walled) |
| **FR / NFR** | Functional / Non-Functional Requirement |

### 1.4 References
- Hutto & Gilbert (2014), *VADER: A Parsimonious Rule-based Model for Sentiment Analysis of Social Media Text* (ICWSM)
- Sanh et al. (2019), *DistilBERT, a distilled version of BERT* (arXiv:1910.01108)
- Barbieri et al. (2020), *TimeLMs / cardiffnlp twitter-roberta-base-sentiment* (argosindustria)
- Zaharia et al. (2013), *Discretized Streams: Fault-Tolerant Streaming Computation at Scale* (SOSP)
- Kreps et al. (2011), *Kafka: a Distributed Messaging System for Log Processing* (NetDB)

---

## 2. Overall Description

### 2.1 Product Perspective
A self-contained analytics platform demonstrating industrial big-data
concepts — decoupled ingestion (Kafka), scalable stream processing (Spark),
three NLP scorers including a custom fine-tuned model, relational storage,
per-account history, REST serving, and a live multi-tab dashboard — on a
single machine via Docker with one-command startup per OS.

```
Datasets ─┐
YouTube ──┤→ Producer/Ingesters → Kafka → Spark Streaming → PostgreSQL + Kafka(scored)
Reddit ───┘         (links/accounts/keywords/topics)         ↓
                                              FastAPI (30+ endpoints) ← 8-tab React dashboard
                                                        ↑
                                              Auth (signup/login) + per-account history
```

### 2.2 User Classes
| User | Role | Features used |
|---|---|---|
| **Analyst (logged in)** | Faculty, demo audience | Own account: dashboard, live feed, analyze (link/account/keyword/topic), trends, history, export |
| **Guest** | — | Redirected to login (all pages behind auth) |
| **Developer / operator** | Team members | Runs pipeline via `startup/<os>/start.sh`, REST docs at `/docs`, evaluation script, Jenkins CI |

### 2.3 Operating Environment
- Linux / macOS / Windows(WSL2) with Docker + Docker Compose
- Python 3.10–3.12 (virtualenv), Node.js 18+
- Hardware: ≥ 8 GB RAM, 4 CPUs (16 GB recommended for full transformer mode)

### 2.4 Constraints
- C-1: Runs fully on one machine; no cloud services
- C-2: No paid API keys; datasets are public Kaggle/CSV files (bundled, 54 MB)
- C-3: All components start with one documented command per platform
- C-4: Student team; every technology must be explainable in a viva

### 2.5 Assumptions
- Dataset comments are representative of real social media language
- English-only content is sufficient
- Replayed/pool-matched data is an acceptable simulation where platform APIs
  are bot-walled (X/Reddit); YouTube is fully live via yt-dlp

---

## 3. Functional Requirements

### 3.1 Ingestion
- **FR-1** The producer shall read comments from `data/raw/all_sources.csv` (configurable).
- **FR-2** The producer shall publish each comment as a JSON event `{id, source, author, text, label, ts, post_id, post_title}` to Kafka topic `comments-raw`.
- **FR-3** The producer shall run a one-time seed pass (default 6,000 rows) then idle, watching a control file.
- **FR-4** `POST /api/stream/live` shall trigger a high-rate burst (5–120 msg/s, 0.5–30 min) by writing the control file; `POST /api/stream/stop` ends it.
- **FR-5** Every event id shall be unique per send so downstream sinks remain idempotent.

### 3.2 Link, Account, Keyword & Topic Ingestion (v2)
- **FR-6** `POST /api/analyze` shall accept a YouTube video URL, a Reddit/X thread URL, or pasted text; fetch comments (yt-dlp / PullPush / line parser) and publish them with `post_id` + `post_title`.
- **FR-7** `POST /api/analyze-account` shall fetch comments across an account's recent posts (YouTube/Reddit).
- **FR-8** `POST /api/keyword-search` and `POST /api/topics/stream` shall fetch/collect comments matching a keyword or trending topic (YouTube live; X/Reddit pool-matched from the full source pool via indexed SQL).
- **FR-9** Fetched comments shall flow through the same Kafka → Spark → PostgreSQL pipeline (no separate analysis path).

### 3.3 Stream Processing
- **FR-10** The Spark job shall consume `comments-raw` via Structured Streaming (`local[6]`, arrow batches of 512, `maxOffsetsPerTrigger=8000`, 10 s trigger).
- **FR-11** The job shall clean text: lowercase, strip URLs, HTML entities, emojis, extra whitespace.
- **FR-12** The job shall score every comment with VADER (|compound| ≤ 0.05 = neutral), DistilBERT-SST2, and the cardiffnlp tweet-RoBERTa LLM (the authoritative score); transformer batching capped at 256 chars with `OMP_NUM_THREADS` pinned before torch loads; model failures must not crash the stream.
- **FR-13** The job shall aggregate 1-minute tumbling windows (counts, percentages, avg score, top words) with a watermark.
- **FR-14** All sinks shall run in one `foreachBatch` (PostgreSQL upserts + Kafka `comments-scored` feed), checkpointed for exactly-once resumability.

### 3.4 Storage
- **FR-15** The job shall upsert scored comments into `comments` keyed by `id`.
- **FR-16** The job shall upsert window aggregates into `window_stats` keyed by `window_start`.
- **FR-17** The API shall auto-migrate the schema at startup (`history` table, `user_email` column, indexes) so existing databases upgrade without manual SQL.

### 3.5 API (30+ endpoints)
- **FR-18** `GET /health` — liveness + DB check.
- **FR-19** `GET /api/summary` — totals, LLM sentiment split, scorer coverage, per-source counts.
- **FR-20** `GET /api/timeline?minutes=N` — window aggregates; `GET /api/pipeline` — live Kafka offsets, Spark throughput, DB rows.
- **FR-21** `GET /api/comments?limit&source&sentiment&q&post_id` — latest scored comments with filters.
- **FR-22** `GET /api/words`, `GET /api/trends`, `GET /api/trending` — word frequencies, velocity ranking, per-source topics.
- **FR-23** `GET /api/compare` — 3-way model agreement (VADER vs BERT vs LLM) + label accuracy + LLM corrections of VADER.
- **FR-24** `GET /api/alerts` — negative-spike detection (≥ +10 pts vs trailing average); `GET /api/spam` — heuristic spam summary; `GET /api/export` — CSV download.
- **FR-25** `GET /api/posts`, `/api/accounts`, `/api/topics/streams` — analyzed posts/accounts/topic streams **from the history table** (survive API restarts), **401 without `?user=`**.

### 3.6 Auth & Per-Account History
- **FR-26** `POST /api/signup` / `POST /api/login` — accounts in the `users` table; passwords hashed with PBKDF2-SHA256 (120k iterations); tokens returned.
- **FR-27** Every analysis (post/account/topic/keyword/paste) shall be recorded in `history` with `user_email` of the logged-in account.
- **FR-28** `GET /api/history?kind&platform&user` — the account's analyses only (401 without user); frontend redirects guests to login.
- **FR-29** The History tab shall show an owner chip (which account ran what); `/api/posts`/`/api/accounts`/`/api/topics/streams` shall be strictly per-account.

### 3.7 Dashboard (8 tabs)
- **FR-30** Dashboard: KPI cards, sentiment timeline, donut, trending-topic cards (clickable → topic stream), round-robin live feed, "Go live" button.
- **FR-31** Live: real-time scored feed with source/sentiment/keyword filters + CSV export.
- **FR-32** Analyze: platform picker (YouTube/Reddit/X/Instagram/Facebook/Threads), post/URL/paste analysis, account analysis, keyword search, Threads OAuth panel.
- **FR-33** Trends: rising hashtags/words with velocity + drill-down.
- **FR-34** Models: 3-way comparison, corrections, accuracy; Pipeline: live stage counters; Sources: dataset inventory.
- **FR-35** History: every analysis of the logged-in account with live sentiment, owner chips, kind filters.
- **FR-36** Settings: profile, theme, polling speed.
- **FR-37** Poll the API every 2.5–12 s per tab without page reload; degrade gracefully with status banners.

### 3.8 Model Training & Evaluation
- **FR-38** `models/training/prepare_data.py` shall build train/val JSONL from the merged dataset (63,603 rows).
- **FR-39** `models/training/finetune.py` shall fine-tune DistilBERT (3-class) with checkpoint auto-resume; weights split into ≤90 MB parts + SHA256 for GitHub, rejoined by `split_weights.py --join` during setup.
- **FR-40** `evaluation/evaluate.py` shall compute accuracy, per-class precision/recall/F1, and confusion matrices against dataset labels (DB or CSV mode).

---

## 4. Non-Functional Requirements

- **NFR-1 Latency** — end-to-end (produce → dashboard update) ≤ 30 s; API response ≤ 500 ms for ≤ 5k rows.
- **NFR-2 Throughput** — sustain **≈ 59 records/s** (measured; up from ~9/s before tuning) on 48 threads; ≥ 15/s on a 16 GB laptop.
- **NFR-3 Usability** — one-command startup per OS (`startup/<os>/start.sh`); everything (venv, JDK, weights, models, demo user) installed automatically; API self-documented at `/docs`.
- **NFR-4 Reliability** — pipeline survives producer/API restarts; sinks idempotent; model errors never kill the stream; history survives restarts (DB-backed).
- **NFR-5 Reproducibility** — datasets bundled in the repo (54 MB); fine-tuned weights split+committed; all deps in `requirements.txt`; fresh clone → full demo.
- **NFR-6 Maintainability** — modules separated (producer / spark / api / frontend / evaluation / models); 42 pytest cases green in CI.
- **NFR-7 Portability** — Linux/macOS/Windows one-command startup; macOS-safe process handling; no sudo required.
- **NFR-8 Security (scope-appropriate)** — PBKDF2 password hashing; no secrets in repo (`.env.local` gitignored); per-account endpoints 401 without a user; guests redirected to login.

---

## 5. Use Cases

**UC-1: View live sentiment (Analyst)**
1. Analyst logs in and opens the dashboard.
2. System polls API and renders KPIs, charts, live feed.
3. Analyst hits "Go live" → producer bursts at N/s → counters climb.
   → *Alternate:* API down → status banner (FR-37).

**UC-2: Run the pipeline (Developer)**
1. `bash startup/linux/setup.sh` (everything: venv, JDK, weights, models, docker, services, Jenkins CI).
2. Open `localhost:5173`, log in, analyze.

**UC-3: Analyze a post/account/keyword (Analyst)**
1. Analyze tab → paste a YouTube URL → scores appear in ~30–60 s.
2. The analysis is recorded in History under the logged-in account forever.

**UC-4: Evaluate models (Developer)**
1. `python evaluation/evaluate.py --csv data/raw/reddit.csv --sample 2000`
2. Accuracy, per-class metrics, confusion matrices printed.

---

## 6. Acceptance Criteria (summary)
| # | Criterion | Status |
|---|---|---|
| AC-1 | Console round-trip through Kafka succeeds | ✅ |
| AC-2 | 42/42 pytest cases pass (NLP, API, features, threads) | ✅ |
| AC-3 | Producer → Kafka → Spark → PostgreSQL yields scored rows + window rows | ✅ (369k+ rows) |
| AC-4 | 30+ API endpoints return valid JSON against live data | ✅ |
| AC-5 | 8-tab dashboard renders live; filters/analyze/history work | ✅ |
| AC-6 | Fine-tuned model reaches ≥ 80% validation accuracy | ✅ (84.2%) |
| AC-7 | Every analysis is attributed to the logged-in account and persists | ✅ |
| AC-8 | Jenkins CI 5/5 stages green | ✅ |
