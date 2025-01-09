"""Synthetic clickstream generator.

Runs entirely inside Spark (``spark.range`` + column expressions), so producing 100M+ events
is just a matter of cluster size -- nothing is materialised on the driver. A small fraction
of rows is deliberately corrupted (duplicates, nulls, bad event types, negative revenue,
late arrivals) so that the cleaning stage has realistic work to do.

Usage:
    python -m sparkhouse.generate --events 100000000 --start-date 2024-06-01 --days 30
"""
from __future__ import annotations

import argparse
from datetime import date, datetime, timezone

from pyspark.sql import Column, DataFrame, SparkSession
from pyspark.sql import functions as F

from .config import PipelineConfig
from .schema import DEVICES, GEO_LOOKUP, PAGES, REFERRERS
from .spark import build_spark


def _pick(values: tuple[str, ...], rnd: Column) -> Column:
    """Pick an element of ``values`` using a [0, 1) random column."""
    arr = F.array(*[F.lit(v) for v in values])
    idx = (F.floor(rnd * len(values)) + 1).cast("int")
    return F.element_at(arr, idx)


def _event_type(rnd: Column) -> Column:
    # Roughly realistic e-commerce mix.
    return (
        F.when(rnd < 0.55, "page_view")
        .when(rnd < 0.80, "click")
        .when(rnd < 0.92, "add_to_cart")
        .when(rnd < 0.97, "purchase")
        .otherwise("signup")
    )


def generate_events(
    spark: SparkSession,
    num_events: int,
    start_date: date,
    days: int,
    num_users: int,
    seed: int = 42,
    dirty_fraction: float = 0.01,
    num_partitions: int | None = None,
) -> DataFrame:
    """Return a DataFrame matching ``RAW_EVENT_SCHEMA`` with ``num_events`` (+ duplicates) rows."""
    epoch_start = int(datetime(start_date.year, start_date.month, start_date.day, tzinfo=timezone.utc).timestamp())
    span_seconds = days * 86_400
    partitions = num_partitions or max(8, num_events // 1_000_000)

    def r(k: int) -> Column:
        return F.rand(seed + k)

    countries = tuple(GEO_LOOKUP.keys())

    base = spark.range(0, num_events, numPartitions=partitions)

    # Diurnal shape: squash uniform seconds-of-day towards the afternoon with a sine bump.
    day_offset = F.floor(r(1) * days) * 86_400
    u = r(2)
    second_of_day = F.floor((u + 0.15 * F.sin(F.lit(2 * 3.14159265) * u)) * 86_399)
    second_of_day = F.greatest(F.lit(0), F.least(F.lit(86_399), second_of_day))
    event_epoch = F.lit(epoch_start) + day_offset + second_of_day

    # Mostly near-real-time ingestion, with a long tail of late arrivals (up to 72h).
    lateness = F.floor(F.pow(r(3), 12) * 72 * 3600) + F.floor(r(4) * 30)

    events = base.select(
        F.substring(F.sha2(F.concat_ws("-", F.lit(seed), F.col("id").cast("string")), 256), 1, 32).alias("event_id"),
        F.timestamp_seconds(event_epoch).alias("event_time"),
        F.timestamp_seconds(event_epoch + lateness).alias("ingest_time"),
        _event_type(r(5)).alias("event_type"),
        # Power-law-ish user activity: low ids are heavy users.
        (F.floor(F.pow(r(6), 2) * num_users) + 1).cast("long").alias("user_id"),
        _pick(PAGES, F.pow(r(7), 1.5)).alias("page"),
        _pick(REFERRERS, r(8)).alias("referrer"),
        _pick(countries, F.pow(r(9), 1.8)).alias("country_code"),
        _pick(DEVICES, F.pow(r(10), 1.3)).alias("device"),
        F.round(5 + F.pow(r(11), 2) * 495, 2).alias("revenue"),
        r(12).alias("_dirt"),
        r(13).alias("_dirt_kind"),
    ).withColumn(
        "revenue", F.when(F.col("event_type") == "purchase", F.col("revenue")).otherwise(F.lit(0.0))
    )

    # Inject dirty rows.
    dirty = F.col("_dirt") < dirty_fraction
    kind = F.col("_dirt_kind")
    events = (
        events.withColumn("user_id", F.when(dirty & (kind < 0.25), F.lit(None).cast("long")).otherwise(F.col("user_id")))
        .withColumn(
            "event_type",
            F.when(dirty & (kind >= 0.25) & (kind < 0.40), F.upper(F.concat(F.col("event_type"), F.lit(" "))))
            .when(dirty & (kind >= 0.40) & (kind < 0.50), F.lit("heartbeat"))
            .otherwise(F.col("event_type")),
        )
        .withColumn(
            "revenue",
            F.when(dirty & (kind >= 0.50) & (kind < 0.60) & (F.col("revenue") > 0), -F.col("revenue")).otherwise(
                F.col("revenue")
            ),
        )
        .withColumn("country_code", F.when(dirty & (kind >= 0.60) & (kind < 0.75), F.lit("ZZ")).otherwise(F.col("country_code")))
        .withColumn("device", F.when(dirty & (kind >= 0.75), F.lit(None).cast("string")).otherwise(F.col("device")))
    )

    # At-least-once delivery: ~0.5% of events are delivered twice.
    duplicates = events.sample(withReplacement=False, fraction=0.005, seed=seed + 99)
    events = events.unionByName(duplicates)

    return events.drop("_dirt", "_dirt_kind")


def write_raw(df: DataFrame, path: str) -> None:
    """Land raw events as Parquet partitioned by ingestion date (how a real landing zone looks)."""
    (
        df.withColumn("dt", F.to_date("ingest_time"))
        .write.mode("overwrite")
        .partitionBy("dt")
        .parquet(path)
    )


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Generate synthetic clickstream events")
    parser.add_argument("--events", type=int, default=10_000_000, help="number of events (default 10M)")
    parser.add_argument("--start-date", type=date.fromisoformat, default=date(2024, 6, 1))
    parser.add_argument("--days", type=int, default=30)
    parser.add_argument("--users", type=int, default=2_000_000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--dirty-fraction", type=float, default=0.01)
    parser.add_argument("--partitions", type=int, default=None)
    parser.add_argument("--output", default=None, help="output path (default <data_dir>/raw/events)")
    args = parser.parse_args(argv)

    config = PipelineConfig()
    spark = build_spark("sparkhouse-generate", config)
    df = generate_events(
        spark,
        num_events=args.events,
        start_date=args.start_date,
        days=args.days,
        num_users=args.users,
        seed=args.seed,
        dirty_fraction=args.dirty_fraction,
        num_partitions=args.partitions,
    )
    output = args.output or config.raw_dir
    write_raw(df, output)
    print(f"wrote ~{args.events:,} events to {output}")
    spark.stop()


if __name__ == "__main__":
    main()
