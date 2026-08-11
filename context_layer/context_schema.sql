-- =====================================================================
-- Insurance PoC V2.0 — Enterprise Context Layer (Phase A)
-- Spec: docs/context-layer/DESIGN.md
--
-- initiative_registry : one row per playbook use case (H1..A21); source of
--                       truth is the ingested workbook in context_layer/registry/
-- agent_registry      : the agent control plane — each agent is a THIN
--                       composition (skills + knowledge scopes + norms + tier)
--                       over the shared context; no per-agent facts.
-- conversations /     : multi-turn memory; agent turns correlate to
-- conversation_messages agent_reasoning_log via query_id.
-- =====================================================================

create table if not exists initiative_registry (
  initiative_id     varchar primary key,          -- 'H1', 'O2B', 'A21'
  domain            varchar not null,             -- Health | Operations | Agency
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
  phase             varchar,                      -- Quick Win | Phase 1 | Phase 2 | Phase 3
  industry_maturity varchar,
  value_score       integer,
  complexity_score  integer,
  source_systems    json,
  core_tables       json,
  master_data       json,
  events            json,
  external_data     json,
  document_data     json,
  model_families    json,                         -- ['classification','genai_llm','rag',...]
  kpi_impact        json,                         -- {revenue_uplift:'High',...}
  charter_md        text,                         -- Vol2 profile text
  status            varchar default 'registered', -- registered | in_build | functional | live | retired
  created_at        timestamp default current_timestamp,
  updated_at        timestamp default current_timestamp
);

create table if not exists agent_registry (
  agent_id         varchar primary key,           -- 'agent::a3'
  initiative_id    varchar,                       -- FK -> initiative_registry (null for platform agents)
  name             varchar not null,
  description      varchar,
  persona_prompt   text,                          -- flavour ONLY — facts live in the shared layer
  skills           json,                          -- [pattern,...] from the four skill patterns
  knowledge_scopes json,                          -- {subject_areas:[], lance_collections:[]}
  role_scope       varchar,                       -- joins ROLE_PROMPTS / table_access_policy.role
  jurisdiction     varchar default 'regional',    -- SG | HK | regional (Phase B activates filtering)
  model_tier       varchar default 'standard',
  policies         json,                          -- [policy_id,...] (Phase B)
  hitl_gate        varchar default 'none',        -- none | draft_for_approval | referral_threshold
  status           varchar default 'draft',       -- draft | functional | live | retired
  owner            varchar,
  created_at       timestamp default current_timestamp,
  updated_at       timestamp default current_timestamp
);

create table if not exists conversations (
  conversation_id varchar primary key default uuid(),
  agent_id        varchar not null,
  user_id         varchar,
  user_role       varchar,
  title           varchar,
  created_at      timestamp default current_timestamp,
  last_active_at  timestamp default current_timestamp
);

create table if not exists conversation_messages (
  message_id      varchar primary key default uuid(),
  conversation_id varchar not null,
  turn_index      integer not null,
  role            varchar not null,               -- user | agent
  content         text not null,
  query_id        varchar,                        -- correlates to agent_reasoning_log
  created_at      timestamp default current_timestamp
);
create index if not exists idx_conv_msgs on conversation_messages (conversation_id, turn_index);
create index if not exists idx_conv_agent on conversations (agent_id, last_active_at);
