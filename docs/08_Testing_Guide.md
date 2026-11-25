# Testing guide: unit, Selenium, Postman, Jenkins, webhook

Sentio has three layers of automated tests. All three run in Jenkins on every push.

| Layer | Tool | Where | What it covers |
|---|---|---|---|
| Unit / API | pytest | `tests/*.py` | NLP models, auth, API endpoints, MongoDB store (58 tests) |
| API contract | Postman + Newman | `postman/` | 21 requests, 67 assertions over the live API |
| UI end-to-end | Selenium WebDriver | `tests/e2e/` | 15 browser tests over the live dashboard |

The Postman and Selenium tests need the stack running. Start it first:

```powershell
cd C:\projects\Sentio
startup\windows\start.bat --fast
```

---

## 1. Unit tests (pytest)

```powershell
.venv\Scripts\activate
pip install -r requirements.txt pytest
pytest tests -v --ignore=tests/e2e
```

The API and MongoDB tests need PostgreSQL on `localhost:5432` (the Docker stack provides it). Without PostgreSQL they are skipped.

---

## 2. Selenium UI tests

### Run them

```powershell
pip install -r requirements-test.txt
pytest tests/e2e -v
```

* Uses your installed Google Chrome, headless. To watch the browser, run `$env:HEADLESS="0"` first.
* If ChromeDriver complains about the version, install the one that matches your Chrome: `pip install "chromedriver-py==<your Chrome major>.*"`. Find your Chrome version at `chrome://version`.
* When a test fails, a screenshot is saved to `tests/e2e/screenshots/<test name>.png`.
* If the dashboard isn't reachable at `http://localhost:5173`, the whole folder is skipped, so plain `pytest` still passes.

Settings (environment variables):

| Variable | Default | Purpose |
|---|---|---|
| `BASE_URL` | `http://localhost:5173` | Dashboard URL |
| `E2E_EMAIL` / `E2E_PASSWORD` | `admin@sentio.app` / `admin123` | Login used by the tests |
| `HEADLESS` | `1` | `0` shows the browser window |
| `SELENIUM_REMOTE_URL` | none | Use a Selenium Grid, e.g. `http://localhost:4444/wd/hub` |
| `CHROME_BIN` / `CHROMEDRIVER` | none | Explicit browser and driver paths (Jenkins uses these) |

### What is tested

1. The login page renders (email, password, Sign in).
2. Opening `/dashboard` while signed out redirects to `/login`.
3. A wrong password shows the error message and stays on `/login`.
4. The admin login reaches the Dashboard and shows the "Comments processed" KPI.
5. Every sidebar link opens its page: Live Feed, Analyze, History, Trends, Models, Pipeline, Sources (7 tests).
6. The Pipeline page lists the Kafka, PostgreSQL and MongoDB stages.
7. Pasting 3 comments on Analyze → Instagram shows "3 comments streaming through the pipeline", opens the analysis page, and the analysis appears in History under the title you typed.
8. The light/dark theme toggle switches.
9. Sign out returns to `/login`, and protected pages are locked again.

Test 7 caught a real bug: History ignored the title you typed for pasted comments and always showed "Pasted comments". That is fixed in `api/main.py`, and covered by `tests/test_mongo_api.py::test_paste_keeps_the_user_title`.

---

## 3. Postman collection

Files in `postman/`:

* `Sentio.postman_collection.json`: the collection (5 folders, 21 requests, each with test scripts).
* `Sentio-local.postman_environment.json`: `baseUrl = http://localhost:8000` (the API directly).
* `Sentio-nginx.postman_environment.json`: `baseUrl = http://localhost:5173` (through nginx, as the browser does).

### In the Postman app

1. **Import** → drag in the collection and both environment files.
2. Choose the **Sentio - local Docker** environment (top right).
3. Right-click the collection → **Run collection** → **Run Sentio API**. Keep the order; Login stores the token that the later requests use.

### From the command line (Newman)

```powershell
npx newman run postman/Sentio.postman_collection.json -e postman/Sentio-local.postman_environment.json
```

### What is tested

| Folder | Requests |
|---|---|
| 1 Health | `/health` (API, PostgreSQL, MongoDB), `/openapi.json` (Swagger spec is served) |
| 2 Auth | Wrong password is rejected; Login saves the Bearer token; History without a token is refused (401/403) |
| 3 Analytics | Summary KPIs, timeline (checks there is no `NaN`), comments, model comparison, trends, alerts, pipeline stages (Kafka, MongoDB, PostgreSQL), CSV export |
| 4 Analyze flow | Paste 3 comments → find them in History → read the MongoDB document (raw comments) → re-score from MongoDB → wait until Spark has scored them (retries every 5 s, up to 60 s) |
| 5 Admin | List users |

Every request also checks for HTTP 200 and a response time under 3 seconds.

---

## 4. Jenkins pipeline

`Jenkinsfile` stages:

1. **Setup Python**: virtualenv plus the test packages.
2. **Lint**: `compileall` over all Python packages.
3. **Unit Tests**: pytest, written to `reports/unit.xml`.
4. **Frontend Build**: `npm install && npm run build`.
5. **Docker Compose Config**: validates `docker-compose.yml`.
6. **Connect to running stack**: Jenkins joins the `sentio_default` Docker network and waits for `http://api:8000/health`.
7. **API Tests (Postman/Newman)**: written to `reports/newman.xml`.
8. **UI Tests (Selenium)**: headless Chromium inside the Jenkins container against `http://frontend`, written to `reports/selenium.xml`.

All the XML reports are published with the JUnit plugin. Open a build and click **Tests** to see each test case. Failure screenshots are archived under **Artifacts**.

If the Sentio stack isn't running, stages 7–8 are skipped and the build is marked **UNSTABLE** (yellow), with a note to start it. To skip them deliberately, use **Build with Parameters** and untick `RUN_E2E`.

### Rebuild the Jenkins image once

The image now includes Chromium and the GitHub and JUnit plugins, so recreate it once:

```powershell
docker rm -f sma-jenkins
$env:AUTO="1"; $env:JENKINS_PORT="8090"; bash run_jenkins.sh
```

Your Jenkins home volume (jobs, history, the `sentio` login) is kept.

---

## 5. GitHub webhook: a build on every push

The Jenkinsfile has `triggers { githubPush() }`, and the job is created with "GitHub hook trigger for GITScm polling" switched on. GitHub needs a public URL for Jenkins. Jenkins on a laptop isn't public, so open a tunnel.

### Step 1: expose Jenkins with a free tunnel

Use Cloudflare's quick tunnel (no account needed):

```powershell
winget install --id Cloudflare.cloudflared
cloudflared tunnel --url http://localhost:8090
```

It prints a URL such as `https://random-words.trycloudflare.com`. Keep the window open. The URL changes each time you restart the tunnel. ngrok works the same way (`ngrok http 8090`).

### Step 2: add the webhook on GitHub

The repo owner (mannu01-svg), or a collaborator with admin access, does this:

1. Open github.com/mannu01-svg/Sentio → **Settings** → **Webhooks** → **Add webhook**.
2. **Payload URL**: `https://random-words.trycloudflare.com/github-webhook/` (keep the trailing slash).
3. **Content type**: `application/json`.
4. **Which events**: *Just the push event*.
5. **Add webhook**. GitHub sends a ping; a green tick under **Recent Deliveries** means Jenkins received it.

### Step 3: test it

```powershell
git commit --allow-empty -m "test webhook"
git push
```

A new `sentio-ci` build starts within a few seconds. Its log begins with *Started by GitHub push by <user>*.

**Fallback:** if the tunnel is down, Jenkins still polls GitHub every 5 minutes (`pollSCM("H/5 * * * *")`), so pushes are always built, just later.

**Branch:** the job builds `*/main`. To demo from another branch, open the job → **Configure** → **Branches to build** → change it (for example `*/docker-mongodb`), or merge into main.

---

## 6. What to show the evaluators

1. Run `pytest tests -v --ignore=tests/e2e`: all green.
2. Run `pytest tests/e2e -v` with `$env:HEADLESS="0"`: the browser logs in, clicks through every page and runs an analysis.
3. Open Postman → run the collection: 67 green assertions.
4. Push a commit, and a Jenkins build starts from the webhook. Open **Stage View** to see all 8 stages, then the **Tests** tab.
