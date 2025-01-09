"""SparkSession factory with settings tuned for wide batch aggregations."""
from __future__ import annotations

from pyspark.sql import SparkSession

from .config import PipelineConfig


def build_spark(app_name: str, config: PipelineConfig | None = None, with_jdbc: bool = False) -> SparkSession:
    config = config or PipelineConfig()
    builder = (
        SparkSession.builder.appName(app_name)
        .master(config.spark_master)
        .config("spark.sql.session.timeZone", "UTC")
        # Adaptive execution coalesces small shuffle partitions and handles skewed user keys.
        .config("spark.sql.adaptive.enabled", "true")
        .config("spark.sql.adaptive.coalescePartitions.enabled", "true")
        .config("spark.sql.adaptive.skewJoin.enabled", "true")
        .config("spark.sql.shuffle.partitions", "400")
        .config("spark.sql.parquet.compression.codec", "zstd")
        .config("spark.sql.sources.partitionOverwriteMode", "dynamic")
        .config("spark.serializer", "org.apache.spark.serializer.KryoSerializer")
    )
    if with_jdbc:
        builder = builder.config("spark.jars.packages", config.jdbc_package)
    return builder.getOrCreate()
