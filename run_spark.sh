#!/usr/bin/env bash
# Launch the Spark Structured Streaming job with the local JDK on PATH.
set -e
cd "$(dirname "$0")/.."

export JAVA_HOME="${JAVA_HOME:-$HOME/.tools/jdk-17}"
export PATH="$JAVA_HOME/bin:$PATH"
# make spark/nlp.py importable on driver AND python workers
export PYTHONPATH="$HOME/Downloads/SocialMEdia/spark:${PYTHONPATH}"
# run python workers inside the project venv (has vaderSentiment, pyarrow, etc.)
export PYSPARK_PYTHON="$HOME/Downloads/SocialMEdia/.venv/bin/python"
export PYSPARK_DRIVER_PYTHON="$HOME/Downloads/SocialMEdia/.venv/bin/python"

exec "$HOME/Downloads/SocialMEdia/.venv/bin/python" "$HOME/Downloads/SocialMEdia/spark/streaming_job.py"
