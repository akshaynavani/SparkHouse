import type { EventRow } from "../types";

interface Props {
  rows: EventRow[];
  offset: number;
  pageSize: number;
  userId: number | undefined;
  onUser: (userId: number | undefined) => void;
  onPage: (offset: number) => void;
}

export function EventsTable({ rows, offset, pageSize, userId, onUser, onPage }: Props) {
  return (
    <div>
      <div className="table-toolbar">
        {userId !== undefined ? (
          <button className="chip" onClick={() => onUser(undefined)}>
            User {userId} ×
          </button>
        ) : (
          <span className="muted">Click a user id to see their full journey.</span>
        )}
        <div className="pager">
          <button disabled={offset === 0} onClick={() => onPage(Math.max(0, offset - pageSize))}>
            ← Prev
          </button>
          <span className="muted">
            {rows.length ? `${offset + 1}–${offset + rows.length}` : "0"}
          </span>
          <button disabled={rows.length < pageSize} onClick={() => onPage(offset + pageSize)}>
            Next →
          </button>
        </div>
      </div>
      <div className="table-scroll">
        <table className="table compact">
          <thead>
            <tr>
              <th>Time (UTC)</th>
              <th>Event</th>
              <th>User</th>
              <th>Session</th>
              <th>Page</th>
              <th>Referrer</th>
              <th>Country</th>
              <th>Device</th>
              <th className="num">Revenue</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((e) => (
              <tr key={e.event_id}>
                <td>{e.event_time.replace("T", " ").slice(0, 19)}</td>
                <td>
                  <span className={`tag tag-${e.event_type}`}>{e.event_type}</span>
                </td>
                <td>
                  <button className="link" onClick={() => onUser(e.user_id)}>
                    {e.user_id}
                  </button>
                </td>
                <td className="mono">{e.session_id}</td>
                <td>{e.page}</td>
                <td>{e.referrer}</td>
                <td>{e.country}</td>
                <td>{e.device}</td>
                <td className="num">{e.revenue ? e.revenue.toFixed(2) : ""}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
