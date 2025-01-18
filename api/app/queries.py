"""SQL builders for the dashboard.

The browser never sends SQL. Dimensions and metrics are looked up in whitelists, so only
known identifiers are interpolated into query text, and every user-supplied *value* is bound
with ClickHouse server-side parameters (``{name:Type}``). Each builder returns ``(sql, params)``
and is a pure function, which keeps it unit-testable without a database.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any

DB = "sparkhouse"

# Which filterable columns each table carries.
TABLE_DIMENSIONS: dict[str, set[str]] = {
    "events": {"country", "region", "device", "event_type", "page"},
    "hourly_metrics": {"country", "region", "device", "event_type"},
    "daily_users": {"country", "device"},
    "funnel_daily": {"country", "device"},
    "page_stats_daily": {"country", "device", "page"},
}

# Additive metrics served from pre-aggregated hourly_metrics.
HOURLY_METRICS = {
    "events": "sum(events)",
    "sessions": "sum(sessions)",
    "revenue": "round(sum(revenue), 2)",
}

# Distinct-count metrics must be computed from detail rows.
EVENT_METRICS = {
    "users": "uniq(user_id)",
    "sessions_exact": "uniqExact(session_id)",
}

BREAKDOWN_DIMENSIONS = ("country", "region", "device", "event_type")

PAGE_METRICS = {
    "views": "sum(views)",
    "clicks": "sum(clicks)",
    "purchases": "sum(purchases)",
    "revenue": "round(sum(revenue), 2)",
}

GRANULARITIES = {"hour": "event_hour", "day": "event_date"}


class QueryError(ValueError):
    """Raised for requests that name an unknown metric/dimension."""


@dataclass
class Filters:
    start_date: date
    end_date: date
    countries: list[str] = field(default_factory=list)
    regions: list[str] = field(default_factory=list)
    devices: list[str] = field(default_factory=list)
    event_types: list[str] = field(default_factory=list)
    pages: list[str] = field(default_factory=list)

    def where(self, table: str) -> tuple[str, dict[str, Any]]:
        """WHERE clause for ``table``; filters on columns the table lacks are ignored."""
        if self.end_date < self.start_date:
            raise QueryError("end_date must be on or after start_date")
        dims = TABLE_DIMENSIONS[table]
        clauses = ["event_date BETWEEN {start_date:Date} AND {end_date:Date}"]
        params: dict[str, Any] = {"start_date": self.start_date, "end_date": self.end_date}
        for column, values, param in (
            ("country", self.countries, "countries"),
            ("region", self.regions, "regions"),
            ("device", self.devices, "devices"),
            ("event_type", self.event_types, "event_types"),
            ("page", self.pages, "pages"),
        ):
            if values and column in dims:
                clauses.append(f"{column} IN {{{param}:Array(String)}}")
                params[param] = list(values)
        return " AND ".join(clauses), params


def _metric(name: str, table: dict[str, str]) -> str:
    try:
        return table[name]
    except KeyError as exc:
        raise QueryError(f"unknown metric '{name}'") from exc


def filter_options() -> list[tuple[str, str]]:
    """(key, sql) pairs for populating the filter bar."""
    return [
        ("countries", f"SELECT DISTINCT country AS v FROM {DB}.hourly_metrics ORDER BY v"),
        ("regions", f"SELECT DISTINCT region AS v FROM {DB}.hourly_metrics ORDER BY v"),
        ("devices", f"SELECT DISTINCT device AS v FROM {DB}.hourly_metrics ORDER BY v"),
        ("event_types", f"SELECT DISTINCT event_type AS v FROM {DB}.hourly_metrics ORDER BY v"),
    ]


def date_bounds() -> str:
    return f"SELECT min(event_date) AS min_date, max(event_date) AS max_date FROM {DB}.hourly_metrics"


def overview_aggregates(f: Filters) -> tuple[str, dict[str, Any]]:
    where, params = f.where("hourly_metrics")
    sql = f"""
        SELECT
            sum(events) AS events,
            sum(sessions) AS sessions,
            round(sum(revenue), 2) AS revenue,
            sumIf(events, event_type = 'purchase') AS purchases
        FROM {DB}.hourly_metrics
        WHERE {where}
    """
    return sql, params


def overview_users(f: Filters) -> tuple[str, dict[str, Any]]:
    where, params = f.where("events")
    sql = f"""
        SELECT
            uniq(user_id) AS users,
            uniqIf(user_id, event_type = 'purchase') AS purchasers,
            uniqIf(user_id, is_new_user = 1) AS new_users
        FROM {DB}.events
        WHERE {where}
    """
    return sql, params


def timeseries(
    f: Filters, metric: str = "events", granularity: str = "day", split_by: str | None = None
) -> tuple[str, dict[str, Any]]:
    if granularity not in GRANULARITIES:
        raise QueryError(f"unknown granularity '{granularity}'")
    if split_by is not None and split_by not in BREAKDOWN_DIMENSIONS:
        raise QueryError(f"cannot split by '{split_by}'")

    if metric in HOURLY_METRICS:
        table, expr = "hourly_metrics", HOURLY_METRICS[metric]
        bucket = GRANULARITIES[granularity]
    else:
        table, expr = "events", _metric(metric, EVENT_METRICS)
        bucket = "toStartOfHour(event_time)" if granularity == "hour" else "event_date"

    where, params = f.where(table)
    series = f"{split_by} AS series" if split_by else "'all' AS series"
    sql = f"""
        SELECT {bucket} AS bucket, {series}, {expr} AS value
        FROM {DB}.{table}
        WHERE {where}
        GROUP BY bucket, series
        ORDER BY bucket, series
    """
    return sql, params


def breakdown(f: Filters, dimension: str, metric: str = "events", limit: int = 20) -> tuple[str, dict[str, Any]]:
    if dimension not in BREAKDOWN_DIMENSIONS:
        raise QueryError(f"unknown dimension '{dimension}'")
    if metric in HOURLY_METRICS:
        table, expr = "hourly_metrics", HOURLY_METRICS[metric]
    else:
        table, expr = "events", _metric(metric, EVENT_METRICS)
    where, params = f.where(table)
    params["limit"] = int(limit)
    sql = f"""
        SELECT {dimension} AS key, {expr} AS value
        FROM {DB}.{table}
        WHERE {where}
        GROUP BY key
        ORDER BY value DESC
        LIMIT {{limit:UInt32}}
    """
    return sql, params


def funnel(f: Filters) -> tuple[str, dict[str, Any]]:
    where, params = f.where("funnel_daily")
    sql = f"""
        SELECT step, any(step_name) AS step_name, sum(users) AS users
        FROM {DB}.funnel_daily
        WHERE {where}
        GROUP BY step
        ORDER BY step
    """
    return sql, params


def top_pages(f: Filters, metric: str = "views", limit: int = 10) -> tuple[str, dict[str, Any]]:
    order_expr = _metric(metric, PAGE_METRICS)
    where, params = f.where("page_stats_daily")
    params["limit"] = int(limit)
    sql = f"""
        SELECT
            page,
            sum(views) AS views,
            sum(clicks) AS clicks,
            sum(purchases) AS purchases,
            round(sum(revenue), 2) AS revenue,
            {order_expr} AS sort_value
        FROM {DB}.page_stats_daily
        WHERE {where}
        GROUP BY page
        ORDER BY sort_value DESC
        LIMIT {{limit:UInt32}}
    """
    return sql, params


def drilldown_events(
    f: Filters, user_id: int | None = None, limit: int = 100, offset: int = 0
) -> tuple[str, dict[str, Any]]:
    where, params = f.where("events")
    if user_id is not None:
        where += " AND user_id = {user_id:UInt64}"
        params["user_id"] = int(user_id)
    params["limit"] = int(limit)
    params["offset"] = int(offset)
    sql = f"""
        SELECT event_id, event_time, event_type, user_id, session_id, page, referrer,
               country, region, device, revenue
        FROM {DB}.events
        WHERE {where}
        ORDER BY event_time DESC
        LIMIT {{limit:UInt32}} OFFSET {{offset:UInt32}}
    """
    return sql, params
