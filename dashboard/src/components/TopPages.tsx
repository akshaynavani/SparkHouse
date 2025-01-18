import { fmtCurrency, fmtNumber, fmtPct } from "../format";
import type { PageStat } from "../types";

interface Props {
  rows: PageStat[];
  onSelect: (page: string) => void;
}

export function TopPages({ rows, onSelect }: Props) {
  if (rows.length === 0) return <div className="empty">No page data.</div>;
  return (
    <table className="table">
      <thead>
        <tr>
          <th>Page</th>
          <th className="num">Views</th>
          <th className="num">Clicks</th>
          <th className="num">CTR</th>
          <th className="num">Purchases</th>
          <th className="num">Revenue</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((r) => (
          <tr key={r.page}>
            <td>
              <button className="link" onClick={() => onSelect(r.page)} title="Drill into events on this page">
                {r.page}
              </button>
            </td>
            <td className="num">{fmtNumber(r.views)}</td>
            <td className="num">{fmtNumber(r.clicks)}</td>
            <td className="num">{fmtPct(r.ctr)}</td>
            <td className="num">{fmtNumber(r.purchases)}</td>
            <td className="num">{fmtCurrency(r.revenue)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
