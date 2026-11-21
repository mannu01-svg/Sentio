# Software Design Document (SDD)
## Sentio — Real-Time Social Media Sentiment Analysis Platform

| | |
|---|---|
| **Version** | 2.0 (final) |
| **Companion docs** | `01_SRS.md` (requirements) · `03_Final_Report.md` (results) |

---

## 1. Architecture Overview

```
                            ┌──────────────────────────────────────────────┐
                            │              INGESTION SOURCES               │
                            │  bundled Kaggle datasets (274k rows, 54MB)   │
                            │  yt-dlp (YouTube live) · PullPush (Reddit)   │
                            │  paste · account crawl · keyword/topic match │
                            └───────────────────────┬──────────────────────┘
                                                    │
              producer.py (seed + live bursts)      │ api/main.py ingesters
              control-file driven                   │ (post/account/keyword/topic)
                            └───────────┬──────────┘
                                        │ topic: comments-raw (3 partitions)
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                  SPARK STRUCTURED STREAMING (local[6], 10 s trigger)        │
│                                                                             │
│  read Kafka → parse JSON → clean text (UDF)                                 │
│      → VADER (pandas UDF: compound + label)                                 │
│      → DistilBERT-SST2 (mapInPandas) + fine-tuned weights (84.2%)           │
│      → cardiffnlp tweet-RoBERTa LLM (authoritative 3-class score)           │
│      → 1-min tumbling window + watermark                                    │
│                                                                             │
│  ONE foreachBatch write path (checkpointed, exactly-once offsets):          │
│      ① PostgreSQL.comments        (upsert by id, kafka-python-ng feed)      │
│      ② PostgreSQL.window_stats    (upsert by window_start)                  │
│      ③ Kafka comments-scored      (live feed for the dashboard)             │
└──────────────────────────────┬──────────────────────────────────────────────┘
                               ▼
                     ┌─────────────────────────────┐
                     │     POSTGRESQL (docker)     │
                     │  comments · window_stats ·  │
                     │  users · history            │
                     └──────────────┬──────────────┘
                                    │ SELECT
                                    ▼
                     ┌──────────────────────────────┐
                     │   FASTAPI (30+ endpoints)    │
                     │  analytics · analyze · auth  │
                     │  history · trends · export   │
                     └──────────────┬───────────────┘
                                    │ HTTP (poll 2.5–12 s)
                                    ▼
                     ┌──────────────────────────────┐
                     │  REACT DASHBOARD (8 tabs)    │
                     │  Vite + Tailwind + Recharts  │
                     │  per-account (user_email)    │
                     └──────────────────────────────┘
```

### 1.1 Design rationale
| Decision | Rationale |
|---|---|
| Kafka KRaft (no Zookeeper) | one less system to run/explain; modern default |
| Single `foreachBatch` write path | the graph is computed once, not 3×; PG upsert + Kafka feed + window stats in one checkpointed pass |
| `OMP_NUM_THREADS` pinned **before torch imports** | Spark's JVM overrides it to 1 inside python workers → torch ran single-threaded (~200 s/2k batch). Setting it at module import recovered ~6.5× throughput |
| 256-char truncation before scoring | 34/s @512 chars → 70/s @256; label drift negligible |
| Polling (2.5–12 s) not WebSockets | stateless, trivially reliable, sufficient for 1-min windows |
| History in PostgreSQL (not memory) | analyses survive API restarts; per-account attribution via `user_email` |
| Auto-migration at API startup | existing DBs upgrade with no manual SQL (`history`, `user_email`, indexes) |
| Per-account endpoints 401 without `?user=` | defense-in-depth behind the frontend login redirect |
| Weights split into ≤90 MB parts | GitHub's 100 MB hard limit; rejoined by `split_weights.py --join` at setup |

---

## 2. Data Flow Diagrams

### 2.1 Level 0 (context)
```
[Datasets / yt-dlp / PullPush] → (INGESTERS) → [Kafka] → (SPARK) → [PostgreSQL]
                                                                  │
(Logged-in Analyst) ←→ (8-TAB DASHBOARD) ←→ (FASTAPI + AUTH) ←────┘
```

### 2.2 Level 1 (processing)
```
P1  Ingest:   CSV rows / fetched comments ──▶ JSON event ──▶ Kafka[comments-raw]

P2  Process:  Kafka[comments-raw] ──parse──▶ raw_df
              raw_df ──clean_text──▶ cleaned_df
              cleaned_df ──vader──▶ +vader_label/score
                         ──distilbert (fine-tuned)──▶ +bert_label/score
                         ──roberta LLM──▶ +llm_label/score
              scored_df ──window(1min, watermark)──▶ window_agg

P3  Store:    ONE foreachBatch ──▶ upsert PG.comments + PG.window_stats
                                 ──▶ Kafka[comments-scored]

P4  Serve:    PG ──SELECT──▶ FastAPI (auth: signup/login; per-account history)
              FastAPI ──JSON──▶ React (8 tabs, polling)
```

---

## 3. Component Design

### 3.1 producer/producer.py
| Aspect | Design |
|---|---|
| Input | `data/raw/all_sources.csv` (auto-detects text/label/id/author/source columns) |
| Output | Kafka `comments-raw`, JSON value, key = `{source}-{seq}` |
| Modes | seed pass (default 6,000 rows @150/s) → idle; live bursts on control file |
| Control | `logs/live-stream.json` `{"until": <epoch>, "rate": N}` — written by the API's "Go live" endpoint |
| Errors | retries=3; skips empty rows; flush+close on Ctrl+C |
| ID policy | unique per send → idempotent sinks |

### 3.2 spark/nlp.py (pure scoring — unit tested)
| Function | Purpose |
|---|---|
| `clean_text(text)` | lowercase; strip URLs, HTML entities, emoji, collapse whitespace |
| `vader_scores/label` | compound + pos/neg/neu; ≥+0.05 pos, ≤−0.05 neg, else neutral |
| `bert_batch(df)` | fine-tuned DistilBERT (3-class), `torch.inference_mode()`, 256-char cap |
| `llm_batch(df)` | cardiffnlp tweet-RoBERTa (authoritative live score) |
| `warm()` | pre-load models in the driver before workers fork |
| Env | `NLP_TORCH_THREADS` → `OMP_NUM_THREADS`/`MKL_NUM_THREADS` set at import, **before** torch loads; `NLP_MAX_CHARS=256`; `HF_HUB_OFFLINE=1` in CI |

### 3.3 spark/streaming_job.py
| Aspect | Design |
|---|---|
| Source | `readStream.format("kafka")`, `startingOffsets=latest`, `maxOffsetsPerTrigger=8000`, trigger `processingTime="10 seconds"` |
| Engine | `local[6]` × `NLP_TORCH_THREADS=8` (48 cores), arrow batches 512, `SPARK_DRIVER_MEMORY` env |
| Scoring | VADER UDF + one `mapInPandas` for both transformers; failures → null cols, stream survives |
| Windowing | 1-min tumbling on event ts, watermark; `dt.floor("60s")` groupby inside `foreachBatch` |
| Sinks | **one** `foreachBatch write_batch`: PG upserts (psycopg2) + Kafka feed (kafka-python-ng producer) + window stats |
| Checkpoints | `checkpoints/pg-comments` (single sink) — resumable; `first_run` detection keys off `_metadata` |
| Fast mode | `SKIP_BERT=1` skips transformers for quick demos |

### 3.4 api/main.py (FastAPI, 30+ endpoints)
| Group | Endpoints | Notes |
|---|---|---|
| Auth | `POST /api/signup`, `/api/login` | PBKDF2-SHA256 ×120k; token returned |
| Analytics | `/api/summary`, `/api/timeline`, `/api/comments`, `/api/words`, `/api/compare`, `/api/pipeline` | public; SQL aggregation |
| Ingest | `POST /api/analyze`, `/api/analyze-account`, `/api/keyword-search`, `/api/topics/stream` | yt-dlp / PullPush / pool-matched (indexed SQL, `DISTINCT ON` dedupe) |
| Live | `POST /api/stream/live`, `/api/stream/stop`, `GET /api/stream/status` | control-file bursts |
| Insights | `/api/trends`, `/api/trending`, `/api/alerts`, `/api/spam`, `/api/export` | velocity, spikes, heuristics, CSV |
| Per-account | `GET /api/posts`, `/api/accounts`, `/api/topics/streams`, `/api/history` | **DB-backed** (survive restarts), `_require_user` → 401 without `?user=` |
| Threads | `/api/threads/auth-url`, `/status`, `/callback`, `/disconnect` | OAuth flow (needs Meta app creds) |

### 3.5 frontend (React SPA, 8 tabs)
| Aspect | Design |
|---|---|
| Stack | Vite + React 19 + Tailwind v4 + Recharts |
| Auth | `AuthProvider` (localStorage `sentio-user`); all routes `Protected` → guests redirected to `/login` |
| Attribution | `api.js` attaches `user_email` to every analyze call + `?user=` to per-account fetches |
| Tabs | Dashboard (KPIs/timeline/donut/trending/live) · Live (filtered feed) · Analyze (platform picker + post/account/keyword) · Trends · Models · Pipeline · Sources · History (owner chips) · Settings |
| TopicStream | reads the history-driven `/api/topics/streams` (keyword match — works for video-id and topic-slug posts) |
| Resilience | error banners, empty states, polling hook with per-tab interval |

### 3.6 models/ (training + inference)
| Component | Design |
|---|---|
| `training/prepare_data.py` | merged dataset → `train.jsonl` (59k) + `val.jsonl` (4.6k) |
| `training/finetune.py` | DistilBERT 3-class fine-tune, 3 epochs, auto-resume from latest checkpoint |
| `training/split_weights.py` | `--split` (90 MB parts + SHA256) / `--join` (rebuild safetensors) |
| `sentiment-finetuned/` | final weights: 84.2% validation accuracy (63,603 training rows) |

---

## 4. Database Schema

### 4.1 `comments`
| Column | Type | Notes |
|---|---|---|
| id | TEXT PK | unique per send |
| source | VARCHAR(32) | reddit / youtube / x / facebook / instagram / threads / paste |
| author, text, cleaned_text, label | TEXT | label = dataset ground truth |
| vader_label/score/pos/neg/neu | | VADER output |
| bert_label/score | | fine-tuned DistilBERT |
| llm_label/score | | cardiffnlp RoBERTa (authoritative) |
| ts, processed_at | TIMESTAMP | event time / sink write |
| post_id, post_title | TEXT | link/topic analysis grouping |

Indexes: `ts`, `source`, `vader_label`, `post_id`, `(source, lower(left(text,200)) text_pattern_ops)` for the topic-match ILIKE scan.

### 4.2 `users`
| Column | Type |
|---|---|
| email | TEXT PK |
| name, password_hash | TEXT |
| created_at, last_login | TIMESTAMP |

### 4.3 `history`
| Column | Type | Notes |
|---|---|---|
| id | SERIAL PK | |
| kind | TEXT | post / account / topic / keyword |
| post_id, title, platform, handle, keyword | TEXT | what was analyzed |
| posts | TEXT | comma-separated post ids |
| comments_published | INTEGER | |
| **user_email** | TEXT | who ran it (per-account attribution) |
| created_at | TIMESTAMP | |

Indexes: `created_at DESC`, `user_email`.

### 4.4 `window_stats`
| Column | Type |
|---|---|
| window_start | TIMESTAMP PK |
| window_end, total, positive, negative, neutral | TIMESTAMP/INTEGER |
| pos_pct, neg_pct, neu_pct, avg_score | DOUBLE PRECISION |
| top_words, processed_at | TEXT/TIMESTAMP |

---

## 5. Sequence Diagram — a comment's journey

```
Ingester      Kafka        Spark           Postgres      API          React
   │            │            │                │            │             │
   │──JSON────▶ │            │                │            │             │
   │            │─micro-batch─▶               │            │             │
   │            │            │─clean+VADER+BERT+LLM        │             │
   │            │◀────────── foreachBatch: upsert + Kafka feed           │
   │            │            │──upsert──────▶ │            │             │
   │            │            │──upsert agg──▶ │            │             │
   │            │            │                │◀──SELECT───│             │
   │            │            │                │──rows─────▶│             │
   │            │            │                │            │──JSON─────▶ │
   │            │            │                │            │             │─render
```

---

## 6. Error Handling Matrix
| Failure | Detection | Behaviour |
|---|---|---|
| Kafka down | producer/spark connection errors | producer retries ×3; spark fails visibly (restart after Kafka returns) |
| Bad/empty CSV row | producer `build_message` | row skipped |
| Model load/OOM | try/except in `bert_map` | bert/llm cols = null; stream continues |
| Duplicate id in batch | `ON CONFLICT` upserts | no crash, idempotent |
| Postgres down | foreachBatch exception | batch retried on next micro-batch |
| `history` table missing on old DB | startup migration | `_ensure_history_table()` CREATE + ALTER, idempotent |
| Per-account endpoint without user | `_require_user` | 401 `login required` |
| API DB down | `/health` | `{status: degraded}`; dashboard banner |
| Dashboard API unreachable | fetch errors | status dot + banner; empty states |

---

## 7. Testing Strategy
| Level | Tool | Scope | Result |
|---|---|---|---|
| Unit | pytest | `nlp.py` cleaning/labeling + API helpers + features | ✅ |
| API | pytest + TestClient | endpoint shapes, filters (DB-skipped in bare CI) | ✅ |
| Threads | pytest (hermetic) | env persistence without touching `.env.local` | ✅ |
| Integration | scripted | Kafka console round-trip; pipeline → PG row counts | ✅ |
| E2E | demo run | producer → dashboard live (369k+ rows accumulated) | ✅ |
| CI | Jenkins 5 stages | compile → lint → tests → frontend build → compose config | ✅ green |

**Total: 42 pytest cases, all green at delivery.**
