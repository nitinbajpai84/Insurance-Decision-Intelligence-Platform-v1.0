"use client";

/**
 * InsightEvidenceHubV2 — major upgrade over V1's Evidence Hub.
 *
 * Mode A (default): history browser of the last 20 queries from
 *   GET /api/v2/evidence/recent — click any row to open its full trace.
 * Mode B: full evidence for one query_id (backwards compatible with V1's
 *   insight_id input) — 4-column architecture view + V2 additions
 *   (agent reasoning trace, token budget breakdown, cache status, latency
 *   waterfall).
 */
import { useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { Bar, BarChart, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Cpu, Database, FileSearch, Layers, Loader2, Sparkles, Zap } from "lucide-react";
import {
  formatMs,
  getEvidence,
  getRecentEvidence,
  type EvidenceTrace,
  type RecentTrace,
  type TraceStep
} from "@/services/apiV2";

const AGENT_SHORT: Record<string, string> = {
  context_agent: "Context",
  sql_agent: "SQL",
  execution_agent: "Execution",
  insight_agent: "Insight",
  semantic_cache: "Cache"
};

function shortAgent(name: string): string {
  return AGENT_SHORT[name] || name;
}

function stepByAgent(steps: TraceStep[], agent: string): TraceStep | undefined {
  return steps.find((s) => s.agent_name === agent);
}

function parseContextCounts(out: string | undefined): { schema: number; glossary: number; docs: number; cache: string } {
  const grab = (k: string) => {
    const m = (out || "").match(new RegExp(`${k}=([0-9]+)`));
    return m ? Number(m[1]) : 0;
  };
  const cacheM = (out || "").match(/cache_hit=(\w+)/i);
  return { schema: grab("schema"), glossary: grab("glossary"), docs: grab("docs"), cache: cacheM ? cacheM[1] : "False" };
}

function parseTables(out: string | undefined): string[] {
  const m = (out || "").match(/tables=\[([^\]]*)\]/);
  if (!m) return [];
  return m[1]
    .split(",")
    .map((t) => t.replace(/['"\s]/g, ""))
    .filter(Boolean);
}

const BRAND_COLORS = ["#3454D1", "#5B7CE0", "#D97706", "#F5A623", "#0F172A"];

export default function InsightEvidenceHubV2() {
  const searchParams = useSearchParams();
  const initialId = searchParams.get("insight_id") || "";

  const [insightId, setInsightId] = useState(initialId);
  const [recent, setRecent] = useState<RecentTrace[]>([]);
  const [trace, setTrace] = useState<EvidenceTrace | null>(null);
  const [loadingRecent, setLoadingRecent] = useState(true);
  const [loadingTrace, setLoadingTrace] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    void refreshRecent();
    if (initialId) void loadTrace(initialId);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function refreshRecent() {
    setLoadingRecent(true);
    try {
      setRecent(await getRecentEvidence(20));
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoadingRecent(false);
    }
  }

  async function loadTrace(id: string) {
    if (!id.trim()) return;
    setLoadingTrace(true);
    setError("");
    try {
      const t = await getEvidence(id.trim());
      setTrace(t);
      setInsightId(id.trim());
    } catch (err) {
      setError((err as Error).message || "No trace found for that query_id.");
      setTrace(null);
    } finally {
      setLoadingTrace(false);
    }
  }

  const steps = trace?.steps || [];
  const ctx = parseContextCounts(stepByAgent(steps, "context_agent")?.output_summary);
  const tables = parseTables(stepByAgent(steps, "sql_agent")?.output_summary);
  const insightOut = stepByAgent(steps, "insight_agent")?.output_summary || "";
  const questionText = stepByAgent(steps, "context_agent")?.input_summary || "";

  const latencyData = steps.map((s) => ({ name: shortAgent(s.agent_name), ms: s.duration_ms }));
  const tokenData = steps.filter((s) => s.tokens_used > 0).map((s) => ({ name: shortAgent(s.agent_name), tokens: s.tokens_used }));

  return (
    <div className="mx-auto w-full max-w-[1500px] px-4 py-6 sm:px-6 lg:px-8">
      <p className="text-xs font-bold uppercase tracking-wide text-brand-orange">Business workspace</p>
      <h1 className="mt-1 text-2xl font-bold text-gray-900">Insight Evidence Hub</h1>
      <p className="mt-1 max-w-3xl text-sm text-gray-500">
        Browse recent queries or load any query_id to trace its full agent reasoning, context, SQL, and latency.
      </p>

      {/* loader bar */}
      <section className="mt-5 rounded-lg border border-gray-100 bg-white p-5 shadow-sm">
        <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
          <div className="flex-1">
            <label className="text-xs font-semibold uppercase tracking-wide text-gray-500">Load by query_id (insight_id)</label>
            <div className="mt-2 flex gap-2">
              <input
                value={insightId}
                onChange={(e) => setInsightId(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && loadTrace(insightId)}
                placeholder="query_id from AI Intelligence"
                className="h-11 flex-1 rounded-lg border border-gray-200 px-3 text-sm outline-none focus:border-brand-orange focus:ring-2 focus:ring-brand-orange/20"
              />
              <button
                onClick={() => loadTrace(insightId)}
                disabled={loadingTrace}
                className="inline-flex h-11 items-center gap-2 rounded-lg bg-brand-orange px-4 text-sm font-bold text-white hover:bg-brand-orangeDark disabled:opacity-60"
              >
                {loadingTrace ? <Loader2 size={16} className="animate-spin" /> : <FileSearch size={16} />}
                Load Evidence
              </button>
            </div>
          </div>
        </div>
        {error && <p className="mt-3 rounded-md bg-amber-50 px-3 py-2 text-sm text-amber-800">{error}</p>}
      </section>

      {/* Mode A — history browser */}
      {!trace && (
        <section className="mt-5 rounded-lg border border-gray-100 bg-white shadow-sm">
          <div className="border-b border-gray-100 px-5 py-4">
            <h3 className="text-base font-bold text-gray-900">Recent queries</h3>
            <p className="text-sm text-gray-500">Click a row to open its full evidence trace.</p>
          </div>
          {loadingRecent ? (
            <p className="p-6 text-center text-sm text-gray-400">Loading history…</p>
          ) : recent.length === 0 ? (
            <p className="p-6 text-center text-sm text-gray-400">No queries recorded yet. Ask a question in AI Intelligence.</p>
          ) : (
            <div className="thin-scroll overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-xs uppercase tracking-wide text-gray-500">
                    <th className="px-5 py-2 font-semibold">Question</th>
                    <th className="px-3 py-2 font-semibold">Steps</th>
                    <th className="px-3 py-2 font-semibold">Latency</th>
                    <th className="px-3 py-2 font-semibold">Tokens</th>
                    <th className="px-3 py-2 font-semibold">Cache</th>
                    <th className="px-3 py-2 font-semibold">When</th>
                  </tr>
                </thead>
                <tbody>
                  {recent.map((r) => (
                    <tr
                      key={r.query_id}
                      onClick={() => loadTrace(r.query_id)}
                      className="cursor-pointer border-t border-gray-100 hover:bg-brand-orange/5"
                    >
                      <td className="max-w-md truncate px-5 py-3 font-semibold text-gray-900">{r.question || r.query_id}</td>
                      <td className="px-3 py-3 text-gray-600">{r.steps}</td>
                      <td className="px-3 py-3 font-mono text-gray-600">{formatMs(r.total_duration_ms)}</td>
                      <td className="px-3 py-3 font-mono text-gray-600">{r.total_tokens}</td>
                      <td className="px-3 py-3">
                        {r.any_cache_hit ? (
                          <span className="inline-flex items-center gap-1 rounded-full bg-brand-yellow/20 px-2 py-0.5 text-xs font-bold text-brand-orangeDark">
                            <Zap size={11} /> hit
                          </span>
                        ) : (
                          <span className="rounded-full bg-gray-100 px-2 py-0.5 text-xs font-semibold text-gray-500">miss</span>
                        )}
                      </td>
                      <td className="px-3 py-3 text-gray-500">
                        {r.finished_at ? new Date(r.finished_at).toLocaleString() : "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      )}

      {/* Mode B — full evidence trace */}
      {trace && (
        <div className="mt-5 space-y-5">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs font-semibold uppercase tracking-wide text-gray-500">Query</p>
              <h3 className="text-base font-bold text-gray-900">{questionText || trace.query_id}</h3>
              <p className="font-mono text-xs text-gray-400">{trace.query_id}</p>
            </div>
            <button
              onClick={() => {
                setTrace(null);
                void refreshRecent();
              }}
              className="rounded-lg border border-gray-200 px-3 py-2 text-sm font-semibold text-gray-600 hover:bg-gray-50"
            >
              ← Back to history
            </button>
          </div>

          {/* summary chips */}
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <Stat label="Agents" value={String(trace.agents_involved.length)} />
            <Stat label="Total latency" value={formatMs(trace.total_duration_ms)} />
            <Stat label="Total tokens" value={String(trace.total_tokens)} />
            <Stat label="Cache" value={trace.cache_hit ? "Hit ⚡" : "Miss"} />
          </div>

          {/* GROUNDING — metric bindings + traversal + validation (Prompt 19-D) */}
          <GroundingPanel steps={steps} />

          {/* 4-column architecture view */}
          <div className="grid gap-4 lg:grid-cols-4">
            <ArchCol icon={<Database size={15} />} title="DuckDB Tables" tint="bg-brand-orange/10 text-brand-orange">
              {tables.length ? (
                <ul className="space-y-1">
                  {tables.map((t) => (
                    <li key={t} className="font-mono text-xs text-gray-700">{t}</li>
                  ))}
                </ul>
              ) : (
                <p className="text-xs text-gray-400">No tables parsed from SQL agent trace.</p>
              )}
            </ArchCol>
            <ArchCol icon={<Sparkles size={15} />} title="Model Layer" tint="bg-brand-tangerine/10 text-brand-tangerine">
              <ul className="space-y-1 text-xs text-gray-700">
                <li>Gemini (generation)</li>
                <li>gemini-embedding-001</li>
                <li className="text-gray-400">Vector recall over LanceDB</li>
              </ul>
            </ArchCol>
            <ArchCol icon={<Layers size={15} />} title="Context Layer" tint="bg-brand-yellow/15 text-brand-orangeDark">
              <ul className="space-y-1 text-xs text-gray-700">
                <li>Schema items: {ctx.schema}</li>
                <li>Glossary terms: {ctx.glossary}</li>
                <li>Semantic docs: {ctx.docs}</li>
                <li className="text-gray-400">cache_hit={ctx.cache}</li>
              </ul>
            </ArchCol>
            <ArchCol icon={<Cpu size={15} />} title="AI Layer" tint="bg-gray-100 text-gray-700">
              <p className="text-xs leading-5 text-gray-700">{insightOut || "No insight summary captured."}</p>
            </ArchCol>
          </div>

          {/* charts */}
          <div className="grid gap-4 lg:grid-cols-2">
            <ChartCard title="Latency waterfall (per agent)">
              <ResponsiveContainer width="100%" height={220}>
                <BarChart data={latencyData} margin={{ top: 8, right: 12, bottom: 4, left: 4 }}>
                  <XAxis dataKey="name" tick={{ fontSize: 12 }} />
                  <YAxis tick={{ fontSize: 11 }} unit="ms" width={48} />
                  <Tooltip formatter={(v) => `${Number(v)} ms`} />
                  <Bar dataKey="ms" radius={[4, 4, 0, 0]}>
                    {latencyData.map((_, i) => (
                      <Cell key={i} fill={BRAND_COLORS[i % BRAND_COLORS.length]} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </ChartCard>
            <ChartCard title="Token budget by agent">
              {tokenData.length ? (
                <ResponsiveContainer width="100%" height={220}>
                  <BarChart data={tokenData} margin={{ top: 8, right: 12, bottom: 4, left: 4 }}>
                    <XAxis dataKey="name" tick={{ fontSize: 12 }} />
                    <YAxis tick={{ fontSize: 11 }} width={48} />
                    <Tooltip formatter={(v) => `${Number(v)} tokens`} />
                    <Bar dataKey="tokens" radius={[4, 4, 0, 0]}>
                      {tokenData.map((_, i) => (
                        <Cell key={i} fill={BRAND_COLORS[(i + 1) % BRAND_COLORS.length]} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              ) : (
                <p className="flex h-[220px] items-center justify-center text-sm text-gray-400">No token usage recorded.</p>
              )}
            </ChartCard>
          </div>

          {/* agent reasoning trace */}
          <section className="rounded-lg border border-gray-100 bg-white shadow-sm">
            <div className="border-b border-gray-100 px-5 py-4">
              <h3 className="text-base font-bold text-gray-900">Agent reasoning trace</h3>
              <p className="text-sm text-gray-500">Each agent in execution order, with timing, tokens, and output.</p>
            </div>
            <ol className="divide-y divide-gray-100">
              {steps.map((s, i) => (
                <li key={s.id ?? i} className="flex gap-4 px-5 py-3.5">
                  <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-brand-orange text-xs font-bold text-white">
                    {i + 1}
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <span className="font-semibold text-gray-900">{shortAgent(s.agent_name)}</span>
                      <span className="flex items-center gap-3 font-mono text-xs text-gray-500">
                        <span>{formatMs(s.duration_ms)}</span>
                        <span>{s.tokens_used} tok</span>
                        {s.cache_hit && <span className="text-brand-orangeDark">⚡ cache</span>}
                      </span>
                    </div>
                    <p className="mt-0.5 break-words text-sm text-gray-600">{s.output_summary}</p>
                  </div>
                </li>
              ))}
            </ol>
          </section>
        </div>
      )}
    </div>
  );
}

function GroundingPanel({ steps }: { steps: TraceStep[] }) {
  const g = steps.find((s) => s.agent_name === "graph_sql_agent");
  const legacy = steps.find((s) => s.agent_name === "sql_agent");
  if (!g && !legacy) return null;

  // ungoverned / unsupported signals from the trace text
  if (g && /ungoverned fallback/i.test(g.output_summary)) {
    return (
      <section className="rounded-lg border border-amber-200 bg-amber-50 p-5">
        <h3 className="text-base font-bold text-amber-900">⚠ Ungoverned answer</h3>
        <p className="mt-1 text-sm text-amber-800">No sanctioned metric matched — the legacy free-SQL agent answered. Not validated against the semantic model.</p>
      </section>
    );
  }
  if (g && /unsupported/i.test(g.output_summary)) {
    return (
      <section className="rounded-lg border border-gray-200 bg-gray-50 p-5">
        <h3 className="text-base font-bold text-gray-900">Refused (no sanctioned metric)</h3>
        <p className="mt-1 text-sm text-gray-600">The graph-grounded agent found no governed metric for this question and produced no SQL.</p>
      </section>
    );
  }
  if (!g) {
    return (
      <section className="rounded-lg border border-gray-200 bg-gray-50 p-4 text-sm text-gray-600">
        Legacy SQL agent (ungoverned) — this answer was not produced under the graph-grounded contract.
      </section>
    );
  }

  const out = g.output_summary || "";
  const grab = (re: RegExp) => {
    const m = out.match(re);
    return m ? m[1] : "";
  };
  const list = (raw: string) =>
    raw.replace(/[[\]']/g, "").split(",").map((x) => x.trim()).filter(Boolean);
  const metrics = list(grab(/metrics=\[([^\]]*)\]/));
  const bindings = list(grab(/bindings=\[([^\]]*)\]/));
  const rules = list(grab(/rules=\[([^\]]*)\]/));
  const validated = /validated=True/i.test(out);
  const repaired = /repaired=True/i.test(out);

  return (
    <section className="rounded-lg border border-green-200 bg-green-50/40 p-5">
      <div className="flex items-center gap-2">
        <span className="rounded-full bg-green-600 px-2.5 py-1 text-xs font-bold text-white">✓ Governed answer</span>
        <span className="text-sm text-gray-600">grounded in the semantic model</span>
      </div>
      <div className="mt-3 grid gap-4 md:grid-cols-3">
        <div>
          <p className="text-[11px] font-bold uppercase tracking-wide text-gray-500">Metrics used</p>
          {metrics.length ? (
            <ul className="mt-1 space-y-0.5 text-sm text-gray-800">
              {metrics.slice(0, 8).map((m) => <li key={m} className="font-semibold">{m.replace("metric::", "")}</li>)}
            </ul>
          ) : <p className="text-sm text-gray-400">—</p>}
        </div>
        <div>
          <p className="text-[11px] font-bold uppercase tracking-wide text-gray-500">Bindings</p>
          <p className="mt-1 text-sm text-gray-700">{bindings.length} metric binding(s) applied</p>
          <p className="mt-2 text-[11px] font-bold uppercase tracking-wide text-gray-500">Validation</p>
          <p className={`mt-1 text-sm font-semibold ${validated ? "text-green-700" : "text-brand-rose"}`}>
            {validated ? "Validated against contract" : "Refused (off-contract)"}{repaired ? " · auto-repaired" : ""}
          </p>
        </div>
        <div>
          <p className="text-[11px] font-bold uppercase tracking-wide text-gray-500">Applicable rules</p>
          {rules.length ? (
            <ul className="mt-1 space-y-0.5 text-sm text-gray-800">{rules.slice(0, 5).map((r) => <li key={r}>{r}</li>)}</ul>
          ) : <p className="text-sm text-gray-400">none</p>}
        </div>
      </div>
    </section>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-gray-100 bg-white p-4 shadow-sm">
      <p className="text-xs font-semibold uppercase tracking-wide text-gray-500">{label}</p>
      <p className="mt-1 text-2xl font-bold text-gray-900">{value}</p>
    </div>
  );
}

function ArchCol({
  icon,
  title,
  tint,
  children
}: {
  icon: React.ReactNode;
  title: string;
  tint: string;
  children: React.ReactNode;
}) {
  return (
    <div className="rounded-lg border border-gray-100 bg-white p-4 shadow-sm">
      <div className="mb-3 flex items-center gap-2">
        <span className={`flex h-7 w-7 items-center justify-center rounded-lg ${tint}`}>{icon}</span>
        <h4 className="text-sm font-bold text-gray-900">{title}</h4>
      </div>
      {children}
    </div>
  );
}

function ChartCard({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="rounded-lg border border-gray-100 bg-white p-5 shadow-sm">
      <h3 className="mb-3 text-sm font-bold text-gray-900">{title}</h3>
      {children}
    </section>
  );
}
