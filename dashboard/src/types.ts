export interface Filters {
  startDate: string;
  endDate: string;
  country: string[];
  region: string[];
  device: string[];
  eventType: string[];
  page: string[];
}

export interface FilterOptions {
  countries: string[];
  regions: string[];
  devices: string[];
  event_types: string[];
  min_date: string | null;
  max_date: string | null;
}

export interface Overview {
  events: number;
  sessions: number;
  revenue: number;
  purchases: number;
  users: number;
  purchasers: number;
  new_users: number;
  conversion_rate: number;
  query_ms: number;
}

export interface Point {
  bucket: string;
  series: string;
  value: number;
}

export interface BreakdownRow {
  key: string;
  value: number;
}

export interface FunnelStep {
  step: number;
  step_name: string;
  users: number;
  rate_from_start: number;
  rate_from_previous: number;
}

export interface PageStat {
  page: string;
  views: number;
  clicks: number;
  purchases: number;
  revenue: number;
  ctr: number;
}

export interface EventRow {
  event_id: string;
  event_time: string;
  event_type: string;
  user_id: number;
  session_id: string;
  page: string;
  referrer: string;
  country: string;
  region: string;
  device: string;
  revenue: number;
}

export interface EventPage {
  rows: EventRow[];
  limit: number;
  offset: number;
}

export type Dimension = "region" | "country" | "device" | "event_type";
export type Metric = "events" | "sessions" | "revenue" | "users";
