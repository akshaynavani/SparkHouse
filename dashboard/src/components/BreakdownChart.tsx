import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { fmtMetric } from "../format";
import type { BreakdownRow, Metric } from "../types";
import { PALETTE } from "./TimeSeriesChart";

interface Props {
  rows: BreakdownRow[];
  metric: Metric;
  onSelect: (key: string) => void;
}

/** Horizontal bars; clicking a bar drills into that value. */
export function BreakdownChart({ rows, metric, onSelect }: Props) {
  return (
    <ResponsiveContainer width="100%" height={Math.max(160, rows.length * 28 + 24)}>
      <BarChart data={rows} layout="vertical" margin={{ top: 4, right: 16, bottom: 4, left: 8 }}>
        <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="#e5e7eb" />
        <XAxis type="number" tickFormatter={(v: number) => fmtMetric(metric, v)} fontSize={12} />
        <YAxis type="category" dataKey="key" width={120} fontSize={12} />
        <Tooltip formatter={(v: number) => fmtMetric(metric, v)} cursor={{ fill: "#f3f4f6" }} />
        <Bar dataKey="value" radius={[0, 4, 4, 0]} onClick={(d: { key?: string }) => d.key && onSelect(d.key)} cursor="pointer">
          {rows.map((r, i) => (
            <Cell key={r.key} fill={PALETTE[i % PALETTE.length]} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
