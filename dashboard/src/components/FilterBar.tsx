import type { FilterOptions, Filters } from "../types";

interface Props {
  filters: Filters;
  options: FilterOptions | undefined;
  onChange: (f: Filters) => void;
}

type ListKey = "country" | "region" | "device" | "eventType" | "page";

function MultiSelect({
  label,
  values,
  selected,
  onChange,
}: {
  label: string;
  values: string[];
  selected: string[];
  onChange: (v: string[]) => void;
}) {
  return (
    <label className="filter">
      <span>{label}</span>
      <select
        multiple
        value={selected}
        onChange={(e) => onChange(Array.from(e.target.selectedOptions, (o) => o.value))}
      >
        {values.map((v) => (
          <option key={v} value={v}>
            {v}
          </option>
        ))}
      </select>
    </label>
  );
}

const CHIP_LABELS: Record<ListKey, string> = {
  country: "Country",
  region: "Region",
  device: "Device",
  eventType: "Event",
  page: "Page",
};

export function FilterBar({ filters, options, onChange }: Props) {
  const set = (patch: Partial<Filters>) => onChange({ ...filters, ...patch });
  const remove = (key: ListKey, value: string) => set({ [key]: filters[key].filter((v) => v !== value) });
  const active = (Object.keys(CHIP_LABELS) as ListKey[]).flatMap((k) => filters[k].map((v) => ({ k, v })));

  return (
    <div className="filter-bar">
      <div className="filter-row">
        <label className="filter">
          <span>From</span>
          <input
            type="date"
            value={filters.startDate}
            min={options?.min_date ?? undefined}
            max={filters.endDate}
            onChange={(e) => set({ startDate: e.target.value })}
          />
        </label>
        <label className="filter">
          <span>To</span>
          <input
            type="date"
            value={filters.endDate}
            min={filters.startDate}
            max={options?.max_date ?? undefined}
            onChange={(e) => set({ endDate: e.target.value })}
          />
        </label>
        <MultiSelect label="Region" values={options?.regions ?? []} selected={filters.region} onChange={(v) => set({ region: v })} />
        <MultiSelect label="Country" values={options?.countries ?? []} selected={filters.country} onChange={(v) => set({ country: v })} />
        <MultiSelect label="Device" values={options?.devices ?? []} selected={filters.device} onChange={(v) => set({ device: v })} />
        <MultiSelect label="Event type" values={options?.event_types ?? []} selected={filters.eventType} onChange={(v) => set({ eventType: v })} />
      </div>
      {active.length > 0 && (
        <div className="chips">
          {active.map(({ k, v }) => (
            <button key={`${k}:${v}`} className="chip" onClick={() => remove(k, v)} title="Remove filter">
              {CHIP_LABELS[k]}: {v} ×
            </button>
          ))}
          <button
            className="chip clear"
            onClick={() => set({ country: [], region: [], device: [], eventType: [], page: [] })}
          >
            Clear all
          </button>
        </div>
      )}
    </div>
  );
}
