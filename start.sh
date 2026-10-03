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
[ -d "$ROOT/.venv" ] || { echo "❌ .venv missing — run: python3 -m venv .venv && .venv/bin/pip install -r requirements.txt"; exit 1; }
[ -f "$ROOT/data/raw/all_sources.csv" ] || { echo "⚠️  data/raw/all_sources.csv missing — falling back to sample dataset"; SAMPLE=1; }
command -v docker >/dev/null || { echo "❌ docker not found"; exit 1; }

# secrets (.env.local — "Kaggle API token = ..." style lines) → export for kagglehub
if [ -f "$ROOT/.env.local" ]; then
  while IFS= read -r line; do
    case "$line" in
      *'='*) KEY="${line%%=*}"; VAL="${line#*=}"
             KEY=$(echo "$KEY" | tr ' ' '_' | tr '[:upper:]' '[:lower:]')
             VAL=$(echo "$VAL" | sed 's/^ *//;s/ *$//')
             export "$KEY=$VAL" ;;
    esac
  done < "$ROOT/.env.local"
fi

# stop anything already running from a previous start ----------------------
"$ROOT/stop.sh" >/dev/null 2>&1 || true

echo "▶ [1/6] docker compose up..."
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

# topics (idempotent) ------------------------------------------------------
echo "▶ [3/6] ensuring kafka topics..."
docker exec sma-kafka /opt/kafka/bin/kafka-topics.sh --bootstrap-server localhost:9092 --create --topic comments-raw --partitions 3 --if-not-exists >/dev/null 2>&1 || \
docker exec sma-kafka /opt/kafka/bin/kafka-topics.sh --bootstrap-server localhost:9092 --create --topic comments-raw --partitions 3 >/dev/null 2>&1 || true
docker exec sma-kafka /opt/kafka/bin/kafka-topics.sh --bootstrap-server localhost:9092 --create --topic comments-scored --partitions 3 --if-not-exists >/dev/null 2>&1 || \
docker exec sma-kafka /opt/kafka/bin/kafka-topics.sh --bootstrap-server localhost:9092 --create --topic comments-scored --partitions 3 >/dev/null 2>&1 || true

# fresh state --------------------------------------------------------------
if [ "$FRESH" = "1" ]; then
  echo "▶ [4/6] --fresh: truncating tables + checkpoints..."
  docker exec sma-postgres psql -U sentiment -d sentiment -c "TRUNCATE comments, window_stats;" >/dev/null 2>&1 || true
  rm -rf "$ROOT/checkpoints"
else
  echo "▶ [4/6] keeping existing data (use --fresh for a clean demo state)"
fi

# java ---------------------------------------------------------------------
if [ -d "$HOME/.tools/jdk-17" ]; then
  export JAVA_HOME="$HOME/.tools/jdk-17"
  export PATH="$JAVA_HOME/bin:$PATH"
fi

# background services ------------------------------------------------------
echo "▶ [5/6] starting services..."

SKIP_BERT_FLAG=""
[ "$FAST" = "1" ] && SKIP_BERT_FLAG="1"

( setsid nohup env SKIP_BERT=$SKIP_BERT_FLAG ./run_spark.sh > "$LOGS/spark.log" 2>&1 < /dev/null & echo $! > "$LOGS/spark.pid" )

DATA_FILE="data/raw/all_sources.csv"
[ "${SAMPLE:-0}" = "1" ] && DATA_FILE="data/sample_comments.csv"
( setsid nohup "$ROOT/.venv/bin/python" producer/producer.py --file "$DATA_FILE" --rate 15 --loop --shuffle > "$LOGS/producer.log" 2>&1 < /dev/null & echo $! > "$LOGS/producer.pid" )

( setsid nohup "$ROOT/.venv/bin/uvicorn" api.main:app --port 8000 > "$LOGS/api.log" 2>&1 < /dev/null & echo $! > "$LOGS/api.pid" )

( cd "$ROOT/frontend" && setsid nohup npm run dev > "$LOGS/frontend.log" 2>&1 < /dev/null & echo $! > "$LOGS/frontend.pid" )

# verify -------------------------------------------------------------------
echo -n "▶ [6/6] verifying services"
sleep 45
for i in $(seq 1 12); do
  API_OK=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/health 2>/dev/null || echo 000)
  [ "$API_OK" = "200" ] && break
  echo -n "."; sleep 5
done
echo

SPARK_ALIVE=$(pgrep -fc "streaming_job.py" 2>/dev/null || echo 0)
PROD_ALIVE=$(pgrep -fc "producer/producer.py" 2>/dev/null || echo 0)
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
