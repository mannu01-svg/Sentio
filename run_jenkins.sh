#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# One-command Jenkins CI setup for this repo (demo on YOUR machine).
#
#   ./run_jenkins.sh           manual mode: Jenkins up + click-path printed
#   AUTO=1 ./run_jenkins.sh    zero-click: admin user + sentio-ci job +
#                              first build kicked off automatically
#
# Jenkins runs wherever you execute this — nothing external is required.
# ---------------------------------------------------------------------------
set -e
cd "$(dirname "$0")"

JENKINS_NAME="${JENKINS_NAME:-sma-jenkins}"
JENKINS_PORT="${JENKINS_PORT:-8080}"
REPO_URL="https://github.com/mannu01-svg/Sentio.git"
JOB_NAME="sentio-ci"
AUTO="${AUTO:-0}"

command -v docker >/dev/null || { echo "❌ docker not found — install Docker Desktop first"; exit 1; }
docker info >/dev/null 2>&1 || { echo "❌ docker daemon not running — start Docker Desktop"; exit 1; }

# reuse an existing container if present
if [ "$(docker ps -q -f name=^${JENKINS_NAME}$)" ]; then
  echo "✓ Jenkins already running: http://localhost:${JENKINS_PORT}"
  if [ "$AUTO" = "1" ]; then
    AUTO_LOGIN="sentio" AUTO_PW="sentio123" AUTO_PORT="$JENKINS_PORT" bash "$0" --auto-only 2>/dev/null || true
  else
    PW=$(docker exec "$JENKINS_NAME" cat /var/jenkins_home/secrets/initialAdminPassword 2>/dev/null || echo "(already configured — use your saved admin password)")
    echo "  admin password: $PW"
  fi
  exit 0
fi

# clean up a stopped instance with the same name
docker rm -f "$JENKINS_NAME" >/dev/null 2>&1 || true

echo "▶ building the sentio-jenkins image (python3 + node + plugins baked in, one-time)…"
docker build -q -t sentio-jenkins -f Dockerfile.jenkins . >/dev/null \
  || { echo "❌ image build failed — check Dockerfile.jenkins"; exit 1; }

EXTRA_MOUNTS=""
[ "$AUTO" = "1" ] && [ -d init.groovy.d ] && EXTRA_MOUNTS="-v $(pwd)/init.groovy.d:/var/jenkins_home/init.groovy.d:ro"

echo "▶ starting Jenkins (first run pulls ~350MB, one-time)…"
docker run -d --name "$JENKINS_NAME" \
  -p "${JENKINS_PORT}:8080" -p 50000:50000 \
  -v "${JENKINS_NAME}_home:/var/jenkins_home" \
  $EXTRA_MOUNTS \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -e JAVA_OPTS="-Djenkins.install.runSetupWizard=false" \
  sentio-jenkins >/dev/null

echo -n "▶ waiting for Jenkins to come up"
for i in $(seq 1 90); do
  LOG_OK=$(docker logs "$JENKINS_NAME" 2>&1 | grep -c "Jenkins is fully up and running" || true)
  [ "$LOG_OK" -ge 1 ] && break
  echo -n "."; sleep 2
done
echo

if [ "$AUTO" != "1" ]; then
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
  exit 0
fi

# ---------------------------------------------------------------------------
# AUTO mode: zero-click setup (admin user comes from init.groovy.d mount)
# ---------------------------------------------------------------------------
echo "▶ auto mode: creating ${JOB_NAME} pipeline job via REST…"

# wait for the API to accept a crumb (Jenkins fully initialized)
CRUMB=""
for i in $(seq 1 30); do
  CRUMB=$(curl -s -u sentio:sentio123 -c /tmp/jk_cookies.$$ "${JENKINS_URL:-http://localhost:${JENKINS_PORT}}/crumbIssuer/api/json" 2>/dev/null | grep -o '"crumb":"[^"]*"' | cut -d'"' -f4 || true)
  [ -n "$CRUMB" ] && break
  sleep 2
done
[ -n "$CRUMB" ] || { echo "❌ could not get Jenkins crumb — is Jenkins up at :${JENKINS_PORT}?"; exit 1; }

JENKINS_URL_FINAL="${JENKINS_URL:-http://localhost:${JENKINS_PORT}}"

# job config.xml — Pipeline script from SCM, public repo, */main
cat > /tmp/sentio_ci_config.xml <<XMLEOF
<?xml version='1.1' encoding='UTF-8'?>
<flow-definition plugin="workflow-job">
  <description>Sentio CI pipeline (created automatically by run_jenkins.sh)</description>
  <keepDependencies>false</keepDependencies>
  <definition class="org.jenkinsci.plugins.workflow.cps.CpsScmFlowDefinition" plugin="workflow-cps">
    <scm class="hudson.plugins.git.GitSCM" plugin="git">
      <configVersion>2</configVersion>
      <userRemoteConfigs>
        <hudson.plugins.git.UserRemoteConfig>
          <url>${REPO_URL}</url>
        </hudson.plugins.git.UserRemoteConfig>
      </userRemoteConfigs>
      <branches>
        <hudson.plugins.git.BranchSpec>
          <name>*/main</name>
        </hudson.plugins.git.BranchSpec>
      </branches>
      <doGenerateSubmoduleConfigurations>false</doGenerateSubmoduleConfigurations>
      <submoduleCfg class="list"/>
      <extensions/>
    </scm>
    <scriptPath>Jenkinsfile</scriptPath>
    <lightweight>true</lightweight>
  </definition>
  <triggers/>
  <disabled>false</disabled>
</flow-definition>
XMLEOF

CREATE_CODE=$(curl -s -o /tmp/jk_create_resp.txt -w "%{http_code}" \
  -u sentio:sentio123 -b /tmp/jk_cookies.$$ \
  -H "Jenkins-Crumb: ${CRUMB}" -H "Content-Type: application/xml" \
  -X POST --data-binary @/tmp/sentio_ci_config.xml \
  "${JENKINS_URL_FINAL}/createItem?name=${JOB_NAME}")

if [ "$CREATE_CODE" = "200" ]; then
  echo "  ✓ job ${JOB_NAME} created"
elif [ "$CREATE_CODE" = "400" ]; then
  echo "  ✓ job ${JOB_NAME} already exists — updating config"
  curl -s -o /dev/null -u sentio:sentio123 -b /tmp/jk_cookies.$$ \
    -H "Jenkins-Crumb: ${CRUMB}" -H "Content-Type: application/xml" \
    -X POST --data-binary @/tmp/sentio_ci_config.xml \
    "${JENKINS_URL_FINAL}/job/${JOB_NAME}/config.xml" || true
else
  echo "⚠ job creation returned HTTP ${CREATE_CODE} — check ${JENKINS_URL_FINAL}/job/${JOB_NAME}/"
fi

# kick off the first build
CRUMB=$(curl -s -u sentio:sentio123 -c /tmp/jk_cookies.$$ "${JENKINS_URL_FINAL}/crumbIssuer/api/json" | grep -o '"crumb":"[^"]*"' | cut -d'"' -f4 || true)
BUILD_CODE=$(curl -s -o /dev/null -w "%{http_code}" \
  -u sentio:sentio123 -b /tmp/jk_cookies.$$ \
  -H "Jenkins-Crumb: ${CRUMB}" \
  -X POST "${JENKINS_URL_FINAL}/job/${JOB_NAME}/build")
[ "$BUILD_CODE" = "201" ] || [ "$BUILD_CODE" = "200" ] && echo "  ✓ build #1 queued" \
  || echo "⚠ build trigger returned HTTP ${BUILD_CODE} — click Build Now at ${JENKINS_URL_FINAL}/job/${JOB_NAME}/"

rm -f /tmp/jk_cookies.$$ /tmp/sentio_ci_config.xml /tmp/jk_create_resp.txt

cat <<EOF

─────────────────────────────────────────────────────────
✅ Jenkins is running:  ${JENKINS_URL_FINAL}
✅ Login:               sentio / sentio123
✅ Pipeline job:        ${JENKINS_URL_FINAL}/job/${JOB_NAME}/
✅ First build queued — watch it run (~6-8 min first time):
    Expected: 5 green stages — Setup Python → Lint → Unit Tests (42) →
    Frontend Build → Docker Compose Config

Stop Jenkins later:
    docker rm -f ${JENKINS_NAME}
─────────────────────────────────────────────────────────
EOF
