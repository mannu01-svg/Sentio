# Docker Guide

## 1. Why Docker here?

Sentio needs eight cooperating services: Kafka, PostgreSQL, MongoDB, a Spark
streaming job with two transformer models, a FastAPI service, a stream
producer and a React dashboard. Running them natively needed Python 3.12,
Java 17, Node.js, Spark's Windows helper binaries and per-OS scripts, and it
broke on Windows (no JDK install, missing `winutils.exe`, `.bat` quoting bugs)
and on machines with Python 3.13+.

Everything now runs in containers from one `docker-compose.yml`, identical on
Windows, macOS (Intel and Apple Silicon) and Linux. The only prerequisite is
Docker Desktop.

```
docker-compose.yml  (project name: sentio)
├── kafka        apache/kafka:3.9.0      :9092 host listener, kafka:29092 inside the network
├── kafka-init   apache/kafka:3.9.0      one-shot: creates comments-raw / -analyze / -scored
├── postgres     postgres:16-alpine      :5432   volume pgdata    (scores, windows, users, history)
├── mongodb      mongo:7                 :27017  volume mongodata (raw comments, analysis documents)
├── models       sentio-app              one-shot: downloads DistilBERT + RoBERTa into volume hf-cache
├── spark        sentio-app              :4040   streaming job (replay + analyze queries), volume checkpoints
├── api          sentio-app              :8000   FastAPI + Swagger, seeds the logins
├── producer     sentio-app              seed pass, then "Go live" bursts (control file in volume shared)
└── frontend     sentio-frontend         :5173   nginx: React build, proxies /api, /health, /docs to api
```

## 2. Images

### 2.1 `sentio-app` (`docker/Dockerfile.app`)
One image for all Python services, so it is built once.

| Layer | Why |
|---|---|
| `python:3.12-slim-bookworm` | PySpark 3.5.4 does not support Python 3.13+ |
| `openjdk-17-jre-headless` | Spark runs on the JVM; Spark 3.5 is not compatible with Java 21 |
| CPU-only PyTorch (`download.pytorch.org/whl/cpu`) | the default wheel pulls ~3 GB of CUDA libraries nobody uses here |
| `requirements.txt` | Spark, FastAPI, transformers, pymongo, yt-dlp + Deno (YouTube needs a JS runtime) |
| `docker/prefetch_spark_jars.py` | downloads the Spark-Kafka connector at build time into `/opt/spark-jars`; Spark loads it via `SPARK_EXTRA_JARS` (no Maven access at runtime) |
| `PYTHONPATH=/app/spark:/app/fetcher` | Spark's Python workers import `nlp`; the API imports `fetchers`, `publisher`, `mongo_store` |

### 2.2 `sentio-frontend` (`docker/Dockerfile.frontend`)
Two stages: `node:22-bookworm-slim` runs `npm ci && npm run build`, then
`nginx:1.27-alpine` serves `dist/` with `docker/nginx.conf`, which proxies
`/api`, `/health`, `/docs`, `/redoc` and `/openapi.json` to `api:8000` and
falls back to `index.html` for React routes.

## 3. Every container explained

### 3.1 kafka
| Setting | Value | Meaning |
|---|---|---|
| KAFKA_PROCESS_ROLES | broker,controller | **KRaft mode**: no ZooKeeper |
| KAFKA_LISTENERS | INTERNAL://:29092, PLAINTEXT://:9092, CONTROLLER://:9093 | one listener for containers, one for the host |
| KAFKA_ADVERTISED_LISTENERS | INTERNAL://kafka:29092, PLAINTEXT://localhost:9092 | containers reach `kafka:29092`; host tools reach `localhost:9092` |
| KAFKA_INTER_BROKER_LISTENER_NAME | INTERNAL | broker-to-broker traffic on the internal listener |
| healthcheck | `kafka-broker-api-versions.sh` | dependants wait until the broker answers |

### 3.2 kafka-init
Creates the three topics (3 partitions each) and exits. `spark`, `api` and
`producer` start only after it **completed successfully**, so nothing ever
subscribes to a topic that doesn't exist yet.

| Topic | Producer | Consumer |
|---|---|---|
| `comments-raw` | producer (seed + live bursts) | Spark replay query |
| `comments-analyze` | API (analyze link/account/topic, Re-score) | Spark analyze query |
| `comments-scored` | Spark | live feed |

### 3.3 postgres
Volume `pgdata`; `db/init.sql` runs on the first start. The healthcheck uses
`pg_isready -h 127.0.0.1` (TCP), which only passes after `init.sql` finished.

### 3.4 mongodb
Volume `mongodata`, database `sentio`, collections `raw_comments` and
`analyses` (indexes are created by the API on first use). Healthcheck:
`mongosh --eval "db.adminCommand('ping').ok"`. Browse it with MongoDB Compass
at `mongodb://localhost:27017`.

### 3.5 models
Runs `scripts/warmup_models.py` with the Hugging Face hub online, saving both
models to the `hf-cache` volume (~750 MB, first run only). If the download
fails it still exits 0: Spark then scores with VADER only until the next start.

### 3.6 spark
`python spark/streaming_job.py`, two streaming queries in FAIR scheduler pools:

| Query | Topic | Trigger | Writes |
|---|---|---|---|
| replay | `comments-raw` | 10 s, max 2,000 messages | `comments`, `window_stats`, `comments-scored` |
| analyze | `comments-analyze` | 3 s | `comments`, `comments-scored` (not the live windows) |

Sizing via environment (defaults suit Docker with ~8 GB): `SPARK_MASTER=local[2]`,
`SPARK_DRIVER_MEMORY=2g`, `NLP_TORCH_THREADS=2`. `SKIP_BERT=1` (`--fast`) skips
the transformer models. Checkpoints persist in the `checkpoints` volume.

### 3.7 api
Seeds the admin and demo logins, then runs Uvicorn on :8000. Swagger UI at
`/docs`. Reads Kafka offsets with the Kafka client for the Pipeline page.

### 3.8 producer
Replays 6,000 shuffled rows of `data/raw/all_sources.csv` (`SEED_ROWS` to
change), then idles watching `/shared/live-stream.json`, which the API writes
when someone presses **Go live**.

### 3.9 frontend
nginx on :5173 (container port 80).

## 4. Commands

```bash
docker compose up -d --build          # build + start everything
docker compose ps                     # status (one-shot services show "Exited (0)")
docker compose logs -f spark          # follow one service
docker compose restart spark          # restart one service
SKIP_BERT=1 docker compose up -d      # VADER-only mode
docker compose down                   # stop, keep data
docker compose down -v                # stop and wipe all volumes
```

The start scripts (`startup/<os>/start.*`) wrap these with `--fast` and `--fresh`.

## 5. Kafka cheat-sheet

```bash
docker exec sma-kafka /opt/kafka/bin/kafka-topics.sh --bootstrap-server localhost:9092 --list
docker exec sma-kafka /opt/kafka/bin/kafka-get-offsets.sh --bootstrap-server localhost:9092 --topic comments-analyze
docker exec sma-kafka /opt/kafka/bin/kafka-console-consumer.sh --bootstrap-server localhost:9092 \
  --topic comments-scored --from-beginning --max-messages 5
```

## 6. PostgreSQL and MongoDB cheat-sheet

```bash
docker exec sma-postgres psql -U sentiment -d sentiment -c "SELECT count(*) FROM comments;"
docker exec sma-postgres psql -U sentiment -d sentiment -c "SELECT id, kind, title, user_email FROM history ORDER BY id DESC LIMIT 5;"

docker exec sma-mongodb mongosh sentio --quiet --eval "db.raw_comments.countDocuments()"
docker exec sma-mongodb mongosh sentio --quiet --eval "db.analyses.find().sort({created_at:-1}).limit(1)"
```

## 7. Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| History stays "scoring pending…" | Spark not running | `docker compose logs --tail 80 spark`; Pipeline tab compares `comments-analyze` with `PostgreSQL · comments` |
| `spark` exits with code 137 | out of memory | `--fast`, or more RAM for Docker (Windows: `.wslconfig` → `memory=8GB`) |
| build fails with `no such host` / timeout | flaky network | re-run (layers are cached); Docker Engine settings → `"dns": ["8.8.8.8","1.1.1.1"]` |
| port already in use | local Postgres/Mongo/other app | change the left port in `docker-compose.yml` |
| model download failed | network | `docker compose up models && docker compose restart spark` |
| Spark stuck after an unclean shutdown | stale checkpoint | `docker compose rm -sf spark && docker volume rm sentio_checkpoints && docker compose up -d spark` |


## YouTube API key (optional, needed on cloud servers)

YouTube blocks yt-dlp from data-centre IPs ("Sign in to confirm you're not a bot"),
so the GitHub Actions cloud demo needs the official **YouTube Data API v3**.
It is free (10,000 units/day, roughly 100 video analyses) and needs no card.

1. Open console.cloud.google.com, sign in, then create a project (e.g. `sentio`).
2. **APIs & Services** -> **Library** -> search **YouTube Data API v3** -> **Enable**.
3. **APIs & Services** -> **Credentials** -> **Create credentials** -> **API key**. Copy it.
4. Optional: **Edit API key** -> **API restrictions** -> restrict to YouTube Data API v3.

Use it:

* **Laptop:** create a file named `.env` in the project folder with
  `YOUTUBE_API_KEY=your-key`, then `docker compose up -d api`. `.env` is git-ignored.
* **Cloud demo:** repo admin -> **Settings** -> **Secrets and variables** -> **Actions**
  -> **New repository secret**: name `YOUTUBE_API_KEY`, value = the key.

Without a key Sentio falls back to yt-dlp, which works on home networks.
