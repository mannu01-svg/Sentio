# Work Division — Team of 4

> Replace Member A–D with real names. Each workstream is independently
> demoable; pairs can work in parallel after Phase 1.

## 1. Workstreams & Ownership

| Workstream | Scope | Primary | Secondary |
|---|---|---|---|
| **W1 — Infra & Producer** | docker-compose (Kafka+Postgres), DB schema (`db/init.sql`), topics, `producer/producer.py`, dataset selection & download | Member A | Member D |
| **W2 — Spark & NLP** | `spark/nlp.py`, `spark/streaming_job.py`, windowing/watermarks, sinks, unit tests, `evaluation/evaluate.py` | Member B | Member A |
| **W3 — Storage & API** | PostgreSQL tuning, `api/main.py` (6 endpoints), API tests, docs for endpoints | Member C | Member B |
| **W4 — Frontend & Docs** | React dashboard (charts, live feed, filters, polling), README, report, diagrams | Member D | Member C |

## 2. Phase Plan (who does what, when)

| Phase | Deliverable | Owner | Helper |
|---|---|---|---|
| 1. Infra up | docker-compose runs; Kafka round-trip verified | A | — |
| 2. Producer | CSV → `comments-raw` streaming | A | D |
| 3. NLP core | `nlp.py` + 12 unit tests green | B | — |
| 4. Streaming job | Kafka → clean → VADER → console/PG | B | A |
| 5. Sinks | PG upserts (comments + window_stats) | B | C |
| 6. API | 6 endpoints + tests against live data | C | — |
| 7. Dashboard v1 | KPIs + charts + feed (static fetch) | D | C |
| 8. Live polling | 3 s polling, filters, compare panel | D | C |
| 9. DistilBERT mode | BERT in stream + comparison panel | B | D |
| 10. Evaluation | accuracy/F1/confusion matrices | B | C |
| 11. Docs & report | SRS, SDD, report, README, diagrams | D | all |
| 12. CI & polish | Jenkinsfile, GitHub templates, demo run | A | all |

## 3. RACI Matrix (key deliverables)

| Deliverable | A | B | C | D |
|---|---|---|---|---|
| docker-compose + schema | **R** | C | C | I |
| producer.py | **R** | C | I | I |
| nlp.py + tests | C | **R** | I | I |
| streaming_job.py | C | **R** | C | I |
| api/main.py + tests | I | C | **R** | I |
| frontend dashboard | I | I | C | **R** |
| evaluation.py | I | **R** | C | I |
| SRS / SDD / report | C | C | C | **R** |
| Jenkinsfile / GitHub | **R** | I | I | C |
| Final demo | C | C | C | **R** |

*R = responsible, A = accountable (all: whole team), C = consulted, I = informed*

## 4. For 3 members
Merge W3 into W1 (A: infra+producer+API) and keep B (Spark+NLP) and D (frontend+docs).

## 5. Individual contribution summary (for the report title page)
Each member writes 3–5 lines: workstream, concrete modules delivered, and one
lesson learned. Collect these in `docs/` before submission.
