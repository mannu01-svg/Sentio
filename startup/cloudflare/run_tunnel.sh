#!/usr/bin/env bash
# Public HTTPS tunnel for Sentio via Cloudflare (no sudo, no port-forward).
# Requires: cloudflared on PATH (or ~/.tools/cloudflared).
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"
cd "$ROOT"
mkdir -p logs

CLOUDFLARED="$(command -v cloudflared || echo "$HOME/.tools/cloudflared")"
[ -x "$CLOUDFLARED" ] || { echo "❌ cloudflared not found — bootstrap: see deploy/README.md"; exit 1; }

curl -sk -o /dev/null https://localhost/ || { echo "❌ nginx not up — run: docker compose -f deploy/docker-compose.prod.yml up -d"; exit 1; }

echo "▶ starting cloudflared quick tunnel (random public URL)…"
"$CLOUDFLARED" tunnel --url https://localhost:443 --no-tls-verify --logfile logs/cloudflared.log &
TUNNEL_PID=$!
echo $TUNNEL_PID > logs/cloudflared.pid

for i in $(seq 1 20); do
  URL=$(grep -oE "https://[a-z0-9-]+\.trycloudflare\.com" logs/cloudflared.log 2>/dev/null | head -1)
  [ -n "$URL" ] && break
  sleep 1
done
[ -n "$URL" ] && echo "✓ public URL: $URL" || { echo "❌ tunnel didn't start — check logs/cloudflared.log"; exit 1; }
echo "  stop it:  kill \$(cat logs/cloudflared.pid)"
