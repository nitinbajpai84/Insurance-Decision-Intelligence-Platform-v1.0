"use client";

/**
 * RecommendationCard — structured card shown when an answer carries a
 * recommended action. Priority badge + confidence %, expandable evidence
 * (the key_data_points that drove the recommendation), assigned-role tag,
 * and an action button.
 */
import { useState } from "react";
import { ArrowUpRight, ChevronDown, ChevronUp, Sparkles } from "lucide-react";
import type { KeyDataPoint } from "@/services/apiV2";

export type Priority = "Critical" | "High" | "Medium";

export interface RecommendationCardProps {
  title?: string;
  reasoning: string;
  action: string;
  role: string;
  confidence: number; // 0..1
  priority?: Priority;
  keyDataPoints?: KeyDataPoint[];
  onAction?: () => void;
}

const PRIORITY_STYLE: Record<Priority, string> = {
  // priority-tinted badge styles, driven by the shared brand accent palette
  Critical: "bg-brand-rose/15 text-brand-rose border border-brand-rose/30",
  High: "bg-brand-orange/10 text-brand-orange border border-brand-orange/30",
  Medium: "bg-gray-100 text-gray-600 border border-gray-200"
};

/** Heuristic priority from confidence + action wording when none supplied. */
export function derivePriority(action: string, confidence: number): Priority {
  const a = (action || "").toLowerCase();
  if (/(urgent|immediately|at risk|retention|fraud|critical|churn)/.test(a) && confidence >= 0.8) return "Critical";
  if (confidence >= 0.85 || /(prioritize|assign|review|coach)/.test(a)) return "High";
  return "Medium";
}

function formatValue(v: string | number): string {
  if (typeof v === "number") {
    return Number.isInteger(v) ? v.toLocaleString() : v.toLocaleString(undefined, { maximumFractionDigits: 4 });
  }
  return String(v);
}

export default function RecommendationCard({
  title = "Recommended action",
  reasoning,
  action,
  role,
  confidence,
  priority,
  keyDataPoints = [],
  onAction
}: RecommendationCardProps) {
  const [open, setOpen] = useState(false);
  const pct = Math.round((confidence || 0) * 100);
  const resolvedPriority = priority || derivePriority(action, confidence);

  return (
    <section className="rounded-lg border border-gray-100 bg-white shadow-sm">
      <div className="border-l-4 border-brand-orange p-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="flex items-center gap-2">
            <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-brand-orange/10 text-brand-orange">
              <Sparkles size={17} />
            </span>
            <h3 className="text-base font-bold text-gray-900">{title}</h3>
          </div>
          <div className="flex items-center gap-2">
            <span className={`rounded-full px-2.5 py-1 text-xs font-bold ${PRIORITY_STYLE[resolvedPriority]}`}>
              {resolvedPriority}
            </span>
            <span className="inline-flex items-center gap-1 rounded-full bg-green-50 px-2.5 py-1 text-xs font-bold text-green-700">
              <ArrowUpRight size={12} />
              {pct}%
            </span>
          </div>
        </div>

        <p className="mt-3 text-sm leading-6 text-gray-700">{reasoning}</p>

        <div className="mt-3 flex flex-wrap items-center gap-2">
          <span className="rounded bg-gray-900 px-2 py-1 text-[10px] font-bold uppercase tracking-wide text-white">
            {role}
          </span>
        </div>

        {keyDataPoints.length > 0 && (
          <div className="mt-4">
            <button
              onClick={() => setOpen((v) => !v)}
              className="inline-flex items-center gap-1 text-xs font-bold uppercase tracking-wide text-gray-500 hover:text-gray-800"
            >
              {open ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
              Evidence ({keyDataPoints.length})
            </button>
            {open && (
              <ul className="mt-2 space-y-1.5">
                {keyDataPoints.slice(0, 8).map((p, i) => (
                  <li key={`${p.label}-${i}`} className="rounded-md border border-gray-100 bg-gray-50 px-3 py-2 text-sm">
                    <span className="font-semibold text-gray-900">{p.label}</span>
                    <span className="text-gray-700"> — {formatValue(p.value)}</span>
                    {p.source_table && (
                      <span className="ml-2 text-xs text-gray-400">
                        {p.source_table}
                        {p.source_column ? `.${p.source_column}` : ""}
                      </span>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}

        <button
          onClick={onAction}
          className="mt-4 inline-flex items-center gap-2 rounded bg-brand-orange px-4 py-2.5 text-sm font-bold text-white hover:bg-brand-orangeDark"
        >
          {action || "Take action"}
          <ArrowUpRight size={16} />
        </button>
      </div>
    </section>
  );
}
