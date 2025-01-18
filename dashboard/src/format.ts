const compact = new Intl.NumberFormat("en-US", { notation: "compact", maximumFractionDigits: 1 });
const currency = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 });

export const fmtNumber = (n: number) => compact.format(n);
export const fmtCurrency = (n: number) => currency.format(n);
export const fmtPct = (n: number) => `${(n * 100).toFixed(1)}%`;
export const fmtMetric = (metric: string, n: number) => (metric === "revenue" ? fmtCurrency(n) : fmtNumber(n));
