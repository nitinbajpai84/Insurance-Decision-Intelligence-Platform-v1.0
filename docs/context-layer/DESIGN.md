# Enterprise Context Layer — Design Specification

**Status:** reviewed direction, approved phasing · August 2026
**Scope:** evolve Insurance PoC V2.0 into a *one context layer, many agents* platform,
aligned to the enterprise-context-layer model (substrate = knowledge graph + semantics +
skills; capabilities = mining, lifecycle, learning loops, activation, governance) and to
the AI Insurance Playbook (Vol1 architecture, Vol2 profiles, Workbook registry — 46
initiatives: Health 7 · Operations 18 · Agency 21).

---

## 1. Decision record

These were discussed and settled before this spec was written:

| # | Decision | Choice | Rationale |
|---|---|---|---|
| D1 | Agent Gallery scope | **All 46 initiatives browsable**; a small subset functional at launch | The registry itself *is* the demo of the context-layer idea. A `status` field (`registered` / `functional` / `live`) distinguishes browsable charters from agents you can actually talk to. |
| D2 | Where the code lives | **Extend V2 in place**, as a new `context_layer/` subsystem directory alongside `graph/` | Everything composts into the existing ontology (`concept_nodes`, `graph_edges`, `metric_bindings`, `table_access_policy`, tracer, feedback loop). A separate repo/app would recreate the context-island fragmentation this project exists to disprove. Same DuckDB file, same conventions as `graph/` (own `*_schema.sql`, own routes module, registered in `backend_v2/api/main.py` behind a try/except like the graph routers). |
| D3 | Priority order | Gallery + architecture first → **jurisdiction (SG/HK)** second → **personas/personalisation** third → skills/evals/mining after | User-set ordering, 2026-08-11. |

Core design rule (applies to every phase): **an agent is a thin composition over shared
context** — `agent = skills + knowledge scopes + norms + model tier + KPI contract`. No
agent gets its own private glossary, prompt pile, or data definitions. All 46 use cases
are rows in a registry, not 46 codebases; the existing
`context_agent → sql/retrieval → execution → insight` pipeline (with tracer) remains the
single runtime.

## 2. The workbook is the seed context artifact

`AI_Insurance_Playbook_Workbook.xlsx` (18-column master table, per-initiative data
requirements, 9-family model matrix, KPI matrix, roadmap) is ingested — not transcribed —
into the layer. It gets **copied into the repo** at
`context_layer/registry/AI_Insurance_Playbook_Workbook.xlsx` and versioned in git: context
is versioned data, and the workbook remains the human editing surface. Re-running the
ingest is idempotent (upsert by initiative ID).

Vol2's per-initiative charter text is extracted into `initiative_registry.charter_md` so
the Agent Gallery can render a real profile page per initiative without re-authoring
content.

Vol1 §7.2's four GenAI patterns are adopted as the four **skill patterns** of the layer:
`summarise_and_cite`, `retrieve_and_answer`, `draft_for_approval`,
`orchestrate_with_checkpoints`. Every one of the 46 initiatives decomposes into these plus
a knowledge scope plus a model family (Workbook Sheet 7 supplies the family per
initiative).

## 3. Schema (Phase A tables)

Conventions follow `graph/graph_schema.sql`. All DDL lives in
`context_layer/context_schema.sql`; applied via the same guarded pattern as the graph
migrations. Every `duckdb.connect()` must use `backend_v2.config.DUCKDB_CONFIG` (see the
OOM fix in DEPLOY.md — mismatched configs raise ConnectionException).

```sql
-- One row per playbook use case (H1..A21). Source of truth: the ingested workbook.
create table if not exists initiative_registry (
  initiative_id     varchar primary key,        -- 'H1', 'O2B', 'A21'
  domain            varchar not null,           -- Health | Operations | Agency
  name              varchar not null,
  strategic_goal    varchar,
  business_problem  varchar,
  ai_capability     varchar,
  genai_ml_approach varchar,
  expected_output   varchar,
  primary_users     varchar,
  kpis              varchar,
  business_value    varchar,
  complexity        varchar,
  phase             varchar,                    -- Quick Win | Phase 1 | Phase 2 | Phase 3
  industry_maturity varchar,
  value_score       integer,                    -- 1-5 (workbook)
  complexity_score  integer,                    -- 1-5 (workbook)
  source_systems    json,                       -- Sheet 6
  core_tables       json,
  master_data       json,
  events            json,
  external_data     json,
  document_data     json,
  model_families    json,                       -- Sheet 7: ['classification','genai_llm','rag',...]
  kpi_impact        json,                       -- Sheet 8: {revenue_uplift:'High',...}
  charter_md        text,                       -- Vol2 profile (charter + value case)
  status            varchar default 'registered', -- registered | in_build | functional | live
  created_at        timestamp default current_timestamp,
  updated_at        timestamp default current_timestamp
);

-- The agent control plane. One row per talkable agent; thin composition only.
create table if not exists agent_registry (
  agent_id         varchar primary key,          -- 'agent::a3_presales'
  initiative_id    varchar,                      -- FK -> initiative_registry (null for platform agents)
  name             varchar not null,
  description      varchar,
  persona_prompt   text,                         -- system-prompt flavour ONLY — no facts/definitions here
  skills           json,                         -- [skill pattern or skill_id, ...]
  knowledge_scopes json,                         -- {subject_areas:[], lance_collections:[], table_scope_role:''}
  role_scope       varchar,                      -- joins table_access_policy.role
  jurisdiction     varchar default 'regional',   -- SG | HK | regional  (Phase B activates filtering)
  model_tier       varchar default 'standard',   -- standard | frontier | local
  policies         json,                         -- [policy_id,...] -> governance_policies (Phase B)
  hitl_gate        varchar default 'none',       -- none | draft_for_approval | referral_threshold
  status           varchar default 'draft',      -- draft | functional | live | retired
  owner            varchar,
  created_at       timestamp default current_timestamp,
  updated_at       timestamp default current_timestamp
);

-- Conversation memory — prerequisite for anything that feels like "talking to" an agent.
create table if not exists conversations (
  conversation_id varchar primary key default uuid(),
  agent_id        varchar not null,
  user_id         varchar,
  user_role       varchar,
  title           varchar,                       -- first question, truncated
  created_at      timestamp default current_timestamp,
  last_active_at  timestamp default current_timestamp
);

create table if not exists conversation_messages (
  message_id      varchar primary key default uuid(),
  conversation_id varchar not null,
  turn_index      integer not null,
  role            varchar not null,              -- user | agent
  content         text not null,
  query_id        varchar,                       -- correlates agent turns to agent_reasoning_log
  created_at       timestamp default current_timestamp
);
create index if not exists idx_conv_msgs on conversation_messages (conversation_id, turn_index);
```

Graph integration (same ingest run): each initiative becomes a `concept_nodes` row with
`node_type='initiative'`, plus edges — `initiative -consumes_data_from-> entity_class`,
`initiative -measured_by-> metric` (where a workbook KPI matches an existing metric node),
`initiative -depends_on-> initiative` (Vol1 §13.1 critical path: O2→O4, H1/O1→O16→O17,
O8→O10). Agents likewise become nodes so graph traversal can answer "which agents consume
lapse_rate?".

## 4. Phase B — Jurisdiction & norms pack (SG / HK)

Second priority by decision D3.

**Jurisdiction dimension.** Add `jurisdiction varchar default 'regional'` to
`business_glossary`, `metric_bindings`, and to the metadata of LanceDB documents at embed
time. The context agent filters retrieval by the asking agent's jurisdiction
(`SG`-scoped agents retrieve `SG + regional`, never `HK`-only, and vice versa).
Rationale: persistency rules, product names, currency (SGD/HKD), and med-claims practice
differ between the SG and HK books; retrofitting this later means re-embedding everything.

**Norms as data.** Machine-readable governance policies referenced by every agent:

```sql
create table if not exists governance_policies (
  policy_id          varchar primary key,        -- 'pol::sg_advice_hitl'
  jurisdiction       varchar not null,           -- SG | HK | regional
  decision_class     varchar not null,           -- underwriting|claims|advice|coaching|marketing|servicing
  hitl_requirement   varchar not null,           -- none | review_above_threshold | mandatory_approval
  referral_threshold varchar,
  audit_requirement  varchar,
  source_regulation  varchar,                    -- e.g. 'MAS AI Risk Mgmt Guidelines (2026 consultation)',
                                                 --      'MAS FEAT', 'HKIA GenA.I. Sandbox++ (Mar 2026)'
  notes              text,
  status             varchar default 'active',
  created_at         timestamp default current_timestamp
);
```

Seed set (from Aug-2026 research): MAS published an AI Risk Management Toolkit (Mar 2026)
and is consulting on binding AI Risk Management Guidelines explicitly covering GenAI and
AI agents — supervisory expectations, not just principles. HK's GenA.I. Sandbox++
(HKMA/SFC/IA/MPFA joint, Mar 2026) covers authorised insurers, focus areas risk
management / anti-fraud / customer experience. Prudential Corporation Asia is a designated
D-SII in HK. Practical consequences encoded as policies: customer-facing draft outputs
require `draft_for_approval`; underwriting/claims decision classes require
`review_above_threshold` with logged referral thresholds; every agent answer must remain
traceable end-to-end (already satisfied by `agent_reasoning_log` + Evidence Hub — cite
this in sandbox/inspection narratives).

## 5. Phase C — Personas / personalisation

Third priority by decision D3. Flagship: **A21 (PruAction-style action-oriented
performance coaching)** — feasible on existing agent-performance synthetic data, and the
strongest Prudential-relevant showcase per Vol1 §11. Supporting quick-win agents (all
buildable on current data, all in the playbook's 13 quick wins): O6 helpdesk (pure RAG),
A3 pre-sales briefing, A6 pre-pitch, A12 NBA (closest to the existing ask pipeline),
A11/A15 nudges. Persona work = `persona_prompt` + `knowledge_scopes` + role-scoped
`table_access_policy` rows per agent; **no facts in prompts** — facts live in the shared
layer.

## 6. Phase D — Skills registry, evals, prompt registry, mining loop

Deferred by design (D3) but schema-sketched so nothing above blocks it: `skills`
(versioned procedures with `pattern` = one of the four, eval_set linkage,
draft→tested→active lifecycle), `prompt_registry` (versioned prompts with owners),
`eval_sets`/`eval_runs` (seeded from the existing demo-question smoke-test artifacts), and
the mining job (cluster repeated ungrounded/low-confidence questions from
`agent_reasoning_log` + `answer_feedback` → propose glossary/binding/rule candidates into
the existing `graph_feedback` `pending_review` queue).

## 7. API & frontend additions (Phase A)

Backend — `context_layer/registry_routes.py`, prefix `/api/v2`, registered in `main.py`
behind try/except like the graph routers:

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/v2/agents` | Gallery list: all initiatives joined to agent status |
| GET | `/api/v2/agents/{agent_id}` | Full profile (charter_md, skills, scopes, policies) |
| POST | `/api/v2/agents/{agent_id}/ask` | SSE ask, wraps `stream_pipeline` with agent context + `conversation_id` |
| GET | `/api/v2/conversations?agent_id=` | Conversation list |
| GET | `/api/v2/conversations/{id}` | Messages for a conversation |

Orchestrator change: `stream_pipeline(question, role, query_id)` gains
`agent: AgentContext | None` and `conversation_id: str | None`. The agent row supplies
role scope, persona flavour, jurisdiction, and (Phase B+) policies; prior turns are
retrieved into the context budget alongside the existing four parallel searches. The
current 7-role experience is re-expressed as 7 default `agent_registry` rows so nothing
breaks.

Frontend — `frontend_v2/app/agent-gallery-v2/page.tsx`: all 46, grouped by domain, filter
by wave/status, each card → profile page (charter from Vol2) → **Talk to this agent** when
`status='functional'`. Nav entry added in `components/navItems.ts` (shared by Sidebar +
MobileNav). Evidence Hub gains agent/conversation columns via `query_id` correlation —
no schema change needed there.

## 8. Ingest pipeline

`context_layer/ingest_workbook.py` (openpyxl — add to `embeddings/requirements.txt`):
reads the repo-versioned workbook + Vol2 docx (charter extraction), upserts
`initiative_registry`, creates/refreshes graph nodes + edges, embeds initiative summaries
into a new `insurance_initiative_vectors` LanceDB table so retrieval can ground "what does
A12 do?" questions. Rerunnable; deletes nothing (initiatives removed from the workbook are
flagged `status='retired'`, never dropped).

## 9. Non-goals / honest constraints

- DuckDB + LanceDB on a 512MB Render instance stays the substrate for this phase. The
  schemas above are the durable contract; Vol1's lakehouse/feature-store architecture is
  the eventual home. Design schema-first, treat the engine as swappable.
- No real PII/health data enters the layer — synthetic only, consistent with the rest of
  the PoC. The consent-registry and PII-tokenisation layers in Vol1 §3.4 are out of scope
  here and must precede any real-data deployment.
- WebContainer/StackBlitz constraints are unchanged — the backend still needs a real host.
