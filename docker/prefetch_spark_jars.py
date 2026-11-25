"""Build-time helper: resolve the Spark-Kafka connector (and its dependencies)
from Maven Central once and copy the jars to /opt/spark-jars, which
streaming_job.py loads via SPARK_EXTRA_JARS."""
import glob
import os
import shutil

from pyspark.sql import SparkSession

PKG = "org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.4"
spark = SparkSession.builder.master("local[1]").config("spark.jars.packages", PKG).getOrCreate()
spark.stop()
jars = glob.glob(os.path.expanduser("~/.ivy2/jars/*.jar"))
os.makedirs("/opt/spark-jars", exist_ok=True)
for jar in jars:
    shutil.copy(jar, "/opt/spark-jars")
print(f"copied {len(jars)} jars to /opt/spark-jars")
if not any("spark-sql-kafka" in j for j in jars):
    raise SystemExit("Kafka connector was not downloaded")
