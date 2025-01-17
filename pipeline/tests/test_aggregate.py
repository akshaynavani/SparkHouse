from datetime import datetime

import pytest

from sparkhouse.transform.aggregate import (
    daily_users,
    funnel_daily,
    hourly_metrics,
    page_stats_daily,
)
from sparkhouse.transform.clean import clean_events
from sparkhouse.transform.enrich import enrich_events


@pytest.fixture
def events(spark, make_raw):
    raw = make_raw(
        [
            # user 1: full ordered funnel on mobile, US
            ("1a", "2024-06-01 10:00:00", "page_view", 1, "/product/101", "US", "mobile", 0.0),
            ("1b", "2024-06-01 10:01:00", "click", 1, "/product/101", "US", "mobile", 0.0),
            ("1c", "2024-06-01 10:02:00", "add_to_cart", 1, "/product/101", "US", "mobile", 0.0),
            ("1d", "2024-06-01 10:03:00", "purchase", 1, "/checkout", "US", "mobile", 50.0),
            # user 2: purchase *before* add_to_cart -> funnel depth stops at add_to_cart
            ("2a", "2024-06-01 10:00:00", "page_view", 2, "/", "US", "mobile", 0.0),
            ("2b", "2024-06-01 10:05:00", "click", 2, "/", "US", "mobile", 0.0),
            ("2c", "2024-06-01 10:06:00", "purchase", 2, "/checkout", "US", "mobile", 20.0),
            ("2d", "2024-06-01 10:07:00", "add_to_cart", 2, "/", "US", "mobile", 0.0),
            # user 3: only views, new user, next hour
            ("3s", "2024-06-01 11:00:00", "signup", 3, "/account", "US", "mobile", 0.0),
            ("3a", "2024-06-01 11:01:00", "page_view", 3, "/", "US", "mobile", 0.0),
        ]
    )
    return enrich_events(clean_events(raw), spark).cache()


def test_hourly_metrics(events):
    rows = {
        (r.event_hour, r.event_type): r
        for r in hourly_metrics(events).collect()
    }
    ten = datetime(2024, 6, 1, 10)
    assert rows[(ten, "page_view")].events == 2
    assert rows[(ten, "purchase")].revenue == pytest.approx(70.0)
    assert rows[(datetime(2024, 6, 1, 11), "signup")].events == 1


def test_daily_users(events):
    (row,) = daily_users(events).collect()
    assert row.active_users == 3
    assert row.new_users == 1
    assert row.sessions == 3


def test_ordered_funnel(events):
    steps = {r.step_name: r.users for r in funnel_daily(events).collect()}
    assert steps == {"page_view": 3, "click": 2, "add_to_cart": 2, "purchase": 1}


def test_page_stats(events):
    rows = {r.page: r for r in page_stats_daily(events).collect()}
    assert rows["/product/101"].views == 1
    assert rows["/product/101"].clicks == 1
    assert rows["/checkout"].purchases == 2
    assert rows["/checkout"].revenue == pytest.approx(70.0)
