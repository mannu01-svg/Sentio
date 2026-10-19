#!/usr/bin/env bash
# Launch the Spark Structured Streaming job with the local JDK on PATH.
set -e
cd "$(dirname "$0")"
ROOT="$(pwd)"

export JAVA_HOME="${JAVA_HOME:-$HOME/.tools/jdk-17}"
export PATH="$JAVA_HOME/bin:$PATH"
# make spark/nlp.py importable on driver AND python workers
export PYTHONPATH="$ROOT/spark:${PYTHONPATH}"
# run python workers inside the project venv (has vaderSentiment, pyarrow, transformers, etc.)
export PYSPARK_PYTHON="$ROOT/.venv/bin/python"
export PYSPARK_DRIVER_PYTHON="$ROOT/.venv/bin/python"

exec "$ROOT/.venv/bin/python" "$ROOT/spark/streaming_job.py"
