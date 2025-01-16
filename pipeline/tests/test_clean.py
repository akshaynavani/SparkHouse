from datetime import date

from sparkhouse.transform.clean import CleanOptions, clean_events


def test_normalizes_and_rejects_invalid_rows(make_raw):
    raw = make_raw(
        [
            ("e1", "2024-06-01 10:00:00", " PAGE_VIEW ", 1, "/", "us", "Mobile", 0.0),
            ("e2", "2024-06-01 10:01:00", "heartbeat", 1, "/", "US", "mobile", 0.0),
            ("e3", "2024-06-01 10:02:00", "click", None, "/", "US", "mobile", 0.0),
            ("e4", "2024-06-01 10:03:00", "purchase", 1, "/", "US", "mobile", -5.0),
            ("e5", "2024-06-01 10:04:00", "click", 1, "/", "US", "mobile", 12.0),
            ("e6", "2024-06-01 10:05:00", "purchase", 1, "/", "US", None, 19.99),
        ]
    )
    out = {r.event_id: r for r in clean_events(raw).collect()}
    assert set(out) == {"e1", "e6"}
    assert out["e1"].event_type == "page_view"
    assert out["e1"].device == "mobile"
    assert out["e1"].country_code == "US"
    assert out["e6"].device == "unknown"


def test_dedupes_keeping_earliest_ingest(make_raw):
    raw = make_raw(
        [
            ("dup", "2024-06-01 10:00:00", "click", 1, "/a", "US", "desktop", 0.0, "2024-06-01 10:05:00"),
            ("dup", "2024-06-01 10:00:00", "click", 1, "/b", "US", "desktop", 0.0, "2024-06-01 10:00:01"),
        ]
    )
    rows = clean_events(raw).collect()
    assert len(rows) == 1
    assert rows[0].page == "/b"


def test_drops_late_events_and_filters_dates(make_raw):
    raw = make_raw(
        [
            ("ok", "2024-06-01 10:00:00", "click", 1, "/", "US", "desktop", 0.0, "2024-06-02 09:00:00"),
            ("late", "2024-06-01 10:00:00", "click", 1, "/", "US", "desktop", 0.0, "2024-06-04 11:00:00"),
            ("outside", "2024-06-05 10:00:00", "click", 1, "/", "US", "desktop", 0.0),
        ]
    )
    opts = CleanOptions(start_date=date(2024, 6, 1), end_date=date(2024, 6, 2), max_lateness_hours=48)
    ids = {r.event_id for r in clean_events(raw, opts).collect()}
    assert ids == {"ok"}
