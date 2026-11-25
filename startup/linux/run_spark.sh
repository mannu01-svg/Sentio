#!/usr/bin/env bash
# Launch the Spark Structured Streaming job with the local JDK on PATH.
set -e
# repo root: resolve from this script's location (works from linux/, mac/, or repo root)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
case "$(basename "$SCRIPT_DIR")" in
  # startup/<platform>/ -> repo root is two levels up
  linux|mac|windows) ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")" ;;
  startup)           ROOT="$(dirname "$SCRIPT_DIR")" ;;          # startup/ itself
  *)                 ROOT="$SCRIPT_DIR" ;;                       # repo root
esac
cd "$ROOT"

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
#
# auto-detect machine profile → Spark sizing. Any SPARK_MASTER /
# SPARK_DRIVER_MEMORY / NLP_TORCH_THREADS already set in the environment
# wins, so manual tuning still works.
CORES="$(nproc 2>/dev/null || echo 4)"
RAM_GB="$(free -g 2>/dev/null | awk '/^Mem:/{print $2}')"
RAM_GB="${RAM_GB:-0}"
if [ "$RAM_GB" -ge 24 ] && [ "$CORES" -ge 8 ]; then
  PROFILE="high";  _MASTER="local[6]"; _MEM=4g; _THREADS=8
elif [ "$RAM_GB" -ge 8 ]; then
  PROFILE="mid";   _MASTER="local[4]"; _MEM=2g; _THREADS=4
else
  PROFILE="low";   _MASTER="local[2]"; _MEM=1g; _THREADS=2
fi
export SPARK_MASTER="${SPARK_MASTER:-$_MASTER}"
export SPARK_DRIVER_MEMORY="${SPARK_DRIVER_MEMORY:-$_MEM}"
export NLP_TORCH_THREADS="${NLP_TORCH_THREADS:-$_THREADS}"
echo "▶ machine profile: ${PROFILE} (${CORES} cores, ${RAM_GB} GB RAM) → master=$SPARK_MASTER driver=$SPARK_DRIVER_MEMORY torch-threads=$NLP_TORCH_THREADS"

export PYTHONUNBUFFERED=1
export PYTHONFAULTHANDLER=1
exec "$ROOT/.venv/bin/python" -X faulthandler "$ROOT/spark/streaming_job.py"
