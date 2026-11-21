# Work Division — Team of 3

> Team: **Member A**, **Member B**, **Member C** (replace B/C with real
> names). Each workstream is independently demoable; pairs worked in parallel
> after Sprint 2. Timeline: August → November, mid-term evaluation in October.

## 1. Workstreams & Ownership

| Workstream | Scope | Primary | Secondary |
|---|---|---|---|
| **W1 — Infra, Producer & Frontend** | docker-compose (Kafka+PG), DB schema, topics, `producer/producer.py`, React dashboard (8 tabs), `startup/{linux,mac,windows}` scripts, CI (Jenkins), docs set | Member A | Member C |
| **W2 — Spark, NLP & Model Training** | `spark/nlp.py`, `spark/streaming_job.py`, windowing/watermarks, single `foreachBatch` sink, perf tuning (~59 rec/s), fine-tuning (84.2%), `evaluation/evaluate.py` | Member B | Member A |
| **W3 — API, Auth & History** | `api/main.py` (30+ endpoints), auth (PBKDF2 signup/login), per-account history + attribution, API tests, Postgres tuning | Member C | Member B |

## 2. Phase Plan (who did what, when — Aug → Nov)

| Phase | Deliverable | Owner | Helper | When |
|---|---|---|---|---|
| 1. Foundations | repo, docs skeleton, docker-compose up | Member A | — | Aug wk 1–2 |
| 2. Producer | CSV → `comments-raw` streaming (seed + bursts) | Member A | B | Aug wk 3 |
| 3. NLP core | `nlp.py` + unit tests green | B | — | Aug wk 3–4 |
| 4. Streaming job | Kafka → clean → VADER → PG | B | Member A | Aug wk 4 |
| 5. Sinks + windows | single `foreachBatch` upserts, 1-min windows | B | C | Sep wk 1 |
| 6. API v1 | 6 core endpoints + tests vs live data | C | — | Sep wk 1–2 |
| 7. Transformer | DistilBERT via mapInPandas, failure-safe | B | C | Sep wk 2 |
| 8. Dashboard v1 | 8 tabs, charts, live feed, polling | Member A | C | Sep wk 3–4 |
| 9. First full demo | end-to-end pipeline + dashboard | All | — | Sep wk 4 |
| 10. Link & account analysis | `/api/analyze`, account mode, trends/alerts/spam/export | C | B | Oct wk 1–2 |
| 11. **Mid-term evaluation** | demo + mid-term report | All | — | Oct wk 3 |
| 12. Auth & history | signup/login, per-account history, users table | C | Member A | Oct wk 3–4 |
| 13. Mid-term fixes | history persistence, owner chips, API hardening | C | B | Oct wk 4 |
| 14. Fine-tuning | `prepare_data.py` + `finetune.py` → **84.2% val accuracy** | B | — | Nov wk 1–2 |
| 15. CI/CD | Jenkinsfile 5 stages + zero-click `run_jenkins.sh` | Member A | C | Nov wk 1–2 |
| 16. Perf tuning | thread env fix, 256-char cap → **~59 rec/s** | B | Member A | Nov wk 3 |
| 17. Startup DX | one-command `startup/{linux,mac,windows}` + bundled datasets | Member A | — | Nov wk 3 |
| 18. Delivery | final docs, SRS/SDD rewrite, demo rehearsal | All | — | Nov wk 4 |

## 3. RACI Matrix (key deliverables)

| Deliverable | A | B | C |
|---|---|---|---|
| docker-compose + schema + topics | **R** | C | C |
| producer.py + dataset merge | **R** | C | I |
| nlp.py + unit tests | C | **R** | I |
| streaming_job.py + windows + perf | C | **R** | C |
| fine-tuning (84.2%) | I | **R** | I |
| api/main.py + auth + history | I | C | **R** |
| React dashboard (8 tabs) | **R** | I | C |
| startup scripts + CI (Jenkins) | **R** | I | C |
| evaluation.py | I | **R** | C |
| SRS / SDD / final report | **R** | C | C |
| Final demo | **R** | C | C |

*R = responsible, A = accountable (whole team on all deliverables), C = consulted, I = informed*

## 4. Individual contribution summary (for the report title page)

Each member writes 3–5 lines: workstream, concrete modules delivered, one
lesson learned. Template:

> **Member A — Infra, Producer & Frontend.** Built the docker-compose
> infra (Kafka KRaft + PostgreSQL), the CSV→Kafka producer with seed/live-burst
> control, the 8-tab React dashboard (Recharts, polling, filters, topic
> streams), the Jenkins CI pipeline (zero-click AUTO mode), and the
> cross-platform one-command startup (`startup/{linux,mac,windows}`). Lesson:
> *developer experience (one command, green checks) is what makes a demo
> land.*

> **Member B — Spark, NLP & Model Training.** Implemented the streaming job
> (parse → clean → dual scoring → 1-min windows → idempotent PG sinks), the
> unit-tested NLP module, the single `foreachBatch` write path, the
> performance tuning that lifted sustained throughput from ~9 to ~59
> records/s, and the DistilBERT fine-tune reaching 84.2% validation accuracy.
> Lesson: *profile before optimizing — the bottleneck was a silently
> overridden thread env var, not the model.*

> **Member C — API, Auth & History.** Built the FastAPI service (30+
> endpoints: analytics, link/account analysis, trends, alerts, spam, export),
> PBKDF2-based signup/login, per-account history with automatic attribution
> (`user_email` on every analysis), history persistence that survives API
> restarts, and the 42-case test suite. Lesson: *silent best-effort writes
> hide schema drift — fail loudly, migrate on startup.*
