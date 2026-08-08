# Agent Best Practices → Insurance PoC V2.0 Mapping

**Date:** 2026-06-10
**Sources analyzed:**
1. *AI Agent Best Practices: Production-Ready Harness Engineering (2026 Guide)* — Medium, @tort_mario ("Medium")
2. *agents-best-practices* — github.com/DenisSergeevitch/agents-best-practices ("GitHub")

**V1 baseline:** `act-as-an-enterprise-insurance-data` (FastAPI gateway :8071 → intent classifier → pgvector hybrid retrieval → Gemini text-to-SQL → strict schema validation/repair → guarded execution → Gemini insight generation → Next.js UI).

---

## 1. Key findings from the sources

### Core architectural patterns
- **Both sources converge on a sequential, harness-centric loop:** the model *proposes*; the harness *validates, authorizes, executes, records, returns observations*. Neither recommends parallel agents by default — GitHub explicitly says "Use the single-agent MVP first. Add goal loops, connectors, and broader autonomy only after measured failures justify them."
- **Risk-stratified execution** (both): read-only → autonomous; draft → simulated, no side effects; external write / financial / destructive → human approval recorded outside the prompt.
- **Keep the loop simple, make the runtime rigorous** (GitHub) — discipline lives in the harness, not the prompt.

### Context management
- **Layered, cache-aware context assembly** (Medium): Layer 0 stable system policies (cached) → Layer 1 skill definitions (cached) → Layer 2 session instructions → Layer 3 JIT-retrieved tool outputs (fresh, uncached). Order most-stable → least-stable to maximize prompt caching.
- **"Context is built, not dumped"** (GitHub): retrieve just enough, label trust boundaries, preserve *active state* (plan, approvals, todos, artifacts) across compaction — not prose history.
- **Trust labeling** (both): mark untrusted data (user input, retrieved content) so the harness treats it differently.

### Tool schema design
- **Narrow, typed tools with structured results** (GitHub): "Do not expose generic send_message, write_database, or run_command." Each tool: single purpose, typed args, deterministic structured output, declared risk class.
- **Tool registry with risk classification** (Medium): every tool registered with typed schema + risk class; three-part call path: schema validation → permission check → execute-or-pause.

### Retry, fallback, error handling
- **Every tool call returns a structured observation, even on failure** (both): denial, timeout, malformed args, abort — all become labeled observations the model can react to.
- **Budgets as the stop mechanism** (both): step / time / token / cost / tool-call budgets; on exhaustion the harness "terminates gracefully and returns a structured failure."
- **"Repeated failures become harness features"** (GitHub): convert recurring errors into validators, tools, docs, evals, or policies — not more prompt text.

### Observability & tracing
- **Trace every step**: prompt, tool call, observation, latency, cost (Medium); event trace model output → tool call → observation (GitHub).
- **Eval suites as launch gates**: injection resistance, timeout resilience, over-tooling detection (Medium); "20 historical accounts, trace review, no unapproved external sends, human acceptance ≥80% of drafts" (GitHub).
- **Pre-launch audit**: budgets enforced, permissions correct, injection/timeout evals pass, traces/logs in place.

### Prompt engineering
- **Scoped per-task/per-domain instructions** assembled dynamically, not a monolithic system prompt (Medium).
- **Instruction hierarchy** with runtime discipline (budgets, validation, permissions) moved *out* of prompts (GitHub).
- **Progressive disclosure** for skills/connectors: expose names + descriptions first, load details only when relevant (GitHub).

### Enterprise / insurance-specific guidance
- Neither source is insurance-specific. Applicable enterprise guidance: risk taxonomy (read_only / financial / destructive), draft-then-commit approval workflows with approval records outside the prompt, compliance audit checklists, connector governance. For an insurance decision platform this maps naturally to: SQL reads = autonomous; recommendation/NBA publication = draft; any customer-facing or write action = approval-gated.

---

## 2. Cross-reference mapping table

| # | Best Practice | Source | Currently in V1? | Where to implement in V2 | Priority |
|---|---|---|---|---|---|
| 1 | Harness validates/authorizes/executes; model only proposes | Both | **Partial** — SQL path is well-harnessed (`validate_sql` + `validate_sql_strict` + allowlist + read-only enforcement), but insight/recommendation generation output is published with only heuristic checks | Formalize a single harness layer in `copilot_sql_engine/engine.py`: every model output (SQL *and* insight JSON) passes schema validation + policy check before use | High |
| 2 | Sequential single-agent loop before multi-agent | Both | **Yes** — V1 is a fixed sequential pipeline (intent → retrieve → generate → validate → execute → insight) | Keep. Do not add parallel agents in V2; instead parallelize *independent I/O* (embedding + retrieval queries) inside the single loop | Done / keep |
| 3 | Risk-stratified execution (read / draft / write+approval) | Both | **Partial** — everything is read-only by construction (SELECT/WITH only, unsafe functions blocked); no risk registry, no draft/approval concept for NBA actions | Add `risk_class` to a tool/action registry; NBA "publish recommendation" and any future write actions go through a draft → approval record (`nba_decision_audit` already exists as the natural store) | Medium |
| 4 | Layered, cache-ordered context assembly (stable → volatile) | Medium | **No** — prompt payload is one JSON blob mixing stable schema/governance with the volatile question; Gemini prompt caching unused; governance context rebuilt per request | In V2 prompt builder (`prompts.py`): fixed-order layers — (0) system rules, (1) schema catalog + governance digest, (2) role context, (3) retrieved docs, (4) question. Enable provider-side prompt/context caching for layers 0–1 | **High** |
| 5 | "Built, not dumped" — retrieve just enough context | GitHub | **No** — full `information_schema` dump + full registry SELECTs (40 tables/25 KPIs/25 models) sent on every request, even when a curated template bypasses the LLM | Token-budgeted context builder: select only tables relevant to retrieved docs/intent; skip context assembly entirely on the curated-template path | **High** |
| 6 | Trust labeling of untrusted input | Both | **No** — user question is interpolated directly into the prompt payload alongside system instructions | Wrap user question + retrieved document content in explicit `<untrusted>` blocks; system prompt instructs the model to treat them as data, never instructions | High |
| 7 | Preserve active state across compaction (approvals, plan) | Both | **N/A-ish** — V1 is single-turn; no conversation memory at all | If V2 adds multi-turn copilot: store plan/approvals/insight lineage outside the prompt (DB) and rehydrate state, not chat history | Low (until multi-turn) |
| 8 | Narrow typed tools, no generic `run_command`/`write_database` | GitHub | **Partial** — there is effectively one broad tool ("generate any SQL"), constrained by allowlist + validators rather than narrow tools | Keep guarded text-to-SQL, but promote recurring intents (lapse-rate KPI, campaign conversion, NBA lookup) to dedicated typed tools backed by curated SQL — V1's template library is already halfway there | Medium |
| 9 | Tool registry with typed schema + risk class | Medium | **Partial** — `cld_table_registry`/`cld_kpi_registry`/`cld_model_registry` govern *data*, but there is no registry of *actions/tools* | Add a small tool registry module in V2 (name, JSON schema, risk class, timeout, budget) consumed by the gateway | Medium |
| 10 | Structured failure observations (denial/timeout/malformed all labeled) | Both | **Mostly yes** — `SqlExecutionResult(execution_status=...)`, `StrictSqlValidationResult`, `unsupported_response()` with `NOT_SUPPORTED` are exemplary; LLM JSON parse failures silently degrade to `{}` | Make `parse_json_object()` failures explicit observations (`malformed_llm_output`) instead of returning empty dicts that read as "no data" | Medium |
| 11 | Budgets: step/time/token/cost; graceful termination | Both | **Partial** — statement timeout (5 s), row limit, LLM timeout (120 s) exist; **no token/cost budget, no per-request total deadline** | V2 gateway: per-request wall-clock budget (e.g. 30 s) and token/cost budget per ask; return structured `BUDGET_EXCEEDED` answer status; log spend per request | **High** |
| 12 | Repeated failures become harness features, not prompt patches | GitHub | **Yes, organically** — repair service, deterministic templates, invalid-context exclusion list, demo-question catalog all grew from observed failures | Continue the pattern deliberately in V2: a failure-review loop that feeds `cld_demo_question_catalog` / validators rather than expanding the system prompt | Medium |
| 13 | Full trace per step: prompt, tool call, observation, latency, cost | Both | **Partial** — `timings` dict per stage, `lifecycle[]` steps, `llm_request_log` (latency + token estimates), `insight_lineage`/`context_usage_log` exist but are fragmented across tables and not correlated by one trace ID | V2: single `trace_id` (UUID) propagated through every stage and written to one trace table/log stream; include prompt hash, model, tokens, cost, cache hits | **High** |
| 14 | Eval suites as launch gates (injection, timeout, regression) | Both | **Partial** — strong regression harness (smoke tests, `cld_demo_question_catalog`, `insight_test_snapshots`, RAG SQL validation reports); **no injection or timeout evals** | Add prompt-injection eval set (malicious questions attempting non-SELECT SQL / instruction override) and timeout-resilience tests to `scripts/`; wire into a pre-demo checklist | High |
| 15 | Pre-launch audit checklist (budgets, permissions, evals, traces) | Both | **Partial** — `demo_readiness_check.py` checks data/context health only | Extend readiness check to assert: budgets configured, allowlist non-empty, injection evals pass, trace logging on | Medium |
| 16 | Scoped per-task instructions instead of monolithic prompt | Medium | **Partial** — `INTENT_SQL_GUIDANCE` per intent is exactly this pattern; insight prompt is monolithic | Extend per-intent scoping to insight generation (per-role, per-intent answer templates); keep `docs/llm-harness/*.md` skills as loadable scoped instructions | Medium |
| 17 | Progressive disclosure of skills/connectors | GitHub | **No** — everything is inlined every call | If V2 keeps many context corpora, expose titles/descriptions first and fetch full content only for top-ranked docs (two-stage retrieval) | Low |
| 18 | Runtime discipline outside prompts (don't prompt-beg for safety) | GitHub | **Mixed** — validators do real enforcement (good), but the system prompt also carries long lists of "never use INSERT…" rules that the validator already enforces | Trim prompt safety boilerplate to what shapes *generation quality*; rely on validators for enforcement — shorter prompt, better cache hit rate | Low |
| 19 | Approval records outside the prompt for high-risk actions | Both | **No** (nothing writes today) | When V2 adds actions (assign lead, trigger campaign, send coaching note): draft-and-commit flow with approval rows in `nba_decision_audit` / new `action_approvals` table; UI approve/deny | Medium (gating any write feature) |
| 20 | Cost optimization via prompt caching + model tiering | Both (Medium explicit) | **No caching; single model** for all tasks (`gemini-2.5-flash-lite` everywhere); curated templates are the only cost lever | V2: cache stable prompt layers; tier models (cheap/fast for intent+repair, stronger for SQL gen and insight); track cost per request in trace | High |
| 21 | Timeout resilience (harness stops when a tool hangs) | Medium | **Partial** — LLM and statement timeouts exist, but a hung Supabase connection or embedding call can stall the synchronous request thread with no overall deadline | Per-request deadline (see #11) + connection pool with pool-level timeouts (fixes V1's per-request connect too) | High |
| 22 | Structured results from tools (not prose) | GitHub | **Yes** — all internal services return dataclasses/Pydantic models with typed fields | Keep; extend the same discipline to V2 insight output (validated JSON schema for insight/recommendation objects) | Done / keep |

---

## 3. Top-priority V2 implementation themes (synthesis)

1. **Layered, cached, budgeted prompt assembly** (#4, #5, #20) — biggest cost+latency win; V1 currently ships its largest, mostly-static payload on every call.
2. **Unified tracing with one trace_id + cost accounting** (#13) — V1 already records the pieces; correlation is the missing 20% that enables debugging, evals, and cost control.
3. **Request-level budgets and deadlines** (#11, #21) — converts V1's worst case (2× 120 s LLM calls) into a bounded, structured failure.
4. **Trust labeling + injection evals** (#6, #14) — the only materially missing *security* layer; V1's SQL validator catches the damage, but the prompt channel is unlabeled.
5. **Action/tool registry with risk classes** (#3, #8, #9, #19) — prerequisite for any V2 feature that moves from "answer questions" to "take actions" in an insurance workflow.

**What V1 already does well (preserve in V2):** strict actual-schema SQL validation with repair, read-only enforcement at the validator level, structured failure responses (`NOT_SUPPORTED` instead of hallucinated answers), evidence lineage tables, curated-template fast path, and a regression smoke-test culture — these align with the sources' strongest recommendations and should be carried forward unchanged.
