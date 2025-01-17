from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    clickhouse_host: str = "localhost"
    clickhouse_port: int = 8123
    clickhouse_db: str = "sparkhouse"
    clickhouse_user: str = "sparkhouse"
    clickhouse_password: str = ""
    # Hard cap on rows returned by drill-down endpoints.
    max_rows: int = 1000
    # Per-query execution limit enforced by ClickHouse.
    query_timeout_s: int = 15
    cors_origins: str = "http://localhost:5173,http://localhost:3000"


@lru_cache
def get_settings() -> Settings:
    return Settings()
