from sparkhouse.transform.clean import clean_events
from sparkhouse.transform.enrich import enrich_events


def test_geo_lookup_and_unknown_country(spark, make_raw):
    raw = make_raw(
        [
            ("e1", "2024-06-01 10:00:00", "click", 1, "/", "DE", "desktop", 0.0),
            ("e2", "2024-06-01 10:00:00", "click", 2, "/", "ZZ", "desktop", 0.0),
        ]
    )
    out = {r.event_id: r for r in enrich_events(clean_events(raw), spark).collect()}
    assert (out["e1"].country, out["e1"].region) == ("Germany", "Europe")
    assert (out["e2"].country, out["e2"].region) == ("Unknown", "Unknown")


def test_sessions_split_on_inactivity_gap(spark, make_raw):
    raw = make_raw(
        [
            ("a", "2024-06-01 10:00:00", "page_view", 7, "/", "US", "mobile", 0.0),
            ("b", "2024-06-01 10:20:00", "click", 7, "/", "US", "mobile", 0.0),
            ("c", "2024-06-01 10:45:00", "click", 7, "/", "US", "mobile", 0.0),
            ("d", "2024-06-01 11:30:00", "page_view", 7, "/", "US", "mobile", 0.0),
            ("x", "2024-06-01 10:10:00", "page_view", 8, "/", "US", "mobile", 0.0),
        ]
    )
    out = {r.event_id: r.session_id for r in enrich_events(clean_events(raw), spark, 30).collect()}
    assert out["a"] == out["b"] == out["c"]
    assert out["d"] != out["a"]
    assert out["x"] != out["a"]
    assert out["a"].startswith("7-")


def test_new_user_flag_from_signup(spark, make_raw):
    raw = make_raw(
        [
            ("s", "2024-06-01 09:00:00", "signup", 1, "/", "US", "mobile", 0.0),
            ("v", "2024-06-01 09:05:00", "page_view", 1, "/", "US", "mobile", 0.0),
            ("o", "2024-06-01 09:05:00", "page_view", 2, "/", "US", "mobile", 0.0),
        ]
    )
    out = {r.event_id: r.is_new_user for r in enrich_events(clean_events(raw), spark).collect()}
    assert out == {"s": 1, "v": 1, "o": 0}
