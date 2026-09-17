# Final Project Report
## Real-Time Social Media Sentiment Analysis using Kafka, Spark & NLP

| | |
|---|---|
| **Team** | Member A · Member B · Member C · Member D |
| **Guide** | *(faculty guide name)* |
| **Institution** | *(college, department, year)* |
| **Version** | 1.0 |

---

## Abstract
Public opinion on social media forms in minutes, but manual analysis cannot
scale. This project implements a real-time sentiment analysis pipeline that
ingests social media comments, classifies their sentiment using both a classic
lexicon-based NLP method (VADER) and a transformer-based AI model
(DistilBERT), aggregates live statistics with Apache Spark Structured
Streaming, and serves the results on an interactive web dashboard. Data flows
through Apache Kafka, which decouples ingestion from processing. The system is
evaluated against ground-truth sentiment labels: DistilBERT reaches ≈ 64%
accuracy versus VADER's ≈ 56% on Reddit comments, and the agreement/disagreement
between the two approaches is analyzed in detail. The project demonstrates
industrial big-data concepts — message queuing, micro-batch stream processing,
windowed aggregation, fault-tolerant sinks — while remaining simple enough to
run on a single machine.

**Keywords** — sentiment analysis, Apache Kafka, Spark Structured Streaming, VADER, DistilBERT, real-time analytics

---

## 1. Introduction

### 1.1 Motivation
Brands, researchers and journalists need to understand public sentiment as it
happens: product launches trigger thousands of comments per hour, and the
overall mood shifts in minutes. Batch analysis of yesterday's data misses this
window. A streaming pipeline — ingest → classify → aggregate → visualize —
answers "what does the public feel right now?"

### 1.2 Problem Statement
Build a system that continuously ingests social media comments, classifies
their sentiment with two complementary NLP approaches, aggregates per-minute
statistics, and presents live analytics on a dashboard — while comparing the
two classification approaches quantitatively.

### 1.3 Objectives
1. Ingest comments as a simulated live stream through Apache Kafka.
2. Process the stream with Spark Structured Streaming: clean, classify, window.
3. Implement dual sentiment analysis: VADER (lexicon/rule-based) and DistilBERT (transformer).
4. Persist scored comments and windowed aggregates in PostgreSQL.
5. Serve analytics over a REST API.
6. Visualize live KPIs, charts, a live feed, and a model-comparison panel.
7. Evaluate both models against dataset labels (accuracy, F1, confusion matrices).

### 1.4 Report Structure
§2 background · §3 requirements (summary; full: `01_SRS.md`) · §4 design
(full: `02_SDD.md`) · §5 implementation · §6 testing · §7 results ·
§8 limitations · §9 future work · §10 team contribution · §11 references.

---

## 2. Background & Related Work

### 2.1 Sentiment analysis approaches
| Family | Method | Strengths | Weaknesses |
|---|---|---|---|
| Lexicon / rule-based | **VADER** (Hutto & Gilbert, 2014) | fast, transparent, tuned for social text (punctuation, emoji, negation) | misses context; fixed vocabulary |
| Transformer (deep learning) | **DistilBERT-SST2** (Sanh et al., 2019) | context-aware; learned representations; high accuracy | opaque; binary (no neutral); heavier |

### 2.2 Streaming architectures
Kafka (Kreps et al., 2011) provides a durable, replayable log decoupling
producers from consumers. Spark's Discretized Streams model (Zaharia et al.,
2013) — Structured Streaming in modern Spark — treats the stream as a series
of micro-batches with DataFrame semantics, native windowing and watermarks.
This project applies both patterns at demo scale.

### 2.3 Why two classifiers?
Running VADER and DistilBERT side by side turns the system into a controlled
comparison: identical inputs, two paradigms, measurable agreement. This
directly answers the project brief ("using NLP, then using AI or normal
analysis").

---

## 3. Requirements (summary)
Full specification in `docs/01_SRS.md`. 29 functional requirements across
ingestion (FR-1..5), processing (FR-6..11), storage (FR-12..13), API (FR-14..19),
dashboard (FR-20..28), evaluation (FR-29); 8 non-functional requirements
covering latency, throughput, reliability, reproducibility.

---

## 4. Design

### 4.1 Architecture
```
Datasets → Producer → Kafka[comments-raw] → Spark Structured Streaming
    ├→ clean text (lowercase, URLs/emoji/HTML out)
    ├→ VADER (pandas UDF) → label + compound
    ├→ DistilBERT (mapInPandas) → label + confidence
    ├→ 1-min windows + 2-min watermark
    ├→ Kafka[comments-scored]        (live feed)
    ├→ PostgreSQL.comments           (upsert by id)
    └→ PostgreSQL.window_stats       (upsert by window)
                 ↓
          FastAPI (6 endpoints)  ←— 3s polling —  React dashboard
```
Design rationale, DFDs, sequence diagram, DB schema and error-handling matrix:
`docs/02_SDD.md`.

### 4.2 Key design decisions
| Decision | Alternative rejected | Why |
|---|---|---|
| Kafka KRaft (no Zookeeper) | Kafka + Zookeeper | one less system to run/explain; KRaft is the modern default |
| foreachBatch + upsert sinks | append-only / Delta Lake | idempotent re-runs; no duplicate rows on restart |
| Polling (3 s) | WebSockets | stateless, trivially reliable, sufficient for 1-min windows |
| mapInPandas for BERT | pandas UDF | mapInPandas streams batches through one model instance |
| VADER neutral band 0.05 | tuned threshold | VADER authors' recommended default |

---

## 5. Implementation

### 5.1 Technology stack
Python 3.12 · Kafka (apache/kafka 3.9, KRaft) · PostgreSQL 16 · PySpark 3.5.4 ·
vaderSentiment 3.3.2 · transformers 5.x (DistilBERT-SST2) · FastAPI ·
React 19 + Vite + Tailwind v4 + Recharts · Docker Compose.

### 5.2 Module walkthrough
| Module | Responsibility | Highlights |
|---|---|---|
| `producer/producer.py` | CSV → Kafka replay | column auto-detection across datasets; unique ids; rate/loop/shuffle flags |
| `spark/nlp.py` | pure scoring functions | unit-tested; lazy model init; `clean_text` normalization |
| `spark/streaming_job.py` | stream processing | parse → clean (UDF) → VADER (pandas UDF) → BERT (mapInPandas) → windows → 3 sinks with checkpoints |
| `api/main.py` | REST serving | 6 endpoints; SQL aggregation; stopwords list; CORS for dev |
| `frontend/src/App.jsx` | dashboard | polling hook; Recharts line/donut/bar; live feed; compare panel |
| `evaluation/evaluate.py` | model evaluation | accuracy, per-class P/R/F1, confusion matrices; DB or CSV mode |

### 5.3 Notable implementation details
- **Idempotent sinks:** producer emits unique ids (`{dataset-id}-{seq}`);
  comments upsert `ON CONFLICT (id)`, window stats upsert
  `ON CONFLICT (window_start)` — late window updates overwrite cleanly.
- **BERT schema pitfall (documented in code):** `StructType.add()` mutates in
  place — `mapInPandas` output schema is built as a fresh `StructType` from the
  input fields + bert columns, and worker failures set nulls instead of
  crashing the stream.
- **Event time:** message timestamp parsed from ISO; falls back to Kafka
  timestamp, so windowing survives producer clock skew.

---

## 6. Testing

| Level | Result |
|---|---|
| Unit — NLP (12 tests: cleaning, label mapping, scoring) | ✅ 12/12 pass |
| API — endpoint shapes/filters (6 tests) | ✅ 6/6 pass |
| Integration — Kafka console round-trip | ✅ |
| E2E — producer → Spark → PostgreSQL → API → dashboard | ✅ (4,300+ comments in demo run) |
| CI — Jenkinsfile (compile, tests, frontend build, compose config) | ✅ defined |

---

## 7. Results & Evaluation

### 7.1 End-to-end demonstration
A 50-comment sample replayed at 10 msg/s produced, within a minute, scored
rows in `comments`, per-minute rows in `window_stats`, live JSON on
`comments-scored`, and a fully populated dashboard. A larger replay
(4,300+ comments) ran continuously without duplicates or failures.

### 7.2 Model evaluation (4,509 labeled Reddit comments)
| Model | Accuracy | Notes |
|---|---|---|
| VADER | **56.0%** | best F1 on positive (0.68); weak on negative recall (0.38) |
| DistilBERT | **64.1%** | best F1 on positive (0.80); no neutral class — forced binary choice |
| Agreement (VADER↔BERT) | **44.1%** | disagreement concentrated on questions/requests (BERT→negative, VADER→neutral) |

Confusion matrices and per-class precision/recall/F1: `evaluation/evaluate.py`
output; reproduction: `python evaluation/evaluate.py --csv <dataset> --sample N`.

### 7.3 Interpretation
1. **The transformer wins on label accuracy** (+8 pts) by using context.
2. **VADER's "neutral" band** maps questions/requests to neutral — often the
   dataset label agrees — but its negative recall is weak.
3. **BERT's missing neutral class** is its largest single error source:
   901 neutral comments were labeled negative in our run.
4. **Disagreement ≠ error**: examples where the two disagree are the most
   interesting artifacts for human inspection — the dashboard surfaces them.

### 7.4 Latency
End-to-end (producer send → dashboard poll) ≈ 10–20 s in demo configuration:
producer rate (10/s) + Spark trigger + 3 s poll. API response < 100 ms at
5k rows.

---

## 8. Limitations
- English-only; both models are English-centric.
- Replayed datasets approximate, not replicate, a live platform feed (no
  deletions, threads, or rate limits).
- DistilBERT-SST2 is binary; neutral detection relies on VADER or thresholds.
- Single broker / single machine — no replication or horizontal scale.
- Sarcasm and heavy irony remain hard for both approaches.

## 9. Future Work
- Live ingestion via Reddit/YouTube APIs (OAuth, rate limits) — the producer
  interface already accepts any row source.
- Multi-class transformer (e.g. cardiffnlp/twitter-roberta: 3-class).
- WebSocket push for sub-second dashboard updates.
- Kafka multi-broker + Spark cluster for scale experiments.
- Periodic model evaluation and drift monitoring in the pipeline itself.

## 10. Team Contribution
| Member | Workstream | Key deliverables |
|---|---|---|
| Member A | Infra & producer | docker-compose, DB schema, producer.py, CI |
| Member B | Spark & NLP | nlp.py, streaming job, evaluation, BERT integration |
| Member C | Storage & API | Postgres upserts, FastAPI endpoints + tests |
| Member D | Frontend & docs | React dashboard, report, guides |

## 11. References
1. C. Hutto and E. Gilbert, "VADER: A Parsimonious Rule-based Model for Sentiment Analysis of Social Media Text," *ICWSM*, 2014.
2. V. Sanh, L. Debut, J. Chaumond, T. Wolf, "DistilBERT, a distilled version of BERT: smaller, faster, cheaper and lighter," *arXiv:1910.01108*, 2019.
3. M. Zaharia et al., "Discretized Streams: Fault-Tolerant Streaming Computation at Scale," *SOSP*, 2013.
4. J. Kreps, N. Narkhede, J. Rao, "Kafka: a Distributed Messaging System for Log Processing," *NetDB*, 2011.
5. Apache Spark Structured Streaming Programming Guide, spark.apache.org.
6. Datasets: Kaggle — *Twitter and Reddit Sentimental Analysis Dataset* (cosmos98); UCI — *YouTube Spam Collection* (CC BY 4.0).

### Appendix A — Repository map
```
docs/           this report + SRS, SDD, guides, work division, demo script
producer/       CSV → Kafka replay
spark/          streaming job + NLP scoring (unit tested)
api/            FastAPI service
frontend/       React dashboard
evaluation/     model evaluation vs labels
db/             Postgres init schema
docker-compose.yml   Kafka + PostgreSQL
Jenkinsfile     CI pipeline
```
