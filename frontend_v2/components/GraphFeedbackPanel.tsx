"use client";

/**
 * GraphFeedbackPanel — right-hand detail panel for a selected graph node.
 * Shows definition/formula/sources, connected relationships (with confirm/reject),
 * a "suggest a missing relationship" form, governed "edit definition" (diff +
 * reason → review), and feedback history.
 */
import { useEffect, useMemo, useState } from "react";
import { Check, ChevronDown, Loader2, Pencil, Plus, ThumbsDown, ThumbsUp, X } from "lucide-react";
import {
  EDGE_TYPES,
  getNode,
  postFeedback,
  proposeEdge,
  type GraphNode,
  type NodeDetail
} from "@/services/graphApi";

type Toast = (msg: string, kind: "auto" | "review" | "error") => void;

export default function GraphFeedbackPanel({
  nodeId,
  nodes,
  role,
  onClose,
  onToast,
  onChanged
}: {
  nodeId: string;
  nodes: GraphNode[];
  role: string;
  onClose: () => void;
  onToast: Toast;
  onChanged: () => void;
}) {
  const [detail, setDetail] = useState<NodeDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState(false);
  const [draftDef, setDraftDef] = useState("");
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);

  // suggest-missing-relationship form
  const [suggestOpen, setSuggestOpen] = useState(false);
  const [targetId, setTargetId] = useState("");
  const [edgeType, setEdgeType] = useState("informs");

  useEffect(() => {
    void load();
    setEditing(false);
    setSuggestOpen(false);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [nodeId]);

  async function load() {
    setLoading(true);
    try {
      const d = await getNode(nodeId);
      setDetail(d);
      setDraftDef(d.definition || "");
    } catch (err) {
      onToast((err as Error).message, "error");
    } finally {
      setLoading(false);
    }
  }

  const otherNodes = useMemo(
    () => nodes.filter((n) => n.id !== nodeId).sort((a, b) => a.label.localeCompare(b.label)),
    [nodes, nodeId]
  );

  async function edgeFeedback(edgeId: string, type: "confirm" | "reject") {
    setBusy(true);
    try {
      const r = await postFeedback({ target_type: "edge", target_id: edgeId, feedback_type: type, user_role: role });
      onToast(`Edge ${type}ed — weight auto-tuned to ${(r as { new_weight?: number }).new_weight}`, "auto");
      await load();
      onChanged();
    } catch (err) {
      onToast((err as Error).message, "error");
    } finally {
      setBusy(false);
    }
  }

  async function nodeConfirm(type: "confirm" | "reject") {
    setBusy(true);
    try {
      const r = (await postFeedback({ target_type: "node", target_id: nodeId, feedback_type: type, rating: type === "confirm" ? 5 : 2, user_role: role })) as {
        edges_adjusted?: number;
      };
      onToast(`Node ${type}ed — ${r.edges_adjusted ?? 0} edge weights auto-tuned`, "auto");
      await load();
      onChanged();
    } catch (err) {
      onToast((err as Error).message, "error");
    } finally {
      setBusy(false);
    }
  }

  async function submitEdit() {
    if (draftDef.trim() === (detail?.definition || "").trim()) return onToast("Definition unchanged", "error");
    if (reason.trim().length < 3) return onToast("A reason is required", "error");
    setBusy(true);
    try {
      await postFeedback({
        target_type: "node",
        target_id: nodeId,
        feedback_type: "edit",
        comment: reason.trim(),
        proposed_change: { field: "definition", value: draftDef.trim() },
        user_role: role
      });
      onToast("Definition change submitted for review", "review");
      setEditing(false);
      setReason("");
      await load();
      onChanged();
    } catch (err) {
      onToast((err as Error).message, "error");
    } finally {
      setBusy(false);
    }
  }

  async function submitProposal() {
    if (!targetId) return onToast("Pick a target node", "error");
    setBusy(true);
    try {
      await proposeEdge(nodeId, targetId, edgeType, "console.user", role);
      onToast("Relationship submitted for review", "review");
      setSuggestOpen(false);
      setTargetId("");
      onChanged();
    } catch (err) {
      onToast((err as Error).message, "error");
    } finally {
      setBusy(false);
    }
  }

  return (
    <aside className="flex h-full w-full flex-col overflow-y-auto thin-scroll border-l border-gray-200 bg-white">
      <div className="flex items-start justify-between gap-2 border-b border-gray-100 p-4">
        <div>
          <span className="rounded-full bg-gray-100 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide text-gray-500">
            {detail?.node_type || "node"}
          </span>
          <h3 className="mt-1 text-base font-bold text-gray-900">{detail?.name || nodeId}</h3>
        </div>
        <button onClick={onClose} className="rounded p-1 text-gray-400 hover:bg-gray-100">
          <X size={16} />
        </button>
      </div>

      {loading || !detail ? (
        <div className="flex flex-1 items-center justify-center text-gray-400">
          <Loader2 className="animate-spin" size={18} />
        </div>
      ) : (
        <div className="space-y-4 p-4">
          {/* confirm / reject node */}
          <div className="flex gap-2">
            <button onClick={() => nodeConfirm("confirm")} disabled={busy}
              className="inline-flex items-center gap-1 rounded-full bg-green-50 px-3 py-1 text-xs font-bold text-green-700 hover:bg-green-100">
              <ThumbsUp size={12} /> Confirm
            </button>
            <button onClick={() => nodeConfirm("reject")} disabled={busy}
              className="inline-flex items-center gap-1 rounded-full bg-pwc-rose/10 px-3 py-1 text-xs font-bold text-pwc-rose hover:bg-pwc-rose/20">
              <ThumbsDown size={12} /> Reject
            </button>
            {detail.health != null && (
              <span className="ml-auto rounded-full bg-gray-100 px-2 py-1 text-xs font-semibold text-gray-600">
                health {detail.health}
              </span>
            )}
          </div>

          <Field label="Definition">
            {editing ? (
              <div className="space-y-2">
                <div className="rounded border border-gray-100 bg-gray-50 p-2 text-sm">
                  <p className="text-red-600 line-through">{detail.definition || "(none)"}</p>
                  <p className="text-green-700">{draftDef || <span className="italic text-gray-400">empty</span>}</p>
                </div>
                <textarea value={draftDef} onChange={(e) => setDraftDef(e.target.value)} rows={3}
                  className="w-full rounded border border-gray-200 p-2 text-sm outline-none focus:border-pwc-orange" />
                <input value={reason} onChange={(e) => setReason(e.target.value)} placeholder="Why change this? (required)"
                  className="w-full rounded border border-gray-200 p-2 text-sm outline-none focus:border-pwc-orange" />
                <div className="flex gap-2">
                  <button onClick={submitEdit} disabled={busy}
                    className="rounded bg-pwc-orange px-3 py-1.5 text-xs font-bold text-white hover:bg-pwc-orangeDark">
                    Submit for review
                  </button>
                  <button onClick={() => setEditing(false)} className="rounded border border-gray-200 px-3 py-1.5 text-xs font-bold text-gray-600">
                    Cancel
                  </button>
                </div>
              </div>
            ) : (
              <div className="flex items-start justify-between gap-2">
                <p className="text-sm text-gray-700">{detail.definition || <span className="text-gray-400">No definition.</span>}</p>
                <button onClick={() => setEditing(true)} className="shrink-0 rounded border border-gray-200 px-2 py-1 text-xs font-semibold text-gray-600 hover:bg-gray-50">
                  <Pencil size={11} className="inline" /> Edit
                </button>
              </div>
            )}
          </Field>

          {detail.formula && <Field label="Formula"><code className="text-xs text-gray-700">{detail.formula}</code></Field>}
          {detail.source_columns.length > 0 && (
            <Field label="Source columns">
              <div className="flex flex-wrap gap-1">
                {detail.source_columns.map((c) => (
                  <span key={c} className="rounded bg-gray-100 px-2 py-0.5 font-mono text-[11px] text-gray-700">{c}</span>
                ))}
              </div>
            </Field>
          )}
          {detail.owner_role && <Field label="Owner role"><span className="text-sm text-gray-700">{detail.owner_role}</span></Field>}

          {/* relationships */}
          <Field label={`Relationships (${detail.connected_edges.length})`}>
            <div className="space-y-1.5">
              {detail.connected_edges.slice(0, 30).map((e) => (
                <div key={e.edge_id} className="flex items-center justify-between gap-2 rounded border border-gray-100 bg-gray-50 px-2 py-1.5">
                  <span className="min-w-0 truncate text-xs text-gray-700">
                    {e.direction === "out" ? "" : "← "}
                    <span className="font-semibold text-gray-900">{e.edge_type}</span>{" "}
                    {e.direction === "out" ? "→ " : ""}
                    {e.direction === "out" ? e.dst_name : e.src_name}
                    <span className="ml-1 text-gray-400">w{e.weight}</span>
                  </span>
                  <span className="flex shrink-0 gap-1">
                    <button onClick={() => edgeFeedback(e.edge_id, "confirm")} disabled={busy} className="text-green-600 hover:text-green-800"><ThumbsUp size={13} /></button>
                    <button onClick={() => edgeFeedback(e.edge_id, "reject")} disabled={busy} className="text-pwc-rose hover:opacity-70"><ThumbsDown size={13} /></button>
                  </span>
                </div>
              ))}
              {detail.connected_edges.length === 0 && <p className="text-xs text-gray-400">No active relationships.</p>}
            </div>
          </Field>

          {/* suggest missing relationship */}
          <div>
            <button onClick={() => setSuggestOpen((v) => !v)} className="inline-flex items-center gap-1 text-xs font-bold text-pwc-orange hover:text-pwc-orangeDark">
              <Plus size={13} /> Suggest a missing relationship
            </button>
            {suggestOpen && (
              <div className="mt-2 space-y-2 rounded border border-gray-100 bg-gray-50 p-2">
                <select value={edgeType} onChange={(e) => setEdgeType(e.target.value)} className="w-full rounded border border-gray-200 p-1.5 text-xs">
                  {EDGE_TYPES.map((t) => <option key={t}>{t}</option>)}
                </select>
                <select value={targetId} onChange={(e) => setTargetId(e.target.value)} className="w-full rounded border border-gray-200 p-1.5 text-xs">
                  <option value="">— target node —</option>
                  {otherNodes.map((n) => <option key={n.id} value={n.id}>{n.label} ({n.type})</option>)}
                </select>
                <button onClick={submitProposal} disabled={busy} className="w-full rounded bg-pwc-orange px-3 py-1.5 text-xs font-bold text-white hover:bg-pwc-orangeDark">
                  Submit for review
                </button>
              </div>
            )}
          </div>

          {/* feedback history */}
          {detail.feedback_history.length > 0 && (
            <Field label="Feedback history">
              <ul className="space-y-1">
                {detail.feedback_history.slice(0, 8).map((f, i) => (
                  <li key={i} className="text-xs text-gray-600">
                    <span className="font-semibold text-gray-800">{f.feedback_type}</span>
                    <span className="rounded-full bg-gray-100 px-1.5 py-0.5 text-[10px] text-gray-500"> {f.status}</span>
                    {f.comment ? ` — ${f.comment}` : ""}
                  </li>
                ))}
              </ul>
            </Field>
          )}

          <p className="border-t border-gray-100 pt-2 text-[11px] text-gray-400">
            last adapted: {detail.last_adapted ? new Date(detail.last_adapted).toLocaleString() : "—"}
          </p>
        </div>
      )}
    </aside>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <p className="mb-1 text-[11px] font-bold uppercase tracking-wide text-gray-500">{label}</p>
      {children}
    </div>
  );
}
