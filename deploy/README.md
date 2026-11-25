# Deploying Sentio to the internet (HTTPS)

Public deployment: nginx terminates TLS, serves the built React app and
proxies `/api` to uvicorn. Only **80/443** are public — Postgres (5432) and
Kafka (9092) bind to `127.0.0.1` on the host.

```
internet ──▶ nginx :443 (TLS, frontend/dist + /api proxy)
                    │
                    ▼
              uvicorn :8000 (localhost only)
                    │
        ┌───────────┴───────────┐
        ▼                       ▼
  kafka :9092 (localhost)   postgres :5432 (localhost)
        ▲
  Spark + producer (data plane, startup/<platform>/start.sh)
```

## One-time setup

```bash
# 1. TLS cert (self-signed; swap for Let's Encrypt when you have a domain)
bash deploy/gen-certs.sh

# 2. build the frontend (already committed at frontend/dist)
cd frontend && npm run build && cd ..

# 3. data plane (Spark + producer + API) — auto-detects machine profile
startup/linux/start.sh        # or mac/, windows\start.bat

# 4. edge (nginx + kafka + postgres, prod compose)
docker compose -f deploy/docker-compose.prod.yml up -d --build
```

Open `https://<host>` — the dashboard loads over TLS and `/api/*` is proxied
to uvicorn behind the scenes.

## Accounts (approval-gated)

- Signups land as **pending** — nobody can use the dashboard until approved.
- The seeded admin (`admin@sentio.app`) approves accounts from
  **Settings → User Management** (approve / reject / role / delete).
- The admin password is printed once by the seed step
  (`scripts/seed_admin.py`, runs inside `start.sh`); re-run it any time to
  see the reminder or re-approve a rejected admin.
- All mutating endpoints (`/api/analyze`, `/api/analyze-account`,
  `/api/topics/stream`, `/api/stream/live|stop`, `/api/admin/*`) require
  `Authorization: Bearer <token>` issued at login.

## Let's Encrypt swap (real domain)

```bash
sudo certbot certonly --webroot -w deploy/certbot/www -d <your-domain>
sudo cp /etc/letsencrypt/live/<your-domain>/fullchain.pem deploy/nginx/certs/
sudo cp /etc/letsencrypt/live/<your-domain>/privkey.pem  deploy/nginx/certs/
docker restart sentio-nginx
```

`deploy/nginx.conf` already serves `/.well-known/acme-challenge/` from the
mounted `deploy/certbot/www` webroot.

## Firewall (public host)

```bash
sudo ufw allow 80/tcp && sudo ufw allow 443/tcp && sudo ufw enable
# do NOT open 5432 / 9092 / 8000 — they stay on 127.0.0.1
```
