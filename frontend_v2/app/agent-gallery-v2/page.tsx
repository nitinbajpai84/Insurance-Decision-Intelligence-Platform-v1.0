"use client";

/**
 * Agent Gallery — all 46 playbook initiatives as browsable agents.
 *
 * Per docs/context-layer/DESIGN.md D1: every initiative is visible (the registry
 * IS the demo of the context layer); `status` separates a browsable charter from
 * an agent you can actually talk to. Selecting one opens its profile; functional
 * agents additionally get a multi-turn chat panel.
 */
import { useEffect, useMemo, useState } from "react";
import {
  fetchAgent,
  fetchAgents,
  streamAgentAsk,
  type AgentDetail,
  type AgentListResponse,
  type InitiativeCard,
  type PlatformAgent
} from "@/services/agentApi";

type Turn = { role: "user" | "agent"; content: string };

const DOMAIN_STYLE: Record<string, string> = {
  Health: "bg-emerald-50 text-emerald-700 border-emerald-200",
  Operations: "bg-sky-50 text-sky-700 border-sky-200",
  Agency: "bg-amber-50 text-amber-700 border-amber-200"
};

function StatusPill({ status }: { status: string | null }) {
  const live = status === "functional" || status === "live";
  return (
    <span
      className={`rounded-full border px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide ${
        live ? "border-pwc-orange/30 bg-pwc-orange/10 text-pwc-orange" : "border-gray-200 bg-gray-50 text-gray-500"
      }`}
    >
      {live ? "Talkable" : "Registered"}
    </span>
  );
}

export default function AgentGalleryPage() {
  const [data, setData] = useState<AgentListResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [domain, setDomain] = useState<string>("All");
  const [phase, setPhase] = useState<string>("All");
  const [onlyTalkable, setOnlyTalkable] = useState(false);
  const [search, setSearch] = useState("");

  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detail, setDetail] = useState<AgentDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  const [turns, setTurns] = useState<Turn[]>([]);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [question, setQuestion] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [sql, setSql] = useState<string | null>(null);
  const [chatError, setChatError] = useState<string | null>(null);

  useEffect(() => {
    fetchAgents().then(setData).catch((e) => setError(String(e)));
  }, []);

  useEffect(() => {
    if (!selectedId) return;
    setDetailLoading(true);
    setDetail(null);
    setTurns([]);
    setConversationId(null);
    setSql(null);
    setChatError(null);
    fetchAgent(selectedId)
      .then(setDetail)
      .catch((e) => setChatError(String(e)))
      .finally(() => setDetailLoading(false));
  }, [selectedId]);

  const phases = useMemo(() => {
    const set = new Set((data?.initiatives ?? []).map((i) => i.phase).filter(Boolean) as string[]);
    return ["All", ...Array.from(set)];
  }, [data]);

  const filtered = useMemo(() => {
    let list = data?.initiatives ?? [];
    if (domain !== "All") list = list.filter((i) => i.domain === domain);
    if (phase !== "All") list = list.filter((i) => i.phase === phase);
    if (onlyTalkable) list = list.filter((i) => i.status === "functional" || i.status === "live");
    const q = search.trim().toLowerCase();
    if (q) {
      list = list.filter(
        (i) =>
          i.name?.toLowerCase().includes(q) ||
          i.initiative_id?.toLowerCase().includes(q) ||
          i.strategic_goal?.toLowerCase().includes(q)
      );
    }
    return list;
  }, [data, domain, phase, onlyTalkable, search]);

  const grouped = useMemo(() => {
    const out: Record<string, InitiativeCard[]> = {};
    filtered.forEach((i) => {
      (out[i.domain] ||= []).push(i);
    });
    return out;
  }, [filtered]);

  const canChat = detail?.status === "functional" || detail?.status === "live";

  async function send() {
    const q = question.trim();
    if (!q || !detail || streaming) return;
    setQuestion("");
    setChatError(null);
    setSql(null);
    setTurns((t) => [...t, { role: "user", content: q }, { role: "agent", content: "" }]);
    setStreaming(true);
    await streamAgentAsk(detail.agent_id, q, conversationId, {
      onConversation: setConversationId,
      onToken: (tok) =>
        setTurns((t) => {
          const next = [...t];
          next[next.length - 1] = { role: "agent", content: next[next.length - 1].content + tok };
          return next;
        }),
      onSql: setSql,
      onError: (m) => setChatError(m)
    });
    setStreaming(false);
  }

  if (error) {
    return (
      <div className="mx-auto w-full max-w-[1500px] px-4 py-6 sm:px-6 lg:px-8">
        <p className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          Could not load the agent registry: {error}
        </p>
      </div>
    );
  }

  return (
    <div className="mx-auto w-full max-w-[1500px] space-y-5 px-4 py-6 sm:px-6 lg:px-8">
      <header>
        <p className="text-[11px] font-bold uppercase tracking-[0.16em] text-gray-400">Context layer</p>
        <h1 className="text-2xl font-bold text-gray-900">Agent Gallery</h1>
        <p className="mt-1 max-w-3xl text-sm text-gray-600">
          Every initiative in the AI Insurance Playbook, registered against one shared context layer.
          Each agent is a thin composition — skills, knowledge scope and role — over the same ontology,
          metric bindings and governed data. Talkable agents run the existing agentic pipeline.
        </p>
      </header>

      {data && (
        <div className="flex flex-wrap items-center gap-3 rounded-lg border border-gray-100 bg-white p-4 shadow-sm">
          <span className="text-sm font-semibold text-gray-900">
            {data.counts.total} initiatives · {data.counts.functional} talkable
          </span>
          <div className="ml-auto flex flex-wrap items-center gap-2">
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search initiatives"
              className="rounded-lg border border-gray-200 px-3 py-1.5 text-sm outline-none focus:border-pwc-orange"
            />
            <select
              value={domain}
              onChange={(e) => setDomain(e.target.value)}
              className="rounded-lg border border-gray-200 px-2 py-1.5 text-sm"
            >
              {["All", "Health", "Operations", "Agency"].map((d) => (
                <option key={d}>{d}</option>
              ))}
            </select>
            <select
              value={phase}
              onChange={(e) => setPhase(e.target.value)}
              className="rounded-lg border border-gray-200 px-2 py-1.5 text-sm"
            >
              {phases.map((p) => (
                <option key={p}>{p}</option>
              ))}
            </select>
            <label className="flex items-center gap-2 text-sm text-gray-700">
              <input type="checkbox" checked={onlyTalkable} onChange={(e) => setOnlyTalkable(e.target.checked)} />
              Talkable only
            </label>
          </div>
        </div>
      )}

      {data && (
        <section className="rounded-lg border border-gray-100 bg-white p-4 shadow-sm">
          <p className="text-[11px] font-bold uppercase tracking-[0.16em] text-gray-400">Role advisors</p>
          <div className="mt-2 flex flex-wrap gap-2">
            {data.platform_agents.map((a: PlatformAgent) => (
              <button
                key={a.agent_id}
                onClick={() => setSelectedId(a.agent_id)}
                className={`rounded-lg border px-3 py-1.5 text-sm font-semibold transition-colors ${
                  selectedId === a.agent_id
                    ? "border-pwc-orange bg-pwc-orange text-white"
                    : "border-gray-200 text-gray-700 hover:border-pwc-orange hover:text-pwc-orange"
                }`}
              >
                {a.name}
              </button>
            ))}
          </div>
        </section>
      )}

      <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_minmax(0,420px)]">
        <div className="space-y-5">
          {Object.entries(grouped).map(([dom, items]) => (
            <section key={dom} className="rounded-lg border border-gray-100 bg-white p-5 shadow-sm">
              <div className="mb-3 flex items-center gap-2">
                <h2 className="text-sm font-bold text-gray-900">{dom}</h2>
                <span className="text-xs text-gray-500">{items.length}</span>
              </div>
              <div className="grid gap-3 sm:grid-cols-2">
                {items.map((i) => (
                  <button
                    key={i.initiative_id}
                    onClick={() => i.agent_id && setSelectedId(i.agent_id)}
                    className={`rounded-lg border p-3 text-left transition-colors ${
                      selectedId === i.agent_id
                        ? "border-pwc-orange bg-pwc-orange/5"
                        : "border-gray-200 hover:border-pwc-orange/50"
                    }`}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <span className="rounded border border-gray-200 bg-gray-50 px-1.5 py-0.5 text-[10px] font-bold text-gray-600">
                        {i.initiative_id}
                      </span>
                      <StatusPill status={i.status} />
                    </div>
                    <p className="mt-1.5 text-sm font-semibold leading-snug text-gray-900">{i.name}</p>
                    <p className="mt-1 line-clamp-2 text-xs text-gray-600">{i.strategic_goal}</p>
                    <div className="mt-2 flex flex-wrap gap-1">
                      {i.phase && (
                        <span className={`rounded border px-1.5 py-0.5 text-[10px] ${DOMAIN_STYLE[i.domain] ?? ""}`}>
                          {i.phase}
                        </span>
                      )}
                      {(i.model_families ?? []).slice(0, 2).map((f) => (
                        <span key={f} className="rounded border border-gray-200 px-1.5 py-0.5 text-[10px] text-gray-600">
                          {f}
                        </span>
                      ))}
                    </div>
                  </button>
                ))}
              </div>
            </section>
          ))}
          {filtered.length === 0 && data && (
            <p className="rounded-lg border border-gray-100 bg-white p-5 text-sm text-gray-500 shadow-sm">
              No initiatives match these filters.
            </p>
          )}
        </div>

        <aside className="lg:sticky lg:top-4 lg:self-start">
          <div className="rounded-lg border border-gray-100 bg-white p-5 shadow-sm">
            {!selectedId && <p className="text-sm text-gray-500">Select an agent to see its charter.</p>}
            {detailLoading && <p className="text-sm text-gray-500">Loading profile…</p>}
            {detail && (
              <>
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <h2 className="text-base font-bold text-gray-900">{detail.name}</h2>
                    <p className="text-xs text-gray-500">
                      {detail.initiative_id ?? "platform"} · role: {detail.role_scope} · {detail.jurisdiction}
                    </p>
                  </div>
                  <StatusPill status={detail.status} />
                </div>

                <div className="mt-3 flex flex-wrap gap-1">
                  {(detail.skills ?? []).map((s) => (
                    <span key={s} className="rounded border border-pwc-orange/30 bg-pwc-orange/5 px-1.5 py-0.5 text-[10px] font-semibold text-pwc-orange">
                      {s}
                    </span>
                  ))}
                </div>

                {detail.initiative && (
                  <dl className="mt-4 space-y-2 text-xs">
                    {detail.initiative.business_problem && (
                      <div>
                        <dt className="font-bold uppercase tracking-wide text-gray-400">Problem</dt>
                        <dd className="text-gray-700">{detail.initiative.business_problem}</dd>
                      </div>
                    )}
                    {detail.initiative.expected_output && (
                      <div>
                        <dt className="font-bold uppercase tracking-wide text-gray-400">Expected output</dt>
                        <dd className="text-gray-700">{detail.initiative.expected_output}</dd>
                      </div>
                    )}
                    {detail.initiative.kpis && (
                      <div>
                        <dt className="font-bold uppercase tracking-wide text-gray-400">KPIs</dt>
                        <dd className="text-gray-700">{detail.initiative.kpis}</dd>
                      </div>
                    )}
                    {(detail.initiative.core_tables ?? []).length > 0 && (
                      <div>
                        <dt className="font-bold uppercase tracking-wide text-gray-400">Core tables</dt>
                        <dd className="text-gray-700">{(detail.initiative.core_tables ?? []).join(", ")}</dd>
                      </div>
                    )}
                  </dl>
                )}

                {!canChat && (
                  <p className="mt-4 rounded-lg border border-gray-200 bg-gray-50 p-3 text-xs text-gray-600">
                    Registered in the context layer, not yet wired to the pipeline. Its charter, data
                    requirements and KPIs are governed here; promoting it to talkable is a registry
                    change, not a new codebase.
                  </p>
                )}

                {canChat && (
                  <div className="mt-4 border-t border-gray-100 pt-4">
                    <div className="max-h-72 space-y-2 overflow-y-auto thin-scroll">
                      {turns.length === 0 && (
                        <p className="text-xs text-gray-500">
                          Ask a business question — multi-turn, so follow-ups keep context.
                        </p>
                      )}
                      {turns.map((t, i) => (
                        <div
                          key={i}
                          className={`rounded-lg p-2 text-xs ${
                            t.role === "user" ? "bg-gray-50 text-gray-800" : "bg-pwc-orange/5 text-gray-900"
                          }`}
                        >
                          <span className="mb-0.5 block text-[10px] font-bold uppercase tracking-wide text-gray-400">
                            {t.role}
                          </span>
                          <span className="whitespace-pre-wrap">{t.content || (streaming && i === turns.length - 1 ? "…" : "")}</span>
                        </div>
                      ))}
                    </div>

                    {sql && (
                      <pre className="mt-2 max-h-28 overflow-auto rounded-lg bg-gray-900 p-2 text-[10px] leading-relaxed text-gray-100 thin-scroll">
                        {sql}
                      </pre>
                    )}
                    {chatError && (
                      <p className="mt-2 rounded-lg border border-red-200 bg-red-50 p-2 text-xs text-red-700">{chatError}</p>
                    )}

                    <div className="mt-2 flex gap-2">
                      <input
                        value={question}
                        onChange={(e) => setQuestion(e.target.value)}
                        onKeyDown={(e) => e.key === "Enter" && send()}
                        placeholder="Ask this agent…"
                        disabled={streaming}
                        className="flex-1 rounded-lg border border-gray-200 px-3 py-1.5 text-sm outline-none focus:border-pwc-orange disabled:bg-gray-50"
                      />
                      <button
                        onClick={send}
                        disabled={streaming || !question.trim()}
                        className="rounded-lg bg-pwc-orange px-3 py-1.5 text-sm font-semibold text-white disabled:opacity-50"
                      >
                        {streaming ? "…" : "Ask"}
                      </button>
                    </div>
                    {conversationId && (
                      <p className="mt-1 text-[10px] text-gray-400">conversation {conversationId.slice(0, 8)}</p>
                    )}
                  </div>
                )}
              </>
            )}
          </div>
        </aside>
      </div>
    </div>
  );
}
