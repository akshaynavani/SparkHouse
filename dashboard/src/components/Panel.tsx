import type { ReactNode } from "react";

interface Props {
  title: string;
  actions?: ReactNode;
  loading?: boolean;
  error?: string;
  children: ReactNode;
  className?: string;
}

export function Panel({ title, actions, loading, error, children, className }: Props) {
  return (
    <section className={`panel ${className ?? ""}`}>
      <header className="panel-header">
        <h2>{title}</h2>
        <div className="panel-actions">
          {loading && <span className="spinner" aria-label="loading" />}
          {actions}
        </div>
      </header>
      {error ? <div className="error">{error}</div> : children}
    </section>
  );
}
