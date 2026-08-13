"use client";

/**
 * StreamingInsightPanel — replaces V1's static "Answer summary" box.
 *
 * Presentational: the page owns the SSE connection and feeds this panel step
 * state + streamed text. Helpers (initialSteps / applySSE) live here so the
 * event->UI mapping stays colocated with the 6-step tracker.
 *
 * Shows: live 6-step pipeline (green when done, blue when active, grey pending,
 * dashed when skipped by cache) with per-step time_ms; word-by-word streaming
 * answer with a "Thinking..." indicator; ⚡ cache badge; colour-coded
 * confidence badge; Copy answer; and a "View full evidence" link.
 */
import { useState } from "react";
import { Check, Copy, FileSearch, Loader2, Zap } from "lucide-react";
import { confidenceTone, formatMs, type SSEEvent } from "@/services/apiV2";

export type StepStatus = "pending" | "active" | "done" | "skipped";

export interface StepState {
  key: string;
  label: string;
  status: StepStatus;
  ms?: number;
}

const STEP_DEFS: { key: string; label: string }[] = [
  { key: "context", label: "Context retrieved" },
  { key: "sql_generated", label: "SQL generated" },
  { key: "sql_validated", label: "SQL validated" },
  { key: "sql_executed", label: "SQL executed" },
  { key: "result_validated", label: "Result validated" },
  { key: "insight", label: "Insight generated" }
];

export function initialSteps(): StepState[] {
  return STEP_DEFS.map((d, i) => ({ ...d, status: i === 0 ? "pending" : "pending" }));
}

function set(steps: StepState[], key: string, status: StepStatus, ms?: number): StepState[] {
  return steps.map((s) => (s.key === key ? { ...s, status, ms: ms ?? s.ms } : s));
}

function activateNextPending(steps: StepState[]): StepState[] {
  const idx = steps.findIndex((s) => s.status === "pending");
  if (idx === -1) return steps;
  return steps.map((s, i) => (i === idx ? { ...s, status: "active" } : s));
}

/** Fold one SSE event into the 6-step tracker state. */
export function applySSE(steps: StepState[], event: SSEEvent): StepState[] {
  let next = [...steps];
  switch (event.step) {
    case "context_retrieved":
      next = set(next, "context", "done", event.time_ms);
      next = activateNextPending(next);
      break;
    case "cache_hit":
      // Cache short-circuits SQL + execution; insight comes straight from cache.
      next = set(next, "sql_generated", "skipped");
      next = set(next, "sql_validated", "skipped");
      next = set(next, "sql_executed", "skipped");
      next = set(next, "result_validated", "skipped");
      next = set(next, "insight", "active");
      break;
    case "sql_generated":
      next = set(next, "sql_generated", "done", event.time_ms);
      if (event.validation_status === "validated") next = set(next, "sql_validated", "done", 0);
      else next = set(next, "sql_validated", "active");
      if (next.find((s) => s.key === "sql_executed")?.status === "pending")
        next = set(next, "sql_executed", "active");
      break;
    case "sql_executed":
      if (event.status === "executed") {
        // Execution implies validation passed.
        next = set(next, "sql_validated", "done");
        next = set(next, "sql_executed", "done", event.time_ms);
        next = set(next, "result_validated", "done");
        next = set(next, "insight", "active");
      } else {
        next = set(next, "sql_executed", "done", event.time_ms); // done-but-failed; surfaced via banner
      }
      break;
    case "complete":
      next = next.map((s) => (s.status === "active" || s.status === "pending" ? { ...s, status: "done" } : s));
      if (event.metadata?.step_latencies?.insight_ms !== undefined) {
        next = set(next, "insight", "done", event.metadata.step_latencies.insight_ms);
      }
      break;
    default:
      break;
  }
  return next;
}

function StepCircle({ step }: { step: StepState }) {
  const base = "flex h-9 w-9 items-center justify-center rounded-full border-2 text-sm font-bold";
  const idx = STEP_DEFS.findIndex((d) => d.key === step.key) + 1;
  if (step.status === "done")
    return <div className={`${base} border-green-500 bg-green-500 text-white`}><Check size={16} /></div>;
  if (step.status === "active")
    return <div className={`${base} border-blue-500 bg-blue-50 text-blue-600`}><Loader2 size={15} className="animate-spin" /></div>;
  if (step.status === "skipped")
    return <div className={`${base} border-dashed border-brand-yellow text-brand-orangeDark`}><Zap size={14} /></div>;
  return <div className={`${base} border-gray-300 bg-white text-gray-400`}>{idx}</div>;
}

export interface StreamingInsightPanelProps {
  steps: StepState[];
  answer: string;
  status: "idle" | "running" | "done" | "error";
  cacheHit?: boolean;
  cacheSimilarity?: number;
  confidence?: number;
  queryId?: string;
  errorMessage?: string;
  onViewEvidence?: (queryId: string) => void;
}

export default function StreamingInsightPanel({
  steps,
  answer,
  status,
  cacheHit = false,
  cacheSimilarity,
  confidence,
  queryId,
  errorMessage,
  onViewEvidence
}: StreamingInsightPanelProps) {
  const [copied, setCopied] = useState(false);
  const activeStep = steps.find((s) => s.status === "active");

  async function copyAnswer() {
    try {
      await navigator.clipboard.writeText(answer);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      /* ignore */
    }
  }

  const tone = confidence !== undefined ? confidenceTone(confidence) : null;
  const toneClass =
    tone === "green"
      ? "bg-green-50 text-green-700"
      : tone === "amber"
        ? "bg-amber-50 text-amber-700"
        : "bg-brand-rose/10 text-brand-rose";

  return (
    <section className="rounded-lg border border-gray-100 bg-white p-5 shadow-sm">
      {/* header row */}
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <h3 className="text-base font-bold text-gray-900">Answer</h3>
          {cacheHit && (
            <span className="inline-flex items-center gap-1 rounded-full bg-brand-yellow/20 px-2.5 py-1 text-xs font-bold text-brand-orangeDark">
              <Zap size={12} /> Answered from semantic cache
              {typeof cacheSimilarity === "number" ? ` · ${(cacheSimilarity * 100).toFixed(0)}%` : ""}
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          {confidence !== undefined && (
            <span className={`rounded-full px-2.5 py-1 text-xs font-bold ${toneClass}`}>
              Confidence {Math.round(confidence * 100)}%
            </span>
          )}
          <button
            onClick={copyAnswer}
            disabled={!answer}
            className="inline-flex items-center gap-1 rounded border border-gray-200 px-2.5 py-1 text-xs font-bold text-gray-600 hover:bg-gray-50 disabled:opacity-40"
          >
            {copied ? <Check size={12} /> : <Copy size={12} />}
            {copied ? "Copied" : "Copy answer"}
          </button>
        </div>
      </div>

      {/* 6-step pipeline */}
      <div className="mt-4 overflow-x-auto thin-scroll">
        <div className="flex min-w-[640px] items-start">
          {steps.map((step, i) => (
            <div key={step.key} className="flex flex-1 items-start">
              <div className="flex flex-col items-center text-center" style={{ minWidth: 92 }}>
                <StepCircle step={step} />
                <span className="mt-1.5 text-[11px] font-semibold leading-tight text-gray-700">{step.label}</span>
                <span className="mt-0.5 h-3 text-[10px] font-mono text-gray-400">
                  {step.status === "done" && step.ms !== undefined ? formatMs(step.ms) : step.status === "skipped" ? "skipped" : ""}
                </span>
              </div>
              {i < steps.length - 1 && (
                <div className={`mt-4 h-0.5 flex-1 ${step.status === "done" ? "bg-green-400" : step.status === "skipped" ? "bg-brand-yellow/50" : "bg-gray-200"}`} />
              )}
            </div>
          ))}
        </div>
      </div>

      {/* thinking indicator */}
      {status === "running" && activeStep && (
        <div className="mt-4 flex items-center gap-2 text-sm font-medium text-blue-600">
          <Loader2 size={15} className="animate-spin" />
          <span>Thinking — {activeStep.label.toLowerCase()}</span>
          <span className="flex gap-0.5">
            <span className="h-1.5 w-1.5 rounded-full bg-blue-500 animate-pulse-dot" />
            <span className="h-1.5 w-1.5 rounded-full bg-blue-500 animate-pulse-dot [animation-delay:0.2s]" />
            <span className="h-1.5 w-1.5 rounded-full bg-blue-500 animate-pulse-dot [animation-delay:0.4s]" />
          </span>
        </div>
      )}

      {/* error */}
      {status === "error" && (
        <div className="mt-4 flex items-start gap-2 rounded-md border border-amber-200 bg-amber-50 px-3 py-2.5 text-sm text-amber-800">
          <span className="font-semibold">Could not complete the answer.</span>
          <span>{errorMessage}</span>
        </div>
      )}

      {/* streamed answer */}
      <div className="mt-4 rounded-lg border border-brand-orange/15 bg-brand-orange/5 p-4">
        {answer ? (
          <p className="whitespace-pre-wrap text-sm leading-7 text-gray-800">
            {answer}
            {status === "running" && <span className="ml-0.5 inline-block h-4 w-1.5 -translate-y-px animate-pulse-dot bg-brand-orange align-middle" />}
          </p>
        ) : (
          <p className="text-sm text-gray-400">
            {status === "running" ? "Generating a SQL-backed business answer…" : "Ask a question to generate a streamed, SQL-backed answer."}
          </p>
        )}
      </div>

      {/* evidence link */}
      {status === "done" && queryId && (
        <div className="mt-3">
          <button
            onClick={() => onViewEvidence?.(queryId)}
            className="inline-flex items-center gap-1.5 text-sm font-semibold text-brand-orange hover:text-brand-orangeDark"
          >
            <FileSearch size={15} />
            View full evidence
          </button>
        </div>
      )}
    </section>
  );
}
