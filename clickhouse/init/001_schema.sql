-- SparkHouse ClickHouse schema.
-- Every table is partitioned by event_date so a pipeline run can atomically replace the
-- days it processed (ALTER TABLE ... DROP PARTITION) and stay idempotent.

CREATE DATABASE IF NOT EXISTS sparkhouse;

-- Cleaned + enriched event detail, used for drill-downs and exact distinct counts.
CREATE TABLE IF NOT EXISTS sparkhouse.events
(
    event_id     String,
    event_time   DateTime64(3, 'UTC'),
    event_date   Date,
    event_type   LowCardinality(String),
    user_id      UInt64,
    session_id   String,
    page         LowCardinality(String),
    referrer     LowCardinality(String),
    country      LowCardinality(String),
    region       LowCardinality(String),
    device       LowCardinality(String),
    revenue      Float64,
    is_new_user  UInt8
)
ENGINE = MergeTree
PARTITION BY event_date
ORDER BY (event_date, event_type, country, device, user_id)
SETTINGS index_granularity = 8192;

-- Skip index so drill-downs by a single user stay fast.
ALTER TABLE sparkhouse.events
    ADD INDEX IF NOT EXISTS idx_user user_id TYPE bloom_filter(0.01) GRANULARITY 4;

-- Hourly additive metrics per (type, geo, device). Summable, so SummingMergeTree collapses
-- duplicate keys during background merges.
CREATE TABLE IF NOT EXISTS sparkhouse.hourly_metrics
(
    event_date   Date,
    event_hour   DateTime('UTC'),
    event_type   LowCardinality(String),
    country      LowCardinality(String),
    region       LowCardinality(String),
    device       LowCardinality(String),
    events       UInt64,
    sessions     UInt64,
    revenue      Float64
)
ENGINE = SummingMergeTree((events, sessions, revenue))
PARTITION BY event_date
ORDER BY (event_date, event_hour, event_type, country, region, device);

-- Daily active / new users per (geo, device). Distinct counts are not additive across
-- groups, so the dashboard uses the raw events table when filters span multiple groups.
CREATE TABLE IF NOT EXISTS sparkhouse.daily_users
(
    event_date   Date,
    country      LowCardinality(String),
    device       LowCardinality(String),
    active_users UInt64,
    new_users    UInt64,
    sessions     UInt64
)
ENGINE = ReplacingMergeTree
PARTITION BY event_date
ORDER BY (event_date, country, device);

-- Per-day ordered funnel: users reaching each step (page_view -> click -> add_to_cart -> purchase).
CREATE TABLE IF NOT EXISTS sparkhouse.funnel_daily
(
    event_date   Date,
    country      LowCardinality(String),
    device       LowCardinality(String),
    step         UInt8,
    step_name    LowCardinality(String),
    users        UInt64
)
ENGINE = SummingMergeTree(users)
PARTITION BY event_date
ORDER BY (event_date, country, device, step, step_name);

-- Page-level engagement.
CREATE TABLE IF NOT EXISTS sparkhouse.page_stats_daily
(
    event_date   Date,
    page         LowCardinality(String),
    country      LowCardinality(String),
    device       LowCardinality(String),
    views        UInt64,
    clicks       UInt64,
    purchases    UInt64,
    revenue      Float64
)
ENGINE = SummingMergeTree((views, clicks, purchases, revenue))
PARTITION BY event_date
ORDER BY (event_date, page, country, device);

-- Audit trail of pipeline executions.
CREATE TABLE IF NOT EXISTS sparkhouse.pipeline_runs
(
    run_id        String,
    started_at    DateTime('UTC'),
    finished_at   DateTime('UTC'),
    start_date    Date,
    end_date      Date,
    input_rows    UInt64,
    clean_rows    UInt64,
    status        LowCardinality(String),
    message       String
)
ENGINE = MergeTree
ORDER BY (started_at, run_id);
