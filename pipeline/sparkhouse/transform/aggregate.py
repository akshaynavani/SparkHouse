"""Aggregation stage: one DataFrame per ClickHouse aggregate table."""
from __future__ import annotations

from pyspark.sql import DataFrame
from pyspark.sql import functions as F

from ..schema import FUNNEL_STEPS


def hourly_metrics(events: DataFrame) -> DataFrame:
    return (
        events.withColumn("event_hour", F.date_trunc("hour", F.col("event_time")))
        .groupBy("event_date", "event_hour", "event_type", "country", "region", "device")
        .agg(
            F.count(F.lit(1)).alias("events"),
            # Approximate distinct keeps this a single cheap pass at 100M+ rows (~2% error).
            F.approx_count_distinct("session_id", rsd=0.02).alias("sessions"),
            F.round(F.sum("revenue"), 2).alias("revenue"),
        )
    )


def daily_users(events: DataFrame) -> DataFrame:
    return events.groupBy("event_date", "country", "device").agg(
        F.countDistinct("user_id").alias("active_users"),
        F.countDistinct(F.when(F.col("is_new_user") == 1, F.col("user_id"))).alias("new_users"),
        F.countDistinct("session_id").alias("sessions"),
    )


def _funnel_depth(events: DataFrame) -> DataFrame:
    """Per (day, country, device, user): deepest funnel step reached *in order*.

    Events are sorted by time and folded with a higher-order ``aggregate``: the depth only
    advances when the next expected step is observed, so a purchase without a prior
    add_to_cart does not count as reaching the purchase step.
    """
    step_index = F.lit(0)
    for i, name in enumerate(FUNNEL_STEPS, start=1):
        step_index = F.when(F.col("event_type") == name, F.lit(i)).otherwise(step_index)

    per_user = (
        events.where(F.col("event_type").isin(*FUNNEL_STEPS))
        .withColumn("step_idx", step_index)
        .groupBy("event_date", "country", "device", "user_id")
        .agg(F.array_sort(F.collect_list(F.struct("event_time", "step_idx"))).alias("path"))
    )
    depth = F.aggregate(
        "path",
        F.lit(0),
        lambda acc, x: F.when(x["step_idx"] == acc + 1, acc + 1).otherwise(acc),
    )
    return per_user.select("event_date", "country", "device", depth.alias("depth"))


def funnel_daily(events: DataFrame) -> DataFrame:
    depths = _funnel_depth(events)
    sums = depths.groupBy("event_date", "country", "device").agg(
        *[
            F.sum(F.when(F.col("depth") >= i, 1).otherwise(0)).alias(f"s{i}")
            for i in range(1, len(FUNNEL_STEPS) + 1)
        ]
    )
    steps = F.array(
        *[
            F.struct(F.lit(i).alias("step"), F.lit(name).alias("step_name"), F.col(f"s{i}").alias("users"))
            for i, name in enumerate(FUNNEL_STEPS, start=1)
        ]
    )
    return (
        sums.select("event_date", "country", "device", F.explode(steps).alias("s"))
        .select(
            "event_date",
            "country",
            "device",
            F.col("s.step").alias("step"),
            F.col("s.step_name").alias("step_name"),
            F.col("s.users").cast("long").alias("users"),
        )
    )


def page_stats_daily(events: DataFrame) -> DataFrame:
    def count_of(event_type: str) -> F.Column:
        return F.sum(F.when(F.col("event_type") == event_type, 1).otherwise(0)).cast("long")

    return events.groupBy("event_date", "page", "country", "device").agg(
        count_of("page_view").alias("views"),
        count_of("click").alias("clicks"),
        count_of("purchase").alias("purchases"),
        F.round(F.sum("revenue"), 2).alias("revenue"),
    )


def build_aggregates(events: DataFrame) -> dict[str, DataFrame]:
    """Map ClickHouse table name -> aggregate DataFrame."""
    return {
        "hourly_metrics": hourly_metrics(events),
        "daily_users": daily_users(events),
        "funnel_daily": funnel_daily(events),
        "page_stats_daily": page_stats_daily(events),
    }
