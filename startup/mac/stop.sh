#!/usr/bin/env bash
# Sentio - stop every container (stored data is kept; start.sh --fresh wipes it).
cd "$(dirname "$(dirname "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)")")"
docker compose down
echo "stopped (data kept in Docker volumes)"
