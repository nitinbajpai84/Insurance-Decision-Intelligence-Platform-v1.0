/**
 * dataV2 — typed fetchers for the V2 data-product endpoints (backend_v2
 * api/data_products.py). Read-only; every call carries an optional role for
 * server-side row scoping.
 */
import { API_BASE } from "@/services/apiV2";

export type Json = Record<string, any>;

async function get<T = Json>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, { headers: { Accept: "application/json" } });
  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      const b = await res.json();
      detail = b?.detail || b?.error || detail;
    } catch {
      /* ignore */
    }
    throw new Error(detail);
  }
  return (await res.json()) as T;
}

const q = (params: Record<string, string | number | undefined | null>) =>
  Object.entries(params)
    .filter(([, v]) => v !== undefined && v !== null && v !== "")
    .map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(String(v))}`)
    .join("&");

export const dataV2 = {
  homeKpis: () => get("/api/v2/home/kpis"),

  customersSearch: (query: string, role?: string, limit = 25) =>
    get(`/api/v2/customers/search?${q({ q: query, role, limit })}`),
  customer: (id: string, role?: string) => get(`/api/v2/customers/${encodeURIComponent(id)}?${q({ role })}`),

  agentsSearch: (query: string, role?: string, limit = 25) =>
    get(`/api/v2/agents/search?${q({ q: query, role, limit })}`),
  agent: (id: string, role?: string) => get(`/api/v2/agents/${encodeURIComponent(id)}?${q({ role })}`),
  leaderboard: (f: { region?: string; segment?: string; customer_type?: string; product?: string; role?: string }) =>
    get(`/api/v2/agents/leaderboard?${q(f)}`),

  campaigns: (f: { search?: string; medium?: string; from?: string; to?: string }) =>
    get(`/api/v2/campaigns?${q(f)}`),
  campaign: (id: string) => get(`/api/v2/campaigns/${encodeURIComponent(id)}`),

  lapseSummary: (f: { region?: string; product?: string; segment?: string }) =>
    get(`/api/v2/lapse-risk/summary?${q(f)}`),
  lapseHotspots: (f: { region?: string; product?: string; segment?: string }) =>
    get(`/api/v2/lapse-risk/hotspots?${q(f)}`),

  glossary: () => get<any[]>("/api/v2/glossary")
};

/** Format a number as SGD-ish currency with K/M suffixes. */
export function money(v: number | null | undefined): string {
  const n = Number(v);
  if (!Number.isFinite(n) || n === 0) return "S$0";
  const abs = Math.abs(n);
  if (abs >= 1_000_000) return `S$${(n / 1_000_000).toFixed(abs >= 10_000_000 ? 0 : 1)}M`;
  if (abs >= 1_000) return `S$${Math.round(n / 1_000).toLocaleString()}K`;
  return `S$${Math.round(n).toLocaleString()}`;
}

export function pct(v: number | null | undefined, digits = 1): string {
  const n = Number(v);
  return Number.isFinite(n) ? `${n.toFixed(digits)}%` : "—";
}

export function num(v: number | null | undefined): string {
  const n = Number(v);
  return Number.isFinite(n) ? Math.round(n).toLocaleString() : "—";
}

export function titleCase(s: string | null | undefined): string {
  if (!s) return "—";
  return String(s)
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}
