-- Next-best-action decisioning layer using model scores and CRM context.
-- Run after:
--   001_insurance_analytics_mvp_schema.sql
--   005_ml_schema_enhancements.sql
--   014_ml_scoring_serving_schema.sql
--
-- This layer keeps the decision logic transparent in SQL while the Python
-- engine/API can run the same rules for batch or customer-level decisions.

alter table public.next_best_actions
  add column if not exists recommended_action text,
  add column if not exists suggested_message text,
  add column if not exists expiry_date date,
  add column if not exists decision_rule text,
  add column if not exists suppression_reason text;

comment on column public.next_best_actions.recommended_action is
  'Human-readable next-best-action recommendation.';
comment on column public.next_best_actions.suggested_message is
  'Suggested customer or agent message for the recommended action.';
comment on column public.next_best_actions.expiry_date is
  'Date after which the recommendation should be considered stale.';
comment on column public.next_best_actions.decision_rule is
  'Rule or model/rule combination that selected the recommendation.';
comment on column public.next_best_actions.suppression_reason is
  'Reason the recommendation was suppressed or changed, if applicable.';

create index if not exists idx_next_best_actions_customer_expiry
  on public.next_best_actions (customer_id, expiry_date desc);

create or replace view public.v_nba_latest_customer_scores as
select
  entity_id::uuid as customer_id,
  max(score) filter (where model_name = 'propensity_to_buy') as propensity_to_buy_score,
  max(score) filter (where model_name = 'customer_churn') as churn_risk_score,
  max(score) filter (where model_name = 'next_best_product') as next_best_product_score,
  max(score) filter (where model_name = 'claim_prediction') as claim_prediction_score,
  max(score) filter (where model_name = 'customer_lifetime_value') as customer_lifetime_value,
  max(score_ts) as latest_score_ts
from public.v_latest_model_scores
where entity_type = 'customer'
group by entity_id;

comment on view public.v_nba_latest_customer_scores is
  'Pivoted latest customer-level model scores used by the next-best-action engine.';

create or replace view public.v_nba_customer_context as
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
    count(*) filter (
      where status in ('open', 'pending_customer', 'in_progress')
         or sla_breached
    ) as recent_service_issue_count,
    max(request_ts) as latest_service_issue_ts
  from public.customer_service_requests
  where request_ts >= now() - interval '90 days'
  group by customer_id
),
marketing_opt_out as (
  select
    customer_id,
    true as marketing_opt_out
  from public.campaign_responses
  where response_type = 'unsubscribed'
    and customer_id is not null
  group by customer_id
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
  hp.product_id as default_health_product_id,
  coalesce(scores.propensity_to_buy_score, 0) as propensity_to_buy_score,
  coalesce(policy_lapse.lapse_risk_score, 0) as lapse_risk_score,
  coalesce(scores.churn_risk_score, 0) as churn_risk_score,
  coalesce(scores.next_best_product_score, 0) as next_best_product_score,
  coalesce(lead_conversion.lead_conversion_score, 0) as lead_conversion_score,
  coalesce(scores.customer_lifetime_value, 0) as customer_lifetime_value,
  coalesce(campaign_response.campaign_response_score, 0) as campaign_response_score
from public.customers c
join public.parties party on party.party_id = c.party_id
left join active_policies ap on ap.customer_id = c.customer_id
left join open_opportunities oo on oo.customer_id = c.customer_id
left join complaints comp on comp.customer_id = c.customer_id
left join service_issues si on si.customer_id = c.customer_id
left join marketing_opt_out moo on moo.customer_id = c.customer_id
left join lateral (
  select product_id
  from public.products
  where active_flag
    and product_component_type = 'base'
    and (
      lower(line_of_business) like '%health%'
      or lower(product_family) like '%health%'
      or lower(product_name) like '%health%'
    )
  order by product_name
  limit 1
) hp on true
left join public.v_nba_latest_customer_scores scores on scores.customer_id = c.customer_id
left join lateral (
  select max(ms.score) as lapse_risk_score
  from public.v_latest_model_scores ms
  join public.policies p on p.policy_id = ms.entity_id
  where ms.model_name = 'policy_lapse'
    and ms.entity_type = 'policy'
    and p.customer_id = c.customer_id
) policy_lapse on true
left join lateral (
  select max(ms.score) as lead_conversion_score
  from public.v_latest_model_scores ms
  join public.leads l on l.lead_id = ms.entity_id
  where ms.model_name = 'lead_conversion'
    and ms.entity_type = 'lead'
    and l.customer_id = c.customer_id
 ) lead_conversion on true
left join lateral (
  select max(ms.score) as campaign_response_score
  from public.v_latest_model_scores ms
  join public.campaign_targets ct on ct.campaign_target_id = ms.entity_id
  where ms.model_name = 'campaign_response'
    and ms.entity_type = 'campaign'
    and ct.customer_id = c.customer_id
) campaign_response on true;

comment on view public.v_nba_customer_context is
  'Customer-level CRM, policy, service, contact, and model-score context for next-best-action decisioning.';

create or replace view public.v_next_best_action_recommendations as
select
  customer_id,
  agent_id,
  case
    when unresolved_complaint_count > 0 then 'Resolve complaint before sales outreach'
    when recent_service_issue_count > 0 then 'Service recovery follow-up'
    when next_policy_renewal_date is not null then 'Renewal conversation'
    when lapse_risk_score >= 0.60 then 'Retention call'
    when churn_risk_score >= 0.60 then 'Retention call'
    when propensity_to_buy_score >= 0.70 and not has_health_policy then 'Health cross-sell'
    when campaign_response_score >= 0.60 and not marketing_opt_out then 'Campaign follow-up'
    when lead_conversion_score >= 0.60 then 'Lead follow-up'
    when next_best_product_score >= 0.60 then 'Product recommendation follow-up'
    else 'Monitor customer'
  end as recommended_action,
  case
    when propensity_to_buy_score >= 0.70 and not has_health_policy and unresolved_complaint_count = 0 then default_health_product_id
    else null
  end as recommended_product_id,
  round(least(1.0, greatest(
    coalesce(lapse_risk_score, 0),
    coalesce(churn_risk_score, 0),
    coalesce(propensity_to_buy_score, 0),
    coalesce(campaign_response_score, 0),
    coalesce(lead_conversion_score, 0),
    case when customer_lifetime_value >= 10000 then 0.85 else 0 end,
    case when next_policy_renewal_date is not null then 0.90 else 0 end,
    case when unresolved_complaint_count > 0 then 0.95 else 0 end,
    case when recent_service_issue_count > 0 then 0.88 else 0 end
  ))::numeric, 6) as priority_score,
  case
    when unresolved_complaint_count > 0 then 'Unresolved complaint suppresses sales action and requires service recovery.'
    when recent_service_issue_count > 0 then 'Recent service issue should be resolved before promotional outreach.'
    when next_policy_renewal_date is not null then 'Policy renewal is within 60 days.'
    when lapse_risk_score >= 0.60 then 'Lapse risk is high.'
    when churn_risk_score >= 0.60 then 'Churn risk is high.'
    when propensity_to_buy_score >= 0.70 and not has_health_policy then 'Propensity is high and customer has no active health policy.'
    when campaign_response_score >= 0.60 and not marketing_opt_out then 'Campaign response score is high; follow up within 7 days.'
    when marketing_opt_out and campaign_response_score >= 0.60 then 'Marketing opt-out suppresses campaign action.'
    when lead_conversion_score >= 0.60 then 'Lead conversion score is high.'
    when next_best_product_score >= 0.60 then 'Next-best-product score is high.'
    else 'No urgent rule fired; continue monitoring.'
  end as reason,
  case
    when unresolved_complaint_count > 0 then 'We noticed your recent concern and would like to help resolve it before discussing anything else.'
    when recent_service_issue_count > 0 then 'I wanted to check that your recent service request has been handled properly.'
    when next_policy_renewal_date is not null then 'Your policy renewal is coming up soon. Let us review your coverage and payment options.'
    when lapse_risk_score >= 0.60 or churn_risk_score >= 0.60 then 'I would like to review your policy and make sure it still fits your needs.'
    when propensity_to_buy_score >= 0.70 and not has_health_policy then 'Based on your current protection needs, it may be worth reviewing health coverage options.'
    when campaign_response_score >= 0.60 and not marketing_opt_out then 'Thanks for your interest. I can help answer questions and explain the next step.'
    when lead_conversion_score >= 0.60 then 'I can help complete your quote or application when convenient.'
    when next_best_product_score >= 0.60 then 'There may be a product option that complements your current coverage.'
    else 'We will continue monitoring for relevant service or coverage needs.'
  end as suggested_message,
  case
    when unresolved_complaint_count > 0 then current_date + 3
    when recent_service_issue_count > 0 then current_date + 3
    when next_policy_renewal_date is not null then least(next_policy_renewal_date, current_date + 14)
    when campaign_response_score >= 0.60 and not marketing_opt_out then current_date + 7
    else current_date + 30
  end as expiry_date,
  customer_contact_preference,
  marketing_opt_out,
  active_policy_count,
  has_health_policy,
  next_policy_renewal_date,
  open_opportunity_count,
  unresolved_complaint_count,
  recent_service_issue_count,
  propensity_to_buy_score,
  lapse_risk_score,
  churn_risk_score,
  next_best_product_score,
  lead_conversion_score,
  customer_lifetime_value,
  campaign_response_score,
  case
    when unresolved_complaint_count > 0 then 'complaint_suppression'
    when recent_service_issue_count > 0 then 'service_recovery'
    when next_policy_renewal_date is not null then 'renewal_60d'
    when lapse_risk_score >= 0.60 then 'lapse_high'
    when churn_risk_score >= 0.60 then 'churn_high'
    when propensity_to_buy_score >= 0.70 and not has_health_policy then 'health_cross_sell'
    when campaign_response_score >= 0.60 and not marketing_opt_out then 'campaign_response_high'
    when marketing_opt_out and campaign_response_score >= 0.60 then 'marketing_opt_out_suppression'
    when lead_conversion_score >= 0.60 then 'lead_conversion_high'
    when next_best_product_score >= 0.60 then 'nbp_high'
    else 'monitor'
  end as decision_rule
from public.v_nba_customer_context;

comment on view public.v_next_best_action_recommendations is
  'Transparent next-best-action recommendation view using model scores, CRM context, service suppression, and policy renewal rules.';

create or replace function public.generate_next_best_actions(p_limit integer default 1000)
returns table(customer_id uuid, agent_id uuid, recommended_action text, recommended_product_id uuid, priority_score numeric, reason text, suggested_message text, expiry_date date)
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
    suppression_reason
  )
  select
    r.customer_id,
    r.agent_id,
    r.recommended_product_id,
    case
      when r.recommended_action in ('Resolve complaint before sales outreach', 'Service recovery follow-up') then 'service_recovery'
      when r.recommended_action in ('Retention call') then 'retention_outreach'
      when r.recommended_action = 'Renewal conversation' then 'renewal_follow_up'
      when r.recommended_action = 'Health cross-sell' then 'offer_product'
      when r.recommended_action = 'Campaign follow-up' then 'send_campaign'
      when r.recommended_action = 'Lead follow-up' then 'assign_lead'
      when r.recommended_action = 'Product recommendation follow-up' then 'offer_product'
      else 'call_customer'
    end as action_type,
    row_number() over (order by r.priority_score desc, r.expiry_date asc)::integer as action_rank,
    r.priority_score,
    r.expiry_date,
    'recommended',
    r.reason,
    r.recommended_action,
    r.suggested_message,
    r.expiry_date,
    r.decision_rule,
    case
      when r.unresolved_complaint_count > 0 and r.recommended_action <> 'Resolve complaint before sales outreach' then 'unresolved_complaint'
      when r.marketing_opt_out and r.recommended_action = 'Campaign follow-up' then 'marketing_opt_out'
      else null
    end as suppression_reason
  from public.v_next_best_action_recommendations r
  where r.recommended_action <> 'Monitor customer'
  order by r.priority_score desc, r.expiry_date asc
  limit p_limit;

  return query
  select
    r.customer_id,
    r.agent_id,
    r.recommended_action,
    r.recommended_product_id,
    r.priority_score,
    r.reason,
    r.suggested_message,
    r.expiry_date
  from public.v_next_best_action_recommendations r
  where r.recommended_action <> 'Monitor customer'
  order by r.priority_score desc, r.expiry_date asc
  limit p_limit;
end;
$$;

comment on function public.generate_next_best_actions(integer) is
  'Generates and stores next-best-actions from the transparent SQL recommendation view.';
