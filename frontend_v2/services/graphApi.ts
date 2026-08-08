/**
 * graphApi — all /api/v2/graph/* calls for the Context Graph page.
 */
import { API_BASE } from "./apiBase";

export { API_BASE };

export interface GraphNode {
  id: string;
  label: string;
  type: string;
  group: string;
  degree: number;
  health: number | null;
}
export interface GraphLink {
  id: string;
  source: string;
  target: string;
  type: string;
  weight: number;
  status: string;
}
export interface GraphModel {
  nodes: GraphNode[];
  links: GraphLink[];
  subject_area: string | null;
  counts: { nodes: number; links: number };
}

export interface ConnectedEdge {
  edge_id: string;
  src: string;
  src_name: string;
  dst: string;
  dst_name: string;
  edge_type: string;
  weight: number;
  status: string;
  direction: "in" | "out";
}
export interface NodeDetail {
  node_id: string;
  node_type: string;
  name: string;
  definition: string | null;
  formula: string | null;
  default_grain?: string | null;
  subject_area: string | null;
  owner_role: string | null;
  source_columns: string[];
  connected_edges: ConnectedEdge[];
  feedback_history: Array<{
    feedback_type: string;
    rating: number | null;
    comment: string | null;
    status: string;
    user_id: string;
    created_at: string;
  }>;
  health: number | null;
  last_adapted: string | null;
}

export interface ReviewItem {
  feedback_id: string;
  target_type: string;
  target_id: string;
  feedback_type: string;
  comment: string | null;
  proposed_change: Record<string, unknown> | null;
  user_id: string;
  user_role: string;
  created_at: string;
  target_name?: string;
  current_definition?: string;
}

export interface AdaptationItem {
  kind: "edge_weight" | "feedback" | "cache";
  at: string;
  [k: string]: unknown;
}

async function getJSON<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, { headers: { Accept: "application/json" } });
  if (!res.ok) throw new Error(`GET ${path} -> HTTP ${res.status}`);
  return (await res.json()) as T;
}
async function postJSON<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body)
  });
  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      const j = await res.json();
      detail = JSON.stringify(j.detail || j);
    } catch {
      /* ignore */
    }
    throw new Error(detail);
  }
  return (await res.json()) as T;
}

export function getModel(subjectArea?: string, nodeType?: string): Promise<GraphModel> {
  const p = new URLSearchParams();
  if (subjectArea) p.set("subject_area", subjectArea);
  if (nodeType) p.set("node_type", nodeType);
  const qs = p.toString();
  return getJSON<GraphModel>(`/api/v2/graph/model${qs ? `?${qs}` : ""}`);
}

export function getNode(nodeId: string): Promise<NodeDetail> {
  return getJSON<NodeDetail>(`/api/v2/graph/node/${encodeURIComponent(nodeId)}`);
}

export interface FeedbackBody {
  target_type: "node" | "edge" | "rule" | "answer";
  target_id?: string;
  feedback_type?: "confirm" | "reject" | "missing" | "edit";
  rating?: number;
  comment?: string;
  proposed_change?: Record<string, unknown>;
  thumbs?: "up" | "down";
  query_id?: string;
  role?: string;
  user?: string;
  user_role?: string;
}
export function postFeedback(body: FeedbackBody): Promise<Record<string, unknown>> {
  return postJSON("/api/v2/graph/feedback", body);
}

export function proposeEdge(src: string, dst: string, edgeType: string, user = "console.user", userRole = "Data Analyst") {
  return postJSON<Record<string, unknown>>("/api/v2/graph/propose-edge", {
    src,
    dst,
    edge_type: edgeType,
    user,
    user_role: userRole
  });
}

export function getReviewQueue(role: string): Promise<{ items: ReviewItem[] }> {
  return getJSON<{ items: ReviewItem[] }>(`/api/v2/graph/review-queue?role=${encodeURIComponent(role)}`);
}

export function postReview(feedbackId: string, decision: "approve" | "reject", reviewer: string, role: string) {
  return postJSON<Record<string, unknown>>(`/api/v2/graph/review/${encodeURIComponent(feedbackId)}`, {
    decision,
    reviewer,
    role
  });
}

export function getAdaptationLog(limit = 50): Promise<{ items: AdaptationItem[] }> {
  return getJSON<{ items: AdaptationItem[] }>(`/api/v2/graph/adaptation-log?limit=${limit}`);
}

export const NODE_COLORS: Record<string, string> = {
  term: "#2563eb", // concept = blue
  metric: "#16a34a", // green
  process: "#7c3aed", // purple
  decision: "#d97706", // amber
  entity_class: "#6b7280" // grey
};

export const EDGE_TYPES = [
  "owns",
  "scored_by",
  "triggers",
  "considers",
  "routes_to",
  "measured_by",
  "defined_by",
  "informs",
  "escalates_to",
  "targets",
  "manages",
  "against"
];
