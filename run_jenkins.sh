#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# One-command Jenkins CI setup for this repo (demo on YOUR machine).
#
#   ./run_jenkins.sh
#
# Starts a Jenkins LTS container, prints the initial admin password, and
# tells you the exact click-path to create the pipeline job.
# Jenkins runs wherever you execute this — nothing external is required.
# ---------------------------------------------------------------------------
set -e
cd "$(dirname "$0")"

JENKINS_NAME="${JENKINS_NAME:-sma-jenkins}"
JENKINS_PORT="${JENKINS_PORT:-8080}"
REPO_URL="https://github.com/mannu01-svg/Sentio.git"

command -v docker >/dev/null || { echo "❌ docker not found — install Docker Desktop first"; exit 1; }
docker info >/dev/null 2>&1 || { echo "❌ docker daemon not running — start Docker Desktop"; exit 1; }

# reuse an existing container if present
if [ "$(docker ps -q -f name=^${JENKINS_NAME}$)" ]; then
  echo "✓ Jenkins already running: http://localhost:${JENKINS_PORT}"
  PW=$(docker exec "$JENKINS_NAME" cat /var/jenkins_home/secrets/initialAdminPassword 2>/dev/null || echo "(already configured — use your saved admin password)")
  echo "  admin password: $PW"
  exit 0
fi

# clean up a stopped instance with the same name
docker rm -f "$JENKINS_NAME" >/dev/null 2>&1 || true

echo "▶ building the sentio-jenkins image (python3 + node on the agent, one-time)…"
docker build -q -t sentio-jenkins -f Dockerfile.jenkins . >/dev/null \
  || { echo "❌ image build failed — check Dockerfile.jenkins"; exit 1; }

echo "▶ starting Jenkins (first run pulls ~350MB, one-time)…"
docker run -d --name "$JENKINS_NAME" \
  -p "${JENKINS_PORT}:8080" -p 50000:50000 \
  -v "${JENKINS_NAME}_home:/var/jenkins_home" \
  -v /var/run/docker.sock:/var/run/docker.sock \
  sentio-jenkins >/dev/null

echo -n "▶ waiting for Jenkins to come up"
for i in $(seq 1 60); do
  STATUS=$(docker inspect -f '{{.State.Status}}' "$JENKINS_NAME" 2>/dev/null || echo none)
  LOG_OK=$(docker logs "$JENKINS_NAME" 2>&1 | grep -c "Jenkins is fully up and running" || true)
  [ "$LOG_OK" -ge 1 ] && break
  echo -n "."; sleep 2
done
echo

PW=$(docker exec "$JENKINS_NAME" cat /var/jenkins_home/secrets/initialAdminPassword 2>/dev/null || echo "")

cat <<EOF

─────────────────────────────────────────────────────────
✅ Jenkins is running:  http://localhost:${JENKINS_PORT}

Admin password (copy it):
    ${PW}

Click-path (5 minutes):
 1. Open http://localhost:${JENKINS_PORT}
 2. Paste the admin password → Continue
 3. "Install suggested plugins" (waits ~3 min)
 4. Create First Admin User (any name/password — save it)
 5. Dashboard → New Item
 6. Name: sentio-ci   →  type: Pipeline  →  OK
 7. Pipeline section → Definition: "Pipeline script from SCM"
 8. SCM: Git → Repository URL:
        ${REPO_URL}
 9. Branch Specifier: */main      (leave credentials blank — public repo)
10. Script Path: Jenkinsfile      (default)  →  Save
11. Click "Build Now"

Expected: 5 green stages — Setup Python → Lint → Unit Tests (42) →
Frontend Build → Docker Compose Config (~6-8 min first run).

Stop Jenkins later:
    docker rm -f ${JENKINS_NAME}
─────────────────────────────────────────────────────────
EOF
