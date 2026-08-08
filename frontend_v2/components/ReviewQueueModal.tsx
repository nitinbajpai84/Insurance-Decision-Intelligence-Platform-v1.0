"use client";

/**
 * ReviewQueueModal — admin-only governed review of pending structural changes
 * (definition edits + proposed relationships). Approve applies + audits;
 * reject discards. Nothing is ever silently applied.
 */
import { useEffect, useState } from "react";
import { Check, Loader2, X } from "lucide-react";
import { getReviewQueue, postReview, type ReviewItem } from "@/services/graphApi";

export default function ReviewQueueModal({
  role,
  onClose,
  onApplied
}: {
  role: string;
  onClose: () => void;
  onApplied: () => void;
}) {
  const [items, setItems] = useState<ReviewItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [busyId, setBusyId] = useState<string | null>(null);

  useEffect(() => {
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function load() {
    setLoading(true);
    setError("");
    try {
      const r = await getReviewQueue(role);
      setItems(r.items);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  }

  async function decide(item: ReviewItem, decision: "approve" | "reject") {
    setBusyId(item.feedback_id);
    try {
      await postReview(item.feedback_id, decision, "console.reviewer", role);
      setItems((prev) => prev.filter((i) => i.feedback_id !== item.feedback_id));
      onApplied();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusyId(null);
    }
  }

  return (
    <Overlay onClose={onClose}>
      <div className="flex items-center justify-between border-b border-gray-100 px-5 py-3">
        <h3 className="text-base font-bold text-gray-900">Review queue</h3>
        <button onClick={onClose} className="rounded p-1 text-gray-400 hover:bg-gray-100"><X size={16} /></button>
      </div>
      <div className="max-h-[70vh] overflow-y-auto thin-scroll p-5">
        {error && <p className="mb-3 rounded bg-amber-50 px-3 py-2 text-sm text-amber-800">{error}</p>}
        {loading ? (
          <div className="flex justify-center py-8"><Loader2 className="animate-spin text-gray-400" /></div>
        ) : items.length === 0 ? (
          <p className="py-8 text-center text-sm text-gray-400">Nothing pending review. Structural changes appear here before taking effect.</p>
        ) : (
          <ul className="space-y-3">
            {items.map((item) => (
              <li key={item.feedback_id} className="rounded-lg border border-gray-100 p-4">
                <div className="flex items-center gap-2">
                  <span className="rounded-full bg-pwc-orange/10 px-2 py-0.5 text-[10px] font-bold uppercase text-pwc-orange">
                    {item.target_type} · {item.feedback_type}
                  </span>
                  <span className="text-xs text-gray-400">by {item.user_id} ({item.user_role})</span>
                </div>
                <p className="mt-2 text-sm font-semibold text-gray-900">{item.target_name || item.target_id}</p>

                {item.feedback_type === "edit" && item.proposed_change && (
                  <div className="mt-2 rounded border border-gray-100 bg-gray-50 p-2 text-sm">
                    <p className="text-red-600 line-through">{item.current_definition || "(none)"}</p>
                    <p className="text-green-700">{String((item.proposed_change as { value?: string }).value ?? "")}</p>
                  </div>
                )}
                {item.feedback_type === "missing" && item.proposed_change && (
                  <p className="mt-2 font-mono text-xs text-gray-700">
                    {String((item.proposed_change as { src?: string }).src ?? "")} —
                    {String((item.proposed_change as { edge_type?: string }).edge_type ?? "")}→
                    {String((item.proposed_change as { dst?: string }).dst ?? "")}
                  </p>
                )}
                {item.comment && <p className="mt-1 text-xs text-gray-500">reason: {item.comment}</p>}

                <div className="mt-3 flex gap-2">
                  <button onClick={() => decide(item, "approve")} disabled={busyId === item.feedback_id}
                    className="inline-flex items-center gap-1 rounded bg-green-600 px-3 py-1.5 text-xs font-bold text-white hover:bg-green-700 disabled:opacity-50">
                    <Check size={13} /> Approve
                  </button>
                  <button onClick={() => decide(item, "reject")} disabled={busyId === item.feedback_id}
                    className="inline-flex items-center gap-1 rounded border border-gray-200 px-3 py-1.5 text-xs font-bold text-gray-600 hover:bg-gray-50 disabled:opacity-50">
                    <X size={13} /> Reject
                  </button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>
    </Overlay>
  );
}

export function Overlay({ children, onClose }: { children: React.ReactNode; onClose: () => void }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" onClick={onClose}>
      <div className="w-full max-w-2xl rounded-xl bg-white shadow-executive" onClick={(e) => e.stopPropagation()}>
        {children}
      </div>
    </div>
  );
}
