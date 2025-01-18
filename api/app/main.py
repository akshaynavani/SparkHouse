"""SparkHouse query API: read-only analytics endpoints over ClickHouse."""
from __future__ import annotations

import time
from datetime import date, timedelta
from typing import Annotated, Optional

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from . import queries as q
from .db import QueryRunner, get_runner
from .models import Breakdown, Event, EventPage, FilterOptions, FunnelStep, Overview, PageStat, Point
from .settings import get_settings

app = FastAPI(title="SparkHouse API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in get_settings().cors_origins.split(",") if o.strip()],
    allow_methods=["GET"],
    allow_headers=["*"],
)

Runner = Annotated[QueryRunner, Depends(get_runner)]


def _split(values: Optional[list[str]]) -> list[str]:
    """Accept both ?country=US&country=DE and ?country=US,DE."""
    out: list[str] = []
    for v in values or []:
        out.extend(p.strip() for p in v.split(",") if p.strip())
    return out


def get_filters(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    country: Annotated[Optional[list[str]], Query()] = None,
    region: Annotated[Optional[list[str]], Query()] = None,
    device: Annotated[Optional[list[str]], Query()] = None,
    event_type: Annotated[Optional[list[str]], Query()] = None,
    page: Annotated[Optional[list[str]], Query()] = None,
) -> q.Filters:
    end = end_date or date.today()
    start = start_date or end - timedelta(days=29)
    return q.Filters(
        start_date=start,
        end_date=end,
        countries=_split(country),
        regions=_split(region),
        devices=_split(device),
        event_types=_split(event_type),
        pages=_split(page),
    )


FiltersDep = Annotated[q.Filters, Depends(get_filters)]


def _run(runner: QueryRunner, built: tuple[str, dict]) -> list[dict]:
    sql, params = built
    return runner.rows(sql, params)


def _guard(fn):
    try:
        return fn()
    except q.QueryError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/health")
def health(runner: Runner) -> dict:
    runner.rows("SELECT 1 AS ok", {})
    return {"status": "ok"}


@app.get("/api/filters", response_model=FilterOptions)
def filters(runner: Runner) -> FilterOptions:
    options = {key: [r["v"] for r in runner.rows(sql, {})] for key, sql in q.filter_options()}
    bounds = runner.rows(q.date_bounds(), {})
    b = bounds[0] if bounds else {}
    return FilterOptions(**options, min_date=b.get("min_date"), max_date=b.get("max_date"))


@app.get("/api/overview", response_model=Overview)
def overview(f: FiltersDep, runner: Runner) -> Overview:
    t0 = time.perf_counter()
    agg = _guard(lambda: _run(runner, q.overview_aggregates(f)))[0]
    users = _guard(lambda: _run(runner, q.overview_users(f)))[0]
    elapsed = (time.perf_counter() - t0) * 1000
    total_users = int(users.get("users") or 0)
    purchasers = int(users.get("purchasers") or 0)
    return Overview(
        events=int(agg.get("events") or 0),
        sessions=int(agg.get("sessions") or 0),
        revenue=float(agg.get("revenue") or 0),
        purchases=int(agg.get("purchases") or 0),
        users=total_users,
        purchasers=purchasers,
        new_users=int(users.get("new_users") or 0),
        conversion_rate=round(purchasers / total_users, 4) if total_users else 0.0,
        query_ms=round(elapsed, 1),
    )


@app.get("/api/timeseries", response_model=list[Point])
def timeseries(
    f: FiltersDep,
    runner: Runner,
    metric: str = "events",
    granularity: str = "day",
    split_by: Optional[str] = None,
) -> list[Point]:
    rows = _guard(lambda: _run(runner, q.timeseries(f, metric, granularity, split_by)))
    return [Point(bucket=r["bucket"], series=str(r["series"]), value=float(r["value"] or 0)) for r in rows]


@app.get("/api/breakdown", response_model=list[Breakdown])
def breakdown(
    f: FiltersDep,
    runner: Runner,
    dimension: str = "country",
    metric: str = "events",
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> list[Breakdown]:
    rows = _guard(lambda: _run(runner, q.breakdown(f, dimension, metric, limit)))
    return [Breakdown(key=str(r["key"]), value=float(r["value"] or 0)) for r in rows]


@app.get("/api/funnel", response_model=list[FunnelStep])
def funnel(f: FiltersDep, runner: Runner) -> list[FunnelStep]:
    rows = _guard(lambda: _run(runner, q.funnel(f)))
    steps: list[FunnelStep] = []
    first = int(rows[0]["users"]) if rows else 0
    prev = first
    for r in rows:
        users = int(r["users"])
        steps.append(
            FunnelStep(
                step=int(r["step"]),
                step_name=r["step_name"],
                users=users,
                rate_from_start=round(users / first, 4) if first else 0.0,
                rate_from_previous=round(users / prev, 4) if prev else 0.0,
            )
        )
        prev = users
    return steps


@app.get("/api/top-pages", response_model=list[PageStat])
def top_pages(
    f: FiltersDep,
    runner: Runner,
    metric: str = "views",
    limit: Annotated[int, Query(ge=1, le=100)] = 10,
) -> list[PageStat]:
    rows = _guard(lambda: _run(runner, q.top_pages(f, metric, limit)))
    return [
        PageStat(
            page=r["page"],
            views=int(r["views"]),
            clicks=int(r["clicks"]),
            purchases=int(r["purchases"]),
            revenue=float(r["revenue"]),
            ctr=round(int(r["clicks"]) / int(r["views"]), 4) if int(r["views"]) else 0.0,
        )
        for r in rows
    ]


@app.get("/api/events", response_model=EventPage)
def events(
    f: FiltersDep,
    runner: Runner,
    user_id: Optional[int] = None,
    limit: Annotated[int, Query(ge=1)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> EventPage:
    limit = min(limit, get_settings().max_rows)
    rows = _guard(lambda: _run(runner, q.drilldown_events(f, user_id, limit, offset)))
    return EventPage(rows=[Event(**r) for r in rows], limit=limit, offset=offset)
