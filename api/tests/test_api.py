from datetime import date

from fastapi.testclient import TestClient

from app.db import get_runner
from app.main import app


class FakeRunner:
    def __init__(self):
        self.calls = []

    def rows(self, sql, params):
        self.calls.append((sql, params))
        if "funnel_daily" in sql:
            return [
                {"step": 1, "step_name": "page_view", "users": 1000},
                {"step": 2, "step_name": "click", "users": 500},
                {"step": 3, "step_name": "add_to_cart", "users": 100},
                {"step": 4, "step_name": "purchase", "users": 25},
            ]
        if "uniq(user_id) AS users" in sql:
            return [{"users": 200, "purchasers": 20, "new_users": 5}]
        if "sum(events) AS events" in sql:
            return [{"events": 5000, "sessions": 800, "revenue": 1234.5, "purchases": 30}]
        return []


def client():
    fake = FakeRunner()
    app.dependency_overrides[get_runner] = lambda: fake
    return TestClient(app), fake


def test_funnel_rates():
    c, _ = client()
    body = c.get("/api/funnel", params={"start_date": "2024-06-01", "end_date": "2024-06-30"}).json()
    assert [s["users"] for s in body] == [1000, 500, 100, 25]
    assert body[1]["rate_from_start"] == 0.5
    assert body[3]["rate_from_previous"] == 0.25


def test_overview_combines_aggregate_and_user_queries():
    c, fake = client()
    body = c.get("/api/overview", params={"start_date": "2024-06-01", "end_date": "2024-06-30"}).json()
    assert body["events"] == 5000
    assert body["conversion_rate"] == 0.1
    assert len(fake.calls) == 2


def test_comma_separated_filters_are_split():
    c, fake = client()
    c.get("/api/funnel", params={"start_date": "2024-06-01", "end_date": "2024-06-30", "country": "US,DE"})
    _, params = fake.calls[0]
    assert params["countries"] == ["US", "DE"]
    assert params["start_date"] == date(2024, 6, 1)


def test_bad_metric_is_400():
    c, _ = client()
    r = c.get("/api/breakdown", params={"dimension": "nope"})
    assert r.status_code == 400
