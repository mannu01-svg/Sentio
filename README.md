# Social Media Sentiment Analysis — Real-Time Pipeline

Kafka → Spark Structured Streaming → VADER + DistilBERT → PostgreSQL → FastAPI → React dashboard.

![stack](https://img.shields.io/badge/kafka-3.9-black) ![spark](https://img.shields.io/badge/spark-3.5.4-orange) ![python](https://img.shields.io/badge/python-3.12-blue) ![react](https://img.shields.io/badge/react-19-cyan)

## What it does
1. **Producer** replays a comments CSV (Reddit/YouTube datasets) into Kafka as a simulated live stream.
2. **Spark Structured Streaming** consumes, cleans text, scores sentiment with **VADER** (lexicon) and **DistilBERT** (transformer), aggregates 1-minute windows.
3. **Sinks** write scored comments + window stats to PostgreSQL (idempotent upserts) and a scored JSON feed back to Kafka.
4. **FastAPI** serves summary / timeline / comments / words / model-comparison endpoints.
5. **Dashboard** (React + Recharts) polls every 3 s: KPIs, sentiment timeline, distribution, trending words, live feed, VADER-vs-BERT comparison panel.
6. **Evaluation** scores both models against dataset labels (accuracy, F1, confusion matrices).

## Architecture
```
CSV → producer.py → Kafka[comments-raw] → Spark streaming
      ├── clean → VADER → DistilBERT → 1-min windows
      ├── → Kafka[comments-scored]
      ├── → PostgreSQL.comments (upsert id)
      └── → PostgreSQL.window_stats (upsert window)
                    ↓
             FastAPI :8000  ←— poll 3s —  React :5173
```

## Quickstart
```bash
# 1. infra: Kafka + Postgres (wait for "healthy")
docker compose up -d
docker compose ps

# 2. python env
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt

# 3. Spark streaming job (SKIP_BERT=1 for a light smoke run)
./run_spark.sh                      # needs Java 17: export JAVA_HOME to your JDK
# smoke mode: SKIP_BERT=1 ./run_spark.sh

# 4. data: put a Kaggle CSV at data/raw/reddit.csv (see data/README.md)
#    or use the bundled sample:
python producer/producer.py --file data/sample_comments.csv --rate 10 --loop

# 5. API
.venv/bin/uvicorn api.main:app --port 8000     # docs at /docs

# 6. dashboard
cd frontend && npm install && npm run dev       # http://localhost:5173

# 7. evaluate models vs labels (DB rows, or CSV offline)
.venv/bin/python evaluation/evaluate.py
.venv/bin/python evaluation/evaluate.py --csv data/raw/reddit.csv --sample 2000
```

## Java note (Spark needs JDK 17)
```bash
# example user-local install (no sudo):
curl -fsSL -o /tmp/jdk.tar.gz https://download.java.net/java/GA/jdk17.0.2/dfd4a8d0985749f896bed50d7138ee7f/8/GPL/openjdk-17.0.2_linux-x64_bin.tar.gz
mkdir -p ~/.tools && tar xzf /tmp/jdk.tar.gz -C ~/.tools && mv ~/.tools/jdk-17.0.2 ~/.tools/jdk-17
export JAVA_HOME=~/.tools/jdk-17 && export PATH=$JAVA_HOME/bin:$PATH
```
`run_spark.sh` already prefers `~/.tools/jdk-17` if present.

## Datasets
| File | Where | Notes |
|---|---|---|
| `data/sample_comments.csv` | bundled | 50 labeled YouTube-style comments — works out of the box |
| `data/raw/reddit.csv` | Kaggle: *Twitter and Reddit Sentimental Analysis Dataset* (cosmos98) | ~49k Reddit comments with sentiment labels |
| `data/raw/youtube.csv` | Kaggle YouTube comments dataset or UCI YouTube Spam Collection | optional second source |

Producer auto-detects common column names (`comment/text/CONTENT`, `label/sentiment/CLASS`, …).

## Tests
```bash
.venv/bin/pytest tests/ -v        # 18 tests: NLP cleaning/labeling + API endpoints
```

## Documentation (`docs/`)
| Doc | Content |
|---|---|
| `01_SRS.md` | IEEE-style requirements (FR-1..29, NFR-1..8, use cases) |
| `02_SDD.md` | architecture, DFDs, sequence diagram, DB schema, API contract, error matrix |
| `03_Final_Report.md` | full report: abstract → results → references |
| `04_Work_Division.md` | workstreams, phase plan, RACI matrix (team of 4) |
| `05_Docker_Guide.md` | every container/env var explained + troubleshooting |
| `06_Jenkins_Guide.md` | CI pipeline stages + local Jenkins setup |
| `07_Jira_Guide.md` | epics/stories, 3-sprint plan, story points |
| `08_GitHub_Guide.md` | branching, PRs, issues, commit convention |
| `09_Demo_and_Viva.md` | 10-min demo script + 15 viva Q&As |

## Project structure
```
producer/producer.py      CSV → Kafka replay (rate/loop/shuffle)
spark/nlp.py              VADER + DistilBERT scoring (unit tested)
spark/streaming_job.py    Kafka → clean → score → windows → sinks
api/main.py               FastAPI: /api/summary timeline comments words compare
frontend/                 React + Vite + Tailwind + Recharts dashboard
evaluation/evaluate.py    accuracy / F1 / confusion vs labels
db/init.sql               Postgres schema
docker-compose.yml        Kafka (KRaft) + PostgreSQL
Jenkinsfile               CI: lint → tests → frontend build → compose check
```

## Verified numbers (demo run)
- 4,300+ comments streamed & scored end-to-end without duplicates
- VADER 56.0% / DistilBERT 64.1% label accuracy (4,509 labeled Reddit comments)
- Model agreement 44.1% — disagreement analysis on the dashboard
