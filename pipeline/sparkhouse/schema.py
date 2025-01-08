"""Shared schemas and domain constants."""
from __future__ import annotations

from pyspark.sql.types import (
    DoubleType,
    LongType,
    StringType,
    StructField,
    StructType,
    TimestampType,
)

EVENT_TYPES = ("page_view", "click", "add_to_cart", "purchase", "signup")

# Ordered funnel steps used by the funnel aggregation.
FUNNEL_STEPS = ("page_view", "click", "add_to_cart", "purchase")

DEVICES = ("desktop", "mobile", "tablet")

PAGES = (
    "/", "/search", "/category/electronics", "/category/books", "/category/home",
    "/product/101", "/product/202", "/product/303", "/product/404", "/product/505",
    "/cart", "/checkout", "/account", "/blog", "/help",
)

REFERRERS = ("direct", "google", "bing", "facebook", "twitter", "newsletter", "affiliate")

# country code -> (country name, region). Broadcast-joined during enrichment.
GEO_LOOKUP = {
    "US": ("United States", "North America"),
    "CA": ("Canada", "North America"),
    "MX": ("Mexico", "North America"),
    "BR": ("Brazil", "South America"),
    "AR": ("Argentina", "South America"),
    "GB": ("United Kingdom", "Europe"),
    "DE": ("Germany", "Europe"),
    "FR": ("France", "Europe"),
    "ES": ("Spain", "Europe"),
    "IN": ("India", "Asia"),
    "JP": ("Japan", "Asia"),
    "SG": ("Singapore", "Asia"),
    "AU": ("Australia", "Oceania"),
    "ZA": ("South Africa", "Africa"),
    "NG": ("Nigeria", "Africa"),
}

UNKNOWN = "Unknown"

# Raw landing-zone schema. Raw data is untrusted: anything may be null or malformed.
RAW_EVENT_SCHEMA = StructType(
    [
        StructField("event_id", StringType(), True),
        StructField("event_time", TimestampType(), True),
        StructField("ingest_time", TimestampType(), True),
        StructField("event_type", StringType(), True),
        StructField("user_id", LongType(), True),
        StructField("page", StringType(), True),
        StructField("referrer", StringType(), True),
        StructField("country_code", StringType(), True),
        StructField("device", StringType(), True),
        StructField("revenue", DoubleType(), True),
    ]
)

# Column order of the ClickHouse `events` table.
EVENTS_TABLE_COLUMNS = (
    "event_id", "event_time", "event_date", "event_type", "user_id", "session_id",
    "page", "referrer", "country", "region", "device", "revenue", "is_new_user",
)
