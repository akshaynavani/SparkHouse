import { fmtCurrency, fmtNumber, fmtPct } from "../format";
import type { Overview } from "../types";

export function KpiCards({ data }: { data: Overview | undefined }) {
  const cards = [
    { label: "Events", value: data ? fmtNumber(data.events) : "—" },
    { label: "Active users", value: data ? fmtNumber(data.users) : "—" },
    { label: "Sessions", value: data ? fmtNumber(data.sessions) : "—" },
    { label: "Revenue", value: data ? fmtCurrency(data.revenue) : "—" },
    { label: "Purchases", value: data ? fmtNumber(data.purchases) : "—" },
    { label: "Conversion", value: data ? fmtPct(data.conversion_rate) : "—" },
    { label: "New users", value: data ? fmtNumber(data.new_users) : "—" },
  ];
  return (
    <div className="kpis">
      {cards.map((c) => (
        <div key={c.label} className="kpi">
          <div className="kpi-label">{c.label}</div>
          <div className="kpi-value">{c.value}</div>
        </div>
      ))}
      {data && <div className="kpi-footnote">queried in {data.query_ms} ms</div>}
    </div>
  );
}
