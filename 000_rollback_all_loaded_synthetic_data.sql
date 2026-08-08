-- Rollback all loaded synthetic insurance data.
--
-- Use this when core CSV data was already loaded and you need to reload the
-- latest rider-aware / ML-ready CSVs.
--
-- This script preserves tables, extensions, indexes, functions, and triggers.
-- It removes loaded data from both core tables and ML enhancement tables.
-- It is safe to run even if some ML tables do not exist yet.

begin;

-- Drop derived views that depend on loaded policy/product/premium data.
drop view if exists public.v_new_business_premium_by_rider;
drop view if exists public.v_policy_rider_tags;

-- Clear ML enhancement tables first, if present.
do $$
begin
  if to_regclass('public.next_best_actions') is not null then
    execute 'truncate table public.next_best_actions restart identity cascade';
  end if;

  if to_regclass('public.model_predictions') is not null then
    execute 'truncate table public.model_predictions restart identity cascade';
  end if;

  if to_regclass('public.model_scores') is not null then
    execute 'truncate table public.model_scores restart identity cascade';
  end if;

  if to_regclass('public.model_features') is not null then
    execute 'truncate table public.model_features restart identity cascade';
  end if;

  if to_regclass('public.ml_training_labels') is not null then
    execute 'truncate table public.ml_training_labels restart identity cascade';
  end if;

  if to_regclass('public.claim_fraud_indicators') is not null then
    execute 'truncate table public.claim_fraud_indicators restart identity cascade';
  end if;

  if to_regclass('public.claim_assessments') is not null then
    execute 'truncate table public.claim_assessments restart identity cascade';
  end if;

  if to_regclass('public.claim_parties') is not null then
    execute 'truncate table public.claim_parties restart identity cascade';
  end if;

  if to_regclass('public.agent_attrition_events') is not null then
    execute 'truncate table public.agent_attrition_events restart identity cascade';
  end if;

  if to_regclass('public.agent_training') is not null then
    execute 'truncate table public.agent_training restart identity cascade';
  end if;

  if to_regclass('public.agent_commissions') is not null then
    execute 'truncate table public.agent_commissions restart identity cascade';
  end if;

  if to_regclass('public.agent_targets') is not null then
    execute 'truncate table public.agent_targets restart identity cascade';
  end if;

  if to_regclass('public.agent_meetings') is not null then
    execute 'truncate table public.agent_meetings restart identity cascade';
  end if;

  if to_regclass('public.agent_calls') is not null then
    execute 'truncate table public.agent_calls restart identity cascade';
  end if;

  if to_regclass('public.underwriting_decisions') is not null then
    execute 'truncate table public.underwriting_decisions restart identity cascade';
  end if;

  if to_regclass('public.applications') is not null then
    execute 'truncate table public.applications restart identity cascade';
  end if;

  if to_regclass('public.proposals') is not null then
    execute 'truncate table public.proposals restart identity cascade';
  end if;

  if to_regclass('public.quotes') is not null then
    execute 'truncate table public.quotes restart identity cascade';
  end if;

  if to_regclass('public.policy_lapse_events') is not null then
    execute 'truncate table public.policy_lapse_events restart identity cascade';
  end if;

  if to_regclass('public.policy_renewals') is not null then
    execute 'truncate table public.policy_renewals restart identity cascade';
  end if;

  if to_regclass('public.policy_events') is not null then
    execute 'truncate table public.policy_events restart identity cascade';
  end if;

  if to_regclass('public.customer_service_requests') is not null then
    execute 'truncate table public.customer_service_requests restart identity cascade';
  end if;

  if to_regclass('public.customer_nps') is not null then
    execute 'truncate table public.customer_nps restart identity cascade';
  end if;

  if to_regclass('public.customer_satisfaction_surveys') is not null then
    execute 'truncate table public.customer_satisfaction_surveys restart identity cascade';
  end if;

  if to_regclass('public.customer_complaints') is not null then
    execute 'truncate table public.customer_complaints restart identity cascade';
  end if;

  if to_regclass('public.customer_digital_events') is not null then
    execute 'truncate table public.customer_digital_events restart identity cascade';
  end if;

  if to_regclass('public.customer_behavior_daily') is not null then
    execute 'truncate table public.customer_behavior_daily restart identity cascade';
  end if;
end $$;

-- Clear core loaded tables.
truncate table
  public.query_audit_log,
  public.semantic_documents,
  public.business_glossary,
  public.customer_engagement_events,
  public.campaign_responses,
  public.campaign_targets,
  public.claims,
  public.payments,
  public.premiums,
  public.policy_coverages,
  public.policies,
  public.opportunities,
  public.leads,
  public.campaigns,
  public.products,
  public.agent_mapa_metrics,
  public.agent_movements,
  public.agents,
  public.addresses,
  public.customers,
  public.parties
restart identity cascade;

commit;
