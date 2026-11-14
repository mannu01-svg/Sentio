#!/usr/bin/env bash
# Stop every service started by ./start.sh (containers are kept; data intact).
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
case "$(basename "$SCRIPT_DIR")" in linux|mac|windows) cd "$(dirname "$(dirname "$SCRIPT_DIR")")";; startup) cd "$(dirname "$SCRIPT_DIR")";; *) cd "$SCRIPT_DIR";; esac

for pidfile in logs/*.pid; do
  [ -f "$pidfile" ] || continue
  pid=$(cat "$pidfile" 2>/dev/null)
  if [ -n "$pid" ]; then
    # kill the setsid group so children (java workers, vite esbuild) die too
    kill -- -"$pid" 2>/dev/null || kill "$pid" 2>/dev/null || true
  fi
  rm -f "$pidfile"
done

# fallback: catch anything still running
pkill -f "streaming_job.py" 2>/dev/null || true
pkill -f "producer/producer.py" 2>/dev/null || true
pkill -f "uvicorn api.main:app" 2>/dev/null || true
pkill -f "vite" 2>/dev/null || true

docker compose stop 2>/dev/null || true

echo "stopped — run ./start.sh to bring everything back"
