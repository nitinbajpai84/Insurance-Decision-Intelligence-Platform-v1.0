-- =====================================================================
-- Insurance PoC V2.0 — Metric bindings (data contracts) + role access policy
--
-- metric_bindings : the GUARDRAIL contract for each metric — exactly which
--                   canonical view / tables / columns / joins / filters the SQL
--                   agent may use to compute it, plus the reference formula SQL.
-- table_access_policy : per-role table allow-list + row-level filter (e.g. an
--                   Insurance Agent is scoped to their own book via agent_id).
-- =====================================================================

create table if not exists metric_bindings (
  binding_id      varchar primary key default uuid(),
  metric_id       varchar not null unique,        -- FK -> concept_nodes.node_id
  canonical_view  varchar,                         -- e.g. 'v_lapse_risk_summary'
  allowed_tables  json,                            -- whitelist of tables/views
  allowed_columns json,                            -- whitelist of fully-qualified columns
  required_joins  json,                            -- sanctioned join paths
  default_filters json,                            -- e.g. ["policy_status IN ('active','in_force')"]
  grain           varchar,                         -- policy | customer | agent | campaign | month
  formula_sql     text,                            -- reference SQL expression
  sample_question text,
  status          varchar default 'active',
  created_by      varchar,
  created_at      timestamp default current_timestamp
);

create table if not exists table_access_policy (
  policy_id   varchar primary key default uuid(),
  role        varchar not null,
  table_name  varchar not null,
  allowed     boolean default true,
  row_filter  text,                                -- e.g. "agent_id = :current_agent"
  created_at  timestamp default current_timestamp,
  unique (role, table_name)
);
