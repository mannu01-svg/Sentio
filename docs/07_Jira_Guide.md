# Jira Guide — Sprint Plan & Importable Backlog

## 1. Board setup (one-time)
1. Create a **Scrum** project, e.g. `SMA` (Social Media Analysis).
2. Issue types: Epic → Story → Sub-task.
3. Sprints: 2 weeks each, 3 sprints total (matches the phases below).

## 2. Epics → Stories

### EPIC 1 — Infrastructure (Sprint 1)
| Story | Points |
|---|---|
| Set up docker-compose with Kafka (KRaft) + PostgreSQL | 3 |
| Create DB schema `comments` + `window_stats` (`db/init.sql`) | 2 |
| Create Kafka topics + console smoke test | 2 |

### EPIC 2 — Ingestion (Sprint 1)
| Story | Points |
|---|---|
| CSV producer with configurable rate (`producer.py`) | 5 |
| Unique-id policy for idempotent sinks | 2 |
| Sample dataset + download script for Kaggle data | 3 |

### EPIC 3 — Stream processing (Sprint 2)
| Story | Points |
|---|---|
| Spark Structured Streaming reads `comments-raw`, parses JSON | 5 |
| Text cleaning module (`nlp.clean_text`) + unit tests | 3 |
| VADER scoring UDF + label mapping + unit tests | 5 |
| DistilBERT scoring via mapInPandas, failure-safe | 8 |
| 1-minute windowed aggregation with watermark | 5 |

### EPIC 4 — Storage & API (Sprint 2)
| Story | Points |
|---|---|
| foreachBatch upserts to PostgreSQL (comments, window_stats) | 5 |
| FastAPI: /health, /api/summary, /api/timeline | 5 |
| FastAPI: /api/comments, /api/words, /api/compare | 5 |
| API tests against live DB | 3 |

### EPIC 5 — Dashboard (Sprint 3)
| Story | Points |
|---|---|
| React + Vite + Tailwind + Recharts scaffold, dark theme | 3 |
| KPI cards + sentiment timeline + donut charts | 5 |
| Live feed + filters + polling hook | 5 |
| Model comparison panel (VADER vs DistilBERT) | 5 |

### EPIC 6 — Evaluation & delivery (Sprint 3)
| Story | Points |
|---|---|
| `evaluate.py`: accuracy/F1/confusion vs dataset labels | 5 |
| Jenkinsfile pipeline (lint, tests, frontend build) | 3 |
| Documentation: SRS, SDD, final report, README | 8 |
| End-to-end demo rehearsal + viva Q&A | 3 |

## 3. Sprint milestones
| Sprint | Goal (demoable) |
|---|---|
| **Sprint 1** | Data flows into Kafka; Postgres ready |
| **Sprint 2** | Scored comments + aggregates land in Postgres; API serves them |
| **Sprint 3** | Live dashboard + model comparison + evaluation + report |

## 4. Definition of Done (per story)
- Code on a feature branch, PR reviewed, merged to `dev`
- Relevant tests pass (`pytest tests/`)
- Demoable in the running pipeline (or documented why not)
