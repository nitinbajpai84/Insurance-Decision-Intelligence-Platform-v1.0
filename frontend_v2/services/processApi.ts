/** processApi — calls to /api/v2/process/* (Prompt 19 business-process pages). */
export const API_BASE: string =
  (typeof process !== "undefined" && process.env.NEXT_PUBLIC_API_V2_URL) || "http://127.0.0.1:3001";

async function getJSON<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, { headers: { Accept: "application/json" } });
  if (!res.ok) throw new Error(`GET ${path} -> HTTP ${res.status}`);
  return (await res.json()) as T;
}

function qs(params: Record<string, string | undefined>): string {
  const p = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => {
    if (v) p.set(k, v);
  });
  const s = p.toString();
  return s ? `?${s}` : "";
}

export interface FunnelStage {
  stage_order: number;
  stage_name: string;
  count: number;
  conversion_to_next_pct: number | null;
  drop_off: string;
}
export interface LeadConversion {
  process_id: string;
  role: string;
  scoped_to_agent: boolean;
  stages: FunnelStage[];
  overall_conversion_pct: number | null;
  avg_time_to_issue_days: number | null;
  top_drop_off_reasons: string[];
}
export interface Repurchase {
  process_id: string;
  scoped_to_agent: boolean;
  repurchase_rate_pct: number;
  repurchasers: number;
  customers: number;
  cross_line_pct: number | null;
  cross_sell_ratio: number | null;
  by_segment: { segment: string; repurchasers: number; avg_gap_days: number; repurchase_rate_pct: number }[];
  time_to_repurchase_distribution: { bucket: string; count: number }[];
}
export interface Demand {
  process_id: string;
  series: { month: string; product_line: string; region: string; leads: number; quotes: number; responses: number; demand_index: number; policies_issued: number; realized_pct: number | null }[];
  demand_callouts: { product_line: string; recent3: number; prior3: number; growth_pct: number | null; direction: string }[];
}
export interface CampaignProcess {
  process_id: string;
  funnel: Record<string, number>;
  roi_leaderboard: { campaign: string; channel: string; targeted: number; responded: number; conversions: number; premium_generated: number; budget: number; roi_multiple: number | null; conversion_rate: number | null }[];
  by_channel: { channel: string; campaigns: number; conversions: number; premium: number; roi: number | null }[];
}

export const getLeadConversion = (f: Record<string, string | undefined> = {}) =>
  getJSON<LeadConversion>(`/api/v2/process/lead-conversion${qs(f)}`);
export const getRepurchase = (f: Record<string, string | undefined> = {}) =>
  getJSON<Repurchase>(`/api/v2/process/repurchase${qs(f)}`);
export const getDemand = (f: Record<string, string | undefined> = {}) =>
  getJSON<Demand>(`/api/v2/process/demand${qs(f)}`);
export const getCampaignProcess = (f: Record<string, string | undefined> = {}) =>
  getJSON<CampaignProcess>(`/api/v2/process/campaign-effectiveness${qs(f)}`);

/** Build an "Ask why" deep-link into the AI Intelligence page with context hints. */
export function askWhyHref(question: string, opts: { role?: string; process_id?: string; stage?: string; metric_id?: string; page?: string } = {}): string {
  const p = new URLSearchParams();
  p.set("q", question);
  if (opts.role) p.set("role", opts.role);
  if (opts.process_id) p.set("process_id", opts.process_id);
  if (opts.stage) p.set("stage", opts.stage);
  if (opts.metric_id) p.set("metric_id", opts.metric_id);
  if (opts.page) p.set("page", opts.page);
  return `/ai-intelligence-v2?${p.toString()}`;
}
