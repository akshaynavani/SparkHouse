import { useMemo } from "react";
import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { fmtMetric } from "../format";
import type { Metric, Point } from "../types";

export const PALETTE = ["#4f46e5", "#0ea5e9", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6", "#14b8a6", "#ec4899"];

interface Props {
  points: Point[];
  metric: Metric;
  granularity: "hour" | "day";
}

/** Pivot long (bucket, series, value) rows into one object per bucket for Recharts. */
function pivot(points: Point[]): { rows: Record<string, number | string>[]; series: string[] } {
  const series = Array.from(new Set(points.map((p) => p.series)));
  const byBucket = new Map<string, Record<string, number | string>>();
  for (const p of points) {
    const row = byBucket.get(p.bucket) ?? { bucket: p.bucket };
    row[p.series] = p.value;
    byBucket.set(p.bucket, row);
  }
  return { rows: Array.from(byBucket.values()), series };
}

export function TimeSeriesChart({ points, metric, granularity }: Props) {
  const { rows, series } = useMemo(() => pivot(points), [points]);
  const tick = (v: string) => (granularity === "hour" ? v.slice(5, 16).replace("T", " ") : v.slice(5, 10));

  return (
    <ResponsiveContainer width="100%" height={300}>
      <LineChart data={rows} margin={{ top: 8, right: 16, bottom: 0, left: 8 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
        <XAxis dataKey="bucket" tickFormatter={tick} minTickGap={24} fontSize={12} />
        <YAxis tickFormatter={(v: number) => fmtMetric(metric, v)} fontSize={12} width={64} />
        <Tooltip formatter={(v: number) => fmtMetric(metric, v)} labelFormatter={(l: string) => l.replace("T", " ")} />
        {series.length > 1 && <Legend />}
        {series.map((s, i) => (
          <Line key={s} type="monotone" dataKey={s} stroke={PALETTE[i % PALETTE.length]} dot={false} strokeWidth={2} />
        ))}
      </LineChart>
    </ResponsiveContainer>
  );
}
