# One image for every Python service: Spark streaming job, FastAPI, producer, model init.
# Python 3.12 + Java 17 (PySpark 3.5.4 supports neither Python 3.13+ nor Java 21).
FROM python:3.12-slim-bookworm

RUN apt-get update \
 && apt-get install -y --no-install-recommends openjdk-17-jre-headless procps curl \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# CPU-only PyTorch first (the default wheel pulls ~3 GB of CUDA libraries)
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Download the Spark-Kafka connector once, at build time (no Maven access needed at runtime)
COPY docker/prefetch_spark_jars.py docker/
RUN python docker/prefetch_spark_jars.py && rm -rf /root/.ivy2

COPY . .

ENV PYTHONPATH=/app/spark:/app/fetcher \
    PYTHONUNBUFFERED=1 \
    PYSPARK_PYTHON=/usr/local/bin/python \
    PYSPARK_DRIVER_PYTHON=/usr/local/bin/python \
    SPARK_EXTRA_JARS=/opt/spark-jars \
    TZ=UTC

EXPOSE 8000
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
