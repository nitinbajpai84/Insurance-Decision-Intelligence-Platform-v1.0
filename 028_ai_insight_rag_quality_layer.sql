create extension if not exists pgcrypto;
create extension if not exists vector;

alter table if exists public.semantic_documents
  add column if not exists role_scope text[] default '{}',
  add column if not exists intent_scope text[] default '{}',
  add column if not exists related_kpis text[] default '{}',
  add column if not exists related_join_paths jsonb default '[]'::jsonb,
  add column if not exists answer_templates jsonb default '[]'::jsonb,
  add column if not exists confidence_rules jsonb default '[]'::jsonb,
  add column if not exists missing_data_rules jsonb default '[]'::jsonb;

create table if not exists public.kpi_definitions (
  kpi_id uuid primary key default gen_random_uuid(),
  kpi_name text not null,
  business_domain text not null,
  definition text not null,
  formula text,
  grain text,
  numerator_definition text,
  denominator_definition text,
  required_tables text[] default '{}',
  required_columns text[] default '{}',
  valid_filters text[] default '{}',
  example_sql text,
  interpretation_guidance text,
  created_at timestamp with time zone not null default now(),
  updated_at timestamp with time zone not null default now(),
  unique (kpi_name, business_domain)
);

create table if not exists public.table_catalog (
  table_catalog_id uuid primary key default gen_random_uuid(),
  table_name text not null unique,
  subject_area text not null,
  business_description text not null,
  grain text,
  primary_key text,
  common_filters text[] default '{}',
  common_joins jsonb default '[]'::jsonb,
  example_questions text[] default '{}',
  created_at timestamp with time zone not null default now(),
  updated_at timestamp with time zone not null default now()
);

create table if not exists public.column_catalog (
  column_catalog_id uuid primary key default gen_random_uuid(),
  table_name text not null,
  column_name text not null,
  business_name text,
  business_description text,
  data_type text,
  semantic_type text,
  pii_flag boolean default false,
  metric_flag boolean default false,
  dimension_flag boolean default false,
  example_values text[] default '{}',
  created_at timestamp with time zone not null default now(),
  updated_at timestamp with time zone not null default now(),
  unique (table_name, column_name)
);

create table if not exists public.join_path_catalog (
  join_path_id uuid primary key default gen_random_uuid(),
  business_question_type text not null,
  source_table text not null,
  target_table text not null,
  join_condition text not null,
  join_type text not null default 'left join',
  business_reason text,
  example_sql text,
  created_at timestamp with time zone not null default now(),
  updated_at timestamp with time zone not null default now()
);

create table if not exists public.model_catalog (
  model_catalog_id uuid primary key default gen_random_uuid(),
  model_name text not null unique,
  model_type text,
  business_purpose text,
  entity_type text,
  score_column text,
  score_interpretation text,
  source_table text,
  feature_summary text,
  recommended_usage text,
  limitations text,
  example_questions text[] default '{}',
  created_at timestamp with time zone not null default now(),
  updated_at timestamp with time zone not null default now()
);

create table if not exists public.insight_templates (
  template_id uuid primary key default gen_random_uuid(),
  role text,
  intent text,
  business_domain text,
  template_text text not null,
  required_metrics text[] default '{}',
  required_tables text[] default '{}',
  recommended_visualization text,
  created_at timestamp with time zone not null default now(),
  updated_at timestamp with time zone not null default now()
);

create table if not exists public.missing_data_rules (
  rule_id uuid primary key default gen_random_uuid(),
  question_pattern text not null,
  missing_data_condition text not null,
  missing_data_message text not null,
  suggested_additional_data text,
  fallback_answer_strategy text,
  created_at timestamp with time zone not null default now(),
  updated_at timestamp with time zone not null default now()
);

alter table if exists public.insight_test_snapshots
  add column if not exists classified_intent jsonb,
  add column if not exists validation_output jsonb,
  add column if not exists final_answer jsonb,
  add column if not exists key_data_points jsonb,
  add column if not exists missing_data_points jsonb,
  add column if not exists related_context jsonb;

create index if not exists idx_kpi_definitions_domain on public.kpi_definitions(business_domain);
create index if not exists idx_table_catalog_subject_area on public.table_catalog(subject_area);
create index if not exists idx_column_catalog_table on public.column_catalog(table_name);
create index if not exists idx_join_path_catalog_question_type on public.join_path_catalog(business_question_type);
create index if not exists idx_model_catalog_entity_type on public.model_catalog(entity_type);
create index if not exists idx_missing_data_rules_pattern on public.missing_data_rules(question_pattern);

comment on table public.kpi_definitions is 'Business-approved KPI definitions used to ground text-to-SQL and insight explanations.';
comment on table public.table_catalog is 'Human-readable catalog of analytics tables, grains, joins, filters, and common questions.';
comment on table public.column_catalog is 'Column-level semantic catalog for metric, dimension, and PII awareness.';
comment on table public.join_path_catalog is 'Approved join paths that prevent incorrect fact-grain joins in generated SQL.';
comment on table public.model_catalog is 'Insurance ML model catalog for model-score interpretation and recommended usage.';
comment on table public.insight_templates is 'Role and intent specific templates for human-readable insurance insight generation.';
comment on table public.missing_data_rules is 'Rules that tell the AI layer when to publish partial answers or block unsupported claims.';
