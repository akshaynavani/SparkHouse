# SparkHouse — Implementation Plan

**Goal:** a batch analytics pipeline where Apache Spark transforms 100M+ raw product events into
aggregates stored in ClickHouse (columnar OLAP), served through a small SQL-backed query API to a
React dashboard with filters and drill-downs.

**Stack:** PySpark 3.5, ClickHouse 24.x (MergeTree family), FastAPI + clickhouse-connect (query API),
React 18 + TypeScript + Vite + Recharts (dashboard), Docker Compose for local infra, pytest.

## Key design decisions

- **Synthetic event source.** A deterministic generator (also runnable *inside* Spark for 100M+ rows)
  produces clickstream-like events (`page_view`, `click`, `add_to_cart`, `purchase`, `signup`) with
  users, sessions, countries, devices, and revenue. Raw data lands as date-partitioned Parquet.
- **Spark does the heavy lifting.** Cleaning (dedupe by `event_id`, schema validation, late-event
  filtering), enrichment (session derivation, country/region lookup broadcast join) and multi-grain
  aggregation (hourly event metrics, daily active users via HyperLogLog-style `approx_count_distinct`,
  funnel conversion, top pages).
- **ClickHouse stores both detail and aggregates.** A raw `events` MergeTree table (partitioned by
  month, ordered by `(event_type, event_date, user_id)`) for drill-down, plus pre-aggregated
  `SummingMergeTree` / `ReplacingMergeTree` tables for sub-second dashboard queries.
  Loads go through the ClickHouse JDBC driver with large batch sizes; each run is idempotent
  (partitions for the processed dates are dropped before insert).
- **Query API rather than browser→ClickHouse.** The dashboard never sends SQL. The API whitelists
  dimensions/metrics and binds filter values as server-side parameters, preventing injection.

## Phases

### Phase 1 — Infrastructure, schema, event generator
- `docker-compose.yml` (ClickHouse, Spark master/worker, API, dashboard)
- `clickhouse/init/001_schema.sql` — database, raw + aggregate tables
- `pipeline/sparkhouse/config.py`, `pipeline/sparkhouse/schema.py`
- `pipeline/sparkhouse/generate.py` — Spark-native synthetic generator (scales to 100M+)
- `pipeline/requirements.txt`, `.env.example`

### Phase 2 — Spark transformations
- `pipeline/sparkhouse/transform/clean.py` — validation, dedupe, late-event filter
- `pipeline/sparkhouse/transform/enrich.py` — sessionization, geo lookup
- `pipeline/sparkhouse/transform/aggregate.py` — hourly metrics, DAU, funnel, top pages
- `pipeline/sparkhouse/spark.py` — SparkSession factory

### Phase 3 — ClickHouse loading, job orchestration, pipeline tests
- `pipeline/sparkhouse/sink/clickhouse.py` — JDBC writer, idempotent partition replacement
- `pipeline/sparkhouse/jobs/run_pipeline.py` — CLI entrypoint (date range, input, sinks)
- `pipeline/tests/` — local-mode Spark tests for clean/enrich/aggregate
- `Makefile`

### Phase 4 — Query API
- `api/app/main.py`, `api/app/db.py`, `api/app/queries.py` (whitelisted query builder),
  `api/app/models.py`, `api/app/settings.py`
- Endpoints: `/api/filters`, `/api/overview`, `/api/timeseries`, `/api/breakdown`,
  `/api/funnel`, `/api/top-pages`, `/api/events` (drill-down)
- `api/tests/test_queries.py`, `api/Dockerfile`

### Phase 5 — React dashboard
- `dashboard/` Vite + TS app: filter bar (date range, country, device, event type),
  KPI cards, time-series chart, breakdown bars with click-to-drill, funnel, top pages,
  raw events drill-down table
- `dashboard/Dockerfile`, nginx proxy config

Afterwards: `.gitignore`, `README.md` with architecture diagram and run/test instructions.
