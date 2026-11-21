# Final Project Report (SDLC Format)
## Sentio — Real-Time Social Media Sentiment Analysis using Kafka, Spark & NLP

| | |
|---|---|
| **Team** | Mannat Muthreja · Khushi Balyan · Ami Lal |
| **Guide** | *(faculty guide name)* |
| **Institution** | NIIT University · Department of CSE |
| **Duration** | 17 September – 21 November 2026 |
| **Start date** | 17 September 2026 |
| **Mid-eval submission** | 20 September 2026 |
| **Final submission** | 26 November 2026 |
| **Version** | 2.0 (delivered) |
| **Repository** | github.com/mannu01-svg/Sentio |

---

## Abstract
Public opinion on social media forms in minutes, but manual analysis cannot
scale. **Sentio** is a real-time sentiment analysis platform that ingests
social media comments from bundled datasets (274k rows) and live sources
(YouTube via yt-dlp, Reddit via PullPush, paste, account crawls, keyword and
topic search), classifies their sentiment with three scorers — VADER (lexicon),
DistilBERT-SST2 (transformer) and **our own fine-tuned DistilBERT (84.2%
validation accuracy)** with cardiffnlp tweet-RoBERTa as the authoritative live
score — aggregates per-minute statistics with Apache Spark Structured
Streaming, and serves 30+ REST endpoints over FastAPI with per-account history
and an 8-tab React dashboard. Data flows through Apache Kafka (KRaft), which
decouples ingestion from processing. Sustained streaming throughput reaches
**≈59 records/s** (a 6.5× improvement over the naive implementation). The
project demonstrates industrial big-data and software-engineering practice —
message queuing, micro-batch stream processing, windowed aggregation,
fault-tolerant idempotent sinks, authentication, CI/CD — while remaining
simple enough to run on one machine with one command.

**Keywords** — sentiment analysis, Apache Kafka, Spark Structured Streaming,
VADER, DistilBERT, fine-tuning, real-time analytics, FastAPI, React, CI/CD

---

## 1. Introduction

### 1.1 Motivation
Brands, researchers and journalists need to understand public sentiment as it
happens: product launches trigger thousands of comments per hour, and overall
mood shifts in minutes. Batch analysis of yesterday's data misses this window.
A streaming platform — ingest → classify → aggregate → visualize, with
per-account history — answers "what does the public feel right now?" and
"what did *I* analyze last week?"

### 1.2 Problem Statement
Build a platform that continuously ingests social media comments (datasets +
live platforms), classifies their sentiment with complementary NLP approaches
including a custom fine-tuned model, aggregates per-minute statistics, ties
every analysis to a user account, and presents live analytics on a multi-tab
dashboard — while quantitatively comparing the classification approaches.

### 1.3 Objectives
1. Ingest comments as a simulated live stream through Apache Kafka, with
   on-demand bursts controlled from the dashboard.
2. Process the stream with Spark Structured Streaming: clean, classify, window.
3. Implement three scorers: VADER (lexicon), DistilBERT-SST2 (transformer), and
   a fine-tuned DistilBERT on 63.6k social-media rows.
4. Persist scored comments, windowed aggregates, users, and analysis history.
5. Serve 30+ REST endpoints: analytics, link/account/keyword/topic analysis,
   trends, alerts, spam, export, auth, history.
6. Visualize on an 8-tab dashboard with per-account isolation.
7. Evaluate all models against ground-truth labels (accuracy, F1, confusion).
8. Deliver with one-command startup per OS and a green CI pipeline.

### 1.4 Report Structure
§2 background · §3 SDLC process & timeline · §4 requirements (full:
`01_SRS.md`) · §5 design (full: `02_SDD.md`) · §6 implementation · §7 testing
· §8 results · §9 limitations · §10 future work · §11 team contribution ·
§12 references.

---

## 2. Background & Related Work

### 2.1 Sentiment analysis approaches
| Family | Method | Strengths | Weaknesses |
|---|---|---|---|
| Lexicon / rule-based | **VADER** (Hutto & Gilbert, 2014) | fast, transparent, tuned for social text | misses context; fixed vocabulary |
| Transformer (generic) | **DistilBERT-SST2** (Sanh et al., 2019) | context-aware; fast inference | binary only; trained on movie reviews, not social text |
| Transformer (fine-tuned) | **our DistilBERT** | 3-class, social-media-trained: **84.2% val accuracy** | needs labeled data + GPU/CPU hours |
| Transformer (domain) | **cardiffnlp tweet-RoBERTa** | trained on 124M tweets; the authoritative live score | heavier; English-centric |

### 2.2 Streaming architectures
Kafka (Kreps et al., 2011) provides a durable, replayable log decoupling
producers from consumers; KRaft removes the Zookeeper dependency. Spark
Structured Streaming (Zaharia et al., 2013) treats the stream as micro-batches
with DataFrame semantics, native windowing and watermarks. This project
applies both patterns at demo scale with a single checkpointed `foreachBatch`
sink.

### 2.3 Why three scorers?
Running VADER, generic DistilBERT, and a fine-tuned/Domain model side by side
turns the platform into a controlled comparison: identical inputs, measurable
agreement, and a quantified answer to "does fine-tuning help on social text?"
(It does: 84.2% vs 64.1% for generic DistilBERT on our data.)

---

## 3. SDLC Process & Timeline

### 3.1 Process model
Incremental/agile hybrid: 2-week sprints, a demoable increment at every sprint
boundary, Jira board with epics → stories → sub-tasks (full backlog and
step-by-step board setup: `07_Jira_Guide.md`).

### 3.2 Timeline (17 September → 21 November)
| Phase | When | Milestone |
|---|---|---|
| Foundations | 17–19 Sep | repo + docker-compose infra (Kafka+PG) healthy |
| Ingestion & first scores | 22–30 Sep | producer → Kafka → VADER → scored rows in PG |
| Full pipeline + API | 1–12 Oct | DistilBERT + windows + FastAPI serving |
| Dashboard | 13–19 Sep | 8 tabs live — first full end-to-end demo |
| Link/account analysis | 1–17 Oct | analyze by URL/account/keyword/topic, trends/alerts/spam/export |
| **Mid-eval submission** | **20 Sept** | demo + report |
| Auth & history | 20–27 Oct | signup/login, per-account history |
| Mid-eval fixes | 20–27 Oct | history persistence, attribution, API hardening |
| Fine-tuning + CI | Nov wk 1–2 | **84.2% val accuracy**; Jenkins CI green |
| Hardening + delivery | Nov wk 3–4 | perf tuning ~59 rec/s, one-command startup, docs freeze |
| **Final evaluation** | **Nov wk 4** | full demo + viva |

### 3.3 Requirement engineering
Requirements evolved across the timeline: Sprint 1–2 fixed the core pipeline
(FR-1..13), the first full demo (Sep) exposed the need for link analysis and
trends (FR-30..37 range), mid-term feedback drove auth + per-account history
(FR-26..29), and performance work in Nov tightened NFR-2 to ~59 rec/s. The SRS
(`01_SRS.md`, v2.0) is the final consolidated specification — 40 FRs, 8 NFRs.

---

## 4. Requirements (summary)
Full specification: `docs/01_SRS.md`. 40 functional requirements across
ingestion (FR-1..9), stream processing (FR-10..14), storage (FR-15..17), API
(FR-18..25), auth & history (FR-26..29), dashboard (FR-30..37), training &
evaluation (FR-38..40); 8 non-functional requirements (latency, throughput,
usability, reliability, reproducibility, maintainability, portability,
security).

---

## 5. Design
Full design: `docs/02_SDD.md` (architecture, DFDs, component design, DB
schema, sequence diagram, error matrix, testing strategy).

### 5.1 Architecture (one line per stage)
```
Datasets + live sources → Kafka[comments-raw]
  → Spark: clean → VADER + DistilBERT(fine-tuned) + RoBERTa LLM → 1-min windows
  → ONE foreachBatch: PG.comments + PG.window_stats + Kafka[comments-scored]
  → FastAPI (30+ endpoints, auth, per-account history)
  → React 8-tab dashboard (polling)
```

### 5.2 Key design decisions
| Decision | Alternative rejected | Why |
|---|---|---|
| Kafka KRaft (no Zookeeper) | Kafka + Zookeeper | one less system to run/explain |
| Single `foreachBatch` sink | 3 separate streaming queries | graph computed once, not 3×; one checkpoint |
| `OMP_NUM_THREADS` set before torch imports | post-init `torch.set_num_threads` | Spark's JVM silently overrides it to 1 in python workers; import-time env is the only reliable fix (6.5× throughput) |
| Fine-tuned DistilBERT for the Models page, RoBERTa for live scoring | generic models everywhere | domain fine-tune wins on labels; RoBERTa wins on live robustness |
| History in PostgreSQL with `user_email` | in-memory registry | survives API restarts; per-account isolation |
| Auto-migration at API startup | manual SQL / init-only scripts | init.sql runs once; existing DBs must upgrade themselves |
| Weights split ≤90 MB + SHA256 | Git LFS / release assets | no LFS in scope; deterministic rejoin at setup |
| One-command startup per OS | README-only instructions | demo reliability; macOS setsid fallback, Windows bat flow |

---

## 6. Implementation

### 6.1 Technology stack
Python 3.12 · Kafka (apache/kafka 3.9, KRaft) · PostgreSQL 16 · PySpark 3.5.4 ·
vaderSentiment 3.3.2 · transformers 5.x (DistilBERT + cardiffnlp RoBERTa) ·
torch 2.x (CPU) · FastAPI · psycopg2 · kafka-python-ng ·
React 19 + Vite + Tailwind v4 + Recharts · Docker Compose · Jenkins LTS.

### 6.2 Module walkthrough
| Module | Responsibility | Highlights |
|---|---|---|
| `producer/producer.py` | CSV → Kafka replay | seed + live-burst control file; column auto-detection; unique ids |
| `spark/nlp.py` | scoring functions | unit-tested; thread env pinned at import; 256-char cap; `inference_mode` |
| `spark/streaming_job.py` | stream processing | parse → clean → dual transformers → windows → single `foreachBatch` (PG + Kafka) |
| `api/main.py` | REST platform | 30+ endpoints; PBKDF2 auth; per-account history; auto-migration; indexed-SQL topic matching |
| `frontend/src/*` | 8-tab dashboard | polling hook; Recharts; Protected routes; owner chips; Go-live button |
| `models/training/*` | fine-tuning pipeline | prepare → finetune (auto-resume) → split/join weights |
| `evaluation/evaluate.py` | evaluation | accuracy, per-class P/R/F1, confusion matrices; DB or CSV |
| `startup/*` | DX | one-command per OS; bootstrap (venv, JDK, weights, models, demo user) |
| `Jenkinsfile` + `run_jenkins.sh` | CI | 5 stages; zero-click AUTO mode (plugins baked, admin created, job auto-created, build queued) |

### 6.3 Notable implementation details
- **Thread-env fix:** Spark's JVM sets `OMP_NUM_THREADS=1` inside python
  workers, silently single-threading torch (~200 s per 2k-row batch).
  `nlp.py` exports `OMP_NUM_THREADS`/`MKL_NUM_THREADS` from `NLP_TORCH_THREADS`
  at module import — before torch loads — recovering ~6.5× throughput
  (~9 → ~59 rec/s sustained).
- **Single-pass sink:** three streaming queries recomputed the whole graph 3×;
  collapsing to one `foreachBatch` (PG upsert + Kafka feed + pandas window
  groupby) was the second-largest win.
- **Idempotent sinks:** unique event ids + `ON CONFLICT` upserts — pipeline
  restarts never duplicate rows.
- **History attribution:** every analyze endpoint persists `user_email`;
  `/api/posts|accounts|topics/streams|history` read the DB (not memory) and
  401 without a user — analyses survive API restarts and stay per-account.
- **Weight distribution:** 268 MB fine-tuned model split into 3 ≤90 MB parts
  + SHA256; `bootstrap.sh` rejoins them on fresh clones (GitHub's 100 MB
  limit workaround without LFS).

---

## 7. Testing

| Level | Suite | Result |
|---|---|---|
| Unit — NLP + API helpers + features + threads | pytest, 42 cases | ✅ 42/42 |
| API — endpoint shapes/filters (live DB) | TestClient (DB-skipped in bare CI) | ✅ |
| Integration — Kafka round-trip, PG row counts | scripted | ✅ |
| E2E — producer → Spark → PG → API → dashboard | demo runs | ✅ (369k+ rows accumulated) |
| CI — Jenkins 5 stages (compile → lint → tests → frontend → compose) | Jenkins LTS | ✅ green |
| Model — validation accuracy | 4.6k held-out rows | ✅ 84.2% |

---

## 8. Results

### 8.1 End-to-end demonstration
A fresh clone → `bash startup/linux/setup.sh` → full platform running in one
command: 4 services green, demo user seeded, Jenkins CI queued. Accumulated
**369k+ scored comments** across 7 sources with no duplicates. Live bursts
(dashboard "Go live") stream at 40–120 msg/s; scores appear on the dashboard
within ~30–60 s.

### 8.2 Model evaluation
| Model | Accuracy | Notes |
|---|---|---|
| VADER | ≈56% | weak on negative recall; neutral band helps on questions |
| DistilBERT-SST2 (generic) | ≈64% | binary; movie-review domain |
| **DistilBERT (fine-tuned, ours)** | **84.2%** (validation) | 3-class, 63.6k social-media rows, 3 epochs |
| cardiffnlp tweet-RoBERTa | live authority | trained on 124M tweets; used as the dashboard's authoritative score |

### 8.3 Performance
| Metric | Before | After |
|---|---|---|
| Sustained stream throughput | ~9 rec/s | **~59 rec/s** (6.5×) |
| Transformer batch (2k rows) | ~200 s | ~34 s |
| Topic/keyword stream (X/Reddit) | full 150k-row Python scan | indexed SQL, ~0.4 s |
| Keyword search attribution | dropped silently | `user_email` propagated |

### 8.4 Interpretation
1. **Fine-tuning is the single biggest accuracy lever** (+20 pts over generic
   DistilBERT) — domain data beats architecture.
2. **Throughput bottlenecks hide in the environment**, not the code: the
   thread-env override and the 3× graph recomputation accounted for most of
   the 6.5× gap.
3. **Disagreement between scorers is the finding, not a bug** — the dashboard
   surfaces corrections (LLM vs VADER) as demo material.

---

## 9. Limitations
- English-only; all models are English-centric.
- X/Reddit real-time access is bot-walled (HTTP 403/521) — live streams for
  those platforms are pool-matched from dataset rows; YouTube is fully live.
- Single broker / single machine — no replication or horizontal scale.
- Sarcasm and heavy irony remain hard for all three scorers.
- Threads/Instagram/Facebook OAuth flows are built but need Meta app
  credentials to activate.

## 10. Future Work
- Meta app credentials → activate the built Threads/Instagram/Facebook OAuth.
- GPU inference for higher throughput; batch the Kafka feed writes.
- Kafka multi-broker + Spark cluster for scale experiments.
- WebSocket push for sub-second dashboard updates.
- Periodic model re-evaluation and drift monitoring inside the pipeline.

## 11. Team Contribution
| Member | Workstream | Key deliverables |
|---|---|---|
| Khushi Balyan | CI/CD, Startup Tooling, Datasets & Docs | Jenkins CI (zero-click), one-command startup per OS, dataset bundling (54 MB), documentation set |
| Mannat Muthreja | Pipeline, Producer, Frontend & Performance | streaming job, producer, 8-tab dashboard, history/API features, perf tuning (6.5×), fine-tune (84.2%) |
| Ami Lal | Auth, Link Analysis, Tests & Trends | Sentio rebrand, PBKDF2 signup/login, link/account analysis, trends/alerts/spam/export, 42-case test suite |

Full phase-by-phase plan and RACI: `docs/04_Work_Division.md`.

## 12. References
1. C. Hutto and E. Gilbert, "VADER: A Parsimonious Rule-based Model for Sentiment Analysis of Social Media Text," *ICWSM*, 2014.
2. V. Sanh et al., "DistilBERT, a distilled version of BERT," *arXiv:1910.01108*, 2019.
3. F. Barbieri et al., "TweetEval: Unified Benchmark and Comparative Evaluation for Tweet Classification" (cardiffnlp twitter-roberta), 2020.
4. M. Zaharia et al., "Discretized Streams: Fault-Tolerant Streaming Computation at Scale," *SOSP*, 2013.
5. J. Kreps et al., "Kafka: a Distributed Messaging System for Log Processing," *NetDB*, 2011.
6. Apache Spark Structured Streaming Programming Guide, spark.apache.org.
7. Datasets: Kaggle — *Twitter and Reddit Sentimental Analysis Dataset* (cosmos98) + 6 merged Kaggle sources; UCI — *YouTube Spam Collection* (CC BY 4.0).

### Appendix A — Repository map
```
docs/           this report + SRS, SDD, guides (Docker/Jenkins/Jira/GitHub), demo script
producer/       CSV → Kafka replay (seed + live bursts)
spark/          streaming job + NLP scoring (unit tested)
api/            FastAPI platform (30+ endpoints, auth, history)
frontend/       React 8-tab dashboard
models/         fine-tuning pipeline + 84.2% weights (split parts)
evaluation/     model evaluation vs labels
data/raw/       bundled datasets (54 MB, 274k rows)
db/             Postgres init schema
docker-compose.yml   Kafka (KRaft) + PostgreSQL
Jenkinsfile + run_jenkins.sh + Dockerfile.jenkins + jenkins/    CI
startup/{linux,mac,windows}/    one-command startup per OS
tests/          42 pytest cases
```
