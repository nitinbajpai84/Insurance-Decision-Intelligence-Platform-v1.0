-- Smoke test for the GenAI next-best-action layer.
-- Run in Supabase SQL Editor after 020_genai_next_best_action_decisioning.sql.

with required_objects as (
  select 'view' as object_type, 'v_nba_latest_customer_scores_v2' as object_name
  union all select 'view', 'v_nba_agent_capacity_v2'
  union all select 'view', 'v_nba_customer_decision_context_v2'
  union all select 'view', 'v_nba_candidate_actions_v2'
  union all select 'table', 'nba_decision_audit'
  union all select 'function', 'generate_next_best_actions_v2'
),
checks as (
  select
    object_type,
    object_name,
    case
      when object_type in ('view','table') then to_regclass('public.' || object_name) is not null
      when object_type = 'function' then to_regprocedure('public.' || object_name || '(integer)') is not null
      else false
    end as exists_flag
  from required_objects
)
select
  'nba_objects' as check_area,
  object_name,
  case when exists_flag then 'PASS' else 'FAIL' end as status
from checks
order by object_type, object_name;

select
  'candidate_actions' as check_area,
  count(*) as row_count,
  count(*) filter (where recommended_action <> 'Monitor customer') as actionable_count,
  min(priority_score) as min_priority_score,
  max(priority_score) as max_priority_score,
  min(confidence_score) as min_confidence_score,
  max(confidence_score) as max_confidence_score
from public.v_nba_candidate_actions_v2;

select
  customer_id,
  agent_id,
  recommended_action,
  recommended_product_id,
  priority_score,
  business_reason,
  jsonb_array_length(coalesce(model_scores_used, '[]'::jsonb)) as model_scores_used_count,
  suggested_message,
  expiry_date,
  confidence_score,
  decision_rule,
  suppression_reason
from public.v_nba_candidate_actions_v2
where recommended_action <> 'Monitor customer'
order by priority_score desc, expiry_date asc
limit 10;

