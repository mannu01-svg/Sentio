# Work Division — Team of 3

> Team: **Khushi Balyan**, **Mannat Muthreja**, **Ami Lal** 
> names). Each workstream is independently demoable; pairs worked in parallel
> after Sprint 2. Timeline: 17 September → 21 November, mid-term evaluation on 20 September.

## 1. Workstreams & Ownership

| Workstream | Scope | Primary | Secondary |
|---|---|---|---|
| **W1 — CI/CD, Startup Tooling, Datasets & Docs** | Jenkins CI (zero-click), `startup/{linux,mac,windows}` one-command scripts, dataset bundling (54 MB), documentation set, repo templates | Khushi | Mannat |
| **W2 — Pipeline, Producer, Frontend & Performance** | full pipeline (Kafka+Spark+VADER/DistilBERT), `producer.py` (seed/live bursts), React dashboard (8 tabs), history/API features, spark perf tuning (6.5×), fine-tuning (84.2%) | Mannat | Khushi |
| **W3 — Auth, Link Analysis, Tests & Trends** | Sentio rebrand (multi-page app), PBKDF2 signup/login, link/account analysis, trends/alerts/spam/export, 42-case test suite, per-account history UI | Ami | Mannat |

## 2. Phase Plan (who did what, when — Aug → Nov)

| Phase | Deliverable | Owner | Helper | When |
|---|---|---|---|---|
| 1. Foundations | repo, docs skeleton, docker-compose up | Khushi | — | 17–19 Sep |
| 2. Producer | CSV → `comments-raw` streaming (seed + bursts) | Khushi | Mannat | 22 Sep |
| 3. NLP core | `nlp.py` + unit tests green | Mannat | — | 22–30 Sep |
| 4. Streaming job | Kafka → clean → VADER → PG | Mannat | Khushi | 26 Sep |
| 5. Sinks + windows | single `foreachBatch` upserts, 1-min windows | Mannat | Ami | Sep wk 1 |
| 6. API v1 | 6 core endpoints + tests vs live data | Ami | — | Sep wk 1–2 |
| 7. Transformer | DistilBERT via mapInPandas, failure-safe | Mannat | Ami | Sep wk 2 |
| 8. Dashboard v1 | 8 tabs, charts, live feed, polling | Khushi | Ami | Sep wk 3–4 |
| 9. First full demo | end-to-end pipeline + dashboard | All | — | Sep wk 4 |
| 10. Link & account analysis | `/api/analyze`, account mode, trends/alerts/spam/export | Ami | Mannat | Oct wk 1–2 |
| 11. **Mid-term evaluation** | demo + mid-term report | All | — | Oct wk 3 |
| 12. Auth & history | signup/login, per-account history, users table | Ami | Khushi | Oct wk 3–4 |
| 13. Mid-term fixes | history persistence, owner chips, API hardening | Ami | Mannat | Oct wk 4 |
| 14. Fine-tuning | `prepare_data.py` + `finetune.py` → **84.2% val accuracy** | Mannat | — | Nov wk 1–2 |
| 15. CI/CD | Jenkinsfile 5 stages + zero-click `run_jenkins.sh` | Khushi | Ami | Nov wk 1–2 |
| 16. Perf tuning | thread env fix, 256-char cap → **~59 rec/s** | Mannat | Khushi | Nov wk 3 |
| 17. Startup DX | one-command `startup/{linux,mac,windows}` + bundled datasets | Khushi | — | Nov wk 3 |
| 18. Delivery | final docs, SRS/SDD rewrite, demo rehearsal | All | — | Nov wk 4 |

## 3. RACI Matrix (key deliverables)

| Deliverable | Khushi | Mannat | Ami |
|---|---|---|---|
| docker-compose + schema + topics | **R** | Ami | C |
| producer.py + dataset merge | **R** | Ami | I |
| nlp.py + unit tests | Ami | **R** | I |
| streaming_job.py + windows + perf | Ami | **R** | Ami |
| fine-tuning (84.2%) | I | **R** | I |
| api/main.py + auth + history | I | Ami | **R** |
| React dashboard (8 tabs) | **R** | I | Ami |
| startup scripts + CI (Jenkins) | **R** | I | Ami |
| evaluation.py | I | **R** | Ami |
| SRS / SDD / final report | **R** | Ami | C |
| Final demo | **R** | Ami | C |

*R = responsible, A = accountable (whole team on all deliverables), C = consulted, I = informed*

## 4. Individual contribution summary (for the report title page)

Each member writes 3–5 lines: workstream, concrete modules delivered, one
lesson learned. Template:

> **Khushi Balyan — CI/CD, Startup Tooling, Datasets & Docs.** Built the
> Jenkins CI pipeline (zero-click AUTO mode, 5/5 green), the cross-platform
> one-command startup (`startup/{linux,mac,windows}`), bundled all datasets
> (54 MB) and model weights into the repo, and wrote the documentation set
> (SRS, SDD, guides, Capstone report). Lesson: *developer experience (one
> command, green checks) is what makes a demo land.*

> **Mannat Muthreja — Pipeline, Producer, Frontend & Performance.** Built the
> streaming job (parse → clean → dual scoring → 1-min windows → idempotent
> PG sinks), the CSV→Kafka producer with seed/live-burst control, the 8-tab
> React dashboard, per-account history + attribution, and the performance
> tuning that lifted sustained throughput ~9 → ~59 records/s. Lesson:
> *profile before optimizing — the bottleneck was a silently overridden
> thread env var, not the model.*

> **Ami Lal — Auth, Link Analysis, Tests & Trends.** Built the Sentio
> rebrand (multi-page app with router), PBKDF2-based signup/login, link and
> account analysis (yt-dlp / PullPush), trends/alerts/spam/export endpoints,
> and the 42-case test suite. Lesson: *silent best-effort writes hide schema
> drift — fail loudly, migrate on startup.*
