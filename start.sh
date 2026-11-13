#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# One command to run the entire sentiment-analysis pipeline.
#
#   ./start.sh            full mode (VADER + DistilBERT)
#   ./start.sh --fast     skip DistilBERT (lighter, quicker demo)
#   ./start.sh --fresh    truncate DB + reset topics/checkpoints first
#
# Stops: ./stop.sh      Logs: tail -f logs/<spark|producer|api|frontend>.log
# ---------------------------------------------------------------------------
set -e
cd "$(dirname "$0")"

FAST=0
FRESH=0
for arg in "$@"; do
  case "$arg" in
    --fast)  FAST=1 ;;
    --fresh) FRESH=1 ;;
  esac
done

ROOT="$(pwd)"
LOGS="$ROOT/logs"
mkdir -p "$LOGS"

# preflight ---------------------------------------------------------------
command -v docker >/dev/null || { echo "❌ docker not found — install Docker Desktop first"; exit 1; }
command -v node >/dev/null || { echo "❌ node.js not found — install node 18+ first"; exit 1; }
command -v python3 >/dev/null || { echo "❌ python3 not found — install python 3.10-3.12 first"; exit 1; }
[ -f "$ROOT/data/raw/all_sources.csv" ] || { echo "⚠️  data/raw/all_sources.csv missing — falling back to sample dataset"; SAMPLE=1; }

# fresh clone? bootstrap everything (venv, node_modules, JDK, model weights, demo user)
if [ ! -d "$ROOT/.venv" ] || [ ! -d "$ROOT/frontend/node_modules" ]; then
  bash "$ROOT/bootstrap.sh"
else
  # even on an existing setup, make sure weights + demo user exist (cheap checks)
  bash "$ROOT/bootstrap.sh" >/dev/null 2>&1 || true
fi

# secrets (.env.local — canonical SCREAMING_SNAKE_CASE=VALUE lines) → export
if [ -f "$ROOT/.env.local" ]; then
  while IFS= read -r line; do
    line="${line%%#*}"  # strip comments
    case "$line" in
      *'='*) KEY="${line%%=*}"; VAL="${line#*=}"
             KEY=$(echo "$KEY" | sed 's/^ *//;s/ *$//')
             VAL=$(echo "$VAL" | sed 's/^ *//;s/ *$//;s/^"//;s/"$//')
             [ -z "$KEY" ] && continue
             export "$KEY=$VAL" ;;
    esac
  done < "$ROOT/.env.local"
fi

# stop anything already running from a previous start ----------------------
"$ROOT/stop.sh" >/dev/null 2>&1 || true

echo "▶ [1/6] docker compose up..."
# container names are fixed (sma-kafka/sma-postgres): a previous run's stale
# containers (even from a different clone) would conflict — clear them
docker rm -f sma-kafka sma-postgres >/dev/null 2>&1 || true
docker compose up -d

echo -n "▶ [2/6] waiting for containers"
for i in $(seq 1 90); do
  KAFKA_OK=$(docker inspect -f '{{.State.Health.Status}}' sma-kafka 2>/dev/null || echo none)
  PG_OK=$(docker inspect -f '{{.State.Health.Status}}' sma-postgres 2>/dev/null || echo none)
  [ "$KAFKA_OK" = "healthy" ] && [ "$PG_OK" = "healthy" ] && break
  echo -n "."; sleep 1
done
echo
[ "$KAFKA_OK" = "healthy" ] && [ "$PG_OK" = "healthy" ] || { echo "❌ containers not healthy — check: docker compose logs"; exit 1; }
echo "   kafka + postgres healthy"

# containers are now up — complete any bootstrap steps that were skipped
# on the very first run (e.g. the demo login user seed)
bash "$ROOT/bootstrap.sh" 2>&1 | grep -E "→|✓|⚠" || true

# topics (idempotent) ------------------------------------------------------
echo "▶ [3/7] ensuring kafka topics..."
docker exec sma-kafka /opt/kafka/bin/kafka-topics.sh --bootstrap-server localhost:9092 --create --topic comments-raw --partitions 3 --if-not-exists >/dev/null 2>&1 || \
docker exec sma-kafka /opt/kafka/bin/kafka-topics.sh --bootstrap-server localhost:9092 --create --topic comments-raw --partitions 3 >/dev/null 2>&1 || true
docker exec sma-kafka /opt/kafka/bin/kafka-topics.sh --bootstrap-server localhost:9092 --create --topic comments-scored --partitions 3 --if-not-exists >/dev/null 2>&1 || \
docker exec sma-kafka /opt/kafka/bin/kafka-topics.sh --bootstrap-server localhost:9092 --create --topic comments-scored --partitions 3 >/dev/null 2>&1 || true

# one-time model warmup (downloads the sentiment LLMs on first setup) -------
if [ ! -d "$HOME/.cache/huggingface/hub/models--cardiffnlp--twitter-roberta-base-sentiment-latest" ]; then
  echo "▶ [4/7] first run: downloading sentiment models (one-time, ~5 min)..."
  "$ROOT/.venv/bin/python" "$ROOT/scripts/warmup_models.py" || echo "⚠ model warmup failed — the Spark job will retry downloads on start"
else
  echo "▶ [4/7] sentiment models already cached ✓"
fi

# fresh state --------------------------------------------------------------
if [ "$FRESH" = "1" ]; then
  echo "▶ [5/7] --fresh: truncating tables + checkpoints..."
  docker exec sma-postgres psql -U sentiment -d sentiment -c "TRUNCATE comments, window_stats;" >/dev/null 2>&1 || true
  rm -rf "$ROOT/checkpoints"
else
  echo "▶ [5/7] keeping existing data (use --fresh for a clean demo state)"
fi

# java ---------------------------------------------------------------------
if [ -d "$HOME/.tools/jdk-17" ]; then
  export JAVA_HOME="$HOME/.tools/jdk-17"
  export PATH="$JAVA_HOME/bin:$PATH"
fi

# background services ------------------------------------------------------
echo "▶ [6/7] starting services..."

SKIP_BERT_FLAG=""
[ "$FAST" = "1" ] && SKIP_BERT_FLAG="1"

# portable detached launch: setsid is Linux-only, so fall back to a plain
# subshell + nohup on macOS/BSD (nohup already detaches from the terminal)
run_bg() { # run_bg "logfile" "pidfile" cmd...
  local LOGF="$1" PIDF="$2"; shift 2
  if command -v setsid >/dev/null 2>&1; then
    ( setsid nohup "$@" > "$LOGF" 2>&1 < /dev/null & echo $! > "$PIDF" )
  else
    ( nohup "$@" > "$LOGF" 2>&1 < /dev/null & echo $! > "$PIDF" )
  fi
}

run_bg "$LOGS/spark.log" "$LOGS/spark.pid" env SKIP_BERT=$SKIP_BERT_FLAG ./run_spark.sh

DATA_FILE="data/raw/all_sources.csv"
[ "${SAMPLE:-0}" = "1" ] && DATA_FILE="data/sample_comments.csv"
# seed one pass so the dashboard starts populated, then idle; the API's
# "Go live" button writes logs/live-stream.json to trigger high-rate bursts
run_bg "$LOGS/producer.log" "$LOGS/producer.pid" "$ROOT/.venv/bin/python" producer/producer.py --file "$DATA_FILE" --seed "${SEED_ROWS:-6000}" --shuffle

run_bg "$LOGS/api.log" "$LOGS/api.pid" "$ROOT/.venv/bin/uvicorn" api.main:app --port 8000

( cd "$ROOT/frontend" && if command -v setsid >/dev/null 2>&1; then
    setsid nohup npm run dev > "$LOGS/frontend.log" 2>&1 < /dev/null & echo $! > "$LOGS/frontend.pid"
  else
    nohup npm run dev > "$LOGS/frontend.log" 2>&1 < /dev/null & echo $! > "$LOGS/frontend.pid"
  fi )

# verify -------------------------------------------------------------------
echo -n "▶ [7/7] verifying services"
sleep 45
for i in $(seq 1 12); do
  API_OK=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/health 2>/dev/null || echo 000)
  [ "$API_OK" = "200" ] && break
  echo -n "."; sleep 5
done
echo

# pgrep -c is Linux-only; the wc -l form works on macOS/BSD too
SPARK_ALIVE=$(pgrep -f "streaming_job.py" 2>/dev/null | wc -l | tr -d ' ')
PROD_ALIVE=$(pgrep -f "producer/producer.py" 2>/dev/null | wc -l | tr -d ' ')
API_ALIVE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/health 2>/dev/null || echo 000)
FRONT_PORT=$(grep -oE "localhost:[0-9]+" "$LOGS/frontend.log" 2>/dev/null | head -1 | cut -d: -f2)
FRONT_PORT=${FRONT_PORT:-5173}
FRONT_OK=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:$FRONT_PORT/" 2>/dev/null || echo 000)

echo
echo "─────────────────────────────────────────────────────"
[ "$SPARK_ALIVE" -ge 1 ] && echo "🟢 Spark streaming   (logs/spark.log)" || echo "🔴 Spark streaming   — check logs/spark.log"
[ "$PROD_ALIVE" -ge 1 ] && echo "🟢 Producer          (logs/producer.log)" || echo "🔴 Producer          — check logs/producer.log"
[ "$API_OK" = "200" ] && echo "🟢 API               http://localhost:8000/docs" || echo "🔴 API               — check logs/api.log"
[ "$FRONT_OK" = "200" ] && echo "🟢 Dashboard         http://localhost:$FRONT_PORT" || echo "🔴 Dashboard         — check logs/frontend.log"
[ "$FAST" = "1" ] && echo "⚡ fast mode: DistilBERT skipped" || echo "🧠 full mode: VADER + DistilBERT"
echo "─────────────────────────────────────────────────────"
echo "stop everything:  ./stop.sh"
