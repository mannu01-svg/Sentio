#!/usr/bin/env bash
# Generate a self-signed TLS cert for Sentio (deploy/nginx/certs/).
# Idempotent: skips when a valid cert pair already exists.
# Swap for Let's Encrypt later:
#   certbot certonly --webroot -w deploy/certbot/www -d <your-domain>
#   cp /etc/letsencrypt/live/<domain>/fullchain.pem deploy/nginx/certs/
#   cp /etc/letsencrypt/live/<domain>/privkey.pem  deploy/nginx/certs/
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CERT_DIR="$SCRIPT_DIR/nginx/certs"
mkdir -p "$CERT_DIR"

if [ -f "$CERT_DIR/fullchain.pem" ] && [ -f "$CERT_DIR/privkey.pem" ]; then
  echo "✓ TLS cert already present at deploy/nginx/certs/"
  exit 0
fi

echo "→ generating self-signed TLS cert (valid 825 days)…"
openssl req -x509 -nodes -newkey rsa:2048 -days 825 \
  -keyout "$CERT_DIR/privkey.pem" -out "$CERT_DIR/fullchain.pem" \
  -subj "/C=IN/ST=Delhi/L=New Delhi/O=Sentio/CN=sentio.local" \
  -addext "subjectAltName=DNS:sentio.local,DNS:localhost,IP:127.0.0.1" \
  >/dev/null 2>&1
chmod 600 "$CERT_DIR/privkey.pem"
echo "✓ self-signed cert ready: deploy/nginx/certs/{fullchain,privkey}.pem"
