#!/usr/bin/env python3
"""Spark Structured Streaming job.

Reads raw comment JSON events from Kafka, cleans and scores them with VADER +
DistilBERT + RoBERTa (spark/nlp.py), aggregates 1-minute windows, and writes:
  - scored comments -> Kafka topic `comments-scored` (live feed)
  - scored comments -> PostgreSQL table `comments`   (history/API, id-upsert)
  - window aggregates -> PostgreSQL table `window_stats` (charts/API, upsert)

Throughput notes (why this looks the way it does):
  - the scored DataFrame is defined ONCE and shared by all three sinks. Spark
    recomputes each branch independently, but nlp.py keeps warm models in the
    worker processes, so re-scoring is ~2ms/row instead of ~7.5s/batch cold
    loads. A single-batch trigger keeps latency low without tiny-batch churn.
  - workers are forked per batch and re-import nlp; PYSPARK_SETUP_FUNC in
    nlp.py warms torch thread limits + model loads at fork time, so the
    expensive part is paid once per worker, not per row.

Two streaming queries share the same scoring graph:
  - `comments-raw`     seed + live replay stream (feeds the live dashboard)
  - `comments-analyze` comments from analyses users run (links, accounts,
                       topics, re-score). Its own query in its own FAIR
                       scheduler pool, so these are scored within seconds
                       instead of waiting behind thousands of replay comments.

Run:
    docker compose up -d spark      (or ./run_spark.sh outside Docker)
Env:
    SKIP_BERT=1   # smoke mode: skip DistilBERT (nulls), much lighter
"""

import os
import sys

import json

import pandas as pd
import psycopg2
import psycopg2.extras
from kafka import KafkaProducer

from pyspark.sql import SparkSession, functions as F, types as T

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nlp  # noqa: E402

KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP", "localhost:9092")
PG_DSN = os.getenv(
    "PG_DSN",
    "host=localhost port=5432 dbname=sentiment user=sentiment password=sentiment",
)
CHECKPOINT = os.getenv("CHECKPOINT_DIR", "checkpoints")
WINDOW_SECONDS = int(os.getenv("WINDOW_SECONDS", "60"))
SKIP_BERT = os.getenv("SKIP_BERT", "") == "1"
TRIGGER_SECONDS = os.getenv("TRIGGER_SECONDS", "10")
ANALYZE_TOPIC = os.getenv("KAFKA_ANALYZE_TOPIC", "comments-analyze")
ANALYZE_TRIGGER_SECONDS = os.getenv("ANALYZE_TRIGGER_SECONDS", "3")
# smaller replay batches finish sooner, so a busy CPU frees up between batches
MAX_OFFSETS_PER_TRIGGER = int(os.getenv("MAX_OFFSETS_PER_TRIGGER", "2000"))
# Docker image: the Kafka connector jars are pre-downloaded here at build time
EXTRA_JARS_DIR = os.getenv("SPARK_EXTRA_JARS", "")

RAW_SCHEMA = (
    T.StructType()
    .add("id", T.StringType())
    .add("source", T.StringType())
    .add("author", T.StringType())
    .add("text", T.StringType())
    .add("label", T.StringType())
    .add("ts", T.StringType())
    .add("post_id", T.StringType())
    .add("post_title", T.StringType())
)

VADER_SCHEMA = T.StructType([
    T.StructField("vader_label", T.StringType()),
    T.StructField("vader_score", T.DoubleType()),
    T.StructField("vader_positive", T.DoubleType()),
    T.StructField("vader_negative", T.DoubleType()),
    T.StructField("vader_neutral", T.DoubleType()),
])


def bert_full_schema(base_schema: T.StructType) -> T.StructType:
    """mapInPandas replaces the row, so its output schema must be input + new cols.

    Note: StructType.add() mutates in place, so build a fresh StructType
    instead of calling base_schema.add(...) — otherwise the input DataFrame's
    schema gains bert/llm columns that do not exist yet.
    """
    return T.StructType(list(base_schema.fields) + [
        T.StructField("bert_label", T.StringType()),
        T.StructField("bert_score", T.DoubleType()),
        T.StructField("llm_label", T.StringType()),
        T.StructField("llm_score", T.DoubleType()),
    ])


def build_spark() -> SparkSession:
    builder = SparkSession.builder.appName("social-media-sentiment").master(os.getenv("SPARK_MASTER", "local[6]"))
    jars = []
    if EXTRA_JARS_DIR and os.path.isdir(EXTRA_JARS_DIR):
        jars = [os.path.join(EXTRA_JARS_DIR, j) for j in sorted(os.listdir(EXTRA_JARS_DIR)) if j.endswith(".jar")]
    if jars:
        builder = builder.config("spark.jars", ",".join(jars))
    else:
        builder = builder.config("spark.jars.packages", "org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.4")
    return (
        builder
        .config("spark.scheduler.mode", "FAIR")   # analyze query gets its share even mid replay batch
        .config("spark.sql.shuffle.partitions", "4")
        # laptops: SPARK_DRIVER_MEMORY=2g SPARK_MASTER=local[4] if 16GB RAM
        .config("spark.driver.memory", os.getenv("SPARK_DRIVER_MEMORY", "4g"))
        # mapInPandas: hand each worker >=256 rows so transformer batching pays off
        .config("spark.sql.execution.arrow.maxRecordsPerBatch", "512")
        .config("spark.sql.execution.arrow.pyspark.enabled", "true")
        .getOrCreate()
    )


def bert_map(iterator):
    """mapInPandas worker: add bert + llm columns via batched inference.

    Models are warm in the worker process (nlp module-level preload on first
    import), so the first pdf pays nothing and later batches reuse them.
    """
    if not SKIP_BERT:
        try:
            nlp.warm()  # loads torch thread caps + both pipelines once per worker
        except Exception as exc:  # models not downloaded yet: keep scoring with VADER
            print(f"transformer models unavailable ({exc.__class__.__name__}); VADER-only for this batch")
    for pdf in iterator:
        if pdf.empty:
            yield pdf
            continue
        texts = pdf["cleaned_text"].fillna("").tolist()
        try:
            results = pd.DataFrame(nlp.bert_batch(texts))
            pdf = pd.concat([pdf.reset_index(drop=True), results], axis=1)
        except Exception:
            pdf["bert_label"] = None
            pdf["bert_score"] = None
        try:
            llm_results = pd.DataFrame(nlp.llm_batch(texts))
            pdf = pd.concat([pdf.reset_index(drop=True), llm_results], axis=1)
        except Exception:
            pdf["llm_label"] = None
            pdf["llm_score"] = None
        yield pdf


def upsert_stats_rows(rows: list[tuple]) -> None:
    """Write/refresh window aggregates (a window can be updated by later batches)."""
    if not rows:
        return
    with psycopg2.connect(PG_DSN) as conn, conn.cursor() as cur:
        psycopg2.extras.execute_values(
            cur,
            """
            INSERT INTO window_stats (window_start, window_end, total, positive,
                negative, neutral, pos_pct, neg_pct, neu_pct, avg_score)
            VALUES %s
            ON CONFLICT (window_start) DO UPDATE SET
                window_end = EXCLUDED.window_end,
                total = EXCLUDED.total,
                positive = EXCLUDED.positive,
                negative = EXCLUDED.negative,
                neutral = EXCLUDED.neutral,
                pos_pct = EXCLUDED.pos_pct,
                neu_pct = EXCLUDED.neu_pct,
                avg_score = EXCLUDED.avg_score,
                processed_at = NOW()
            """,
            rows,
        )


def write_batch(batch_df, _batch_id: int, windows: bool = True) -> None:
    """Single sink for the whole graph: writes scored comments to PostgreSQL,
    pushes them to Kafka `comments-scored`, and refreshes window aggregates.

    One foreachBatch = the expensive clean/VADER/BERT/LLM computation happens
    ONCE per micro-batch instead of three times (one per sink query), and the
    window aggregate is computed batch-locally (no watermark state, no shuffle).
    """
    cols = [
        "id", "source", "author", "text", "cleaned_text", "label",
        "vader_label", "vader_score", "vader_positive", "vader_negative",
        "vader_neutral", "bert_label", "bert_score",
        "llm_label", "llm_score", "event_ts", "ts",
        "post_id", "post_title",
    ]
    pdf = batch_df.select(*cols).toPandas()
    if pdf.empty:
        return
    # missing model scores arrive as NaN (fast mode / model unavailable): store them
    # as NULL - NaN in PostgreSQL makes the API's JSON responses fail (blank charts)
    pdf_db = pdf.astype(object).where(pd.notna(pdf), None)

    # 1. scored comments -> PostgreSQL (idempotent upsert)
    rows = [
        (
            r.id, r.source, r.author, r.text, r.cleaned_text, r.label,
            r.vader_label, r.vader_score, r.vader_positive, r.vader_negative,
            r.vader_neutral, r.bert_label, r.bert_score,
            r.llm_label, r.llm_score, r.ts, r.post_id, r.post_title,
        )
        for r in pdf_db.itertuples(index=False)
    ]
    # defensive: a batch can contain the same id twice (producer replays);
    # ON CONFLICT cannot update the same row twice in one statement
    unique = {r[0]: r for r in reversed(rows)}
    with psycopg2.connect(PG_DSN) as conn, conn.cursor() as cur:
        psycopg2.extras.execute_values(
            cur,
            """
            INSERT INTO comments (id, source, author, text, cleaned_text, label,
                vader_label, vader_score, vader_positive, vader_negative,
                vader_neutral, bert_label, bert_score, llm_label, llm_score,
                ts, post_id, post_title)
            VALUES %s
            ON CONFLICT (id) DO UPDATE SET
                vader_label = EXCLUDED.vader_label,
                vader_score = EXCLUDED.vader_score,
                vader_positive = EXCLUDED.vader_positive,
                vader_negative = EXCLUDED.vader_negative,
                vader_neutral = EXCLUDED.vader_neutral,
                bert_label = EXCLUDED.bert_label,
                bert_score = EXCLUDED.bert_score,
                llm_label = EXCLUDED.llm_label,
                llm_score = EXCLUDED.llm_score,
                processed_at = NOW()
            """,
            list(unique.values()),
        )

    # 2. scored comments -> Kafka `comments-scored` (dashboard live feed)
    feed = pdf_db.drop(columns=["cleaned_text", "event_ts"])
    producer = KafkaProducer(
        bootstrap_servers=KAFKA_BOOTSTRAP,
        value_serializer=lambda v: v.encode("utf-8"),
        linger_ms=50,
    )
    for rec in feed.to_dict(orient="records"):
        payload = {
            "id": rec["id"], "source": rec["source"], "author": rec["author"],
            "text": rec["text"], "label": rec["label"],
            "vader_label": rec["vader_label"], "vader_score": rec["vader_score"],
            "bert_label": rec["bert_label"], "bert_score": rec["bert_score"],
            "ts": rec["ts"], "post_id": rec["post_id"], "post_title": rec["post_title"],
        }
        producer.send("comments-scored", value=json.dumps(payload))
    producer.flush()
    producer.close()

    # analyses carry the platforms' own (often old) comment timestamps: they are
    # not part of the live stream, so they don't touch the live 1-minute windows
    if not windows:
        return

    # 3. 1-minute window aggregates, computed batch-locally (headline = LLM label)
    primary = pdf["llm_label"].fillna(pdf["vader_label"])
    work = pd.DataFrame({
        "event_ts": pd.to_datetime(pdf["event_ts"]),
        "pos": (primary == "positive").astype(int),
        "neg": (primary == "negative").astype(int),
        "neu": (primary == "neutral").astype(int),
        "score": pd.to_numeric(pdf["llm_score"], errors="coerce").fillna(pd.to_numeric(pdf["vader_score"], errors="coerce")),
    }).dropna(subset=["event_ts"])
    if work.empty:
        return
    work["window_start"] = work["event_ts"].dt.floor(f"{WINDOW_SECONDS}s")
    agg = work.groupby("window_start").agg(
        total=("pos", "size"),
        positive=("pos", "sum"),
        negative=("neg", "sum"),
        neutral=("neu", "sum"),
        avg_score=("score", "mean"),
    ).reset_index()
    agg["window_end"] = agg["window_start"] + pd.Timedelta(seconds=WINDOW_SECONDS)
    agg["pos_pct"] = (agg["positive"] * 100.0 / agg["total"]).round(2)
    agg["neg_pct"] = (agg["negative"] * 100.0 / agg["total"]).round(2)
    agg["neu_pct"] = (agg["neutral"] * 100.0 / agg["total"]).round(2)
    agg["avg_score"] = agg["avg_score"].round(4)
    stat_rows = [
        (
            r.window_start.to_pydatetime().replace(tzinfo=None),
            r.window_end.to_pydatetime().replace(tzinfo=None),
            int(r.total), int(r.positive), int(r.negative), int(r.neutral),
            float(r.pos_pct), float(r.neg_pct), float(r.neu_pct),
            None if pd.isna(r.avg_score) else float(r.avg_score),
        )
        for r in agg.itertuples(index=False)
    ]
    upsert_stats_rows(stat_rows)


def score(spark: SparkSession, topic: str, starting: str, max_offsets: int):
    """Kafka topic -> parsed JSON -> cleaned text -> VADER -> DistilBERT + RoBERTa."""
    raw = (
        spark.readStream.format("kafka")
        .option("kafka.bootstrap.servers", KAFKA_BOOTSTRAP)
        .option("subscribe", topic)
        .option("startingOffsets", starting)
        .option("maxOffsetsPerTrigger", max_offsets)
        .option("failOnDataLoss", "false")
        .load()
    )

    # Parse JSON + clean text + event timestamp (fall back to Kafka time)
    clean_udf = F.udf(nlp.clean_text, T.StringType())
    parsed = (
        raw.selectExpr("CAST(value AS STRING) AS json_str", "timestamp AS kafka_ts")
        .select(F.from_json("json_str", RAW_SCHEMA).alias("event"), "kafka_ts")
        .select("event.*", "kafka_ts")
        .where(F.col("id").isNotNull())
        .withColumn("cleaned_text", clean_udf(F.coalesce(F.col("text"), F.lit(""))))
        .withColumn(
            "event_ts",
            F.coalesce(
                F.to_timestamp(F.substring("ts", 1, 19), "yyyy-MM-dd'T'HH:mm:ss"),
                F.col("kafka_ts"),
            ),
        )
    )

    # VADER scoring (pandas UDF -> vectorized batches)
    @F.pandas_udf(VADER_SCHEMA, F.PandasUDFType.SCALAR)
    def vader_udf(texts: pd.Series) -> pd.DataFrame:
        return pd.DataFrame([nlp.vader_analyze(t or "") for t in texts])

    scored = parsed.withColumn("v", vader_udf("cleaned_text")).select(
        "*",
        F.col("v.vader_label").alias("vader_label"),
        F.col("v.vader_score").alias("vader_score"),
        F.col("v.vader_positive").alias("vader_positive"),
        F.col("v.vader_negative").alias("vader_negative"),
        F.col("v.vader_neutral").alias("vader_neutral"),
    ).drop("v")

    # DistilBERT + LLM scoring (skippable for quick smoke tests)
    if SKIP_BERT:
        return scored.withColumn("bert_label", F.lit(None).cast(T.StringType())) \
                     .withColumn("bert_score", F.lit(None).cast(T.DoubleType())) \
                     .withColumn("llm_label", F.lit(None).cast(T.StringType())) \
                     .withColumn("llm_score", F.lit(None).cast(T.DoubleType()))
    return scored.mapInPandas(bert_map, bert_full_schema(scored.schema))


def starting_offsets(name: str) -> str:
    """No checkpoint yet = first run: read from EARLIEST so nothing already
    published (seed pass, analyses made while Spark was starting) is skipped.
    With a checkpoint, Spark resumes from it and this value is ignored."""
    first_run = not os.path.exists(os.path.join(CHECKPOINT, name, "commits"))
    print(f"[{name}]", "first run - startingOffsets: earliest" if first_run else "resuming from checkpoint offsets")
    return "earliest"


def main() -> None:
    spark = build_spark()
    spark.sparkContext.setLogLevel("WARN")
    models = "VADER" if SKIP_BERT else "VADER + DistilBERT + RoBERTa"

    # Query 1: seed + live replay -> PostgreSQL, comments-scored feed, live windows
    spark.sparkContext.setLocalProperty("spark.scheduler.pool", "replay")
    print(f"Streaming: comments-raw -> [clean, {models}] -> PostgreSQL + comments-scored (trigger={TRIGGER_SECONDS}s)")
    (
        score(spark, "comments-raw", starting_offsets("pg-comments"), MAX_OFFSETS_PER_TRIGGER)
        .writeStream.foreachBatch(write_batch)
        .queryName("replay")
        .option("checkpointLocation", f"{CHECKPOINT}/pg-comments")
        .trigger(processingTime=f"{TRIGGER_SECONDS} seconds")
        .start()
    )

    # Query 2: user analyses -> scored straight away in their own pool
    spark.sparkContext.setLocalProperty("spark.scheduler.pool", "analyze")
    print(f"Streaming: {ANALYZE_TOPIC} -> [clean, {models}] -> PostgreSQL + comments-scored (trigger={ANALYZE_TRIGGER_SECONDS}s)")
    (
        score(spark, ANALYZE_TOPIC, starting_offsets("pg-analyze"), 1000)
        .writeStream.foreachBatch(lambda df, batch_id: write_batch(df, batch_id, windows=False))
        .queryName("analyze")
        .option("checkpointLocation", f"{CHECKPOINT}/pg-analyze")
        .trigger(processingTime=f"{ANALYZE_TRIGGER_SECONDS} seconds")
        .start()
    )
    spark.sparkContext.setLocalProperty("spark.scheduler.pool", None)
    spark.streams.awaitAnyTermination()


if __name__ == "__main__":
    main()
