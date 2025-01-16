"""ClickHouse sink.

Bulk data goes through Spark's JDBC writer (executors insert in parallel, large batches).
Control statements -- partition drops and the run audit row -- are issued from the driver over
ClickHouse's HTTP interface, which needs no extra dependencies.
"""
from __future__ import annotations

import base64
import json
import logging
import urllib.parse
import urllib.request
from datetime import date, timedelta
from typing import Iterable

from pyspark.sql import DataFrame

from ..config import ClickHouseConfig

log = logging.getLogger(__name__)

JDBC_DRIVER = "com.clickhouse.jdbc.ClickHouseDriver"


class ClickHouseHttp:
    """Minimal HTTP client for DDL/admin statements."""

    def __init__(self, config: ClickHouseConfig, timeout: float = 60.0) -> None:
        self.config = config
        self.timeout = timeout

    def _request(self, query: str, body: bytes | None = None) -> str:
        params = urllib.parse.urlencode({"database": self.config.database, "query": query})
        url = f"http://{self.config.host}:{self.config.port}/?{params}"
        token = base64.b64encode(f"{self.config.user}:{self.config.password}".encode()).decode()
        req = urllib.request.Request(url, data=body or b"", method="POST")
        req.add_header("Authorization", f"Basic {token}")
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:  # noqa: S310 - internal host
            return resp.read().decode()

    def execute(self, query: str) -> str:
        log.debug("clickhouse: %s", query)
        return self._request(query)

    def insert_json_rows(self, table: str, rows: Iterable[dict]) -> None:
        payload = "\n".join(json.dumps(r, default=str) for r in rows).encode()
        self._request(f"INSERT INTO {table} FORMAT JSONEachRow", payload)


def daterange(start: date, end: date) -> list[date]:
    return [start + timedelta(days=i) for i in range((end - start).days + 1)]


def drop_partitions(client: ClickHouseHttp, table: str, days: Iterable[date]) -> None:
    """Remove existing data for the given days so reruns replace rather than duplicate."""
    for day in days:
        client.execute(f"ALTER TABLE {table} DROP PARTITION '{day.isoformat()}'")


def write_table(
    df: DataFrame,
    table: str,
    config: ClickHouseConfig,
    batch_size: int = 200_000,
    writers: int = 8,
) -> None:
    """Append ``df`` to ``table`` over JDBC.

    ``writers`` bounds the number of concurrent insert streams: ClickHouse prefers fewer,
    larger inserts over many small ones (each insert creates a data part to merge later).
    """
    (
        df.repartition(writers, "event_date")
        .write.format("jdbc")
        .mode("append")
        .option("url", config.jdbc_url)
        .option("driver", JDBC_DRIVER)
        .option("dbtable", f"{config.database}.{table}")
        .option("user", config.user)
        .option("password", config.password)
        .option("batchsize", str(batch_size))
        .option("isolationLevel", "NONE")
        .option("numPartitions", str(writers))
        .save()
    )


def replace_days(
    tables: dict[str, DataFrame],
    start: date,
    end: date,
    config: ClickHouseConfig,
    batch_size: int = 200_000,
    writers: int = 8,
) -> None:
    """Idempotently load each table for the [start, end] window."""
    client = ClickHouseHttp(config)
    days = daterange(start, end)
    for table, df in tables.items():
        log.info("replacing %s for %s..%s", table, start, end)
        drop_partitions(client, f"{config.database}.{table}", days)
        write_table(df, table, config, batch_size=batch_size, writers=writers)
