#!/usr/bin/env python3
"""Spark Structured Streaming job.

Reads raw comment JSON events from Kafka (`comments-raw`), cleans and scores
them with VADER + DistilBERT (spark/nlp.py), aggregates 1-minute windows, and
writes:
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

Run:
    ./run_spark.sh
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
    return (
        SparkSession.builder.appName("social-media-sentiment")
        .master(os.getenv("SPARK_MASTER", "local[8]"))
        .config("spark.jars.packages", "org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.4")
        .config("spark.sql.shuffle.partitions", "4")
        .config("spark.driver.memory", "4g")
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
        nlp.warm()  # loads torch thread caps + both pipelines once per worker
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


def upsert_comments(batch_df, _batch_id: int) -> None:
    """Write one micro-batch of scored comments to PostgreSQL (idempotent upsert)."""
    rows = [
        (
            r["id"], r["source"], r["author"], r["text"], r["cleaned_text"], r["label"],
            r["vader_label"], r["vader_score"], r["vader_positive"], r["vader_negative"],
            r["vader_neutral"], r["bert_label"], r["bert_score"],
            r["llm_label"], r["llm_score"], r["event_ts"],
            r["post_id"], r["post_title"],
        )
        for r in batch_df.select(
            "id", "source", "author", "text", "cleaned_text", "label",
            "vader_label", "vader_score", "vader_positive", "vader_negative",
            "vader_neutral", "bert_label", "bert_score",
            "llm_label", "llm_score", "event_ts",
            "post_id", "post_title",
        ).collect()
    ]
    if not rows:
        return
    # defensive: a batch can contain the same id twice (producer replays);
    # ON CONFLICT cannot update the same row twice in one statement
    unique = {r[0]: r for r in reversed(rows)}
    rows = list(unique.values())
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
            rows,
        )


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


def write_batch(batch_df, _batch_id: int) -> None:
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
        "llm_label", "llm_score", "event_ts",
        "post_id", "post_title",
    ]
    pdf = batch_df.select(*cols).toPandas()
    if pdf.empty:
        return

    # 1. scored comments -> PostgreSQL (idempotent upsert)
    rows = [
        (
            r.id, r.source, r.author, r.text, r.cleaned_text, r.label,
            r.vader_label, r.vader_score, r.vader_positive, r.vader_negative,
            r.vader_neutral, r.bert_label, r.bert_score,
            r.llm_label, r.llm_score, r.event_ts, r.post_id, r.post_title,
        )
        for r in pdf.itertuples(index=False)
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
    feed = pdf.select(lambda c: c not in ("cleaned_text", "event_ts"), axis=1)
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

    # 3. 1-minute window aggregates, computed batch-locally (headline = LLM label)
    primary = pdf["llm_label"].fillna(pdf["vader_label"])
    work = pd.DataFrame({
        "event_ts": pd.to_datetime(pdf["event_ts"]),
        "pos": (primary == "positive").astype(int),
        "neg": (primary == "negative").astype(int),
        "neu": (primary == "neutral").astype(int),
        "score": pdf["llm_score"],
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
            float(r.pos_pct), float(r.neg_pct), float(r.neu_pct), float(r.avg_score),
        )
        for r in agg.itertuples(index=False)
    ]
    upsert_stats_rows(stat_rows)


def main() -> None:
    spark = build_spark()
    spark.sparkContext.setLogLevel("WARN")

    # 0. Fresh clone/first run: checkpoint state decides the offset start.
    #    No checkpoint = first run ever → start from EARLIEST so the seed pass
    #    published by the producer is never skipped (latest would drop it).
    first_run = not os.path.exists(os.path.join(CHECKPOINT, "pg-comments", "_metadata"))
    print("first run — startingOffsets: earliest" if first_run else "resuming from checkpoint offsets")

    # 1. Raw stream from Kafka
    raw = (
        spark.readStream.format("kafka")
        .option("kafka.bootstrap.servers", KAFKA_BOOTSTRAP)
        .option("subscribe", "comments-raw")
        .option("startingOffsets", "earliest" if first_run else "latest")
        .option("maxOffsetsPerTrigger", 8000)
        .option("failOnDataLoss", "false")
        .load()
    )

    # 2. Parse JSON + clean text + event timestamp (fall back to Kafka time)
    clean_udf = F.udf(nlp.clean_text, T.StringType())
    parsed = (
        raw.selectExpr("CAST(value AS STRING) AS json_str", "timestamp AS kafka_ts")
        .select(F.from_json("json_str", RAW_SCHEMA).alias("event"), "kafka_ts")
        .select("event.*", "kafka_ts")
        .withColumn("cleaned_text", clean_udf(F.coalesce(F.col("text"), F.lit(""))))
        .withColumn(
            "event_ts",
            F.coalesce(
                F.to_timestamp(F.substring("ts", 1, 19), "yyyy-MM-dd'T'HH:mm:ss"),
                F.col("kafka_ts"),
            ),
        )
    )

    # 3. VADER scoring (pandas UDF -> vectorized batches)
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

    # 4. DistilBERT + LLM scoring (skippable for quick smoke tests)
    if SKIP_BERT:
        scored = scored.withColumn("bert_label", F.lit(None).cast(T.StringType())) \
                       .withColumn("bert_score", F.lit(None).cast(T.DoubleType())) \
                       .withColumn("llm_label", F.lit(None).cast(T.StringType())) \
                       .withColumn("llm_score", F.lit(None).cast(T.DoubleType()))
    else:
        scored = scored.mapInPandas(bert_map, bert_full_schema(scored.schema))

    # 5. 1-minute window aggregates are computed inside write_batch (batch-local,
    #    no watermark/shuffle) — see write_batch below.

    # 6. ONE query, ONE trigger: the graph (kafka -> clean -> VADER -> BERT/LLM)
    #    is computed once per micro-batch and write_batch fans out to PostgreSQL,
    #    Kafka feed and window_stats. (Three separate writeStream queries would
    #    recompute the whole graph three times per batch.)
    print("Streaming: comments-raw -> [clean, VADER", "+ DistilBERT" if not SKIP_BERT else "", "]",
          "-> PostgreSQL + comments-scored (trigger=", TRIGGER_SECONDS, "s)")
    (
        scored.writeStream.foreachBatch(write_batch)
        .option("checkpointLocation", f"{CHECKPOINT}/pg-comments")
        .trigger(processingTime=f"{TRIGGER_SECONDS} seconds")
        .start()
    )
    spark.streams.awaitAnyTermination()


if __name__ == "__main__":
    main()
