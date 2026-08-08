-- MLOps scoring/serving additions for insurance ML models.
-- Run after 005_ml_schema_enhancements.sql.
--
-- The existing schema already contains:
--   public.model_scores
--   public.model_predictions
--   public.next_best_actions
--
-- This script adds model artifact registry and scoring job tracking, then
-- extends model_scores / next_best_actions with operational serving fields.

create table if not exists public.model_artifacts (
  model_artifact_id uuid primary key default gen_random_uuid(),
  model_name text not null,
  model_version text not null,
  artifact_uri text not null,
  artifact_format text not null check (artifact_format in ('joblib', 'pickle', 'sklearn_pipeline', 'onnx', 'xgboost', 'lightgbm', 'rule_based')),
  feature_table text not null,
  entity_type text not null check (entity_type in ('customer', 'policy', 'agent', 'lead', 'opportunity', 'claim', 'campaign', 'product')),
  score_name text not null,
  model_type text not null check (model_type in ('classification', 'regression', 'ranking')),
  training_snapshot_date date,
  training_metrics jsonb not null default '{}'::jsonb,
  feature_columns jsonb not null default '[]'::jsonb,
  label_column text default 'target_label',
  active_flag boolean not null default true,
  promoted_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (model_name, model_version)
);

comment on table public.model_artifacts is
  'Registry of trained model artifacts available for batch scoring and online serving.';
comment on column public.model_artifacts.artifact_uri is
  'Local path, object-storage URI, or registry URI for the trained model artifact.';
comment on column public.model_artifacts.feature_columns is
  'Ordered feature column list expected by the model. If empty, the scorer infers numeric/model-safe columns from the feature table.';

create table if not exists public.model_scoring_jobs (
  scoring_job_id uuid primary key default gen_random_uuid(),
  job_name text not null,
  job_status text not null check (job_status in ('started', 'running', 'completed', 'failed', 'partial')),
  scoring_mode text not null check (scoring_mode in ('batch', 'single_model', 'single_snapshot')),
  model_name text,
  model_version text,
  snapshot_date date,
  started_at timestamptz not null default now(),
  finished_at timestamptz,
  rows_scored integer not null default 0,
  rows_failed integer not null default 0,
  error_message text,
  job_payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

comment on table public.model_scoring_jobs is
  'Operational log of model scoring jobs, including status, model version, snapshot date, row counts, and errors.';

alter table public.model_scores
  add column if not exists scoring_job_id uuid references public.model_scoring_jobs(scoring_job_id) on delete set null,
  add column if not exists top_reason_1 text,
  add column if not exists top_reason_2 text,
  add column if not exists top_reason_3 text,
  add column if not exists recommended_action text;

comment on column public.model_scores.scoring_job_id is
  'Scoring job that produced this score.';
comment on column public.model_scores.top_reason_1 is
  'Most important local or global reason for the score.';
comment on column public.model_scores.top_reason_2 is
  'Second most important local or global reason for the score.';
comment on column public.model_scores.top_reason_3 is
  'Third most important local or global reason for the score.';
comment on column public.model_scores.recommended_action is
  'Business-friendly recommended action derived from the score.';

alter table public.next_best_actions
  add column if not exists model_score_id uuid references public.model_scores(model_score_id) on delete set null,
  add column if not exists scoring_job_id uuid references public.model_scoring_jobs(scoring_job_id) on delete set null,
  add column if not exists claim_id uuid references public.claims(claim_id) on delete set null;

comment on column public.next_best_actions.model_score_id is
  'Model score that generated or supported the action.';
comment on column public.next_best_actions.scoring_job_id is
  'Scoring job that generated the action.';
comment on column public.next_best_actions.claim_id is
  'Claim targeted by the action, if applicable.';

create index if not exists idx_model_artifacts_active_latest
  on public.model_artifacts (model_name, active_flag, promoted_at desc, created_at desc);

create index if not exists idx_model_scoring_jobs_status_started
  on public.model_scoring_jobs (job_status, started_at desc);

create index if not exists idx_model_scores_job
  on public.model_scores (scoring_job_id);

create index if not exists idx_model_scores_model_entity_ts
  on public.model_scores (model_name, model_version, entity_type, entity_id, score_ts desc);

create index if not exists idx_model_scores_band
  on public.model_scores (model_name, score_band, score_ts desc);

create index if not exists idx_next_best_actions_score
  on public.next_best_actions (model_score_id);

create index if not exists idx_next_best_actions_job
  on public.next_best_actions (scoring_job_id);

create index if not exists idx_next_best_actions_claim
  on public.next_best_actions (claim_id);

create or replace view public.v_latest_model_scores as
select distinct on (model_name, entity_type, entity_id)
  model_score_id,
  scoring_job_id,
  model_name,
  model_version,
  entity_type,
  entity_id,
  score_ts,
  score_name,
  score_value as score,
  probability,
  score_band,
  top_reason_1,
  top_reason_2,
  top_reason_3,
  recommended_action,
  explanation,
  created_at
from public.model_scores
order by model_name, entity_type, entity_id, score_ts desc;

comment on view public.v_latest_model_scores is
  'Latest score per model/entity, shaped for dashboards and downstream decisioning.';
