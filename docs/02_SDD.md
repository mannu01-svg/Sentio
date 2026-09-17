# Software Design Document (SDD)
## Social Media Sentiment Analysis — Real-Time Streaming Pipeline

| | |
|---|---|
| **Version** | 1.0 |
| **Companion doc** | `01_SRS.md` (requirements) |

---

## 1. Architecture Overview

```
                        ┌─────────────────────────────────────────────┐
                        │                DATA SOURCES                 │
                        │   Kaggle CSVs (Reddit/YouTube comments)     │
                        └──────────────────────┬──────────────────────┘
                                               │ read rows
                                               ▼
                        ┌─────────────────────────────────────────────┐
                        │        PRODUCER  (Python, producer.py)      │
                        │  CSV → JSON events @ N msgs/sec → Kafka     │
                        └──────────────────────┬──────────────────────┘
                                               │ topic: comments-raw
                                               ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                     SPARK STRUCTURED STREAMING (local[*])                   │
│                                                                             │
│  read Kafka → parse JSON → clean text (UDF)                                 │
│      → VADER (pandas UDF: compound + pos/neg/neu + label)                   │
│      → DistilBERT (mapInPandas: label + confidence)                         │
│      → windowed aggregation (1-min tumbling, 2-min watermark)               │
│                                                                             │
│  sinks:  ① comments-scored → Kafka (live feed)                              │
│          ② comments → PostgreSQL (foreachBatch upsert by id)                │
│          ③ window_stats → PostgreSQL (foreachBatch upsert by window_start)  │
└──────────────┬───────────────────────────────────┬──────────────────────────┘
               │ topic: comments-scored            │ JDBC (psycopg2 upserts)
               ▼                                   ▼
     (optional consumer)              ┌────────────────────────┐
                                      │  POSTGRESQL (docker)   │
                                      │  tables: comments,     │
                                      │          window_stats  │
                                      └───────────┬────────────┘
                                                  │ SELECT
                                                  ▼
                                      ┌────────────────────────┐
                                      │   FASTAPI (main.py)    │
                                      │  /health /api/summary  │
                                      │  /api/timeline         │
                                      │  /api/comments         │
                                      │  /api/words /api/compare│
                                      └───────────┬────────────┘
                                                  │ HTTP (poll 3 s)
                                                  ▼
                                      ┌────────────────────────┐
                                      │  REACT DASHBOARD       │
                                      │  (Vite + Tailwind +    │
                                      │   Recharts)            │
                                      └────────────────────────┘
```

### 1.1 Why this shape (design rationale)
| Decision | Rationale |
|---|---|
| Kafka between producer and Spark | Decouples ingestion from processing; buffers bursts; replayable log; standard industry pattern |
| Spark Structured Streaming | DataFrame API with built-in windowing/watermarks; micro-batch model is simple to explain and scales beyond a script |
| Two sinks (Kafka + Postgres) | Kafka feed = low-latency live view; Postgres = queryable history for API/charts |
| VADER + DistilBERT | Rule-based (transparent, fast) vs learned (context-aware) — running both enables the model-comparison analysis |
| foreachBatch + upserts | Simplest fault-tolerant sink; idempotent on re-runs (no duplicate rows) |
| Polling (not WebSockets) | 3 s polling is trivially simple, stateless, and sufficient for 1-minute windows |

---

## 2. Data Flow Diagrams

### 2.1 Level 0 (context)
```
[Dataset CSV] → (PRODUCER) → [Kafka] → (SPARK) → [PostgreSQL]
                                                  │
(Faculty/Viewer) ←→ (DASHBOARD) ←→ (FASTAPI) ←────┘
```

### 2.2 Level 1 (processing)
```
P1  Ingest:   CSV rows ──build_message──▶ JSON event ──▶ Kafka[comments-raw]

P2  Process:  Kafka[comments-raw] ──parse──▶ raw_df
              raw_df ──clean_text──▶ cleaned_df
              cleaned_df ──vader_analyze──▶ +vader_label/score
                        ──bert_analyze───▶ +bert_label/score
              scored_df ──window(1min)──▶ window_agg

P3  Store:    scored_df ──▶ Kafka[comments-scored]
              scored_df ──upsert(id)──▶ PG.comments
              window_agg ──upsert(window_start)──▶ PG.window_stats

P4  Serve:    PG ──SELECT──▶ FastAPI endpoints ──JSON──▶ React
```

---

## 3. Component Design

### 3.1 producer/producer.py
| Aspect | Design |
|---|---|
| Input | CSV (auto-detects text/label/id/author columns across datasets) |
| Output | Kafka `comments-raw`, JSON value, key = `{source}-{seq}` |
| Config | `--file --rate --limit --loop --shuffle --source`, env `KAFKA_BOOTSTRAP` |
| Errors | Retries=3; skips rows without text; flush+close on Ctrl+C |
| ID policy | Unique per send (`{dataset-id}-{global-seq}`) → idempotent sinks |

### 3.2 spark/nlp.py (pure functions — unit tested)
| Function | Purpose |
|---|---|
| `clean_text(text)` | lowercase; strip URLs, HTML entities, emoji, collapse whitespace |
| `vader_scores(text)` | VADER compound + pos/neg/neu proportions |
| `vader_label(compound)` | ≥ +0.05 positive, ≤ −0.05 negative, else neutral |
| `bert_analyze(text)` | DistilBERT-SST2 → `{positive|negative, confidence}` |
| `analyze_row(row)` | both models in one call (used by tests/tools) |

### 3.3 spark/streaming_job.py
| Aspect | Design |
|---|---|
| Source | `spark.readStream.format("kafka")`, `startingOffsets=latest`, `maxOffsetsPerTrigger=2000` |
| Parse | `from_json` with explicit schema; event timestamp = message `ts` (fallback: Kafka timestamp) |
| VADER | pandas scalar UDF (vectorized batches) |
| DistilBERT | `mapInPandas` with schema = input fields + bert columns (built fresh — `StructType.add` mutates); failures → null cols, stream survives |
| Windowing | 1-min tumbling on `event_ts`, watermark 2 min |
| Sinks | 3 streaming queries: Kafka feed + 2 × foreachBatch upserts |
| Smoke mode | `SKIP_BERT=1` skips the transformer for quick demos |
| Checkpoints | `checkpoints/{kafka-feed,pg-comments,pg-stats}` — exactly-once offsets, resumable |

### 3.4 api/main.py (FastAPI)
| Endpoint | Query params | Returns |
|---|---|---|
| `/health` | — | `{status, database}` |
| `/api/summary` | — | totals, sentiment split + %, avg score, bert coverage, per-source, last_processed |
| `/api/timeline` | `minutes=60` | window rows ordered by start |
| `/api/comments` | `limit=50, source, sentiment, q` | latest scored comments |
| `/api/words` | `limit=15, sentiment` | top-N words with weights |
| `/api/compare` | `limit=500` | agreement %, VADER label accuracy, disagreement examples |
| CORS | `allow_origins=["*"]` | dev dashboard on another port |

### 3.5 frontend (React SPA)
| Aspect | Design |
|---|---|
| Stack | Vite + React 19 + Tailwind v4 + Recharts |
| Data | `src/api.js` fetchers; `usePolling` hook (3 s, 10 s compare) |
| Views | KPI cards, timeline LineChart, donut PieChart, words BarChart, compare panel, live feed, filters |
| Proxy | Vite dev proxy `/api` → `localhost:8000` (no CORS in dev) |
| Resilience | Error banner + status dot when API unreachable; empty states |

---

## 4. Database Schema

### 4.1 `comments`
| Column | Type | Notes |
|---|---|---|
| id | VARCHAR PK | unique per send |
| source | VARCHAR NOT NULL | reddit / youtube |
| author, text, cleaned_text, label | TEXT | label = dataset ground truth |
| vader_label | VARCHAR | positive/negative/neutral |
| vader_score, vader_positive, vader_negative, vader_neutral | DOUBLE PRECISION | VADER output |
| bert_label | VARCHAR | positive/negative (SST-2 has no neutral) |
| bert_score | DOUBLE PRECISION | confidence |
| ts | TIMESTAMP | event time |
| processed_at | TIMESTAMP | sink write time |

Indexes: `ts`, `source`, `vader_label`.

### 4.2 `window_stats`
| Column | Type |
|---|---|
| window_start | TIMESTAMP PK |
| window_end, total, positive, negative, neutral | TIMESTAMP/INTEGER |
| pos_pct, neg_pct, neu_pct, avg_score | DOUBLE PRECISION |
| processed_at | TIMESTAMP |

---

## 5. Sequence Diagram — a comment's journey

```
Producer      Kafka        Spark         Postgres      API        React
   │            │            │              │            │           │
   │──JSON────▶ │            │              │            │           │
   │            │──micro-batch──▶           │            │           │
   │            │            │──clean+VADER+BERT         │           │
   │            │◀─scored JSON─│            │            │           │
   │            │            │──upsert────▶ │            │           │
   │            │            │──upsert agg─▶│            │           │
   │            │            │              │◀──SELECT───│           │
   │            │            │              │──rows─────▶│           │
   │            │            │              │            │──JSON───▶│
   │            │            │              │            │           │──render
```

---

## 6. Error Handling Matrix
| Failure | Detection | Behaviour |
|---|---|---|
| Kafka down | producer/spark connection errors | producer retries ×3; spark fails visibly (restart after Kafka returns) |
| Bad/empty CSV row | producer `build_message` | row skipped |
| Model load/OOM | try/except in `bert_map` | bert cols = null; stream continues (FR-9) |
| Duplicate id in batch | sink dedupe + `ON CONFLICT` | upsert, no crash |
| Postgres down | foreachBatch exception | batch retried on next micro-batch |
| API DB down | `/health` | `{status: degraded}`; dashboard shows banner |
| Dashboard API unreachable | fetch errors | status dot + banner (FR-28) |

---

## 7. Testing Strategy
| Level | Tool | Scope |
|---|---|---|
| Unit | pytest | `nlp.py` cleaning + labeling (12 tests) |
| API | pytest + TestClient | endpoint shapes, filters (6 tests) |
| Integration | manual/ scripted | Kafka console round-trip; pipeline → PG row counts |
| E2E | demo script | producer→dashboard live run |
| Evaluation | `evaluate.py` | accuracy/F1/confusion vs dataset labels |
