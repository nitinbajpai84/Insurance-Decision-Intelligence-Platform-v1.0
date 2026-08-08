-- GenAI-aware next-best-action decisioning layer.
--
-- Run after:
--   014_ml_scoring_serving_schema.sql
--   017_genai_context_layer_pgvector.sql
--   019_use_ollama_embeddings_768.sql
--
-- This script keeps candidate action logic in SQL for transparency, while the
-- Python API can enrich each recommendation with pgvector context and LLM-ready
-- explanations.

create extension if not exists pgcrypto;

alter table public.next_best_actions
  add column if not exists business_reason text,
  add column if not exists model_scores_used jsonb not null default '[]'::jsonb,
  add column if not exists context_used jsonb not null default '[]'::jsonb,
  add column if not exists confidence_score numeric(12,6)
    check (confidence_score is null or confidence_score between 0 and 1);

comment on column public.next_best_actions.business_reason is
  'LLM-readable business explanation for why the action was recommended.';
comment on column public.next_best_actions.model_scores_used is
  'JSON array of model scores and predictions used by the decision.';
comment on column public.next_best_actions.context_used is
  'JSON array of semantic document snippets or IDs used to explain the decision.';
comment on column public.next_best_actions.confidence_score is
  'Decision confidence from 0 to 1 after rule, model, suppression, and agent-capacity adjustments.';

create table if not exists public.nba_decision_audit (
  nba_decision_audit_id uuid primary key default gen_random_uuid(),
  customer_id uuid references public.customers(customer_id) on delete set null,
  agent_id uuid references public.agents(agent_id) on delete set null,
  request_payload jsonb not null default '{}'::jsonb,
  decision_payload jsonb not null default '{}'::jsonb,
  context_document_ids uuid[] not null default '{}',
  decision_status text not null default 'completed'
    check (decision_status in ('started', 'completed', 'persisted', 'failed')),
  error_message text,
  created_at timestamptz not null default now()
);

comment on table public.nba_decision_audit is
  'Audit log for next-best-action API decisions, including inputs, output, semantic context, and status.';

create index if not exists idx_nba_decision_audit_customer_created
  on public.nba_decision_audit (customer_id, created_at desc);

create index if not exists idx_nba_decision_audit_status_created
  on public.nba_decision_audit (decision_status, created_at desc);

create or replace view public.v_nba_latest_customer_scores_v2 as
select
  ms.entity_id::uuid as customer_id,
  max(ms.score) filter (where ms.model_name = 'propensity_to_buy')::numeric(12,6) as propensity_to_buy_score,
  max(ms.score_band) filter (where ms.model_name = 'propensity_to_buy') as propensity_to_buy_band,
  max(ms.score) filter (where ms.model_name = 'customer_churn')::numeric(12,6) as churn_risk_score,
  max(ms.score_band) filter (where ms.model_name = 'customer_churn') as churn_risk_band,
  max(ms.score) filter (where ms.model_name = 'next_best_product')::numeric(12,6) as next_best_product_score,
  max(ms.score_band) filter (where ms.model_name = 'next_best_product') as next_best_product_band,
  max(ms.score) filter (where ms.model_name = 'customer_lifetime_value')::numeric(18,6) as customer_lifetime_value,
  max(ms.score_band) filter (where ms.model_name = 'customer_lifetime_value') as customer_lifetime_value_band,
  max(ms.score_ts) as latest_score_ts,
  jsonb_agg(
    jsonb_build_object(
      'model_score_id', ms.model_score_id,
      'model_name', ms.model_name,
      'model_version', ms.model_version,
      'score_name', ms.score_name,
      'score', ms.score,
      'score_band', ms.score_band,
      'top_reasons', jsonb_build_array(ms.top_reason_1, ms.top_reason_2, ms.top_reason_3)
    )
    order by ms.score_ts desc
  ) filter (
    where ms.model_name in ('propensity_to_buy','customer_churn','next_best_product','customer_lifetime_value')
  ) as customer_model_scores_used
from public.v_latest_model_scores ms
where ms.entity_type = 'customer'
group by ms.entity_id;

comment on view public.v_nba_latest_customer_scores_v2 is
  'Latest customer-level model scores pivoted for CRM next-best-action decisioning.';

create or replace view public.v_nba_agent_capacity_v2 as
with latest_mapa as (
  select distinct on (agent_id)
    agent_id,
    metric_month,
    contacts_count,
    quotes_count,
    applications_count,
    policies_bound_count,
    new_business_premium,
    case
      when contacts_count >= 80 or applications_count >= 35 then 'LOW_CAPACITY'
      when contacts_count >= 50 or applications_count >= 20 then 'MEDIUM_CAPACITY'
      else 'AVAILABLE'
    end as capacity_status
  from public.agent_mapa_metrics
  order by agent_id, metric_month desc
),
latest_agent_score as (
  select
    entity_id::uuid as agent_id,
    score::numeric(12,6) as agent_performance_score,
    score_band as agent_performance_band,
    jsonb_build_object(
      'model_score_id', model_score_id,
      'model_name', model_name,
      'model_version', model_version,
      'score_name', score_name,
      'score', score,
      'score_band', score_band,
      'top_reasons', jsonb_build_array(top_reason_1, top_reason_2, top_reason_3)
    ) as agent_model_score_used
  from public.v_latest_model_scores
  where entity_type = 'agent'
    and model_name = 'agent_performance'
)
select
  a.agent_id,
  coalesce(las.agent_performance_score, 0.50)::numeric(12,6) as agent_performance_score,
  coalesce(las.agent_performance_band, 'MEDIUM') as agent_performance_band,
  coalesce(lm.capacity_status, 'AVAILABLE') as agent_capacity_status,
  coalesce(lm.contacts_count, 0) as latest_contacts_count,
  coalesce(lm.applications_count, 0) as latest_applications_count,
  las.agent_model_score_used
from public.agents a
left join latest_mapa lm on lm.agent_id = a.agent_id
left join latest_agent_score las on las.agent_id = a.agent_id;

comment on view public.v_nba_agent_capacity_v2 is
  'Latest agent performance and workload indicators for avoiding overloaded or low-performing agents.';

create or replace view public.v_nba_customer_decision_context_v2 as
with active_policies as (
  select
    p.customer_id,
    count(*) as active_policy_count,
    bool_or(lower(prod.line_of_business) like '%health%' or lower(prod.product_family) like '%health%' or lower(prod.product_name) like '%health%') as has_health_policy,
    min(p.expiration_date) filter (where p.expiration_date between current_date and current_date + interval '60 days') as next_policy_renewal_date,
    (array_agg(p.agent_id order by p.effective_date desc) filter (where p.agent_id is not null))[1] as primary_agent_id
  from public.policies p
  join public.products prod on prod.product_id = p.product_id
  where p.policy_status in ('active', 'issued', 'renewed')
    and p.effective_date <= current_date
    and p.expiration_date >= current_date
  group by p.customer_id
),
open_opportunities as (
  select
    customer_id,
    count(*) as open_opportunity_count,
    (array_agg(agent_id order by opened_date desc) filter (where agent_id is not null))[1] as opportunity_agent_id
  from public.opportunities
  where opportunity_stage in ('opened', 'quoted', 'application', 'underwriting')
    and customer_id is not null
  group by customer_id
),
complaints as (
  select
    customer_id,
    count(*) filter (where status in ('open', 'in_review', 'escalated')) as unresolved_complaint_count,
    max(complaint_date) as latest_complaint_date
  from public.customer_complaints
  group by customer_id
),
service_issues as (
  select
    customer_id,
    count(*) filter (where status in ('open', 'pending_customer', 'in_progress') or sla_breached) as recent_service_issue_count,
    max(request_ts) as latest_service_issue_ts
  from public.customer_service_requests
  where request_ts >= now() - interval '90 days'
  group by customer_id
),
payment_delays as (
  select
    customer_id,
    count(*) filter (
      where payment_status in ('failed', 'past_due')
         or (due_date is not null and payment_date > due_date + 7)
    ) as payment_delay_count,
    max(coalesce(due_date, payment_date)) as latest_payment_delay_date
  from public.payments
  where coalesce(due_date, payment_date) >= current_date - interval '180 days'
  group by customer_id
),
marketing_opt_out as (
  select customer_id, true as marketing_opt_out
  from public.campaign_responses
  where response_type = 'unsubscribed'
    and customer_id is not null
  group by customer_id
),
policy_lapse_scores as (
  select
    p.customer_id,
    max(ms.score)::numeric(12,6) as lapse_risk_score,
    max(ms.score_band) as lapse_risk_band,
    jsonb_agg(
      jsonb_build_object(
        'model_score_id', ms.model_score_id,
        'model_name', ms.model_name,
        'model_version', ms.model_version,
        'score_name', ms.score_name,
        'score', ms.score,
        'score_band', ms.score_band,
        'policy_id', p.policy_id,
        'top_reasons', jsonb_build_array(ms.top_reason_1, ms.top_reason_2, ms.top_reason_3)
      )
      order by ms.score desc
    ) as policy_model_scores_used
  from public.v_latest_model_scores ms
  join public.policies p on p.policy_id = ms.entity_id
  where ms.entity_type = 'policy'
    and ms.model_name = 'policy_lapse'
  group by p.customer_id
),
lead_scores as (
  select
    l.customer_id,
    max(ms.score)::numeric(12,6) as lead_conversion_score,
    max(ms.score_band) as lead_conversion_band,
    jsonb_agg(
      jsonb_build_object(
        'model_score_id', ms.model_score_id,
        'model_name', ms.model_name,
        'model_version', ms.model_version,
        'score_name', ms.score_name,
        'score', ms.score,
        'score_band', ms.score_band,
        'lead_id', l.lead_id,
        'top_reasons', jsonb_build_array(ms.top_reason_1, ms.top_reason_2, ms.top_reason_3)
      )
      order by ms.score desc
    ) as lead_model_scores_used
  from public.v_latest_model_scores ms
  join public.leads l on l.lead_id = ms.entity_id
  where ms.entity_type = 'lead'
    and ms.model_name = 'lead_conversion'
    and l.customer_id is not null
  group by l.customer_id
),
campaign_scores as (
  select
    ct.customer_id,
    max(ms.score)::numeric(12,6) as campaign_response_score,
    max(ms.score_band) as campaign_response_band,
    jsonb_agg(
      jsonb_build_object(
        'model_score_id', ms.model_score_id,
        'model_name', ms.model_name,
        'model_version', ms.model_version,
        'score_name', ms.score_name,
        'score', ms.score,
        'score_band', ms.score_band,
        'campaign_target_id', ct.campaign_target_id,
        'campaign_id', ct.campaign_id,
        'top_reasons', jsonb_build_array(ms.top_reason_1, ms.top_reason_2, ms.top_reason_3)
      )
      order by ms.score desc
    ) as campaign_model_scores_used
  from public.v_latest_model_scores ms
  join public.campaign_targets ct on ct.campaign_target_id = ms.entity_id
  where ms.entity_type = 'campaign'
    and ms.model_name = 'campaign_response'
    and ct.customer_id is not null
  group by ct.customer_id
),
latest_nbp_prediction as (
  select distinct on (entity_id)
    entity_id::uuid as customer_id,
    recommended_product_id,
    predicted_label as next_best_product_prediction,
    coalesce(probability, confidence_score, predicted_value, 0)::numeric(12,6) as next_best_product_prediction_score,
    jsonb_build_object(
      'model_prediction_id', model_prediction_id,
      'model_name', model_name,
      'model_version', model_version,
      'prediction_type', prediction_type,
      'predicted_label', predicted_label,
      'probability', probability,
      'confidence_score', confidence_score,
      'recommended_product_id', recommended_product_id
    ) as next_best_product_prediction_used
  from public.model_predictions
  where entity_type = 'customer'
    and prediction_type = 'next_best_product'
  order by entity_id, prediction_ts desc
)
select
  c.customer_id,
  coalesce(ap.primary_agent_id, oo.opportunity_agent_id) as agent_id,
  party.preferred_contact_method as customer_contact_preference,
  coalesce(moo.marketing_opt_out, false) as marketing_opt_out,
  coalesce(ap.active_policy_count, 0) as active_policy_count,
  coalesce(ap.has_health_policy, false) as has_health_policy,
  ap.next_policy_renewal_date,
  coalesce(oo.open_opportunity_count, 0) as open_opportunity_count,
  coalesce(comp.unresolved_complaint_count, 0) as unresolved_complaint_count,
  comp.latest_complaint_date,
  coalesce(si.recent_service_issue_count, 0) as recent_service_issue_count,
  si.latest_service_issue_ts,
  coalesce(pd.payment_delay_count, 0) as payment_delay_count,
  pd.latest_payment_delay_date,
  coalesce(cs.propensity_to_buy_score, 0)::numeric(12,6) as propensity_to_buy_score,
  coalesce(pls.lapse_risk_score, 0)::numeric(12,6) as lapse_risk_score,
  coalesce(cs.churn_risk_score, 0)::numeric(12,6) as churn_risk_score,
  coalesce(cs.next_best_product_score, nbp.next_best_product_prediction_score, 0)::numeric(12,6) as next_best_product_score,
  coalesce(ls.lead_conversion_score, 0)::numeric(12,6) as lead_conversion_score,
  coalesce(cs.customer_lifetime_value, 0)::numeric(18,6) as customer_lifetime_value,
  coalesce(camps.campaign_response_score, 0)::numeric(12,6) as campaign_response_score,
  coalesce(ac.agent_performance_score, 0.50)::numeric(12,6) as agent_performance_score,
  coalesce(ac.agent_capacity_status, 'AVAILABLE') as agent_capacity_status,
  coalesce(nbp.recommended_product_id, hp.product_id) as recommended_product_id,
  nbp.next_best_product_prediction,
  jsonb_strip_nulls(
    coalesce(cs.customer_model_scores_used, '[]'::jsonb)
    || coalesce(pls.policy_model_scores_used, '[]'::jsonb)
    || coalesce(ls.lead_model_scores_used, '[]'::jsonb)
    || coalesce(camps.campaign_model_scores_used, '[]'::jsonb)
    || case when ac.agent_model_score_used is null then '[]'::jsonb else jsonb_build_array(ac.agent_model_score_used) end
    || case when nbp.next_best_product_prediction_used is null then '[]'::jsonb else jsonb_build_array(nbp.next_best_product_prediction_used) end
  ) as model_scores_used
from public.customers c
join public.parties party on party.party_id = c.party_id
left join active_policies ap on ap.customer_id = c.customer_id
left join open_opportunities oo on oo.customer_id = c.customer_id
left join complaints comp on comp.customer_id = c.customer_id
left join service_issues si on si.customer_id = c.customer_id
left join payment_delays pd on pd.customer_id = c.customer_id
left join marketing_opt_out moo on moo.customer_id = c.customer_id
left join public.v_nba_latest_customer_scores_v2 cs on cs.customer_id = c.customer_id
left join policy_lapse_scores pls on pls.customer_id = c.customer_id
left join lead_scores ls on ls.customer_id = c.customer_id
left join campaign_scores camps on camps.customer_id = c.customer_id
left join latest_nbp_prediction nbp on nbp.customer_id = c.customer_id
left join public.v_nba_agent_capacity_v2 ac on ac.agent_id = coalesce(ap.primary_agent_id, oo.opportunity_agent_id)
left join lateral (
  select product_id
  from public.products
  where active_flag
    and product_component_type = 'base'
    and (lower(line_of_business) like '%health%' or lower(product_family) like '%health%' or lower(product_name) like '%health%')
  order by product_name
  limit 1
) hp on true;

comment on view public.v_nba_customer_decision_context_v2 is
  'Customer decision context for next-best-action: CRM state, model scores, predictions, complaints, payments, renewals, and agent capacity.';

create or replace view public.v_nba_candidate_actions_v2 as
select
  ctx.customer_id,
  case
    when ctx.agent_capacity_status = 'LOW_CAPACITY' or ctx.agent_performance_score < 0.35 then null
    else ctx.agent_id
  end as agent_id,
  case
    when ctx.unresolved_complaint_count > 0 and ctx.churn_risk_score >= 0.60 then 'Service recovery'
    when ctx.unresolved_complaint_count > 0 then 'Resolve complaint before sales outreach'
    when ctx.recent_service_issue_count > 0 then 'Service recovery follow-up'
    when ctx.next_policy_renewal_date is not null then 'Renewal conversation'
    when ctx.lapse_risk_score >= 0.60 then 'Retention call'
    when ctx.churn_risk_score >= 0.60 then 'Retention call'
    when ctx.propensity_to_buy_score >= 0.70 and not ctx.has_health_policy then 'Health cross-sell'
    when ctx.campaign_response_score >= 0.60 and not ctx.marketing_opt_out then 'Campaign follow-up'
    when ctx.lead_conversion_score >= 0.60 then 'Lead follow-up'
    when ctx.next_best_product_score >= 0.60 then 'Product recommendation follow-up'
    else 'Monitor customer'
  end as recommended_action,
  case
    when ctx.propensity_to_buy_score >= 0.70
      and not ctx.has_health_policy
      and ctx.unresolved_complaint_count = 0
      and not ctx.marketing_opt_out
    then ctx.recommended_product_id
    when ctx.next_best_product_score >= 0.60
      and ctx.unresolved_complaint_count = 0
    then ctx.recommended_product_id
    else null
  end as recommended_product_id,
  round(
    least(1.0, greatest(
      ctx.propensity_to_buy_score,
      ctx.lapse_risk_score,
      ctx.churn_risk_score,
      ctx.next_best_product_score,
      ctx.lead_conversion_score,
      ctx.campaign_response_score,
      case when ctx.customer_lifetime_value >= 10000 then 0.85 else 0 end,
      case when ctx.next_policy_renewal_date is not null then 0.90 else 0 end,
      case when ctx.unresolved_complaint_count > 0 then 0.95 else 0 end,
      case when ctx.recent_service_issue_count > 0 then 0.88 else 0 end,
      case when ctx.payment_delay_count > 0 then 0.75 else 0 end
    )
    - case when ctx.agent_capacity_status = 'LOW_CAPACITY' then 0.08 else 0 end
    - case when ctx.agent_performance_score < 0.35 then 0.08 else 0 end
    ), 6
  )::numeric(12,6) as priority_score,
  case
    when ctx.unresolved_complaint_count > 0 and ctx.churn_risk_score >= 0.60 then 'High churn risk with unresolved complaint: service recovery takes precedence over sales.'
    when ctx.unresolved_complaint_count > 0 then 'Unresolved complaint suppresses sales action and requires service recovery.'
    when ctx.recent_service_issue_count > 0 then 'Recent service issue should be resolved before promotional outreach.'
    when ctx.next_policy_renewal_date is not null then 'Policy renewal is within 60 days.'
    when ctx.lapse_risk_score >= 0.60 then 'Policy lapse risk is high.'
    when ctx.churn_risk_score >= 0.60 then 'Customer churn risk is high.'
    when ctx.propensity_to_buy_score >= 0.70 and not ctx.has_health_policy then 'Propensity is high and customer has no active health policy.'
    when ctx.campaign_response_score >= 0.60 and ctx.marketing_opt_out then 'Marketing opt-out suppresses campaign action.'
    when ctx.campaign_response_score >= 0.60 then 'Campaign response score is high; follow up within 7 days.'
    when ctx.lead_conversion_score >= 0.60 then 'Lead conversion score is high.'
    when ctx.next_best_product_score >= 0.60 then 'Next-best-product signal is high.'
    else 'No urgent rule fired; continue monitoring.'
  end as business_reason,
  case
    when ctx.unresolved_complaint_count > 0 then 'I wanted to personally follow up on your recent concern and help get it resolved.'
    when ctx.recent_service_issue_count > 0 then 'I wanted to check that your recent service request has been handled properly.'
    when ctx.next_policy_renewal_date is not null then 'Your policy renewal is coming up soon. Let us review your coverage and payment options.'
    when ctx.lapse_risk_score >= 0.60 or ctx.churn_risk_score >= 0.60 then 'I would like to review your policy and make sure it still fits your needs.'
    when ctx.propensity_to_buy_score >= 0.70 and not ctx.has_health_policy then 'Based on your current protection needs, it may be worth reviewing health coverage options.'
    when ctx.campaign_response_score >= 0.60 and not ctx.marketing_opt_out then 'Thanks for your interest. I can help answer questions and explain the next step.'
    when ctx.lead_conversion_score >= 0.60 then 'I can help complete your quote or application when convenient.'
    when ctx.next_best_product_score >= 0.60 then 'There may be a product option that complements your current coverage.'
    else 'We will continue monitoring for relevant service or coverage needs.'
  end as suggested_message,
  case
    when ctx.unresolved_complaint_count > 0 then current_date + 3
    when ctx.recent_service_issue_count > 0 then current_date + 3
    when ctx.next_policy_renewal_date is not null then least(ctx.next_policy_renewal_date, current_date + 14)
    when ctx.campaign_response_score >= 0.60 and not ctx.marketing_opt_out then current_date + 7
    else current_date + 30
  end as expiry_date,
  round(
    least(1.0, greatest(0.0,
      0.55
      + case when jsonb_array_length(coalesce(ctx.model_scores_used, '[]'::jsonb)) > 0 then 0.15 else 0 end
      + case when greatest(ctx.propensity_to_buy_score, ctx.lapse_risk_score, ctx.churn_risk_score, ctx.campaign_response_score, ctx.lead_conversion_score, ctx.next_best_product_score) >= 0.75 then 0.15 else 0 end
      + case when ctx.unresolved_complaint_count > 0 or ctx.next_policy_renewal_date is not null then 0.10 else 0 end
      - case when ctx.marketing_opt_out then 0.05 else 0 end
      - case when ctx.agent_capacity_status = 'LOW_CAPACITY' or ctx.agent_performance_score < 0.35 then 0.10 else 0 end
    )), 6
  )::numeric(12,6) as confidence_score,
  ctx.model_scores_used,
  case
    when ctx.unresolved_complaint_count > 0 and ctx.churn_risk_score >= 0.60 then 'churn_complaint_service_recovery'
    when ctx.unresolved_complaint_count > 0 then 'complaint_suppression'
    when ctx.recent_service_issue_count > 0 then 'service_recovery'
    when ctx.next_policy_renewal_date is not null then 'renewal_60d'
    when ctx.lapse_risk_score >= 0.60 then 'lapse_high'
    when ctx.churn_risk_score >= 0.60 then 'churn_high'
    when ctx.propensity_to_buy_score >= 0.70 and not ctx.has_health_policy then 'health_cross_sell'
    when ctx.campaign_response_score >= 0.60 and ctx.marketing_opt_out then 'marketing_opt_out_suppression'
    when ctx.campaign_response_score >= 0.60 then 'campaign_response_high'
    when ctx.lead_conversion_score >= 0.60 then 'lead_conversion_high'
    when ctx.next_best_product_score >= 0.60 then 'nbp_high'
    else 'monitor'
  end as decision_rule,
  case
    when ctx.marketing_opt_out and ctx.campaign_response_score >= 0.60 then 'marketing_opt_out'
    when ctx.unresolved_complaint_count > 0 then 'unresolved_complaint'
    when ctx.agent_capacity_status = 'LOW_CAPACITY' then 'agent_low_capacity'
    when ctx.agent_performance_score < 0.35 then 'agent_low_performance'
    else null
  end as suppression_reason,
  ctx.agent_id as original_agent_id,
  ctx.customer_contact_preference,
  ctx.marketing_opt_out,
  ctx.active_policy_count,
  ctx.has_health_policy,
  ctx.next_policy_renewal_date,
  ctx.open_opportunity_count,
  ctx.unresolved_complaint_count,
  ctx.recent_service_issue_count,
  ctx.payment_delay_count,
  ctx.propensity_to_buy_score,
  ctx.lapse_risk_score,
  ctx.churn_risk_score,
  ctx.next_best_product_score,
  ctx.lead_conversion_score,
  ctx.customer_lifetime_value,
  ctx.campaign_response_score,
  ctx.agent_performance_score,
  ctx.agent_capacity_status,
  ctx.next_best_product_prediction
from public.v_nba_customer_decision_context_v2 ctx;

comment on view public.v_nba_candidate_actions_v2 is
  'Transparent candidate next-best-actions with priorities, model evidence, confidence, and suppressions.';

create or replace function public.generate_next_best_actions_v2(p_limit integer default 1000)
returns table(
  customer_id uuid,
  agent_id uuid,
  recommended_action text,
  recommended_product_id uuid,
  priority_score numeric,
  business_reason text,
  model_scores_used jsonb,
  suggested_message text,
  expiry_date date,
  confidence_score numeric
)
language plpgsql
security invoker
as $$
begin
  insert into public.next_best_actions (
    customer_id,
    agent_id,
    product_id,
    action_type,
    action_rank,
    priority_score,
    due_date,
    action_status,
    action_reason,
    recommended_action,
    suggested_message,
    expiry_date,
    decision_rule,
    suppression_reason,
    business_reason,
    model_scores_used,
    confidence_score
  )
  select
    r.customer_id,
    r.agent_id,
    r.recommended_product_id,
    case
      when r.recommended_action in ('Service recovery', 'Resolve complaint before sales outreach', 'Service recovery follow-up') then 'service_recovery'
      when r.recommended_action = 'Retention call' then 'retention_outreach'
      when r.recommended_action = 'Renewal conversation' then 'renewal_follow_up'
      when r.recommended_action in ('Health cross-sell', 'Product recommendation follow-up') then 'offer_product'
      when r.recommended_action = 'Campaign follow-up' then 'send_campaign'
      when r.recommended_action = 'Lead follow-up' then 'assign_lead'
      else 'call_customer'
    end,
    row_number() over (order by r.priority_score desc, r.expiry_date asc)::integer,
    r.priority_score,
    r.expiry_date,
    'recommended',
    r.business_reason,
    r.recommended_action,
    r.suggested_message,
    r.expiry_date,
    r.decision_rule,
    r.suppression_reason,
    r.business_reason,
    r.model_scores_used,
    r.confidence_score
  from public.v_nba_candidate_actions_v2 r
  where r.recommended_action <> 'Monitor customer'
  order by r.priority_score desc, r.expiry_date asc
  limit least(greatest(p_limit, 1), 5000);

  return query
  select
    r.customer_id,
    r.agent_id,
    r.recommended_action,
    r.recommended_product_id,
    r.priority_score,
    r.business_reason,
    r.model_scores_used,
    r.suggested_message,
    r.expiry_date,
    r.confidence_score
  from public.v_nba_candidate_actions_v2 r
  where r.recommended_action <> 'Monitor customer'
  order by r.priority_score desc, r.expiry_date asc
  limit least(greatest(p_limit, 1), 5000);
end;
$$;

comment on function public.generate_next_best_actions_v2(integer) is
  'Generates and stores GenAI-aware next-best-actions with model evidence and confidence.';
