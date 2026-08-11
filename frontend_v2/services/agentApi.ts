/**
 * agentApi — context-layer endpoints (/api/v2/ai-agents, /api/v2/conversations).
 *
 * Note the path is `ai-agents`, not `agents`: /api/v2/agents/{id} is already the
 * data-product endpoint for insurance agents (people), so the context layer uses
 * a distinct prefix to avoid shadowing it.
 */
import { API_BASE } from "./apiBase";

export interface InitiativeCard {
  agent_id: string | null;
  initiative_id: string;
  domain: string;
  name: string;
  strategic_goal: string | null;
  ai_capability: string | null;
  primary_users: string | null;
  phase: string | null;
  value_score: number | null;
  complexity_score: number | null;
  industry_maturity: string | null;
  model_families: string[] | null;
  skills: string[] | null;
  role_scope: string | null;
  status: string | null;
}

export interface PlatformAgent {
  agent_id: string;
  name: string;
  description: string | null;
  role_scope: string | null;
  skills: string[] | null;
  jurisdiction: string | null;
  status: string;
}

export interface AgentListResponse {
  platform_agents: PlatformAgent[];
  initiatives: InitiativeCard[];
  counts: { total: number; functional: number };
}

export interface AgentDetail {
  agent_id: string;
  initiative_id: string | null;
  name: string;
  description: string | null;
  persona_prompt: string | null;
  skills: string[] | null;
  knowledge_scopes: Record<string, unknown> | null;
  role_scope: string | null;
  jurisdiction: string | null;
  model_tier: string | null;
  hitl_gate: string | null;
  status: string;
  owner: string | null;
  initiative?: {
    initiative_id: string;
    domain: string;
    name: string;
    strategic_goal: string | null;
    business_problem: string | null;
    ai_capability: string | null;
    genai_ml_approach: string | null;
    expected_output: string | null;
    primary_users: string | null;
    kpis: string | null;
    business_value: string | null;
    phase: string | null;
    industry_maturity: string | null;
    value_score: number | null;
    complexity_score: number | null;
    source_systems: string[] | null;
    core_tables: string[] | null;
    model_families: string[] | null;
    kpi_impact: Record<string, string> | null;
    charter_md: string | null;
  } | null;
}

export async function fetchAgents(): Promise<AgentListResponse> {
  const res = await fetch(`${API_BASE}/api/v2/ai-agents`, { headers: { Accept: "application/json" } });
  if (!res.ok) throw new Error(`fetchAgents failed: ${res.status}`);
  return res.json();
}

export async function fetchAgent(agentId: string): Promise<AgentDetail> {
  const res = await fetch(`${API_BASE}/api/v2/ai-agents/${encodeURIComponent(agentId)}`, {
    headers: { Accept: "application/json" }
  });
  if (!res.ok) throw new Error(`fetchAgent failed: ${res.status}`);
  return res.json();
}

export interface AgentStreamCallbacks {
  onConversation?: (conversationId: string) => void;
  onStep?: (step: string, payload: Record<string, unknown>) => void;
  onToken?: (token: string) => void;
  onSql?: (sql: string) => void;
  onError?: (message: string) => void;
  onComplete?: () => void;
}

/** POST /ai-agents/{id}/ask and parse the SSE frames (same shape as /api/v2/ask). */
export async function streamAgentAsk(
  agentId: string,
  question: string,
  conversationId: string | null,
  cb: AgentStreamCallbacks
): Promise<void> {
  const res = await fetch(`${API_BASE}/api/v2/ai-agents/${encodeURIComponent(agentId)}/ask`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question, conversation_id: conversationId })
  });
  if (!res.ok || !res.body) {
    let detail = `HTTP ${res.status}`;
    try {
      const j = await res.json();
      detail = j.error || j.detail || detail;
    } catch {
      /* non-JSON error body */
    }
    cb.onError?.(detail);
    return;
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let idx = buffer.indexOf("\n\n");
    while (idx !== -1) {
      const frame = buffer.slice(0, idx);
      buffer = buffer.slice(idx + 2);
      if (frame.startsWith("data: ")) {
        try {
          const data = JSON.parse(frame.slice(6));
          const step = data.step as string;
          if (step === "conversation") cb.onConversation?.(data.conversation_id);
          else if (step === "insight_token") cb.onToken?.(data.token || "");
          else if (step === "sql_generated") {
            cb.onSql?.(data.sql || "");
            cb.onStep?.(step, data);
          } else if (step === "error") cb.onError?.(data.error || "pipeline error");
          else if (step === "complete") cb.onComplete?.();
          else cb.onStep?.(step, data);
        } catch {
          /* ignore malformed frame */
        }
      }
      idx = buffer.indexOf("\n\n");
    }
  }
}
