import { API_BASE } from "./apiBase";

export interface DecisionRule {
  rule_id: string;
  name: string;
  condition_text: string | null;
  condition_json: { metric: string; operator: string; value: number }[] | null;
  threshold_json: Record<string, number> | null;
  action_text: string | null;
  assigned_role: string | null;
  priority: number | null;
  status: string;
  created_by: string | null;
  reason: string | null;
  created_at: string | null;
}

export async function fetchRules(): Promise<DecisionRule[]> {
  const res = await fetch(`${API_BASE}/api/v2/graph/rules`, { headers: { Accept: "application/json" } });
  if (!res.ok) throw new Error(`fetchRules failed: ${res.status}`);
  const data = await res.json();
  return data.rules;
}

export async function editRule(
  ruleId: string,
  patch: { threshold_json?: Record<string, number>; action_text?: string; condition_text?: string },
  updatedBy: string,
  reason: string
): Promise<{ status: string; message: string }> {
  const res = await fetch(`${API_BASE}/api/v2/graph/rules/${encodeURIComponent(ruleId)}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ...patch, updated_by: updatedBy, reason })
  });
  if (!res.ok) throw new Error((await res.json()).detail || `editRule failed: ${res.status}`);
  return res.json();
}

export async function setRuleStatus(
  ruleId: string,
  action: "activate" | "deactivate",
  updatedBy: string,
  reason: string
): Promise<{ status: string }> {
  const res = await fetch(`${API_BASE}/api/v2/graph/rules/${encodeURIComponent(ruleId)}/${action}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ updated_by: updatedBy, reason })
  });
  if (!res.ok) throw new Error((await res.json()).detail || `${action} failed: ${res.status}`);
  return res.json();
}
