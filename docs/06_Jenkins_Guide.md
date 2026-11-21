# Jenkins CI Guide

## 1. Why CI in the report
Continuous Integration means every push is automatically **compiled, linted
and tested**, so a broken commit never reaches `main`. In the project report,
this demonstrates industrial software-engineering practice on top of the data
platform itself.

## 2. What the pipeline does (`Jenkinsfile` in repo root)

| Stage | Command | Checks |
|---|---|---|
| Setup Python | `python3 -m venv .venv-ci` + pip install | reproducible test env |
| Lint | `python -m compileall spark producer api evaluation` | all modules compile |
| Unit Tests | `pytest tests/ -v` | 42 cases (DB/model tests skip gracefully in bare CI) |
| Frontend Build | `npm install && npm run build` in `frontend/` | dashboard bundles cleanly |
| Compose Config | `docker compose config -q` | docker-compose.yml is valid |

## 3. Running Jenkins — one command, two modes (verified working)

```bash
./run_jenkins.sh          # manual mode: Jenkins up + click-path printed
AUTO=1 ./run_jenkins.sh   # zero-click: admin user + sentio-ci job + first build queued
```

`startup/<os>/setup.sh` already runs Jenkins in AUTO mode — the one-command
full setup covers it.

**What AUTO mode does (all automatic, no clicking):**
1. Builds the `sentio-jenkins` image: Jenkins LTS + python3 + node + docker CLI
   + **pipeline plugins baked in** (`jenkins/plugins.txt` via
   `jenkins-plugin-cli`) — no "Install suggested plugins" wizard.
2. Runs the container with a mounted `jenkins/init.groovy.d/basic-security.groovy`
   that creates admin **sentio / sentio123** and disables the setup wizard.
3. Waits for the API, then creates the `sentio-ci` pipeline job via REST
   (crumb + cookie jar): *Pipeline script from SCM* →
   `https://github.com/mannu01-svg/Sentio.git` → `*/main` → `Jenkinsfile`.
4. Queues build #1 automatically.

**Verified end-to-end:** fresh volume → `AUTO=1 ./run_jenkins.sh` → job
created → build #1 auto-triggered → **SUCCESS** (5/5 stages, 34 passed /
8 skipped, ~15 min first run, ~2 min cached).

## 4. Manual equivalent (what the script automates)

```bash
# 1. build the agent image (python3 + node + docker CLI + plugins)
docker build -t sentio-jenkins -f Dockerfile.jenkins .

# 2. start Jenkins (docker.sock mounted so the Compose-Config stage works)
docker run -d --name sma-jenkins -p 8090:8080 -p 50000:50000 \
  -v sma-jenkins_home:/var/jenkins_home \
  -v $(pwd)/jenkins/init.groovy.d:/var/jenkins_home/init.groovy.d:ro \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -e JAVA_OPTS="-Djenkins.install.runSetupWizard=false" \
  sentio-jenkins

# 3. open http://localhost:8090 → login sentio/sentio123 (AUTO) or the
#    printed initialAdminPassword (manual)
# 4. New Item → sentio-ci → Pipeline → Pipeline script from SCM → Git →
#    https://github.com/mannu01-svg/Sentio.git → */main → Save → Build Now
```

> Port 8090 (8080 was commonly taken); override with `JENKINS_PORT=…`.

> If a stage is unavailable in your lab setup (e.g. no docker.sock permission),
> disable just that stage in the Jenkinsfile — the rest still runs.

## 5. Wiring a webhook (optional)
Jenkins → job → Configure → *Build Triggers* → *GitHub hook trigger for
GITScm polling*. Then GitHub repo → Settings → Webhooks →
`http://<jenkins-host>:8090/github-webhook/`.

## 6. Fallback: GitHub Actions
If Jenkins is not available in the lab, an equivalent (simpler) workflow can
be added at `.github/workflows/ci.yml` — the stages map 1:1.

## 7. Viva one-liner
> "Every push triggers a Jenkins pipeline that compiles all Python modules,
> runs the 42-case test suite, builds the React dashboard, and validates the
> Docker Compose file — the whole setup is itself one command
> (`startup/<os>/setup.sh`), and problems surface within minutes."
