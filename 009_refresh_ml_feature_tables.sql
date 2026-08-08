-- Refresh physical ML feature tables from leakage-safe feature views.
-- Run after:
--   006_ml_feature_engineering_views.sql
--   007_ml_feature_tables.sql
--
-- 007 creates empty physical tables with WITH NO DATA. This script populates
-- them from the corresponding v_* feature views and refreshes planner stats.

set statement_timeout = '15min';

truncate table public.propensity_to_buy_features;
insert into public.propensity_to_buy_features
select * from public.v_propensity_to_buy_features;
analyze public.propensity_to_buy_features;

truncate table public.next_best_product_features;
insert into public.next_best_product_features
select * from public.v_next_best_product_features;
analyze public.next_best_product_features;

truncate table public.customer_churn_features;
insert into public.customer_churn_features
select * from public.v_customer_churn_features;
analyze public.customer_churn_features;

truncate table public.policy_lapse_features;
insert into public.policy_lapse_features
select * from public.v_policy_lapse_features;
analyze public.policy_lapse_features;

truncate table public.agent_performance_features;
insert into public.agent_performance_features
select * from public.v_agent_performance_features;
analyze public.agent_performance_features;

truncate table public.next_best_customer_features;
insert into public.next_best_customer_features
select * from public.v_next_best_customer_features;
analyze public.next_best_customer_features;

truncate table public.lead_conversion_features;
insert into public.lead_conversion_features
select * from public.v_lead_conversion_features;
analyze public.lead_conversion_features;

truncate table public.agent_attrition_features;
insert into public.agent_attrition_features
select * from public.v_agent_attrition_features;
analyze public.agent_attrition_features;

truncate table public.claim_prediction_features;
insert into public.claim_prediction_features
select * from public.v_claim_prediction_features;
analyze public.claim_prediction_features;

truncate table public.fraud_detection_features;
insert into public.fraud_detection_features
select * from public.v_fraud_detection_features;
analyze public.fraud_detection_features;

truncate table public.customer_lifetime_value_features;
insert into public.customer_lifetime_value_features
select * from public.v_customer_lifetime_value_features;
analyze public.customer_lifetime_value_features;

truncate table public.campaign_response_features;
insert into public.campaign_response_features
select * from public.v_campaign_response_features;
analyze public.campaign_response_features;

-- Immediate row-count confirmation.
select 'propensity_to_buy_features' as feature_table, count(*) as row_count from public.propensity_to_buy_features
union all select 'next_best_product_features', count(*) from public.next_best_product_features
union all select 'customer_churn_features', count(*) from public.customer_churn_features
union all select 'policy_lapse_features', count(*) from public.policy_lapse_features
union all select 'agent_performance_features', count(*) from public.agent_performance_features
union all select 'next_best_customer_features', count(*) from public.next_best_customer_features
union all select 'lead_conversion_features', count(*) from public.lead_conversion_features
union all select 'agent_attrition_features', count(*) from public.agent_attrition_features
union all select 'claim_prediction_features', count(*) from public.claim_prediction_features
union all select 'fraud_detection_features', count(*) from public.fraud_detection_features
union all select 'customer_lifetime_value_features', count(*) from public.customer_lifetime_value_features
union all select 'campaign_response_features', count(*) from public.campaign_response_features
order by feature_table;
