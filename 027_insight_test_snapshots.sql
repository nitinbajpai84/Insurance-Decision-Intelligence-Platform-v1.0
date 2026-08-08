create extension if not exists pgcrypto;

create table if not exists public.insight_test_snapshots (
  snapshot_id uuid primary key default gen_random_uuid(),
  test_run_id uuid not null,
  role varchar(100),
  question text not null,
  intent varchar(100),
  retrieved_context jsonb,
  generated_sql text,
  sql_validation_status varchar(100),
  sql_execution_status varchar(100),
  row_count int,
  result_preview jsonb,
  models_used jsonb,
  tables_used jsonb,
  columns_used jsonb,
  business_insight text,
  recommendations jsonb,
  confidence_score numeric,
  latency_ms int,
  error_message text,
  created_at timestamp with time zone not null default now()
);

create index if not exists idx_insight_test_snapshots_run on public.insight_test_snapshots(test_run_id);
create index if not exists idx_insight_test_snapshots_role on public.insight_test_snapshots(role);
create index if not exists idx_insight_test_snapshots_created on public.insight_test_snapshots(created_at desc);

comment on table public.insight_test_snapshots is
  'Stores text-to-SQL smoke test evidence proving role, context, SQL, execution, result preview, model usage, insight, and latency.';

comment on column public.insight_test_snapshots.test_run_id is 'Groups one smoke test run across roles and questions.';
comment on column public.insight_test_snapshots.retrieved_context is 'pgvector and keyword context used by the SQL generation flow.';
comment on column public.insight_test_snapshots.generated_sql is 'Read-only SQL generated for the business question.';
comment on column public.insight_test_snapshots.result_preview is 'Small result sample used for business insight generation.';
comment on column public.insight_test_snapshots.models_used is 'Model score or prediction assets used or referenced by the answer.';
