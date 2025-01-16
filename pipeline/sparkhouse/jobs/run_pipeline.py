"""End-to-end batch job: raw Parquet -> clean -> enrich -> aggregate -> ClickHouse.

Usage:
    python -m sparkhouse.jobs.run_pipeline --start-date 2024-06-01 --end-date 2024-06-30
    spark-submit --packages com.clickhouse:clickhouse-jdbc:0.6.3 \
        pipeline/sparkhouse/jobs/run_pipeline.py --start-date ... --end-date ...
"""
from __future__ import annotations

import argparse
import logging
import math
import uuid
from datetime import date, datetime, timedelta, timezone

from pyspark import StorageLevel
from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F

from sparkhouse.config import PipelineConfig
from sparkhouse.sink.clickhouse import ClickHouseHttp, replace_days
from sparkhouse.spark import build_spark
from sparkhouse.transform.aggregate import build_aggregates
from sparkhouse.transform.clean import CleanOptions, clean_events
from sparkhouse.transform.enrich import enrich_events

log = logging.getLogger("sparkhouse.pipeline")


def read_raw(spark: SparkSession, path: str, start: date, end: date, max_lateness_hours: int) -> DataFrame:
    """Read only the ingestion-date partitions that can contain events for [start, end]."""
    last_ingest_day = end + timedelta(days=math.ceil(max_lateness_hours / 24))
    return (
        spark.read.parquet(path)
        .where((F.col("dt") >= F.lit(start)) & (F.col("dt") <= F.lit(last_ingest_day)))
        .drop("dt")
    )


def run(
    spark: SparkSession,
    config: PipelineConfig,
    start: date,
    end: date,
    input_path: str,
    load_clickhouse: bool = True,
    write_curated: bool = True,
    writers: int = 8,
) -> dict:
    started = datetime.now(timezone.utc)
    run_id = uuid.uuid4().hex

    raw = read_raw(spark, input_path, start, end, config.max_lateness_hours)
    input_rows = raw.count()

    cleaned = clean_events(raw, CleanOptions(start, end, config.max_lateness_hours))
    events = enrich_events(cleaned, spark, config.session_gap_minutes)
    # Enriched events feed five outputs; persist once instead of recomputing the window shuffles.
    events = events.persist(StorageLevel.MEMORY_AND_DISK)
    clean_rows = events.count()
    log.info("run %s: %d raw rows -> %d clean rows", run_id, input_rows, clean_rows)

    if write_curated:
        events.write.mode("overwrite").partitionBy("event_date").parquet(f"{config.curated_dir}/events")

    tables = {"events": events, **build_aggregates(events)}

    status, message = "success", ""
    try:
        if load_clickhouse:
            replace_days(
                tables, start, end, config.clickhouse, batch_size=config.jdbc_batch_size, writers=writers
            )
    except Exception as exc:  # record the failure, then re-raise
        status, message = "failed", str(exc)[:2000]
        raise
    finally:
        summary = {
            "run_id": run_id,
            "started_at": started.strftime("%Y-%m-%d %H:%M:%S"),
            "finished_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "input_rows": input_rows,
            "clean_rows": clean_rows,
            "status": status,
            "message": message,
        }
        if load_clickhouse:
            try:
                ClickHouseHttp(config.clickhouse).insert_json_rows(
                    f"{config.clickhouse.database}.pipeline_runs", [summary]
                )
            except Exception:  # audit logging must never mask the real error
                log.exception("failed to record pipeline run")
        events.unpersist()

    return summary


def main(argv: list[str] | None = None) -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    parser = argparse.ArgumentParser(description="Run the SparkHouse batch pipeline")
    parser.add_argument("--start-date", type=date.fromisoformat, required=True)
    parser.add_argument("--end-date", type=date.fromisoformat, required=True)
    parser.add_argument("--input", default=None, help="raw events path (default <data_dir>/raw/events)")
    parser.add_argument("--writers", type=int, default=8, help="concurrent ClickHouse insert streams")
    parser.add_argument("--no-clickhouse", action="store_true", help="skip loading into ClickHouse")
    parser.add_argument("--no-curated", action="store_true", help="skip writing curated Parquet")
    args = parser.parse_args(argv)

    if args.end_date < args.start_date:
        parser.error("--end-date must be on or after --start-date")

    config = PipelineConfig()
    spark = build_spark("sparkhouse-pipeline", config, with_jdbc=not args.no_clickhouse)
    try:
        summary = run(
            spark,
            config,
            args.start_date,
            args.end_date,
            args.input or config.raw_dir,
            load_clickhouse=not args.no_clickhouse,
            write_curated=not args.no_curated,
            writers=args.writers,
        )
        log.info("pipeline finished: %s", summary)
    finally:
        spark.stop()


if __name__ == "__main__":
    main()
