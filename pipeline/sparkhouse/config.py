"""Runtime configuration, read from environment variables (see .env.example)."""
from __future__ import annotations

import os
from dataclasses import dataclass, field


def _env(name: str, default: str) -> str:
    value = os.environ.get(name)
    return value if value not in (None, "") else default


@dataclass(frozen=True)
class ClickHouseConfig:
    host: str = field(default_factory=lambda: _env("CLICKHOUSE_HOST", "localhost"))
    port: int = field(default_factory=lambda: int(_env("CLICKHOUSE_PORT", "8123")))
    database: str = field(default_factory=lambda: _env("CLICKHOUSE_DB", "sparkhouse"))
    user: str = field(default_factory=lambda: _env("CLICKHOUSE_USER", "sparkhouse"))
    password: str = field(default_factory=lambda: _env("CLICKHOUSE_PASSWORD", ""))

    @property
    def jdbc_url(self) -> str:
        return f"jdbc:clickhouse://{self.host}:{self.port}/{self.database}"


@dataclass(frozen=True)
class PipelineConfig:
    spark_master: str = field(default_factory=lambda: _env("SPARK_MASTER", "local[*]"))
    data_dir: str = field(default_factory=lambda: _env("SPARKHOUSE_DATA_DIR", "./data"))
    jdbc_package: str = field(
        default_factory=lambda: _env("CLICKHOUSE_JDBC_PACKAGE", "com.clickhouse:clickhouse-jdbc:0.6.3")
    )
    # Inactivity gap that closes a session.
    session_gap_minutes: int = 30
    # Events arriving more than this many hours after they happened are dropped as late.
    max_lateness_hours: int = 48
    # Rows per JDBC batch when writing to ClickHouse; large batches suit columnar inserts.
    jdbc_batch_size: int = 200_000
    clickhouse: ClickHouseConfig = field(default_factory=ClickHouseConfig)

    @property
    def raw_dir(self) -> str:
        return os.path.join(self.data_dir, "raw", "events")

    @property
    def curated_dir(self) -> str:
        return os.path.join(self.data_dir, "curated")
