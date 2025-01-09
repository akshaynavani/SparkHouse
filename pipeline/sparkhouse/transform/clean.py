"""Cleaning stage: normalise, validate, dedupe and drop late events."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from pyspark.sql import DataFrame, Window
from pyspark.sql import functions as F

from ..schema import DEVICES, EVENT_TYPES, UNKNOWN


@dataclass(frozen=True)
class CleanOptions:
    start_date: date | None = None  # inclusive, by event date
    end_date: date | None = None  # inclusive, by event date
    max_lateness_hours: int = 48


def normalize(df: DataFrame) -> DataFrame:
    """Trim/lower-case categorical fields and fill harmless gaps."""
    return (
        df.withColumn("event_type", F.lower(F.trim(F.col("event_type"))))
        .withColumn("device", F.lower(F.trim(F.col("device"))))
        .withColumn(
            "device",
            F.when(F.col("device").isin(*DEVICES), F.col("device")).otherwise(F.lit(UNKNOWN.lower())),
        )
        .withColumn("country_code", F.upper(F.trim(F.col("country_code"))))
        .withColumn("page", F.coalesce(F.col("page"), F.lit("/")))
        .withColumn("referrer", F.coalesce(F.lower(F.col("referrer")), F.lit("direct")))
        .withColumn("revenue", F.coalesce(F.col("revenue"), F.lit(0.0)))
    )


def validate(df: DataFrame) -> DataFrame:
    """Keep only rows that satisfy the event contract."""
    return df.where(
        F.col("event_id").isNotNull()
        & F.col("event_time").isNotNull()
        & F.col("user_id").isNotNull()
        & (F.col("user_id") > 0)
        & F.col("event_type").isin(*EVENT_TYPES)
        & (F.col("revenue") >= 0)
        # Revenue only makes sense on purchases.
        & ((F.col("event_type") == "purchase") | (F.col("revenue") == 0))
    )


def drop_late(df: DataFrame, max_lateness_hours: int) -> DataFrame:
    """Drop events ingested too long after they occurred (or with clocks in the future)."""
    if "ingest_time" not in df.columns:
        return df
    lateness_s = F.col("ingest_time").cast("long") - F.col("event_time").cast("long")
    return df.where(
        F.col("ingest_time").isNull()
        | ((lateness_s >= -300) & (lateness_s <= max_lateness_hours * 3600))
    )


def dedupe(df: DataFrame) -> DataFrame:
    """At-least-once delivery means repeats of an event_id; keep the earliest ingested copy."""
    order_col = F.col("ingest_time").asc_nulls_last() if "ingest_time" in df.columns else F.col("event_time").asc()
    w = Window.partitionBy("event_id").orderBy(order_col)
    return df.withColumn("_rn", F.row_number().over(w)).where(F.col("_rn") == 1).drop("_rn")


def filter_dates(df: DataFrame, start: date | None, end: date | None) -> DataFrame:
    df = df.withColumn("event_date", F.to_date("event_time"))
    if start is not None:
        df = df.where(F.col("event_date") >= F.lit(start))
    if end is not None:
        df = df.where(F.col("event_date") <= F.lit(end))
    return df


def clean_events(raw: DataFrame, options: CleanOptions | None = None) -> DataFrame:
    """Full cleaning stage. Output adds ``event_date`` and keeps the raw columns."""
    options = options or CleanOptions()
    df = normalize(raw)
    df = validate(df)
    df = drop_late(df, options.max_lateness_hours)
    df = filter_dates(df, options.start_date, options.end_date)
    return dedupe(df)
