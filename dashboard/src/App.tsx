import { useEffect, useState } from "react";
import { api } from "./api";
import { BreakdownChart } from "./components/BreakdownChart";
import { EventsTable } from "./components/EventsTable";
import { FilterBar } from "./components/FilterBar";
import { FunnelChart } from "./components/FunnelChart";
import { KpiCards } from "./components/KpiCards";
import { Panel } from "./components/Panel";
import { TimeSeriesChart } from "./components/TimeSeriesChart";
import { TopPages } from "./components/TopPages";
import type { Dimension, Filters, Metric } from "./types";
import { useQuery } from "./useQuery";

const PAGE_SIZE = 50;

// Drill path: clicking a bar filters on it and moves one level down.
const DRILL: Record<Dimension, { filter: keyof Filters; next: Dimension }> = {
  region: { filter: "region", next: "country" },
  country: { filter: "country", next: "device" },
  device: { filter: "device", next: "event_type" },
  event_type: { filter: "eventType", next: "event_type" },
};

function isoDaysBefore(iso: string, days: number): string {
  const d = new Date(`${iso}T00:00:00Z`);
  d.setUTCDate(d.getUTCDate() - days);
  return d.toISOString().slice(0, 10);
}

const today = new Date().toISOString().slice(0, 10);

export default function App() {
  const [filters, setFilters] = useState<Filters>({
    startDate: isoDaysBefore(today, 29),
    endDate: today,
    country: [],
    region: [],
    device: [],
    eventType: [],
    page: [],
  });
  const [metric, setMetric] = useState<Metric>("events");
  const [granularity, setGranularity] = useState<"hour" | "day">("day");
  const [splitBy, setSplitBy] = useState<Dimension | "">("");
  const [dimension, setDimension] = useState<Dimension>("region");
  const [pageMetric, setPageMetric] = useState("views");
  const [userId, setUserId] = useState<number | undefined>();
  const [offset, setOffset] = useState(0);

  const options = useQuery("filters", (s) => api.filters(s));

  // Snap the default window to the data once we know its bounds.
  useEffect(() => {
    const max = options.data?.max_date;
    if (max) {
      const min = options.data?.min_date ?? max;
      const start = isoDaysBefore(max, 29);
      setFilters((f) => ({ ...f, endDate: max, startDate: start < min ? min : start }));
    }
  }, [options.data?.max_date, options.data?.min_date]);

  const fkey = JSON.stringify(filters);
  const overview = useQuery(`ov:${fkey}`, (s) => api.overview(filters, s));
  const series = useQuery(`ts:${fkey}:${metric}:${granularity}:${splitBy}`, (s) =>
    api.timeseries(filters, metric, granularity, splitBy || undefined, s),
  );
  const breakdown = useQuery(`bd:${fkey}:${dimension}:${metric}`, (s) => api.breakdown(filters, dimension, metric, s));
  const funnel = useQuery(`fn:${fkey}`, (s) => api.funnel(filters, s));
  const pages = useQuery(`pg:${fkey}:${pageMetric}`, (s) => api.topPages(filters, pageMetric, s));
  const events = useQuery(`ev:${fkey}:${userId}:${offset}`, (s) => api.events(filters, userId, offset, s));

  const updateFilters = (f: Filters) => {
    setFilters(f);
    setOffset(0);
  };

  const drill = (key: string) => {
    const { filter, next } = DRILL[dimension];
    const current = filters[filter] as string[];
    if (!current.includes(key)) updateFilters({ ...filters, [filter]: [...current, key] } as Filters);
    setDimension(next);
  };

  const selectPage = (page: string) => {
    updateFilters({ ...filters, page: [page] });
    document.getElementById("events")?.scrollIntoView({ behavior: "smooth" });
  };

  return (
    <div className="app">
      <header className="topbar">
        <h1>
          SparkHouse <span className="muted">clickstream analytics</span>
        </h1>
      </header>

      <FilterBar filters={filters} options={options.data} onChange={updateFilters} />

      <KpiCards data={overview.data} />
      {overview.error && <div className="error">{overview.error}</div>}

      <div className="grid">
        <Panel
          className="wide"
          title="Trend"
          loading={series.loading}
          error={series.error}
          actions={
            <>
              <select value={metric} onChange={(e) => setMetric(e.target.value as Metric)}>
                <option value="events">Events</option>
                <option value="sessions">Sessions</option>
                <option value="revenue">Revenue</option>
                <option value="users">Active users</option>
              </select>
              <select value={granularity} onChange={(e) => setGranularity(e.target.value as "hour" | "day")}>
                <option value="day">Daily</option>
                <option value="hour">Hourly</option>
              </select>
              <select value={splitBy} onChange={(e) => setSplitBy(e.target.value as Dimension | "")}>
                <option value="">No split</option>
                <option value="event_type">By event type</option>
                <option value="device">By device</option>
                <option value="region">By region</option>
              </select>
            </>
          }
        >
          <TimeSeriesChart points={series.data ?? []} metric={metric} granularity={granularity} />
        </Panel>

        <Panel
          title={`Breakdown by ${dimension.replace("_", " ")}`}
          loading={breakdown.loading}
          error={breakdown.error}
          actions={
            <select value={dimension} onChange={(e) => setDimension(e.target.value as Dimension)}>
              <option value="region">Region</option>
              <option value="country">Country</option>
              <option value="device">Device</option>
              <option value="event_type">Event type</option>
            </select>
          }
        >
          <p className="hint">Click a bar to filter and drill down.</p>
          <BreakdownChart rows={breakdown.data ?? []} metric={metric} onSelect={drill} />
        </Panel>

        <Panel title="Conversion funnel" loading={funnel.loading} error={funnel.error}>
          <FunnelChart steps={funnel.data ?? []} />
        </Panel>

        <Panel
          className="wide"
          title="Top pages"
          loading={pages.loading}
          error={pages.error}
          actions={
            <select value={pageMetric} onChange={(e) => setPageMetric(e.target.value)}>
              <option value="views">By views</option>
              <option value="clicks">By clicks</option>
              <option value="purchases">By purchases</option>
              <option value="revenue">By revenue</option>
            </select>
          }
        >
          <TopPages rows={pages.data ?? []} onSelect={selectPage} />
        </Panel>

        <div id="events" className="wide">
          <Panel title="Event drill-down" loading={events.loading} error={events.error}>
            <EventsTable
              rows={events.data?.rows ?? []}
              offset={offset}
              pageSize={PAGE_SIZE}
              userId={userId}
              onUser={(u) => {
                setUserId(u);
                setOffset(0);
              }}
              onPage={setOffset}
            />
          </Panel>
        </div>
      </div>
    </div>
  );
}
