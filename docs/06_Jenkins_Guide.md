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

## 3. Running Jenkins locally (one-time, optional)

```bash
# 1. start Jenkins
docker run -d --name jenkins -p 8080:8080 -p 50000:50000 \
  -v jenkins_home:/var/jenkins_home \
  -v /var/run/docker.sock:/var/run/docker.sock \
  jenkins/jenkins:lts

# 2. get the initial admin password
docker exec jenkins cat /var/jenkins_home/secrets/initialAdminPassword

# 3. open http://localhost:8080 → install suggested plugins
# 4. install Pipeline + Docker plugins
# 5. New Item → Pipeline → point it at this repo (or "Pipeline script from SCM")
```

> The Jenkins container needs docker CLI + node on the agent for all stages;
> if a stage is unavailable in your lab setup, it can be disabled without
> affecting the rest.

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
