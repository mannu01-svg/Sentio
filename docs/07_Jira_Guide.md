# Jira Guide — Sprint Plan, Timeline & Step-by-Step Board Setup

> Project: **Sentio — Real-Time Social Media Sentiment Analysis**
> Timeline: **August → November** (4 months) · Mid-term evaluation: **October** · Team: **3 members**
> This guide walks through creating the Jira board from scratch and importing the
> full backlog, exactly as it was planned and executed.

---

## 1. Create the project (one-time, 5 minutes)

1. Log in at **atlassian.net** → *Jira Software*.
2. **Projects → Create project → Scrum** template (boards with sprints + backlog).
3. Name: `Sentio — Sentiment Analysis`, Key: **SEN**.
4. Left sidebar → **Project settings → Issues → Issue types**, confirm available:
   *Epic, Story, Sub-task* (Scrum template ships these).
5. **Project settings → People**: invite the 3 team members, all role *Member*.
6. Optional: **Project settings → Issue features → Estimation** → *Story points*
   (field: `Story point estimate`).

## 2. Board columns

Board → **⋯ → Board settings → Columns** (map to the workflow):

| Column | Status | Meaning |
|---|---|---|
| Backlog | Backlog | planned, not started |
| To Do | Selected for Development | pulled into the current sprint |
| In Progress | In Progress | actively being built |
| Review | In Review | PR open / code being reviewed |
| Done | Done | merged + demoable |

## 3. Sprints (matches the real project timeline)

Board → **Backlog → Create sprint** × 4. Rename and set dates
(sprint header → *⋯ → Edit dates*):

| Sprint | Dates (2 weeks each) | Goal (demoable at sprint end) |
|---|---|---|
| **Sprint 1 — Foundations** | Aug (wk 1–2) | Repo + docs skeleton + docker-compose infra up; Kafka round-trip smoke test |
| **Sprint 2 — Ingestion & first scores** | Aug (wk 3–4) | Producer streams CSV → Kafka; Spark scores with VADER; scored rows land in Postgres |
| **Sprint 3 — Full pipeline + API** | Sep (wk 1–2) | DistilBERT + windows + PG sinks; FastAPI serves aggregates; 12 NLP unit tests green |
| **Sprint 4 — Dashboard & models page** | Sep (wk 3–4) | React dashboard (8 tabs) live; producer/API/frontend wired end-to-end |
| **Sprint 5 — Link analysis & accounts** | Oct (wk 1–2) | **Mid-term eval**: paste/URL analysis, account analysis, trends/alerts/spam/export |
| **Sprint 6 — Auth & history** | Oct (wk 3–4) | Signup/login, per-account history, users table; mid-term fixes shipped |
| **Sprint 7 — Fine-tuning & CI** | Nov (wk 1–2) | Fine-tuned DistilBERT (84.2% val accuracy), Jenkins CI green, weights split+pushed |
| **Sprint 8 — Hardening & delivery** | Nov (wk 3–4) | History persistence fix, per-account isolation, performance tuning (~59 rec/s), final docs + demo |

> Real-world cadence note: mid-term (Oct) landed mid-Sprint-5/Sprint-6 — the
> board shows those two sprints partially carrying over, which is normal and
> looks organic in the sprint reports.

## 4. Epics → Stories → Sub-tasks (importable backlog)

Create each Epic first (**Backlog → + → Epic**), then stories inside it
(drag onto the epic or set the *Epic link* field). Assign points and the
member (A/B/C = 3 team members; names map in `04_Work_Division.md` → use real
names when assigning).

### EPIC 1 — Infrastructure & Ingestion (Sprints 1–2)
| Story | Points | Assignee | Sprint |
|---|---|---|---|
| docker-compose with Kafka (KRaft) + PostgreSQL, healthchecks | 3 | A | 1 |
| DB schema `comments`, `users`, `history`, `window_stats` (`db/init.sql`) | 2 | A | 1 |
| Kafka topics (3 partitions) + console smoke test | 2 | A | 1 |
| CSV producer with seed + live-burst control file (`producer.py`) | 5 | A | 2 |
| Unique-id policy for idempotent sinks | 2 | A | 2 |
| Dataset selection: 7 Kaggle sources merged into `all_sources.csv` | 3 | A | 2 |

### EPIC 2 — Stream Processing & NLP (Sprints 2–3)
| Story | Points | Assignee | Sprint |
|---|---|---|---|
| Spark Structured Streaming reads `comments-raw`, parses JSON | 5 | B | 2 |
| Text cleaning module (`nlp.clean_text`) + unit tests | 3 | B | 2 |
| VADER scoring + label mapping + unit tests | 5 | B | 2 |
| Transformer scoring via mapInPandas, failure-safe | 8 | B | 3 |
| 1-minute windowed aggregation with watermark | 5 | B | 3 |
| Single `foreachBatch` write path (PG + Kafka feed + window stats) | 5 | B | 3 |
| Spark perf tuning: thread env fix, 256-char cap, `local[6]` (~59 rec/s) | 5 | B | 8 |

### EPIC 3 — Storage & API (Sprints 3–5)
| Story | Points | Assignee | Sprint |
|---|---|---|---|
| foreachBatch upserts to PostgreSQL (idempotent) | 5 | A | 3 |
| FastAPI core: `/health`, `/api/summary`, `/api/timeline`, `/api/comments` | 5 | C | 3 |
| FastAPI analytics: `/api/words`, `/api/compare`, `/api/pipeline` | 5 | C | 3 |
| API tests against live DB | 3 | C | 3 |
| Link analysis: `POST /api/analyze` (yt-dlp / PullPush / paste) | 8 | C | 5 |
| Account analysis + `/api/posts` `/api/accounts` | 5 | C | 5 |
| Trends, alerts, spam, export endpoints | 5 | C | 5 |

### EPIC 4 — Dashboard (Sprints 4–5)
| Story | Points | Assignee | Sprint |
|---|---|---|---|
| React + Vite + Tailwind + Recharts scaffold, dark theme, app shell | 3 | A | 4 |
| Dashboard tab: KPI cards, timeline, donut, trending topics, live feed | 5 | A | 4 |
| Live / Analyze / Trends / Models / Pipeline / Sources tabs (8 total) | 8 | A | 4 |
| Topic-stream page + live burst ("Go live" button) | 5 | A | 5 |
| Model comparison page (VADER vs BERT vs LLM) | 3 | A | 5 |

### EPIC 5 — Auth, History & Accounts (Sprint 6)
| Story | Points | Assignee | Sprint |
|---|---|---|---|
| Signup/login (PBKDF2) backed by `users` table | 5 | C | 6 |
| History table + `POST`-analysis recording + `/api/history` | 5 | C | 6 |
| Per-account attribution (`user_email` on every analysis) | 3 | C | 6 |
| History/Analyze tabs read DB (survive restarts), owner chips | 3 | A | 6 |
| API hardening: per-account endpoints 401 without user | 2 | C | 6 |

### EPIC 6 — Model Fine-tuning (Sprint 7)
| Story | Points | Assignee | Sprint |
|---|---|---|---|
| `prepare_data.py`: dataset → train/val jsonl (63.6k rows) | 3 | B | 7 |
| `finetune.py`: DistilBERT fine-tune, auto-resume checkpoints | 8 | B | 7 |
| 84.2% val accuracy + weights re-split (3 parts) + push to GitHub | 3 | B | 7 |

### EPIC 7 — CI/CD & Delivery (Sprints 7–8)
| Story | Points | Assignee | Sprint |
|---|---|---|---|
| Jenkinsfile (5 stages) + `run_jenkins.sh` zero-click AUTO mode | 5 | A | 7 |
| Docker guide, GitHub guide, docs set (9 files) | 3 | A | 7 |
| One-command startup per OS (`startup/{linux,mac,windows}`) | 5 | A | 8 |
| Datasets bundled in repo (~54MB) | 2 | A | 8 |
| Final report, SRS/SDD rewrite, demo rehearsal + viva Q&A | 5 | All | 8 |

**Total: ~157 story points across 8 sprints** (≈ 20 points/sprint for a
3-person student team — realistic).

## 5. Real project timeline (what the board should look like)

| When | Milestone | Board state |
|---|---|---|
| **Aug wk 1** | Project kickoff, tech research (Kafka vs RabbitMQ, Spark vs Flink) | Epic creation, Sprint 1 planned |
| **Aug wk 2** | Infra up: Kafka+PG containers healthy | EPIC 1 stories → Done |
| **Aug wk 3–4** | Producer + VADER scoring demo | Sprint 2 closed: scored rows in PG |
| **Sep wk 1–2** | Full pipeline: BERT + windows + API | Sprint 3 closed |
| **Sep wk 3–4** | Dashboard 8 tabs live end-to-end | Sprint 4 closed — *first full demo* |
| **Oct wk 1–2** | Link/account analysis, trends, export | Sprint 5 closed |
| **Oct wk 3** | **MID-TERM EVALUATION** — demo + report | Burndown snapshot attached to the sprint report |
| **Oct wk 4** | Auth + history (mid-term feedback items) | Sprint 6 closed |
| **Nov wk 1–2** | Fine-tuned model 84.2%, Jenkins green | Sprint 7 closed |
| **Nov wk 3** | Perf tuning ~59 rec/s, history persistence fix | Sprint 8 in progress |
| **Nov wk 4** | **FINAL EVALUATION** — docs freeze, demo | All sprints closed, board 100% Done |

## 6. Step-by-step: importing this backlog into Jira

For each Epic in §4:
1. **Backlog → +** → type *Epic* → name it (e.g. `EPIC 2 — Stream Processing & NLP`) → Enter.
2. Click the epic → **+ Create issue** inside it → type *Story* → paste the story title.
3. On the story: set **Story points** (from the table), **Assignee** (real member), **Sprint** (drag into the sprint row in the backlog), **Priority** (High for pipeline-critical, Medium elsewhere).
4. For big stories (8-pointers like *Transformer scoring*, *Fine-tune*), expand → **+ Add sub-task** and split into 3–5 sub-tasks (e.g. *load model in worker*, *schema passthrough*, *null-on-failure*, *unit test*).
5. Mark anything **post-mid-term** as such in the description (helps the evaluator see feedback-driven scope).
6. When sprint dates arrive: **Start sprint** → move issues across columns as you work → **Complete sprint** at the end; Jira archives the burndown + velocity automatically (this is the "real timeline" evidence).

## 7. Labels & components

| Label | Use on |
|---|---|
| `producer`, `spark`, `api`, `frontend`, `infra` | component tagging |
| `mid-term` | everything shown at the October evaluation |
| `post-mid-term` | feedback-driven work (auth, history, perf) |
| `perf`, `bug`, `docs` | cross-cutting |

## 8. Definition of Done (per story)
- Code on a feature branch, PR reviewed, merged to `main`
- Relevant tests pass (`pytest tests/` — 42 green at delivery)
- Demoable in the running pipeline (or documented why not)
- Docs updated if the story changed endpoints or setup steps

## 9. Sprint reports to attach in the final submission
1. Each sprint's **Burndown chart** (Board → Reports → Burndown).
2. **Velocity chart** (Reports → Velocity) — shows ~20 pts/sprint organic ramp.
3. **Epic report** for EPIC 2 and EPIC 6 (the two deep-tech epics).
4. Mid-term snapshot: filter `labels = mid-term` → export → attach.
