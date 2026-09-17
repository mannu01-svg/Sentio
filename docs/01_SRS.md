# Software Requirements Specification (SRS)
## Social Media Sentiment Analysis — Real-Time Streaming Pipeline

| | |
|---|---|
| **Project** | Social Media Sentiment Analysis using Kafka, Spark & NLP |
| **Version** | 1.0 |
| **Status** | Final |
| **Team** | Member A, Member B, Member C, Member D |

---

## 1. Introduction

### 1.1 Purpose
This document specifies the functional and non-functional requirements of a
real-time social media sentiment analysis system. The system ingests social
media comments (Reddit/YouTube datasets, replayed as a live stream), processes
them with a streaming pipeline, classifies their sentiment using both a
lexicon-based NLP method (VADER) and a transformer-based AI model
(DistilBERT), aggregates statistics in time windows, and visualizes results on
an interactive dashboard.

Intended readers: project team members, faculty evaluators, and future
maintainers.

### 1.2 Scope
**The system does:**
- Ingest comment data into Apache Kafka as a simulated live stream
- Process the stream with Apache Spark Structured Streaming (clean + score + windowed aggregation)
- Classify sentiment with VADER (classic NLP) and DistilBERT (AI/transformer) side by side
- Persist scored comments and per-minute aggregates in PostgreSQL
- Serve analytics over a REST API (FastAPI)
- Visualize live: KPIs, sentiment timeline, distribution, trending words, model comparison, live feed

**The system does not (explicitly out of scope):**
- Fetch data from live platform APIs (X/Twitter, Reddit) — listed as future work
- Multi-language sentiment analysis (English only)
- User authentication / multi-tenancy
- Production deployment, clustering, or horizontal scaling

### 1.3 Definitions & Acronyms
| Term | Meaning |
|---|---|
| **Kafka** | Distributed event streaming platform used as the pipeline's message backbone |
| **Topic** | Named Kafka channel; this system uses `comments-raw` and `comments-scored` |
| **Producer** | Program that writes events to a Kafka topic |
| **Consumer** | Program that reads events from a Kafka topic |
| **Spark Structured Streaming** | Spark's micro-batch stream processing engine (DataFrame API) |
| **Micro-batch** | Processing model where the stream is treated as a sequence of small batches |
| **Watermark** | Threshold bounding how late data may arrive and still update a window |
| **Tumbling window** | Fixed, non-overlapping time window (here: 1 minute) |
| **VADER** | Valence Aware Dictionary and sEntiment Reasoner — lexicon/rule sentiment analyzer tuned for social media |
| **DistilBERT** | Compressed BERT transformer; here fine-tuned on SST-2 for sentiment |
| **Compound score** | VADER's normalized sentiment score in [-1, 1] |
| **FR / NFR** | Functional / Non-Functional Requirement |

### 1.4 References
- Hutto & Gilbert (2014), *VADER: A Parsimonious Rule-based Model for Sentiment Analysis of Social Media Text* (ICWSM)
- Sanh et al. (2019), *DistilBERT, a distilled version of BERT* (arXiv:1910.01108)
- Zaharia et al. (2013), *Discretized Streams: Fault-Tolerant Streaming Computation at Scale* (SOSP)
- Kreps et al. (2011), *Kafka: a Distributed Messaging System for Log Processing* (NetDB)

---

## 2. Overall Description

### 2.1 Product Perspective
A self-contained analytics pipeline demonstrating industrial big-data
concepts — decoupled ingestion (Kafka), scalable stream processing (Spark),
dual NLP models, relational storage, REST serving, and a live dashboard — on a
single machine via Docker.

```
Datasets → Producer → Kafka → Spark Streaming → PostgreSQL + Kafka(scored)
                                                      ↓
                                    FastAPI ← dashboard (React)
```

### 2.2 User Classes
| User | Role | Features used |
|---|---|---|
| **Analyst / viewer** | Faculty, demo audience | Dashboard: charts, live feed, filters |
| **Developer / operator** | Team members | Runs pipeline components, REST API docs, evaluation script |

### 2.3 Operating Environment
- Linux (or WSL2/macOS) with Docker + Docker Compose
- Python 3.10+ (virtualenv), Node.js 18+
- Hardware: ≥ 8 GB RAM, 2 CPUs (recommended 16 GB for DistilBERT mode)

### 2.4 Constraints
- C-1: Runs fully on one machine; no cloud services
- C-2: No paid API keys; datasets are public Kaggle/CSV files
- C-3: All components must start with simple documented commands
- C-4: Team of students; every technology used must be explainable in a viva

### 2.5 Assumptions
- Dataset comments are representative of real social media language
- English-only content is sufficient for this project
- Replayed "live" data is an acceptable simulation of platform streams

---

## 3. Functional Requirements

### 3.1 Ingestion
- **FR-1** The producer shall read comments from a CSV file with configurable path.
- **FR-2** The producer shall publish each comment as a JSON event `{id, source, author, text, label, ts}` to Kafka topic `comments-raw`.
- **FR-3** The producer shall support a configurable send rate (messages/second).
- **FR-4** The producer shall optionally loop the dataset (continuous stream) and shuffle row order.
- **FR-5** Every event id shall be unique per send so downstream sinks remain idempotent.

### 3.2 Stream Processing
- **FR-6** The Spark job shall consume `comments-raw` via Structured Streaming.
- **FR-7** The job shall clean text: lowercase, strip URLs, HTML entities, emojis, extra whitespace.
- **FR-8** The job shall score every comment with VADER and derive label positive/negative/neutral using |compound| ≤ 0.05 = neutral.
- **FR-9** The job shall score every comment with DistilBERT-SST2 (label + confidence); a model failure must not crash the stream.
- **FR-10** The job shall aggregate 1-minute tumbling windows: total, positive/negative/neutral counts, percentages, mean VADER score, with a 2-minute watermark.
- **FR-11** The job shall write scored comments to Kafka topic `comments-scored` as JSON.

### 3.3 Storage
- **FR-12** The job shall upsert scored comments into PostgreSQL table `comments` keyed by `id` (idempotent re-runs).
- **FR-13** The job shall upsert window aggregates into table `window_stats` keyed by `window_start` (late window updates overwrite).

### 3.4 API
- **FR-14** `GET /health` — liveness + DB check.
- **FR-15** `GET /api/summary` — totals, sentiment split (counts + %), avg score, BERT coverage, per-source counts, last processed timestamp.
- **FR-16** `GET /api/timeline?minutes=N` — window aggregates for the sentiment-over-time chart.
- **FR-17** `GET /api/comments?limit&source&sentiment&q` — latest scored comments with filters.
- **FR-18** `GET /api/words?limit&sentiment` — top-N word frequencies (stopwords removed).
- **FR-19** `GET /api/compare` — VADER vs DistilBERT agreement %, label accuracy, disagreement examples.

### 3.5 Dashboard
- **FR-20** Show KPI cards: total processed, % positive/negative/neutral.
- **FR-21** Show sentiment-over-time line chart from window aggregates.
- **FR-22** Show sentiment distribution donut.
- **FR-23** Show trending-words bar chart.
- **FR-24** Show live feed of scored comments with source, sentiment badges, both model scores.
- **FR-25** Show model-comparison panel (agreement %, accuracy, disagreement examples).
- **FR-26** Provide filters (source, sentiment, keyword) applied to the live feed.
- **FR-27** Poll the API every 3 seconds (10 s for comparison) without page reload.
- **FR-28** Degrade gracefully: show status/errors when the API is unreachable or empty.

### 3.6 Evaluation
- **FR-29** `evaluation/evaluate.py` shall compute accuracy, per-class precision/recall/F1, and confusion matrices for both models against dataset labels, from the DB or directly from a CSV.

---

## 4. Non-Functional Requirements

- **NFR-1 Latency** — end-to-end (produce → dashboard update) ≤ 30 s in demo mode; API response ≤ 500 ms for ≤ 5k rows.
- **NFR-2 Throughput** — sustain ≥ 50 msgs/sec on a laptop (Spark local mode, SKIP_BERT=1).
- **NFR-3 Usability** — dashboard usable without training; API self-documented at `/docs`.
- **NFR-4 Reliability** — pipeline survives producer restarts; sink writes are idempotent; model errors never kill the stream.
- **NFR-5 Reproducibility** — one-command infra (`docker compose up -d`); all deps pinned in `requirements.txt`.
- **NFR-6 Maintainability** — modules separated (producer / spark / api / frontend / evaluation); NLP logic unit-tested.
- **NFR-7 Portability** — runs on any Linux/macOS/WSL2 machine with Docker; no OS-specific code.
- **NFR-8 Security (scope-appropriate)** — no secrets in repo; DB credentials are demo defaults documented in the README.

---

## 5. Use Cases

**UC-1: View live sentiment (Analyst)**
1. Analyst opens the dashboard.
2. System polls API and renders KPIs, charts, live feed.
3. Analyst filters by sentiment/source; feed updates.
   → *Alternate:* API down → status banner shown (FR-28).

**UC-2: Run the pipeline (Developer)**
1. `docker compose up -d` (Kafka + Postgres).
2. `./run_spark.sh` (streaming job).
3. `python producer/producer.py --loop` (feed data).
4. `uvicorn api.main:app` (serve API).
5. `npm run dev` in `frontend/` (dashboard).

**UC-3: Evaluate models (Developer)**
1. `python evaluation/evaluate.py --csv data/raw/reddit.csv --sample 2000`
2. System prints accuracy, per-class metrics, confusion matrices.

---

## 6. Acceptance Criteria (summary)
| # | Criterion |
|---|---|
| AC-1 | Console round-trip through Kafka succeeds |
| AC-2 | 12/12 NLP unit tests pass |
| AC-3 | Producer → Kafka → Spark → PostgreSQL yields scored rows + window rows |
| AC-4 | All 6 API endpoints return valid JSON against live data |
| AC-5 | Dashboard renders live charts/feed; filters work |
| AC-6 | Evaluation produces accuracy + confusion matrices for both models |
