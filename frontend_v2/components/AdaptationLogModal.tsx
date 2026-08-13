"use client";

/**
 * AdaptationLogModal — transparency view of how the system has adapted from
 * feedback: edge-weight changes, auto-applied/approved feedback, and
 * semantic-cache changes.
 */
import { useEffect, useState } from "react";
import { GitBranch, Loader2, ThumbsDown, TrendingUp, X, Zap } from "lucide-react";
import { getAdaptationLog, type AdaptationItem } from "@/services/graphApi";
import { Overlay } from "@/components/ReviewQueueModal";

export default function AdaptationLogModal({ onClose }: { onClose: () => void }) {
  const [items, setItems] = useState<AdaptationItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getAdaptationLog(60)
      .then((r) => setItems(r.items))
      .catch(() => setItems([]))
      .finally(() => setLoading(false));
  }, []);

  return (
    <Overlay onClose={onClose}>
      <div className="flex items-center justify-between border-b border-gray-100 px-5 py-3">
        <div>
          <h3 className="text-base font-bold text-gray-900">Adaptation log</h3>
          <p className="text-xs text-gray-500">How the context model has changed from feedback.</p>
        </div>
        <button onClick={onClose} className="rounded p-1 text-gray-400 hover:bg-gray-100"><X size={16} /></button>
      </div>
      <div className="max-h-[70vh] overflow-y-auto thin-scroll p-5">
        {loading ? (
          <div className="flex justify-center py-8"><Loader2 className="animate-spin text-gray-400" /></div>
        ) : items.length === 0 ? (
          <p className="py-8 text-center text-sm text-gray-400">No adaptations yet. Confirm/reject edges or rate answers to start tuning.</p>
        ) : (
          <ul className="space-y-2">
            {items.map((it, i) => (
              <li key={i} className="flex items-start gap-3 rounded-lg border border-gray-100 px-3 py-2.5">
                <Icon kind={it.kind} />
                <div className="min-w-0 flex-1">
                  <p className="text-sm text-gray-800">{describe(it)}</p>
                  <p className="text-[11px] text-gray-400">{it.at ? new Date(String(it.at)).toLocaleString() : ""}</p>
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>
    </Overlay>
  );
}

function Icon({ kind }: { kind: string }) {
  const cls = "mt-0.5 shrink-0";
  if (kind === "edge_weight") return <TrendingUp size={16} className={`${cls} text-brand-orange`} />;
  if (kind === "cache") return <ThumbsDown size={16} className={`${cls} text-brand-rose`} />;
  return <GitBranch size={16} className={`${cls} text-brand-tangerine`} />;
}

function describe(it: AdaptationItem): string {
  if (it.kind === "edge_weight") {
    return `Edge weight ${it.old_weight} → ${it.new_weight} (${it.reason})`;
  }
  if (it.kind === "cache") {
    return `Cache ${it.thumbs === "down" ? "entry removed" : "entry boosted"} from answer feedback`;
  }
  const status = String(it.status || "");
  const tag = status === "approved" ? "approved in review" : "auto-applied from feedback";
  return `${it.target_type} ${it.feedback_type} — ${tag}`;
}
