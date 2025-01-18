import { fmtNumber, fmtPct } from "../format";
import type { FunnelStep } from "../types";

export function FunnelChart({ steps }: { steps: FunnelStep[] }) {
  if (steps.length === 0) return <div className="empty">No funnel data for this selection.</div>;
  return (
    <ol className="funnel">
      {steps.map((s) => (
        <li key={s.step}>
          <div className="funnel-label">
            <span>{s.step_name.replace(/_/g, " ")}</span>
            <span>
              {fmtNumber(s.users)} · {fmtPct(s.rate_from_start)}
            </span>
          </div>
          <div className="funnel-track">
            <div className="funnel-bar" style={{ width: `${Math.max(1, s.rate_from_start * 100)}%` }} />
          </div>
          {s.step > 1 && <div className="funnel-step-rate">{fmtPct(s.rate_from_previous)} from previous step</div>}
        </li>
      ))}
    </ol>
  );
}
