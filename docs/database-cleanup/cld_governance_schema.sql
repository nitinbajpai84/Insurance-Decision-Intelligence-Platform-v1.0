-- Governance metadata schema for the Insurance Decision Intelligence Platform.
-- Review and apply only to create new cld_ metadata tables.
-- No existing business table is altered by this file.

create extension if not exists pgcrypto;
create extension if not exists vector;

create table if not exists public.cld_table_registry (
  registry_id uuid primary key default gen_random_uuid(),
  schema_name text not null,
  table_name text not null,
  classification_label text not null,
  table_role text not null,
  business_domain text,
  authoritative_for_kpis jsonb not null default '[]'::jsonb,
  used_by_tabs jsonb not null default '[]'::jsonb,
  used_by_models jsonb not null default '[]'::jsonb,
  used_by_ai_sql boolean not null default false,
  used_by_context boolean not null default false,
  used_by_embeddings boolean not null default false,
  used_by_evidence_hub boolean not null default false,
  demo_required boolean not null default false,
  ai_sql_allowed boolean not null default false,
  context_allowed boolean not null default false,
  truncate_candidate boolean not null default false,
  truncate_risk_level text not null default 'LOW',
  recommendation text not null default 'REVIEW_REQUIRED',
  reason text not null default '',
  confidence_score numeric(5,4) not null default 0,
  row_count bigint,
  total_size_bytes bigint,
  index_size_bytes bigint,
  column_count integer,
  primary_key_columns jsonb not null default '[]'::jsonb,
  foreign_keys jsonb not null default '[]'::jsonb,
  has_vector_columns boolean not null default false,
  used_by_frontend boolean not null default false,
  used_by_backend boolean not null default false,
  used_by_demo boolean not null default false,
  used_by_ai_prompt boolean not null default false,
  risk_if_truncated text not null default 'UNKNOWN',
  manual_review_required boolean not null default true,
  status text,
  missing_data_points jsonb not null default '[]'::jsonb,
  fallback_formula jsonb not null default '[]'::jsonb,
  created_at timestamp with time zone not null default now(),
  updated_at timestamp with time zone not null default now(),
  unique(schema_name, table_name)
);

create table if not exists public.cld_kpi_registry (
  kpi_id uuid primary key default gen_random_uuid(),
  kpi_name text not null unique,
  business_definition text not null,
  formula text not null,
  business_domain text not null,
  grain text not null,
  authoritative_tables jsonb not null default '[]'::jsonb,
  required_columns jsonb not null default '[]'::jsonb,
  allowed_join_paths jsonb not null default '[]'::jsonb,
  used_by_tabs jsonb not null default '[]'::jsonb,
  used_by_roles jsonb not null default '[]'::jsonb,
  sql_generation_notes text not null default '',
  demo_priority text not null default 'MEDIUM',
  status text not null default 'ACTUAL',
  missing_data_points jsonb not null default '[]'::jsonb,
  fallback_formula text,
  created_at timestamp with time zone not null default now(),
  updated_at timestamp with time zone not null default now()
);

create table if not exists public.cld_model_registry (
  model_id uuid primary key default gen_random_uuid(),
  model_name text not null unique,
  model_type text not null,
  entity_type text not null,
  business_purpose text not null,
  score_table text not null,
  score_column text not null,
  score_interpretation text not null,
  required_source_tables jsonb not null default '[]'::jsonb,
  feature_sources jsonb not null default '[]'::jsonb,
  used_by_tabs jsonb not null default '[]'::jsonb,
  used_by_roles jsonb not null default '[]'::jsonb,
  ai_sql_allowed boolean not null default false,
  demo_priority text not null default 'MEDIUM',
  limitation_notes text not null default '',
  registry_status text not null default 'PLANNED',
  missing_data_points jsonb not null default '[]'::jsonb,
  created_at timestamp with time zone not null default now(),
  updated_at timestamp with time zone not null default now()
);

create table if not exists public.cld_context_registry (
  context_id uuid primary key default gen_random_uuid(),
  context_type text not null,
  title text not null,
  business_domain text not null,
  content text not null,
  related_tables jsonb not null default '[]'::jsonb,
  related_columns jsonb not null default '[]'::jsonb,
  related_kpis jsonb not null default '[]'::jsonb,
  related_models jsonb not null default '[]'::jsonb,
  sql_usable boolean not null default false,
  business_only boolean not null default true,
  demo_priority text not null default 'MEDIUM',
  embedding_status text not null default 'PENDING',
  embedding vector(768),
  embedding_model text,
  created_at timestamp with time zone not null default now(),
  updated_at timestamp with time zone not null default now()
);

create table if not exists public.cld_llm_skill_registry (
  skill_id uuid primary key default gen_random_uuid(),
  skill_name text not null unique,
  purpose text not null,
  instructions text not null,
  allowed_tables jsonb not null default '[]'::jsonb,
  allowed_kpis jsonb not null default '[]'::jsonb,
  allowed_models jsonb not null default '[]'::jsonb,
  created_at timestamp with time zone not null default now(),
  updated_at timestamp with time zone not null default now()
);

create table if not exists public.cld_sql_guardrail_rules (
  rule_id uuid primary key default gen_random_uuid(),
  rule_name text not null unique,
  severity text not null default 'HIGH',
  applies_to text not null default 'text_to_sql',
  rule_text text not null,
  enabled boolean not null default true,
  created_at timestamp with time zone not null default now(),
  updated_at timestamp with time zone not null default now()
);

create table if not exists public.cld_table_cleanup_report (
  report_id uuid primary key default gen_random_uuid(),
  generated_at timestamp with time zone not null default now(),
  total_tables integer not null default 0,
  active_tables integer not null default 0,
  truncate_candidates integer not null default 0,
  report_json jsonb not null default '{}'::jsonb,
  created_at timestamp with time zone not null default now()
);

create index if not exists idx_cld_table_registry_classification on public.cld_table_registry(classification_label);
create index if not exists idx_cld_table_registry_ai_sql_allowed on public.cld_table_registry(ai_sql_allowed);
create index if not exists idx_cld_kpi_registry_name on public.cld_kpi_registry(kpi_name);
create index if not exists idx_cld_model_registry_name on public.cld_model_registry(model_name);
create index if not exists idx_cld_context_registry_type on public.cld_context_registry(context_type);
create index if not exists idx_cld_context_registry_sql_usable on public.cld_context_registry(sql_usable);
create index if not exists idx_cld_llm_skill_registry_name on public.cld_llm_skill_registry(skill_name);
create index if not exists idx_cld_sql_guardrail_rules_enabled on public.cld_sql_guardrail_rules(enabled);

