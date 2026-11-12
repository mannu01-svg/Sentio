# Jenkins CI Guide

## 1. Why CI in the report
Continuous Integration means every push is automatically **compiled, linted
and tested**, so a broken commit never reaches `main`. In the project report,
this demonstrates industrial software-engineering practice on top of the
data pipeline itself.

## 2. What the pipeline does (`Jenkinsfile` in repo root)

| Stage | Command | Checks |
|---|---|---|
| Setup Python | `python3 -m venv .venv-ci` + pip install | reproducible test env |
| Lint | `python -m compileall spark producer api evaluation` | all modules compile |
| Unit Tests | `pytest tests/test_nlp.py -v` | 12 NLP tests (cleaning, labeling) |
| Frontend Build | `npm install && npm run build` in `frontend/` | dashboard bundles cleanly |
| Compose Config | `docker compose config -q` | docker-compose.yml is valid |

## 3. Running Jenkins locally — one command (verified working)

```bash
./run_jenkins.sh
```

This builds a small `sentio-jenkins` image (stock Jenkins LTS + python3 + node +
docker CLI — the stages need them on the agent) and starts it. It prints the
initial admin password and the exact click-path. Jenkins runs wherever you
execute this script — **nothing external is required**, so each teammate can
demo CI on their own machine with the identical pipeline.

Manual equivalent (what the script does):

```bash
# 1. build the agent image (python3 + node + docker CLI on Debian trixie)
docker build -t sentio-jenkins -f Dockerfile.jenkins .

# 2. start Jenkins (docker.sock mounted so the Compose-Config stage works)
docker run -d --name sma-jenkins -p 8080:8080 -p 50000:50000 \
  -v sma-jenkins_home:/var/jenkins_home \
  -v /var/run/docker.sock:/var/run/docker.sock \
  sentio-jenkins

# 3. get the initial admin password
docker exec sma-jenkins cat /var/jenkins_home/secrets/initialAdminPassword

# 4. open http://localhost:8080 → create admin user (plugins ship preinstalled
#    via the script's first-run; "Install suggested plugins" also works)
# 5. New Item → name: sentio-ci → Pipeline → Pipeline script from SCM
#    → Git → https://github.com/mannu01-svg/Sentio.git → */main → Save → Build Now
```

> Verified end-to-end: 5/5 stages green — Setup Python → Lint → Unit Tests
> (34 passed, 8 skipped: DB/model tests skip gracefully in bare CI containers)
> → Frontend Build → Docker Compose Config.

> If a stage is unavailable in your lab setup (e.g. no docker.sock permission),
> disable just that stage in the Jenkinsfile — the rest still runs.

## 4. Wiring a webhook (optional)
Jenkins → job → Configure → *Build Triggers* → *GitHub hook trigger for
GITScm polling*. Then GitHub repo → Settings → Webhooks →
`http://<jenkins-host>:8080/github-webhook/`.

## 5. Fallback: GitHub Actions
If Jenkins is not available in the lab, an equivalent (simpler) workflow can
be added later at `.github/workflows/ci.yml` — the stages map 1:1.

## 6. Viva one-liner
> "Every commit triggers a Jenkins pipeline that compiles all Python modules,
> runs the NLP unit tests, builds the React dashboard, and validates the
> Docker Compose file — so integration problems surface within minutes."
