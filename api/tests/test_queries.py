from datetime import date

import pytest

from app import queries as q


def filters(**kw):
    return q.Filters(start_date=date(2024, 6, 1), end_date=date(2024, 6, 30), **kw)


def test_where_binds_values_as_parameters():
    f = filters(countries=["United States", "x'); DROP TABLE events; --"], devices=["mobile"])
    where, params = f.where("hourly_metrics")
    assert "country IN {countries:Array(String)}" in where
    assert "device IN {devices:Array(String)}" in where
    # Values never appear in SQL text.
    assert "DROP" not in where
    assert params["countries"][1].startswith("x')")


def test_where_ignores_columns_missing_from_table():
    where, params = filters(event_types=["click"], regions=["Europe"]).where("funnel_daily")
    assert "event_type" not in where
    assert "region" not in where
    assert set(params) == {"start_date", "end_date"}


def test_invalid_date_range():
    with pytest.raises(q.QueryError):
        q.Filters(start_date=date(2024, 6, 2), end_date=date(2024, 6, 1)).where("events")


def test_timeseries_routes_additive_metrics_to_hourly_table():
    sql, _ = q.timeseries(filters(), metric="revenue", granularity="hour")
    assert "sparkhouse.hourly_metrics" in sql
    assert "event_hour AS bucket" in sql


def test_timeseries_routes_distinct_metrics_to_events():
    sql, _ = q.timeseries(filters(), metric="users", granularity="day", split_by="device")
    assert "sparkhouse.events" in sql
    assert "uniq(user_id)" in sql
    assert "device AS series" in sql


@pytest.mark.parametrize(
    "call",
    [
        lambda: q.timeseries(filters(), metric="1; DROP TABLE x"),
        lambda: q.timeseries(filters(), granularity="minute"),
        lambda: q.timeseries(filters(), split_by="user_id"),
        lambda: q.breakdown(filters(), dimension="password"),
        lambda: q.top_pages(filters(), metric="sleep(10)"),
    ],
)
def test_rejects_unknown_identifiers(call):
    with pytest.raises(q.QueryError):
        call()


def test_breakdown_limit_is_parameterised():
    sql, params = q.breakdown(filters(), "country", "events", limit=5)
    assert "LIMIT {limit:UInt32}" in sql
    assert params["limit"] == 5


def test_drilldown_user_filter():
    sql, params = q.drilldown_events(filters(), user_id=42, limit=10, offset=20)
    assert "user_id = {user_id:UInt64}" in sql
    assert params["user_id"] == 42
    assert params["offset"] == 20
