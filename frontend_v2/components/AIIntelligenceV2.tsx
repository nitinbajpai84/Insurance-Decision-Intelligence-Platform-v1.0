"use client";

/**
 * AIIntelligenceV2 — full replacement for V1's AI Intelligence page.
 * Same familiar layout; all V2 features (streaming SSE pipeline, context
 * transparency, reasoning trace, governed recommendation).
 *
 * Owns the SSE connection to POST /api/v2/ask and distributes events to the
 * StreamingInsightPanel (step tracker + streamed answer), the SQL panel,
 * ContextViewer, RecommendationCard, and ReasoningPanel.
 */
import { useEffect, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Loader2, Sparkles } from "lucide-react";
import StreamingInsightPanel, { applySSE, initialSteps, type StepState } from "@/components/StreamingInsightPanel";
import ContextViewer from "@/components/ContextViewer";
import RecommendationCard from "@/components/RecommendationCard";
import ReasoningPanel, { timingsFromStepLatencies } from "@/components/ReasoningPanel";
import SqlBlock from "@/components/SqlBlock";
import { getRoles, streamInsight, type PipelineResult, type RoleInfo } from "@/services/apiV2";

const FALLBACK_ROLES = [
  "Executive Leadership",
  "Agency Manager",
  "Campaign Manager",
  "Sales Director",
  "Insurance Agent",
  "Claims Manager",
  "Data Analyst"
];

const SUGGESTIONS: Record<string, string[]> = {
  "Executive Leadership": [
    "What is the overall policy lapse rate?",
    "Which product line drives the most premium?",
    "How is persistency trending across the book?"
  ],
  "Agency Manager": [
    "Which agents have the highest premium at risk?",
    "Which region has the worst lapse rate?",
    "Which agents need coaching this month?"
  ],
  "Campaign Manager": [
    "Which campaign channel converts best?",
    "What is the conversion funnel by campaign?",
    "Which campaign has the weakest ROI?"
  ],
  "Sales Director": [
    "Who are my top producers this quarter?",
    "Which agents are rising stars?",
    "How is team target attainment tracking?"
  ],
  "Insurance Agent": [
    "Which of my policies are at risk of lapse?",
    "Who are my next best customers to contact?",
    "What renewals are due in my book?"
  ],
  "Claims Manager": [
    "Which claims have the highest fraud indicators?",
    "What is the claims ratio by product?",
    "Which open claims need assessment?"
  ],
  "Data Analyst": [
    "Show lapse rate by product and tenure band",
    "Which tables hold model scores?",
    "Premium concentration by line of business"
  ]
};

type Status = "idle" | "running" | "done" | "error";

export default function AIIntelligenceV2() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const urlRole = searchParams.get("role");
  const urlQ = searchParams.get("q");
  const urlHints = {
    process_id: searchParams.get("process_id") || undefined,
    metric_id: searchParams.get("metric_id") || undefined,
    page: searchParams.get("page") || undefined,
    stage: searchParams.get("stage") || undefined
  };
  const [roles, setRoles] = useState<string[]>(FALLBACK_ROLES);
  const [role, setRole] = useState<string>(urlRole && FALLBACK_ROLES.includes(urlRole) ? urlRole : "Executive Leadership");
  const [question, setQuestion] = useState<string>(
    urlQ || SUGGESTIONS[urlRole || "Executive Leadership"]?.[0] || SUGGESTIONS["Executive Leadership"][0]
  );

  const [status, setStatus] = useState<Status>("idle");
  const [steps, setSteps] = useState<StepState[]>(initialSteps());
  const [answer, setAnswer] = useState<string>("");
  const [liveSql, setLiveSql] = useState<string>("");
  const [contextTokens, setContextTokens] = useState<number | undefined>(undefined);
  const [cacheHit, setCacheHit] = useState(false);
  const [cacheSimilarity, setCacheSimilarity] = useState<number | undefined>(undefined);
  const [meta, setMeta] = useState<PipelineResult | null>(null);
  const [errorMessage, setErrorMessage] = useState("");

  const cancelRef = useRef<null | (() => void)>(null);

  useEffect(() => {
    getRoles()
      .then((r: RoleInfo[]) => {
        if (r?.length) setRoles(r.map((x) => x.role));
      })
      .catch(() => setRoles(FALLBACK_ROLES));
  }, []);

  useEffect(() => () => cancelRef.current?.(), []);

  const suggestions = SUGGESTIONS[role] || SUGGESTIONS["Executive Leadership"];

  function onRoleChange(next: string) {
    setRole(next);
    const first = (SUGGESTIONS[next] || [])[0];
    if (first && status !== "running") setQuestion(first);
  }

  function generate() {
    if (!question.trim() || status === "running") return;
    cancelRef.current?.();
    setStatus("running");
    setSteps(initialSteps());
    setAnswer("");
    setLiveSql("");
    setContextTokens(undefined);
    setCacheHit(false);
    setCacheSimilarity(undefined);
    setMeta(null);
    setErrorMessage("");

    cancelRef.current = streamInsight(question.trim(), role, {
      onStep: (event) => {
        setSteps((prev) => applySSE(prev, event));
        if (event.step === "context_retrieved") {
          if (typeof event.tokens === "number") setContextTokens(event.tokens);
          if (event.cache_hit) setCacheHit(true);
        }
        if (event.step === "cache_hit") {
          setCacheHit(true);
          if (typeof event.similarity === "number") setCacheSimilarity(event.similarity);
        }
        if (event.step === "sql_generated" && event.sql) setLiveSql(event.sql);
      },
      onToken: (token) => setAnswer((prev) => prev + token),
      onComplete: (result) => {
        setMeta(result);
        setCacheHit(result.cache_hit);
        setCacheSimilarity(result.cache_similarity || undefined);
        if (result.sql_generated_text) setLiveSql(result.sql_generated_text);
        if (!answer && result.answer_summary) setAnswer(result.answer_summary);
        setStatus("done");
      },
      onError: (message) => {
        setErrorMessage(message);
        setStatus("error");
      }
    }, urlHints);
  }

  function onKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Enter") generate();
  }

  const sql = liveSql || meta?.sql_generated_text || "";
  const schema = meta?.top_context?.schema || [];
  const glossary = meta?.top_context?.glossary || [];
  const docs = meta?.top_context?.docs || [];
  const hasRecommendation = Boolean(meta?.recommended_action && meta.recommended_action.trim());

  return (
    <div className="mx-auto w-full max-w-[1500px] px-4 py-6 sm:px-6 lg:px-8">
      {/* page header */}
      <p className="text-xs font-bold uppercase tracking-wide text-brand-orange">Business workspace</p>
      <h1 className="mt-1 text-2xl font-bold text-gray-900">AI Intelligence</h1>
      <p className="mt-1 max-w-3xl text-sm text-gray-500">
        Ask a business question. The agentic pipeline retrieves context in parallel, generates validated DuckDB SQL,
        executes it, and streams a role-aware answer with full evidence.
      </p>

      {/* ask box */}
      <section className="mt-5 rounded-lg border border-gray-100 bg-white p-5 shadow-sm">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div className="flex-1">
            <label className="text-xs font-semibold uppercase tracking-wide text-gray-500">Ask a business question</label>
            <div className="mt-2 flex flex-col gap-2 sm:flex-row">
              <input
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                onKeyDown={onKeyDown}
                placeholder="Type any insurance business question"
                className="h-12 flex-1 rounded-lg border border-gray-200 px-4 text-sm outline-none focus:border-brand-orange focus:ring-2 focus:ring-brand-orange/20"
              />
              <button
                onClick={generate}
                disabled={status === "running"}
                className="inline-flex h-12 items-center justify-center gap-2 rounded-lg bg-brand-orange px-6 text-sm font-bold text-white hover:bg-brand-orangeDark disabled:opacity-60"
              >
                {status === "running" ? <Loader2 size={18} className="animate-spin" /> : <Sparkles size={18} />}
                Generate Insight
              </button>
            </div>
          </div>
          <label className="block min-w-[230px]">
            <span className="text-xs font-semibold uppercase tracking-wide text-gray-500">Role</span>
            <select
              value={role}
              onChange={(e) => onRoleChange(e.target.value)}
              className="mt-2 h-12 w-full rounded-lg border border-gray-200 bg-gray-50 px-3 text-sm font-semibold outline-none focus:border-brand-orange"
            >
              {roles.map((r) => (
                <option key={r}>{r}</option>
              ))}
            </select>
          </label>
        </div>

        <div className="mt-4">
          <p className="text-xs font-bold uppercase tracking-wide text-gray-500">Try asking</p>
          <div className="mt-2 flex flex-wrap gap-2">
            {suggestions.map((s) => (
              <button
                key={s}
                onClick={() => setQuestion(s)}
                className="rounded-full border border-gray-200 bg-gray-50 px-3 py-1.5 text-xs font-semibold text-gray-700 hover:border-brand-orange/40 hover:bg-brand-orange/5 hover:text-brand-orange"
              >
                {s}
              </button>
            ))}
          </div>
        </div>
      </section>

      {/* governance banner */}
      {meta && meta.ungoverned && (
        <div className="mt-4 flex items-start gap-2 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
          <span className="font-bold">⚠ {meta.ungoverned_label || "Ungoverned answer — not validated against the semantic model"}.</span>
          <span>This answer was produced by the legacy free-SQL agent and is not bound to a governed metric.</span>
        </div>
      )}
      {meta && meta.governed && meta.grounding?.metrics_used?.length ? (
        <div className="mt-4 flex flex-wrap items-center gap-2 rounded-lg border border-green-200 bg-green-50 px-4 py-2.5 text-sm text-green-800">
          <span className="font-bold">✓ Governed answer</span>
          <span className="text-green-700">
            grounded in {meta.grounding.metrics_used.slice(0, 3).map((m) => m.replace("metric::", "")).join(", ")}
            {meta.grounding.canonical_views?.length ? ` via ${meta.grounding.canonical_views[0]}` : ""}
            {meta.grounding.validation?.repaired ? " (auto-repaired)" : ""}
          </span>
        </div>
      ) : null}

      {/* middle + right */}
      <div className="mt-5 grid gap-5 xl:grid-cols-[1.05fr_0.95fr]">
        <StreamingInsightPanel
          steps={steps}
          answer={answer}
          status={status}
          cacheHit={cacheHit}
          cacheSimilarity={cacheSimilarity}
          confidence={meta?.confidence_score}
          queryId={meta?.query_id}
          errorMessage={errorMessage}
          onViewEvidence={(qid) => router.push(`/insight-evidence-hub-v2?insight_id=${encodeURIComponent(qid)}`)}
        />

        <div className="space-y-5">
          <section className="rounded-lg border border-gray-100 bg-white p-5 shadow-sm">
            <div className="mb-3 flex items-center justify-between">
              <h3 className="text-base font-bold text-gray-900">SQL generated</h3>
              {meta && (
                <span className="rounded-full bg-gray-100 px-2.5 py-1 text-xs font-semibold text-gray-600">
                  {meta.row_count} rows · {meta.answer_status}
                </span>
              )}
            </div>
            <SqlBlock sql={sql} />
          </section>

          <ContextViewer
            schema={schema}
            glossary={glossary}
            docs={docs}
            totalTokens={contextTokens}
            questionType={role}
          />
        </div>
      </div>

      {/* recommendation */}
      {hasRecommendation && meta && (
        <div className="mt-5">
          <RecommendationCard
            reasoning={meta.answer_summary || meta.business_data_limitations || "Grounded in the SQL result for this question."}
            action={meta.recommended_action}
            role={meta.role.toUpperCase()}
            confidence={meta.confidence_score}
            keyDataPoints={meta.key_data_points}
          />
        </div>
      )}

      {/* reasoning */}
      {meta && (
        <div className="mt-5">
          <ReasoningPanel
            agentTimings={timingsFromStepLatencies(meta.step_latencies || {})}
            schema={schema}
            glossary={glossary}
            docs={docs}
            sql={sql}
            cacheHit={meta.cache_hit}
            parallel={meta.parallel_execution}
          />
        </div>
      )}
    </div>
  );
}
