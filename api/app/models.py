from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel


class FilterOptions(BaseModel):
    countries: list[str]
    regions: list[str]
    devices: list[str]
    event_types: list[str]
    min_date: Optional[date]
    max_date: Optional[date]


class Overview(BaseModel):
    events: int
    sessions: int
    revenue: float
    purchases: int
    users: int
    purchasers: int
    new_users: int
    conversion_rate: float
    query_ms: float


class Point(BaseModel):
    bucket: datetime | date
    series: str
    value: float


class Breakdown(BaseModel):
    key: str
    value: float


class FunnelStep(BaseModel):
    step: int
    step_name: str
    users: int
    rate_from_start: float
    rate_from_previous: float


class PageStat(BaseModel):
    page: str
    views: int
    clicks: int
    purchases: int
    revenue: float
    ctr: float


class Event(BaseModel):
    event_id: str
    event_time: datetime
    event_type: str
    user_id: int
    session_id: str
    page: str
    referrer: str
    country: str
    region: str
    device: str
    revenue: float


class EventPage(BaseModel):
    rows: list[Event]
    limit: int
    offset: int
