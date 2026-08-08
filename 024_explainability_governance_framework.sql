-- Explainability and lineage framework for the Insurance Decision Intelligence Copilot.
--
-- Run after:
--   001_insurance_analytics_mvp_schema.sql
--   005_ml_schema_enhancements.sql
--   014_ml_scoring_serving_schema.sql
--   020_genai_next_best_action_decisioning.sql
--
-- This layer persists recommendation explanations, supporting evidence, source
-- lineage, model explanations, and semantic context usage.

create extension if not exists pgcrypto;

create table if not exists public.insight_lineage (
  insight_lineage_id uuid primary key default gen_random_uuid(),
  insight_type text not null check (insight_type in ('recommendation', 'analytics', 'kpi', 'customer_360', 'agent_360', 'campaign_360', 'claims_360', 'model_explanation')),
  insight_ref_table text,
  insight_ref_id uuid,
  user_id uuid references auth.users(id) on delete set null,
  session_id uuid,
  role_code text,
  question text,
  recommendation text,
  business_reason text,
  confidence_score numeric(12,6) check (confidence_score is null or confidence_score between 0 and 1),
  source_tables text[] not null default '{}',
  source_columns jsonb not null default '{}'::jsonb,
  metrics_used text[] not null default '{}',
  business_rules_used text[] not null default '{}',
  ml_models_used text[] not null default '{}',
  context_document_ids uuid[] not null default '{}',
  generated_sql text,
  explanation_payload jsonb not null default '{}'::jsonb,
  status text not null default 'created' check (status in ('created', 'served', 'superseded', 'failed')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

comment on table public.insight_lineage is
  'Governed lineage record for every copilot insight or recommendation, including source tables, columns, metrics, rules, models, context documents, confidence, and timestamp.';
comment on column public.insight_lineage.recommendation is
  'Human-readable recommendation or insight headline.';
comment on column public.insight_lineage.source_columns is
  'JSON object mapping source table names to source column arrays.';
comment on column public.insight_lineage.explanation_payload is
  'Full explanation JSON returned to the frontend or API client.';

create table if not exists public.recommendation_evidence (
  recommendation_evidence_id uuid primary key default gen_random_uuid(),
  insight_lineage_id uuid not null references public.insight_lineage(insight_lineage_id) on delete cascade,
  next_best_action_id uuid references public.next_best_actions(next_best_action_id) on delete set null,
  evidence_type text not null check (evidence_type in ('supporting_fact', 'metric', 'model_score', 'business_rule', 'context_document', 'source_record', 'suppression')),
  evidence_label text not null,
  evidence_value jsonb not null default '{}'::jsonb,
  source_table text,
  source_column text,
  source_record_id uuid,
  metric_name text,
  model_name text,
  business_rule text,
  evidence_weight numeric(12,6) check (evidence_weight is null or evidence_weight between 0 and 1),
  display_order integer not null default 100,
  created_at timestamptz not null default now()
);

comment on table public.recommendation_evidence is
  'Atomic supporting facts, metrics, model scores, rules, source rows, and context evidence behind a recommendation.';

create table if not exists public.model_explanations (
  model_explanation_id uuid primary key default gen_random_uuid(),
  model_score_id uuid references public.model_scores(model_score_id) on delete cascade,
  model_prediction_id uuid references public.model_predictions(model_prediction_id) on delete cascade,
  model_name text not null,
  model_version text,
  entity_type text not null,
  entity_id uuid not null,
  score_name text,
  score_value numeric(18,6),
  probability numeric(12,6) check (probability is null or probability between 0 and 1),
  score_band text,
  explanation_method text not null default 'reason_codes',
  top_features jsonb not null default '[]'::jsonb,
  feature_contributions jsonb not null default '{}'::jsonb,
  shap_values jsonb not null default '{}'::jsonb,
  reason_codes text[] not null default '{}',
  explanation_narrative text,
  source_feature_table text,
  model_artifact_uri text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

comment on table public.model_explanations is
  'Model-level explainability records for scores and predictions, including reason codes, feature contributions, SHAP values when available, and narratives.';

create table if not exists public.context_usage_log (
  context_usage_log_id uuid primary key default gen_random_uuid(),
  insight_lineage_id uuid references public.insight_lineage(insight_lineage_id) on delete cascade,
  semantic_document_id uuid references public.semantic_documents(semantic_document_id) on delete set null,
  title text,
  document_type text,
  business_domain text,
  retrieval_score numeric(12,6),
  usage_purpose text not null check (usage_purpose in ('sql_generation', 'recommendation_explanation', 'kpi_definition', 'entity_360_summary', 'model_explanation', 'follow_up_question')),
  content_snippet text,
  related_tables text[] not null default '{}',
  related_metrics text[] not null default '{}',
  created_at timestamptz not null default now()
);

comment on table public.context_usage_log is
  'Audit log of semantic_documents used as LLM context for a generated insight, recommendation, SQL query, KPI, or explanation.';

create index if not exists idx_insight_lineage_type_created
  on public.insight_lineage (insight_type, created_at desc);
create index if not exists idx_insight_lineage_ref
  on public.insight_lineage (insight_ref_table, insight_ref_id);
create index if not exists idx_insight_lineage_role_created
  on public.insight_lineage (role_code, created_at desc);
create index if not exists idx_insight_lineage_source_tables_gin
  on public.insight_lineage using gin (source_tables);
create index if not exists idx_insight_lineage_models_gin
  on public.insight_lineage using gin (ml_models_used);

create index if not exists idx_recommendation_evidence_lineage_order
  on public.recommendation_evidence (insight_lineage_id, display_order);
create index if not exists idx_recommendation_evidence_nba
  on public.recommendation_evidence (next_best_action_id);
create index if not exists idx_recommendation_evidence_type
  on public.recommendation_evidence (evidence_type, created_at desc);

create index if not exists idx_model_explanations_score
  on public.model_explanations (model_score_id);
create index if not exists idx_model_explanations_prediction
  on public.model_explanations (model_prediction_id);
create index if not exists idx_model_explanations_model_entity
  on public.model_explanations (model_name, entity_type, entity_id, created_at desc);

create index if not exists idx_context_usage_lineage
  on public.context_usage_log (insight_lineage_id, created_at desc);
create index if not exists idx_context_usage_document
  on public.context_usage_log (semantic_document_id, created_at desc);

create or replace view public.v_recommendation_explainability as
select
  il.insight_lineage_id,
  il.insight_ref_id as next_best_action_id,
  il.role_code,
  il.question,
  il.recommendation,
  il.business_reason,
  il.confidence_score,
  il.source_tables,
  il.source_columns,
  il.metrics_used,
  il.business_rules_used,
  il.ml_models_used,
  il.context_document_ids,
  il.created_at as explanation_timestamp,
  coalesce(evidence.evidence_items, '[]'::jsonb) as supporting_evidence,
  coalesce(contexts.context_documents, '[]'::jsonb) as context_documents_used
from public.insight_lineage il
left join lateral (
  select jsonb_agg(
    jsonb_build_object(
      'evidence_type', re.evidence_type,
      'evidence_label', re.evidence_label,
      'evidence_value', re.evidence_value,
      'source_table', re.source_table,
      'source_column', re.source_column,
      'source_record_id', re.source_record_id,
      'metric_name', re.metric_name,
      'model_name', re.model_name,
      'business_rule', re.business_rule,
      'evidence_weight', re.evidence_weight
    )
    order by re.display_order, re.created_at
  ) as evidence_items
  from public.recommendation_evidence re
  where re.insight_lineage_id = il.insight_lineage_id
) evidence on true
left join lateral (
  select jsonb_agg(
    jsonb_build_object(
      'semantic_document_id', cul.semantic_document_id,
      'title', cul.title,
      'document_type', cul.document_type,
      'business_domain', cul.business_domain,
      'retrieval_score', cul.retrieval_score,
      'usage_purpose', cul.usage_purpose,
      'content_snippet', cul.content_snippet
    )
    order by cul.retrieval_score desc nulls last, cul.created_at
  ) as context_documents
  from public.context_usage_log cul
  where cul.insight_lineage_id = il.insight_lineage_id
) contexts on true
where il.insight_type = 'recommendation';

comment on view public.v_recommendation_explainability is
  'API-ready recommendation explainability view with lineage, evidence, source data, models, and context documents.';

create or replace function public.create_recommendation_lineage_from_nba(
  p_next_best_action_id uuid,
  p_question text default null,
  p_role_code text default null
)
returns uuid
language plpgsql
security invoker
as $$
declare
  v_nba record;
  v_lineage_id uuid;
  v_model_names text[];
  v_context_ids uuid[];
begin
  select *
  into v_nba
  from public.next_best_actions
  where next_best_action_id = p_next_best_action_id;

  if not found then
    raise exception 'next_best_action_id not found: %', p_next_best_action_id;
  end if;

  select coalesce(array_agg(distinct item->>'model_name') filter (where item ? 'model_name'), '{}')
  into v_model_names
  from jsonb_array_elements(coalesce(v_nba.model_scores_used, '[]'::jsonb)) item;

  select coalesce(array_agg((item->>'semantic_document_id')::uuid) filter (where item ? 'semantic_document_id'), '{}')
  into v_context_ids
  from jsonb_array_elements(coalesce(v_nba.context_used, '[]'::jsonb)) item
  where (item->>'semantic_document_id') ~* '^[0-9a-f-]{36}$';

  insert into public.insight_lineage (
    insight_type,
    insight_ref_table,
    insight_ref_id,
    role_code,
    question,
    recommendation,
    business_reason,
    confidence_score,
    source_tables,
    source_columns,
    metrics_used,
    business_rules_used,
    ml_models_used,
    context_document_ids,
    explanation_payload,
    status
  )
  values (
    'recommendation',
    'next_best_actions',
    p_next_best_action_id,
    p_role_code,
    p_question,
    coalesce(v_nba.recommended_action, v_nba.action_type),
    coalesce(v_nba.business_reason, v_nba.action_reason),
    v_nba.confidence_score,
    array['next_best_actions','model_scores','model_predictions','customers','policies','products','campaign_responses','customer_complaints','payments'],
    jsonb_build_object(
      'next_best_actions', array['recommended_action','priority_score','business_reason','confidence_score','expiry_date','decision_rule','model_scores_used','context_used'],
      'model_scores', array['model_name','model_version','score_name','score_value','score_band','top_reason_1','top_reason_2','top_reason_3'],
      'policies', array['customer_id','agent_id','product_id','policy_status','effective_date','expiration_date'],
      'campaign_responses', array['response_type','conversion_flag','response_ts'],
      'payments', array['payment_status','due_date','payment_date']
    ),
    array['priority_score','confidence_score','propensity_to_buy_score','lapse_risk_score','churn_risk_score','campaign_response_score','customer_lifetime_value'],
    array_remove(array[v_nba.decision_rule, v_nba.suppression_reason], null),
    coalesce(v_model_names, '{}'),
    coalesce(v_context_ids, '{}'),
    jsonb_build_object(
      'recommendation', coalesce(v_nba.recommended_action, v_nba.action_type),
      'business_reason', coalesce(v_nba.business_reason, v_nba.action_reason),
      'model_scores_used', coalesce(v_nba.model_scores_used, '[]'::jsonb),
      'context_used', coalesce(v_nba.context_used, '[]'::jsonb),
      'suggested_message', v_nba.suggested_message,
      'expiry_date', v_nba.expiry_date,
      'confidence_score', v_nba.confidence_score
    ),
    'created'
  )
  returning insight_lineage_id into v_lineage_id;

  insert into public.recommendation_evidence (
    insight_lineage_id,
    next_best_action_id,
    evidence_type,
    evidence_label,
    evidence_value,
    source_table,
    metric_name,
    model_name,
    evidence_weight,
    display_order
  )
  select
    v_lineage_id,
    p_next_best_action_id,
    'model_score',
    coalesce(item->>'score_name', item->>'model_name', 'model_score'),
    item,
    'model_scores',
    item->>'score_name',
    item->>'model_name',
    case when (item->>'score') ~ '^[0-9.]+$' then (item->>'score')::numeric else null end,
    20 + row_number() over ()
  from jsonb_array_elements(coalesce(v_nba.model_scores_used, '[]'::jsonb)) item;

  insert into public.recommendation_evidence (
    insight_lineage_id,
    next_best_action_id,
    evidence_type,
    evidence_label,
    evidence_value,
    source_table,
    business_rule,
    display_order
  )
  values (
    v_lineage_id,
    p_next_best_action_id,
    case when v_nba.suppression_reason is null then 'business_rule' else 'suppression' end,
    coalesce(v_nba.decision_rule, 'decision_rule'),
    jsonb_build_object('decision_rule', v_nba.decision_rule, 'suppression_reason', v_nba.suppression_reason),
    'next_best_actions',
    v_nba.decision_rule,
    10
  );

  insert into public.context_usage_log (
    insight_lineage_id,
    semantic_document_id,
    title,
    document_type,
    business_domain,
    retrieval_score,
    usage_purpose,
    content_snippet,
    related_tables,
    related_metrics
  )
  select
    v_lineage_id,
    case when (item->>'semantic_document_id') ~* '^[0-9a-f-]{36}$' then (item->>'semantic_document_id')::uuid else null end,
    item->>'title',
    item->>'document_type',
    item->>'business_domain',
    case when item #>> '{score,hybrid}' ~ '^[0-9.]+$' then (item #>> '{score,hybrid}')::numeric else null end,
    'recommendation_explanation',
    item->>'snippet',
    coalesce(array(select jsonb_array_elements_text(item->'related_tables')), '{}'),
    coalesce(array(select jsonb_array_elements_text(item->'related_metrics')), '{}')
  from jsonb_array_elements(coalesce(v_nba.context_used, '[]'::jsonb)) item;

  return v_lineage_id;
end;
$$;

comment on function public.create_recommendation_lineage_from_nba(uuid, text, text) is
  'Creates insight_lineage, recommendation_evidence, and context_usage_log records for a next_best_actions recommendation.';

