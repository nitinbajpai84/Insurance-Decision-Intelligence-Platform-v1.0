/**
 * apiV2 — all calls to the V2 agentic backend (backend_v2.api.main).
 *
 * The /api/v2/ask endpoint is a POST that returns text/event-stream, so the
 * browser's EventSource (GET-only) cannot be used. streamInsight() instead
 * reads the POST response body as a ReadableStream and parses SSE frames
 * ("data: {...}\n\n") manually, dispatching to typed callbacks.
 */

import { API_BASE } from "./apiBase";

export { API_BASE };

// ---------------------------------------------------------------------------
// Event + payload types (mirror backend_v2 orchestrator / routes)
// ---------------------------------------------------------------------------
export type PipelineStep =
  | "context_retrieved"
  | "cache_hit"
  | "sql_generated"
  | "sql_executed"
  | "insight_token"
  | "complete"
  | "error";

export interface SSEEvent {
  step: PipelineStep | string;
  status?: string;
  time_ms?: number;
  cache_hit?: boolean;
  tokens?: number;
  similarity?: number;
  sql?: string;
  validation_status?: string;
  row_count?: number;
  repaired?: boolean;
  token?: string;
  query_id?: string;
  metadata?: PipelineResult;
  error?: string;
}

export interface KeyDataPoint {
  label: string;
  value: string | number;
  source_table?: string;
  source_column?: string;
}

export interface SchemaContextItem {
  table: string;
  column: string;
  description?: string;
  score?: number;
}

export interface GlossaryContextItem {
  term: string;
  definition: string;
}

export interface SemanticDocItem {
  title: string;
  chunk?: string;
  score?: number;
}

export interface PipelineResult {
  query_id: string;
  question: string;
  role: string;
  // V1-compatible
  context_retrieved: boolean;
  sql_generated: boolean;
  sql_validated: boolean;
  sql_executed: boolean;
  result_validated: boolean;
  insight_generated: boolean;
  answer_summary: string;
  sql_generated_text: string;
  validation: { status: string; errors: string[] };
  execution: Record<string, unknown>;
  row_count: number;
  explain_passed: boolean;
  repair_status: string;
  answer_status: string;
  actual_tables: string[];
  actual_columns: string[];
  top_context: {
    schema: SchemaContextItem[];
    glossary: GlossaryContextItem[];
    docs: SemanticDocItem[];
  };
  models_used: string[];
  business_data_limitations: string;
  result_preview: Record<string, unknown>[];
  key_data_points: KeyDataPoint[];
  // V2-new
  cache_hit: boolean;
  cache_similarity: number;
  parallel_execution: boolean;
  total_latency_ms: number;
  step_latencies: Record<string, number>;
  agent_trace_id: string;
  recommended_action: string;
  confidence_score: number;
  streaming: boolean;
  // Prompt 18/19 governance
  governed?: boolean;
  ungoverned?: boolean;
  ungoverned_label?: string;
  grounding?: {
    metrics_used?: string[];
    binding_ids?: string[];
    canonical_views?: string[];
    allowed_tables?: string[];
    subgraph_triples?: string[];
    applicable_rules?: string[];
    traversal_path?: string[] | null;
    validation?: { ok?: boolean; violations?: string[]; repaired?: boolean };
    grounded?: boolean;
  };
}

export interface GlossaryTerm {
  glossary_id: string;
  term: string;
  domain: string | null;
  definition: string;
  synonyms: string | null;
  owner: string | null;
  active_flag: boolean | null;
  updated_at: string | null;
}

export interface RoleInfo {
  role: string;
  description: string;
}

export interface TraceStep {
  id: number;
  query_id: string;
  agent_name: string;
  input_summary: string;
  output_summary: string;
  duration_ms: number;
  tokens_used: number;
  cache_hit: boolean;
  created_at: string;
}

export interface EvidenceTrace {
  query_id: string;
  steps: TraceStep[];
  agents_involved: string[];
  total_duration_ms: number;
  total_tokens: number;
  cache_hit: boolean;
}

export interface RecentTrace {
  query_id: string;
  started_at: string;
  finished_at: string;
  total_duration_ms: number;
  total_tokens: number;
  any_cache_hit: boolean;
  steps: number;
  question: string;
}

export interface HealthStatus {
  service: string;
  duckdb: { status: string; table_count?: number; error?: string };
  lancedb: { status: string; tables?: Record<string, number>; error?: string };
  gemini: { api_key_present: boolean; generation_model: string; embedding_model: string };
  vector_index_stats: Record<string, number>;
  cache_hit_rate_24h: number;
}

// ---------------------------------------------------------------------------
// SSE streaming for /api/v2/ask
// ---------------------------------------------------------------------------
export interface StreamCallbacks {
  onStep?: (event: SSEEvent) => void;
  onToken?: (token: string) => void;
  onComplete?: (result: PipelineResult) => void;
  onError?: (message: string) => void;
}

/** Optional "Ask why" context hints that sharpen graph retrieval. */
export interface AskHints {
  process_id?: string;
  metric_id?: string;
  page?: string;
  stage?: string;
}

/**
 * Open the SSE pipeline for a question. Returns a cancel() function that aborts
 * the in-flight stream.
 */
export function streamInsight(
  question: string,
  role: string,
  callbacks: StreamCallbacks,
  hints: AskHints = {}
): () => void {
  const controller = new AbortController();

  (async () => {
    try {
      const response = await fetch(`${API_BASE}/api/v2/ask`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
        body: JSON.stringify({ question, role, ...hints }),
        signal: controller.signal
      });

      if (!response.ok || !response.body) {
        throw new Error(`ask failed: HTTP ${response.status}`);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      // eslint-disable-next-line no-constant-condition
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });

        // SSE frames are separated by a blank line
        let sep = buffer.indexOf("\n\n");
        while (sep !== -1) {
          const frame = buffer.slice(0, sep);
          buffer = buffer.slice(sep + 2);
          dispatchFrame(frame, callbacks);
          sep = buffer.indexOf("\n\n");
        }
      }
      // flush any trailing frame
      if (buffer.trim()) dispatchFrame(buffer, callbacks);
    } catch (err) {
      if ((err as Error)?.name === "AbortError") return; // user cancelled
      callbacks.onError?.((err as Error)?.message || "stream failed");
    }
  })();

  return () => controller.abort();
}

function dispatchFrame(frame: string, callbacks: StreamCallbacks): void {
  // A frame may contain multiple "data:" lines; concatenate their payloads.
  const dataLines = frame
    .split("\n")
    .filter((l) => l.startsWith("data:"))
    .map((l) => l.slice(5).trim());
  if (!dataLines.length) return;
  const raw = dataLines.join("\n");
  let event: SSEEvent;
  try {
    event = JSON.parse(raw) as SSEEvent;
  } catch {
    return;
  }

  if (event.step === "insight_token") {
    if (event.token) callbacks.onToken?.(event.token);
    return;
  }
  if (event.step === "error") {
    callbacks.onError?.(event.error || "pipeline error");
    return;
  }
  if (event.step === "complete") {
    callbacks.onStep?.(event);
    if (event.metadata) callbacks.onComplete?.(event.metadata);
    return;
  }
  callbacks.onStep?.(event);
}

// ---------------------------------------------------------------------------
// REST helpers
// ---------------------------------------------------------------------------
async function getJSON<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, { headers: { Accept: "application/json" } });
  if (!res.ok) throw new Error(`GET ${path} -> HTTP ${res.status}`);
  return (await res.json()) as T;
}

export function getRoles(): Promise<RoleInfo[]> {
  return getJSON<RoleInfo[]>("/api/v2/roles");
}

export function getGlossary(): Promise<GlossaryTerm[]> {
  return getJSON<GlossaryTerm[]>("/api/v2/glossary");
}

export async function updateGlossaryTerm(
  termId: string,
  newDefinition: string,
  updatedBy: string,
  reason: string
): Promise<{ status: string; term: string; reembedded: boolean; embed_error: string | null; audited: boolean }> {
  const res = await fetch(`${API_BASE}/api/v2/glossary/update`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ term_id: termId, new_definition: newDefinition, updated_by: updatedBy, reason })
  });
  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      const body = await res.json();
      detail = (body && (body.detail || body.message)) || detail;
    } catch {
      /* ignore */
    }
    throw new Error(`glossary update failed: ${detail}`);
  }
  return res.json();
}

export function getEvidence(queryId: string): Promise<EvidenceTrace> {
  return getJSON<EvidenceTrace>(`/api/v2/evidence/${encodeURIComponent(queryId)}`);
}

export function getRecentEvidence(limit = 20): Promise<RecentTrace[]> {
  return getJSON<RecentTrace[]>(`/api/v2/evidence/recent?limit=${limit}`);
}

export function getHealth(): Promise<HealthStatus> {
  return getJSON<HealthStatus>("/api/v2/health");
}

// ---------------------------------------------------------------------------
// Small shared formatting helpers used across components
// ---------------------------------------------------------------------------
export function formatMs(ms: number | undefined | null): string {
  if (ms === undefined || ms === null || Number.isNaN(ms)) return "—";
  if (ms < 1000) return `${Math.round(ms)}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

export function confidenceTone(score: number): "green" | "amber" | "red" {
  if (score >= 0.85) return "green";
  if (score >= 0.7) return "amber";
  return "red";
}
