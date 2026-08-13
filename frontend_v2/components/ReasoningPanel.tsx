"use client";

/**
 * ReasoningPanel — collapsible (collapsed by default) panel shown below every
 * answer. Opens to reveal which agents ran + their timings, the context
 * sources used, cache vs fresh provenance, the raw SQL, and a parallel-vs-
 * sequential execution indicator.
 */
import { useState } from "react";
import { ChevronDown, ChevronUp, Cpu, GitBranch, Layers, Zap } from "lucide-react";
import SqlBlock from "@/components/SqlBlock";
import { formatMs, type GlossaryContextItem, type SchemaContextItem, type SemanticDocItem } from "@/services/apiV2";

export interface AgentTiming {
  name: string;
  ms: number;
}

export interface ReasoningPanelProps {
  agentTimings: AgentTiming[];
  schema: SchemaContextItem[];
  glossary: GlossaryContextItem[];
  docs: SemanticDocItem[];
  sql: string;
  cacheHit: boolean;
  parallel: boolean;
  defaultOpen?: boolean;
}

const AGENT_LABEL: Record<string, string> = {
  context_ms: "Context agent",
  sql_generation_ms: "SQL agent",
  execution_ms: "Execution agent",
  insight_ms: "Insight agent"
};

export function timingsFromStepLatencies(step: Record<string, number>): AgentTiming[] {
  const order = ["context_ms", "sql_generation_ms", "execution_ms", "insight_ms"];
  return order.filter((k) => k in step).map((k) => ({ name: AGENT_LABEL[k] || k, ms: step[k] }));
}

export default function ReasoningPanel({
  agentTimings,
  schema,
  glossary,
  docs,
  sql,
  cacheHit,
  parallel,
  defaultOpen = false
}: ReasoningPanelProps) {
  const [open, setOpen] = useState(defaultOpen);
  const totalMs = agentTimings.reduce((sum, a) => sum + (a.ms || 0), 0);

  return (
    <section className="rounded-lg border border-gray-100 bg-white shadow-sm">
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between px-5 py-3.5 text-left"
      >
        <span className="flex items-center gap-2 text-sm font-bold text-gray-800">
          <Cpu size={16} className="text-brand-orange" />
          Agent reasoning
          <span className="rounded-full bg-gray-100 px-2 py-0.5 text-xs font-semibold text-gray-500">
            {agentTimings.length} agents · {formatMs(totalMs)}
          </span>
        </span>
        {open ? <ChevronUp size={16} className="text-gray-400" /> : <ChevronDown size={16} className="text-gray-400" />}
      </button>

      {open && (
        <div className="space-y-5 border-t border-gray-100 px-5 py-4">
          {/* provenance chips */}
          <div className="flex flex-wrap gap-2">
            <span
              className={`inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-bold ${
                cacheHit ? "bg-brand-yellow/20 text-brand-orangeDark" : "bg-green-50 text-green-700"
              }`}
            >
              <Zap size={12} />
              {cacheHit ? "Served from semantic cache" : "Fresh run"}
            </span>
            <span
              className={`inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-bold ${
                parallel ? "bg-brand-orange/10 text-brand-orange" : "bg-gray-100 text-gray-600"
              }`}
            >
              <GitBranch size={12} />
              {parallel ? "Parallel execution" : "Sequential execution"}
            </span>
          </div>

          {/* agent timings */}
          <div>
            <p className="mb-2 text-xs font-bold uppercase tracking-wide text-gray-500">Agents &amp; timings</p>
            <div className="space-y-1.5">
              {agentTimings.map((a) => {
                const pct = totalMs > 0 ? Math.max(3, Math.round((a.ms / totalMs) * 100)) : 0;
                return (
                  <div key={a.name} className="flex items-center gap-3">
                    <span className="w-32 shrink-0 text-sm font-medium text-gray-700">{a.name}</span>
                    <div className="h-2.5 flex-1 overflow-hidden rounded-full bg-gray-100">
                      <div className="h-full rounded-full bg-brand-orange" style={{ width: `${pct}%` }} />
                    </div>
                    <span className="w-14 shrink-0 text-right font-mono text-xs text-gray-500">{formatMs(a.ms)}</span>
                  </div>
                );
              })}
            </div>
          </div>

          {/* context sources */}
          <div className="grid gap-4 md:grid-cols-3">
            <div>
              <p className="mb-1 flex items-center gap-1 text-xs font-bold uppercase tracking-wide text-gray-500">
                <Layers size={12} /> Glossary
              </p>
              {glossary.length === 0 ? (
                <p className="text-sm text-gray-400">None</p>
              ) : (
                <ul className="space-y-1 text-sm text-gray-700">
                  {glossary.slice(0, 6).map((g, i) => (
                    <li key={`${g.term}-${i}`}>
                      <span className="font-semibold text-gray-900">{g.term}</span>
                      {g.definition ? ` — ${g.definition}` : ""}
                    </li>
                  ))}
                </ul>
              )}
            </div>
            <div>
              <p className="mb-1 text-xs font-bold uppercase tracking-wide text-gray-500">Semantic docs</p>
              {docs.length === 0 ? (
                <p className="text-sm text-gray-400">None</p>
              ) : (
                <ul className="space-y-1 text-sm text-gray-700">
                  {docs.slice(0, 6).map((d, i) => (
                    <li key={`${d.title}-${i}`} className="flex items-center justify-between gap-2">
                      <span>{d.title}</span>
                      {typeof d.score === "number" && <span className="text-xs text-gray-400">{d.score.toFixed(2)}</span>}
                    </li>
                  ))}
                </ul>
              )}
            </div>
            <div>
              <p className="mb-1 text-xs font-bold uppercase tracking-wide text-gray-500">Schema tables</p>
              {schema.length === 0 ? (
                <p className="text-sm text-gray-400">None</p>
              ) : (
                <ul className="space-y-1 text-sm text-gray-700">
                  {schema.slice(0, 8).map((s, i) => (
                    <li key={`${s.table}.${s.column}-${i}`} className="font-mono text-xs">
                      {s.table}.{s.column}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>

          {/* raw SQL */}
          <div>
            <p className="mb-2 text-xs font-bold uppercase tracking-wide text-gray-500">Generated SQL</p>
            <SqlBlock sql={sql} maxHeight="16rem" />
          </div>
        </div>
      )}
    </section>
  );
}
