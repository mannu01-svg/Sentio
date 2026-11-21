# Demo Script & Viva Q&A

## 1. Ten-minute demo (final version — run in this order)

**Pre-demo (one time):** `bash startup/linux/setup.sh` — everything automatic
(venv, JDK, weights, models, docker, services, Jenkins CI, demo user).

| # | Terminal / Browser | Say |
|---|---|---|
| 1 | `docker compose ps` | "Two infra containers: Kafka in KRaft mode — no Zookeeper — and PostgreSQL." |
| 2 | `docker exec sma-kafka ... kafka-topics.sh --list` | "Two topics: raw comments in, scored out — 3 partitions each." |
| 3 | log in at `localhost:5173` (ada@sentio.app / secret123) | "Per-account: everything I analyze is stored under my account." |
| 4 | Dashboard tab | "Live KPIs, sentiment timeline, distribution, trending topic cards, round-robin live feed." |
| 5 | click **Go live** | "The producer bursts at 40 messages/second on demand — watch the counters climb." |
| 6 | Analyze tab → paste a YouTube URL → Analyze | "Link analysis: yt-dlp fetches real comments; they flow through Kafka → Spark → Postgres. Scores in ~30-60s." |
| 7 | History tab | "Every analysis I've ever run — links, accounts, keywords, topics — stored in Postgres with my email, survives restarts." |
| 8 | Models tab | "Three scorers compared: VADER (lexicon), DistilBERT-SST2, and our fine-tuned model — 84.2% validation accuracy. LLM corrections of VADER surfaced." |
| 9 | Pipeline tab | "Live stage counters: Kafka offsets, Spark throughput (~59 records/s), Postgres rows." |
| 10 | Trends tab | "Velocity ranking: hashtags/words rising fastest, recent vs previous window." |
| 11 | `.venv/bin/pytest tests/ -q` | "42 test cases, all green — also enforced in Jenkins CI." |
| 12 | `python evaluation/evaluate.py` | "Offline evaluation: accuracy, per-class F1, confusion matrices vs dataset labels." |

## 2. Viva Q&A

**Q1. Why Kafka at all — why not write rows straight into Spark?**
> Kafka decouples ingestion from processing. The producer can burst while Spark catches up, messages are replayable (offsets), and multiple consumers read the same stream independently — our PG sink and the live-feed topic.

**Q2. What is Spark Structured Streaming's processing model?**
> Micro-batching: the unbounded stream is divided into small batches processed with the same DataFrame API as batch Spark. Each 10-second trigger runs parse → clean → score → aggregate → sink.

**Q3. Explain the 1-minute window and the watermark.**
> A tumbling window groups events by event time into fixed 1-minute buckets. The watermark bounds how long we wait for late events; after it passes the window is finalized. This trades a little delay for correct late-data handling.

**Q4. How does VADER work?**
> A valence lexicon of ~7,500 words tuned for social media, plus rules: punctuation, capitalization, degree modifiers, negation, emoticons. Outputs a normalized compound score in [-1, 1]; |compound| ≤ 0.05 = neutral.

**Q5. Why three scorers?**
> VADER is transparent and fast; generic DistilBERT-SST2 shows the transformer baseline (binary, movie-review domain); our fine-tuned DistilBERT (3-class, 63.6k social-media rows, **84.2% validation accuracy**) shows what domain fine-tuning adds (+20 pts); cardiffnlp tweet-RoBERTa (trained on 124M tweets) is the authoritative live score.

**Q6. Your scorers disagree — is that a problem?**
> No — it's the finding. We quantify agreement percentages and surface LLM corrections of VADER on the Models tab. Disagreement ≠ error; it's the most interesting artifact for human inspection.

**Q7. How do you know the models are accurate?**
> The datasets ship ground-truth labels; we evaluate offline: accuracy, per-class precision/recall/F1, confusion matrices. Fine-tuned DistilBERT: 84.2% on held-out validation rows.

**Q8. Tell me about the fine-tuning.**
> `prepare_data.py` built train/val JSONL from the merged dataset (63,603 rows); `finetune.py` fine-tuned DistilBERT for 3 epochs with checkpoint auto-resume; weights are split into ≤90 MB parts + SHA256 for GitHub and rejoined at setup. 84.2% validation accuracy.

**Q9. Your pipeline does ~59 records/s. How did you get there?**
> Two findings: (1) Spark's JVM silently overrides `OMP_NUM_THREADS=1` inside python workers — torch ran single-threaded (~200s per 2k-row batch). Fix: set the env at module import, before torch loads. (2) Three streaming queries recomputed the whole graph 3× — collapsed into one checkpointed `foreachBatch`. Plus 256-char truncation and `inference_mode`. Together: ~9 → ~59 rec/s.

**Q10. How is fault tolerance handled?**
> Checkpoints store stream progress per sink — a restarted job resumes from offsets. Sinks are idempotent upserts keyed by `id`/`window_start`, so retries never duplicate rows. Model failures are caught and set null columns instead of killing the stream.

**Q11. How does per-account history work?**
> Every analyze endpoint records the analysis in a `history` table with the logged-in user's email (`user_email`), propagated automatically by the frontend. History/Analyze tabs read the DB — they survive API restarts — and 401 without a user. Guests are redirected to login.

**Q12. Why PostgreSQL and not NoSQL/HDFS?**
> Our access pattern is aggregate + recent-rows + per-account queries — a perfect fit for relational SQL with indexes. HDFS/Cassandra add operational complexity without benefit at this scale.

**Q13. What happens if the producer or API stops?**
> Nothing crashes — Spark waits (trigger-based), the dashboard keeps polling, the API serves the last known state from Postgres. Restart either and everything continues; history is DB-backed so nothing is lost.

**Q14. Why polling instead of WebSockets?**
> Windows aggregate per minute; 2.5–12 s polling per tab is stateless, trivially reliable, and simpler to defend. WebSockets would be the choice for sub-second push — noted as future work.

**Q15. What's bundled vs downloaded?**
> Everything is bundled: datasets (54 MB CSVs), fine-tuned weights (3 split parts), demo user seed. A fresh clone + one command runs the whole platform — no downloads, no extraction, no API keys.

**Q16. What would production look like?**
> Real platform APIs with rate limiting (X/Reddit currently bot-walled), Kafka multi-broker + replication, Spark cluster, Postgres read replicas, auth tokens with expiry, WebSocket push, model monitoring/retraining.

## 3. Screenshots to capture for the report
1. `docker compose ps` (infra up)
2. Spark streaming logs (throughput)
3. Postgres `window_stats` + `history` rows with `user_email`
4. FastAPI `/docs` (30+ endpoints)
5. Dashboard: overview + Go-live burst
6. Analyze: link analysis → scores
7. History: owner chips + kinds
8. Models: 3-way comparison
9. Jenkins: 5/5 green stages
10. Evaluation output (accuracy + confusion matrices)
