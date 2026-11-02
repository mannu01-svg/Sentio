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
# Spark's JVM overrides OMP_NUM_THREADS=1 in python workers (single-threaded
# inference, ~200s/batch). Export a custom var that survives and read it in
# nlp.warm() via torch.set_num_threads AFTER load (set_num_interop after init
# deadlocks forked workers, so only intraop is set).
export NLP_TORCH_THREADS="${NLP_TORCH_THREADS:-8}"

export PYTHONUNBUFFERED=1
export PYTHONFAULTHANDLER=1
exec "$ROOT/.venv/bin/python" -X faulthandler "$ROOT/spark/streaming_job.py"
