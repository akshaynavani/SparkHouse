"""Enrichment stage: geo lookup and sessionisation."""
from __future__ import annotations

from pyspark.sql import DataFrame, SparkSession, Window
from pyspark.sql import functions as F

from ..schema import GEO_LOOKUP, UNKNOWN


def geo_dimension(spark: SparkSession) -> DataFrame:
    rows = [(code, name, region) for code, (name, region) in GEO_LOOKUP.items()]
    return spark.createDataFrame(rows, "country_code string, country string, region string")


def add_geo(df: DataFrame, geo: DataFrame) -> DataFrame:
    """Broadcast-join the tiny geo dimension; unknown codes map to 'Unknown'."""
    return (
        df.join(F.broadcast(geo), on="country_code", how="left")
        .withColumn("country", F.coalesce(F.col("country"), F.lit(UNKNOWN)))
        .withColumn("region", F.coalesce(F.col("region"), F.lit(UNKNOWN)))
    )


def sessionize(df: DataFrame, gap_minutes: int = 30) -> DataFrame:
    """Derive ``session_id`` from per-user inactivity gaps.

    A new session starts when a user's previous event is more than ``gap_minutes`` earlier.
    The session id is ``<user_id>-<epoch seconds of the session's first event>``, which is
    stable across reruns over the same data.
    """
    by_user = Window.partitionBy("user_id").orderBy("event_time", "event_id")
    ts = F.col("event_time").cast("long")
    prev_ts = F.lag(ts).over(by_user)
    is_new = F.when(prev_ts.isNull() | ((ts - prev_ts) > gap_minutes * 60), 1).otherwise(0)

    df = df.withColumn("_new_session", is_new)
    df = df.withColumn(
        "_session_start",
        F.max(F.when(F.col("_new_session") == 1, ts)).over(
            by_user.rowsBetween(Window.unboundedPreceding, Window.currentRow)
        ),
    )
    return df.withColumn(
        "session_id", F.concat_ws("-", F.col("user_id").cast("string"), F.col("_session_start").cast("string"))
    ).drop("_new_session", "_session_start")


def flag_new_users(df: DataFrame) -> DataFrame:
    """A user is 'new' on a day if they signed up that day."""
    signups = (
        df.where(F.col("event_type") == "signup")
        .select("user_id", "event_date")
        .distinct()
        .withColumn("is_new_user", F.lit(1))
    )
    return (
        df.join(signups, on=["user_id", "event_date"], how="left")
        .withColumn("is_new_user", F.coalesce(F.col("is_new_user"), F.lit(0)).cast("int"))
    )


def enrich_events(df: DataFrame, spark: SparkSession, session_gap_minutes: int = 30) -> DataFrame:
    df = add_geo(df, geo_dimension(spark))
    df = sessionize(df, session_gap_minutes)
    df = flag_new_users(df)
    return df.select(
        "event_id",
        "event_time",
        "event_date",
        "event_type",
        "user_id",
        "session_id",
        "page",
        "referrer",
        "country",
        "region",
        "device",
        "revenue",
        "is_new_user",
    )
