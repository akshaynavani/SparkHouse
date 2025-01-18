import type {
  BreakdownRow,
  Dimension,
  EventPage,
  FilterOptions,
  Filters,
  FunnelStep,
  Metric,
  Overview,
  PageStat,
  Point,
} from "./types";

const BASE = import.meta.env.VITE_API_BASE ?? "";

function filterParams(f: Filters): URLSearchParams {
  const p = new URLSearchParams({ start_date: f.startDate, end_date: f.endDate });
  f.country.forEach((v) => p.append("country", v));
  f.region.forEach((v) => p.append("region", v));
  f.device.forEach((v) => p.append("device", v));
  f.eventType.forEach((v) => p.append("event_type", v));
  f.page.forEach((v) => p.append("page", v));
  return p;
}

async function get<T>(path: string, params?: URLSearchParams, signal?: AbortSignal): Promise<T> {
  const url = `${BASE}${path}${params ? `?${params.toString()}` : ""}`;
  const res = await fetch(url, { signal });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(`${res.status} ${res.statusText}: ${detail}`);
  }
  return (await res.json()) as T;
}

function withExtra(f: Filters, extra: Record<string, string | number | undefined>): URLSearchParams {
  const p = filterParams(f);
  Object.entries(extra).forEach(([k, v]) => {
    if (v !== undefined && v !== "") p.set(k, String(v));
  });
  return p;
}

export const api = {
  filters: (signal?: AbortSignal) => get<FilterOptions>("/api/filters", undefined, signal),
  overview: (f: Filters, signal?: AbortSignal) => get<Overview>("/api/overview", filterParams(f), signal),
  timeseries: (f: Filters, metric: Metric, granularity: "hour" | "day", splitBy?: Dimension, signal?: AbortSignal) =>
    get<Point[]>("/api/timeseries", withExtra(f, { metric, granularity, split_by: splitBy }), signal),
  breakdown: (f: Filters, dimension: Dimension, metric: Metric, signal?: AbortSignal) =>
    get<BreakdownRow[]>("/api/breakdown", withExtra(f, { dimension, metric, limit: 15 }), signal),
  funnel: (f: Filters, signal?: AbortSignal) => get<FunnelStep[]>("/api/funnel", filterParams(f), signal),
  topPages: (f: Filters, metric: string, signal?: AbortSignal) =>
    get<PageStat[]>("/api/top-pages", withExtra(f, { metric, limit: 10 }), signal),
  events: (f: Filters, userId: number | undefined, offset: number, signal?: AbortSignal) =>
    get<EventPage>("/api/events", withExtra(f, { user_id: userId, limit: 50, offset }), signal),
};
