"""ClickHouse connection handling."""
from __future__ import annotations

from functools import lru_cache
from typing import Any

import clickhouse_connect
from clickhouse_connect.driver.client import Client

from .settings import get_settings


@lru_cache
def get_client() -> Client:
    s = get_settings()
    return clickhouse_connect.get_client(
        host=s.clickhouse_host,
        port=s.clickhouse_port,
        database=s.clickhouse_db,
        username=s.clickhouse_user,
        password=s.clickhouse_password,
        settings={"max_execution_time": s.query_timeout_s, "readonly": 1},
    )


class QueryRunner:
    """Thin wrapper so endpoints can be tested with a fake runner."""

    def __init__(self, client: Client | None = None) -> None:
        self._client = client

    @property
    def client(self) -> Client:
        if self._client is None:
            self._client = get_client()
        return self._client

    def rows(self, sql: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        result = self.client.query(sql, parameters=params)
        return [dict(zip(result.column_names, row)) for row in result.result_rows]


def get_runner() -> QueryRunner:
    return QueryRunner()
