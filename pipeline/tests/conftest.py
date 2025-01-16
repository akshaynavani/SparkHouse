import os
import sys
from datetime import datetime

import pytest
from pyspark.sql import SparkSession

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sparkhouse.schema import RAW_EVENT_SCHEMA  # noqa: E402


@pytest.fixture(scope="session")
def spark():
    session = (
        SparkSession.builder.master("local[2]")
        .appName("sparkhouse-tests")
        .config("spark.sql.session.timeZone", "UTC")
        .config("spark.sql.shuffle.partitions", "4")
        .config("spark.ui.enabled", "false")
        .getOrCreate()
    )
    yield session
    session.stop()


def ts(s: str) -> datetime:
    return datetime.fromisoformat(s)


@pytest.fixture
def make_raw(spark):
    """Build a raw events DataFrame from compact tuples.

    (event_id, event_time, event_type, user_id, page, country_code, device, revenue[, ingest_time])
    """

    def _make(rows):
        full = []
        for r in rows:
            event_id, event_time, event_type, user_id, page, cc, device, revenue = r[:8]
            ingest = r[8] if len(r) > 8 else event_time
            full.append(
                (
                    event_id,
                    ts(event_time) if event_time else None,
                    ts(ingest) if ingest else None,
                    event_type,
                    user_id,
                    page,
                    "google",
                    cc,
                    device,
                    revenue,
                )
            )
        return spark.createDataFrame(full, RAW_EVENT_SCHEMA)

    return _make
