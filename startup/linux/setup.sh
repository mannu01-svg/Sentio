#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# THE one command for a completely fresh clone:
#
#   bash startup/linux/setup.sh
#
# Does everything: python venv + pip, npm install, JDK 17 auto-download,
# model weights rejoin, HuggingFace LLM download, docker (Kafka + Postgres),
# all 4 services, demo login user — then Jenkins CI (zero-click: admin
# user + sentio-ci job + first build kicked off automatically).
# ---------------------------------------------------------------------------
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"
cd "$ROOT"

echo "═══════════════════════════════════════════════════════"
echo "  Sentio — full setup (app + services + Jenkins CI)"
echo "═══════════════════════════════════════════════════════"

# 1. app + services (start.sh runs bootstrap.sh automatically for fresh clones)
bash "$SCRIPT_DIR/start.sh"

# 2. Jenkins CI — zero-click (AUTO=1: admin sentio/sentio123, job created, build queued)
echo
echo "▶ [CI] starting Jenkins…"
AUTO=1 JENKINS_PORT="${JENKINS_PORT:-8090}" bash "$ROOT/run_jenkins.sh"

echo
echo "═══════════════════════════════════════════════════════"
echo "  ✅ Sentio is fully up"
echo "═══════════════════════════════════════════════════════"
echo "  Dashboard : http://localhost:5173        (ada@sentio.app / secret123)"
echo "  API docs  : http://localhost:8000/docs"
echo "  Jenkins   : http://localhost:${JENKINS_PORT:-8090}          (sentio / sentio123)"
echo "  Stop all  : startup/linux/stop.sh  +  docker rm -f sma-jenkins"
echo "═══════════════════════════════════════════════════════"
