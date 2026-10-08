#!/usr/bin/env python3
"""Spark Structured Streaming job.

Reads raw comment JSON events from Kafka (`comments-raw`), cleans and scores
them with VADER + DistilBERT (spark/nlp.py), aggregates 1-minute windows, and
writes:
  - scored comments -> Kafka topic `comments-scored` (live feed)
  - scored comments -> PostgreSQL table `comments`   (history/API, id-upsert)
  - window aggregates -> PostgreSQL table `window_stats` (charts/API, upsert)

Run:
    ./run_spark.sh
Env:
    SKIP_BERT=1   # smoke mode: skip DistilBERT (nulls), much lighter
"""

import os
import sys

import pandas as pd
import psycopg2
import psycopg2.extras

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

BERT_SCHEMA = T.StructType([
    T.StructField("bert_label", T.StringType()),
    T.StructField("bert_score", T.DoubleType()),
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
        .master(os.getenv("SPARK_MASTER", "local[*]"))
        .config("spark.jars.packages", "org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.4")
        .config("spark.sql.shuffle.partitions", "4")
        .config("spark.driver.memory", "2g")
        # mapInPandas: hand each worker >=256 rows so transformer batching pays off
        .config("spark.sql.execution.arrow.maxRecordsPerBatch", "256")
        .getOrCreate()
    )


def bert_map(iterator):
    """mapInPandas worker: add bert + llm columns via batched inference (4x faster)."""
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


def upsert_stats(batch_df, _batch_id: int) -> None:
    """Write/refresh window aggregates (a window can be updated by later batches)."""
    rows = [
        (
            r["window_start"], r["window_end"], r["total"], r["positive"],
            r["negative"], r["neutral"], r["pos_pct"], r["neg_pct"], r["neu_pct"],
            r["avg_score"],
        )
        for r in batch_df.collect()
    ]
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
                neg_pct = EXCLUDED.neg_pct,
                neu_pct = EXCLUDED.neu_pct,
                avg_score = EXCLUDED.avg_score,
                processed_at = NOW()
            """,
            rows,
        )


def main() -> None:
    spark = build_spark()
    spark.sparkContext.setLogLevel("WARN")

    # 1. Raw stream from Kafka
    raw = (
        spark.readStream.format("kafka")
        .option("kafka.bootstrap.servers", KAFKA_BOOTSTRAP)
        .option("subscribe", "comments-raw")
        .option("startingOffsets", "latest")
        .option("maxOffsetsPerTrigger", 2000)
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

    # 5. 1-minute tumbling window aggregates with 2-minute watermark
    #    headline sentiment = LLM label (falls back to VADER in SKIP_BERT fast mode)
    primary_label = F.coalesce(F.col("llm_label"), F.col("vader_label"))
    per_window = (
        scored.withWatermark("event_ts", "2 minutes")
        .groupBy(F.window("event_ts", f"{WINDOW_SECONDS} seconds"))
        .agg(
            F.count("*").alias("total"),
            F.sum(F.when(primary_label == "positive", 1).otherwise(0)).alias("positive"),
            F.sum(F.when(primary_label == "negative", 1).otherwise(0)).alias("negative"),
            F.sum(F.when(primary_label == "neutral", 1).otherwise(0)).alias("neutral"),
            F.avg("llm_score").alias("avg_score"),
        )
        .select(
            F.col("window.start").alias("window_start"),
            F.col("window.end").alias("window_end"),
            "total", "positive", "negative", "neutral",
            F.round(F.col("positive") * 100.0 / F.col("total"), 2).alias("pos_pct"),
            F.round(F.col("negative") * 100.0 / F.col("total"), 2).alias("neg_pct"),
            F.round(F.col("neutral") * 100.0 / F.col("total"), 2).alias("neu_pct"),
            F.round("avg_score", 4).alias("avg_score"),
        )
    )

    # 6a. Scored comments -> Kafka `comments-scored` (dashboard live feed)
    feed_query = (
        scored.select(
            F.to_json(
                F.struct(
                    "id", "source", "author", "text", "cleaned_text", "label",
                    "vader_label", "vader_score", "bert_label", "bert_score", "ts",
                    "post_id", "post_title",
                )
            ).alias("value")
        )
        .writeStream.format("kafka")
        .option("kafka.bootstrap.servers", KAFKA_BOOTSTRAP)
        .option("topic", "comments-scored")
        .option("checkpointLocation", f"{CHECKPOINT}/kafka-feed")
        .start()
    )

    # 6b. Scored comments -> PostgreSQL
    comments_query = (
        scored.writeStream.foreachBatch(upsert_comments)
        .option("checkpointLocation", f"{CHECKPOINT}/pg-comments")
        .start()
    )

    # 6c. Window stats -> PostgreSQL
    stats_query = (
        per_window.writeStream.foreachBatch(upsert_stats)
        .outputMode("update")
        .option("checkpointLocation", f"{CHECKPOINT}/pg-stats")
        .start()
    )

    print("Streaming: comments-raw -> [clean, VADER", "+ DistilBERT" if not SKIP_BERT else "", "]",
          "-> comments-scored / PostgreSQL")
    spark.streams.awaitAnyTermination()


if __name__ == "__main__":
    main()
