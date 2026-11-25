#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Sentio - start the whole stack in Docker.
#
#   start.sh            full mode (VADER + DistilBERT + RoBERTa)
#   start.sh --fast     VADER only (lighter, quicker demo)
#   start.sh --fresh    wipe all data first (clean demo state)
#
# Only prerequisite: Docker (Desktop) running.
# Logs: docker compose logs -f spark | api | producer
# ---------------------------------------------------------------------------
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$(dirname "$(dirname "$SCRIPT_DIR")")"

FRESH=0
for arg in "$@"; do
  case "$arg" in
    --fast)  export SKIP_BERT=1 ;;
    --fresh) FRESH=1 ;;
  esac
done

command -v docker >/dev/null || { echo "❌ docker not found - install Docker Desktop first"; exit 1; }
docker info >/dev/null 2>&1 || { echo "❌ Docker is not running - start Docker Desktop first"; exit 1; }

if [ "$FRESH" = "1" ]; then
  echo "▶ --fresh: removing containers and all stored data…"
  docker compose down -v
fi
[ -n "${SKIP_BERT:-}" ] && echo "⚡ --fast: VADER only"

echo "▶ [1/3] building + starting containers (first run downloads ~4 GB, 15-25 min)…"
docker compose up -d --build

echo -n "▶ [2/3] waiting for the API"
for i in $(seq 1 60); do
  curl -fs http://localhost:8000/health >/dev/null 2>&1 && break
  echo -n "."; sleep 5
done
echo

echo "▶ [3/3] containers:"
docker compose ps
cat <<MSG
─────────────────────────────────────────────────────
  Dashboard : http://localhost:5173   (admin@sentio.app / admin123)
  Swagger   : http://localhost:8000/docs
  Spark UI  : http://localhost:4040
  MongoDB   : mongodb://localhost:27017   (database: sentio)
  Spark log : docker compose logs -f spark
  Stop      : $SCRIPT_DIR/stop.sh
─────────────────────────────────────────────────────
MSG
