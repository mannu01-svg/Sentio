# Demo Script & Viva Q&A

## 1. Ten-minute demo (run in this order)

**Pre-demo (one time):** `docker compose up -d` → wait `(healthy)`, dataset in `data/raw/`.

| # | Terminal / Browser | Say |
|---|---|---|
| 1 | `docker compose ps` | "Two infra containers: Kafka in KRaft mode — no Zookeeper — and PostgreSQL." |
| 2 | `docker exec sma-kafka ... kafka-topics.sh --list` | "Two topics: raw comments in, scored comments out." |
| 3 | `./run_spark.sh` | "Spark Structured Streaming job: cleans text, scores with VADER + DistilBERT, aggregates 1-minute windows." |
| 4 | `python producer/producer.py --file data/raw/reddit.csv --rate 10 --loop` | "Producer replays the dataset as a live stream at 10 comments/second." |
| 5 | (30 s) `docker exec sma-postgres psql ... "SELECT * FROM window_stats ..."` | "Windowed aggregates are landing in Postgres — this is Spark's output." |
| 6 | `uvicorn api.main:app --port 8000` → open `/docs` | "FastAPI serves the analytics; auto-documented." |
| 7 | open dashboard `localhost:5173` | "Live dashboard: KPIs, sentiment timeline, distribution, trending words." |
| 8 | point at **model comparison** panel | "VADER vs DistilBERT — agreement %, label accuracy, disagreement examples." |
| 9 | apply a filter in the live feed | "Filters query the API in real time." |
| 10 | `python evaluation/evaluate.py` | "Offline evaluation: accuracy, per-class F1, confusion matrices vs dataset labels." |

## 2. Viva Q&A

**Q1. Why Kafka at all — why not write CSV rows straight into Spark?**
> Kafka decouples ingestion from processing. The producer can burst while Spark catches up, messages are replayable (offsets), and multiple consumers can read the same stream independently — e.g. our Kafka feed sink and Spark consumer.

**Q2. What is Spark Structured Streaming's processing model?**
> Micro-batching: the unbounded stream is internally divided into small batches processed with the same DataFrame API as batch Spark. Each trigger runs parse → clean → score → aggregate → sink.

**Q3. Explain the 1-minute window and the 2-minute watermark.**
> A tumbling window groups events by event time into fixed 1-minute buckets. The watermark (2 min) bounds how long we wait for late events; after it passes the window is finalized. This trades a little delay for correct late-data handling.

**Q4. How does VADER work?**
> A valence lexicon of ~7,500 words tuned for social media, plus grammar/syntax rules: punctuation, capitalization, degree modifiers, negation, emoticons. It outputs positive/negative/neutral proportions and a normalized compound score in [-1, 1]. We label |compound| ≤ 0.05 as neutral.

**Q5. Why DistilBERT as the AI model?**
> It is a distilled (40% smaller, 60% faster) BERT, fine-tuned on SST-2. It captures context that a lexicon misses (e.g. "not good"). We map its POSITIVE/NEGATIVE output; SST-2 has no neutral class — visible in its confusion matrix.

**Q6. Your two models disagree 55% of the time. Is that a problem?**
> No — it's the finding. VADER treats neutral-ish text literally (score 0), while BERT forces a binary choice and leans negative on questions/requests. We quantify it (agreement %, confusion matrices) and discuss label-vs-model accuracy rather than hiding it.

**Q7. How do you know the models are accurate at all?**
> The dataset ships ground-truth labels; we evaluate offline against them: accuracy, per-class precision/recall/F1, confusion matrices. In our run: VADER ≈ 56%, DistilBERT ≈ 64% on Reddit comments.

**Q8. Why PostgreSQL and not NoSQL/HDFS?**
> Our access pattern is aggregate + recent-rows queries — a perfect fit for relational SQL with indexes. The Spark JDBC sink is standard. HDFS/Cassandra add operational complexity without benefit at this scale.

**Q9. How is fault tolerance handled?**
> Checkpoints store stream progress per sink, so a restarted job resumes from offsets. Sinks are idempotent upserts keyed by `id`/`window_start`, so retries don't duplicate rows. Model failures are caught and set null columns instead of killing the stream.

**Q10. What happens if the producer stops?**
> Nothing crashes — Spark waits for new messages (trigger-based), the dashboard keeps polling, the API serves the last known state. Restart the producer and the stream continues.

**Q11. Why polling instead of WebSockets?**
> The aggregates update per minute; 3 s polling is stateless, trivially reliable, and simpler to defend. WebSockets would be the choice for sub-second push updates — noted as future work.

**Q12. Limitations — state them honestly.**
> English-only; dataset replay simulates (not equals) a live platform feed; BERT has no neutral class; single-machine single-broker (no replication); sarcasm remains hard for both models.

**Q13. What would production look like?**
> Real platform APIs with rate limiting, Kafka multi-broker + replication, Spark cluster, Postgres read replicas or a warehouse, auth on the API, WebSocket push, model monitoring/retraining.

**Q14. Why is the producer's ID unique per send?**
> We replay the same CSV in a loop; if IDs repeated, one micro-batch could contain the same primary key twice and Postgres rejects `ON CONFLICT` updates affecting a row twice. Unique IDs make every write idempotent and safe.

**Q15. What did each team member do?**
> See `docs/04_Work_Division.md` — four workstreams: infra+producer, Spark+NLP, storage+API, frontend+docs.

## 3. Screenshots to capture for the report
1. `docker compose ps` (infra up)
2. Spark console streaming logs
3. Postgres window_stats rows
4. FastAPI `/docs`
5. Dashboard: overview
6. Dashboard: model comparison panel
7. Evaluation output (accuracy + confusion matrices)
