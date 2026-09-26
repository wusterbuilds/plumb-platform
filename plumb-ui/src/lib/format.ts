import type { DealStatus, DealType, FlagColor } from "./types";

export function formatCurrency(value: number | null | undefined): string {
  if (value == null) return "--";
  if (value >= 1_000_000_000) return `$${(value / 1_000_000_000).toFixed(1)}B`;
  if (value >= 1_000_000) return `$${(value / 1_000_000).toFixed(1)}M`;
  if (value >= 1_000) return `$${(value / 1_000).toFixed(0)}K`;
  return `$${value.toLocaleString()}`;
}

export function formatDate(dateStr: string): string {
  const date = new Date(dateStr);
  return date.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

export function timeAgo(dateStr: string): string {
  const now = Date.now();
  const then = new Date(dateStr).getTime();
  const diffMs = now - then;
  const diffMins = Math.floor(diffMs / 60000);
  if (diffMins < 1) return "just now";
  if (diffMins < 60) return `${diffMins}m ago`;
  const diffHours = Math.floor(diffMins / 60);
  if (diffHours < 24) return `${diffHours}h ago`;
  const diffDays = Math.floor(diffHours / 24);
  if (diffDays < 30) return `${diffDays}d ago`;
  return formatDate(dateStr);
}

export function dealTypeLabel(dt: DealType): string {
  const labels: Record<DealType, string> = {
    construction_loan: "Construction",
    stabilized_debt: "Stabilized Debt",
    value_add: "Value-Add",
    equity_placement: "Equity",
  };
  return labels[dt] || dt;
}

export function dealStatusLabel(s: DealStatus): string {
  const labels: Record<DealStatus, string> = {
    docs_received: "Docs Received",
    classifying: "Classifying",
    extracting: "Extracting",
    extraction_review: "Extraction Review",
    model_building: "Model Building",
    market_enrichment: "Market Enrichment",
    om_drafting: "OM Drafting",
    om_review: "OM Review",
    reworking: "Agent Reworking",
    lender_outreach: "Lender Outreach",
    tracking: "Tracking",
    term_sheet_received: "Term Sheet",
    closed: "Closed",
    on_hold: "On Hold",
    dead: "Dead",
    extraction_failed: "Extraction Failed",
    model_error: "Model Error",
  };
  return labels[s] || s;
}

export type StatusCategory = "needs_review" | "processing" | "complete" | "error" | "inactive";

export function statusCategory(s: DealStatus): StatusCategory {
  if (s === "extraction_review" || s === "om_review") return "needs_review";
  if (s === "closed" || s === "term_sheet_received") return "complete";
  if (s === "dead" || s === "on_hold") return "inactive";
  if (s === "extraction_failed" || s === "model_error") return "error";
  return "processing";
}

export function flagColorHex(flag: FlagColor): string {
  switch (flag) {
    case "red": return "#ef4444";
    case "yellow": return "#f59e0b";
    case "green": return "#22c55e";
  }
}

// --- Financial formatting ---

const currencyFull = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  minimumFractionDigits: 0,
  maximumFractionDigits: 0,
});

const currencyDecimals = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

const numberFmt = new Intl.NumberFormat("en-US", {
  minimumFractionDigits: 0,
  maximumFractionDigits: 0,
});

/** Format as full currency: $45,000,000 */
export function formatCurrencyFull(value: number | null | undefined): string {
  if (value == null) return "—";
  return currencyFull.format(value);
}

/** Format as compact currency: $45.0M, $1.2B, $500K */
export function formatCurrencyCompact(value: number | null | undefined): string {
  if (value == null) return "—";
  if (Math.abs(value) >= 1_000_000_000) return `$${(value / 1_000_000_000).toFixed(1)}B`;
  if (Math.abs(value) >= 1_000_000) return `$${(value / 1_000_000).toFixed(1)}M`;
  if (Math.abs(value) >= 1_000) return `$${(value / 1_000).toFixed(0)}K`;
  return currencyFull.format(value);
}

/** Format as per-SF / per-unit currency: $226.19 */
export function formatPerUnit(value: number | null | undefined): string {
  if (value == null) return "—";
  return currencyDecimals.format(value);
}

/** Format as percentage: 52.8% (input is decimal, e.g. 0.528) */
export function formatPercent(value: number | null | undefined): string {
  if (value == null) return "—";
  return `${(value * 100).toFixed(1)}%`;
}

/** Format as percentage with 2 decimals: 4.50% */
export function formatPercentPrecise(value: number | null | undefined): string {
  if (value == null) return "—";
  return `${(value * 100).toFixed(2)}%`;
}

/** Format as plain number with commas: 1,234 */
export function formatNumber(value: number | null | undefined): string {
  if (value == null) return "—";
  return numberFmt.format(value);
}
