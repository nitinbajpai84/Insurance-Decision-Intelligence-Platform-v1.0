-- Diagnostics for ML feature views before materializing tables.
-- Run after 006_ml_feature_engineering_views.sql.
--
-- Purpose:
--   1. Confirm each feature view returns rows.
--   2. Confirm monthly/snapshot distribution where applicable.
--   3. Identify which views need chunked refresh in the SQL Editor.

set statement_timeout = '2min';

-- Overall view row counts. If any of these time out, refresh that table in smaller chunks.
select 'v_propensity_to_buy_features' as view_name, count(*) as row_count from public.v_propensity_to_buy_features
union all select 'v_next_best_product_features', count(*) from public.v_next_best_product_features
union all select 'v_customer_churn_features', count(*) from public.v_customer_churn_features
union all select 'v_policy_lapse_features', count(*) from public.v_policy_lapse_features
union all select 'v_agent_performance_features', count(*) from public.v_agent_performance_features
union all select 'v_next_best_customer_features', count(*) from public.v_next_best_customer_features
union all select 'v_lead_conversion_features', count(*) from public.v_lead_conversion_features
union all select 'v_agent_attrition_features', count(*) from public.v_agent_attrition_features
union all select 'v_claim_prediction_features', count(*) from public.v_claim_prediction_features
union all select 'v_fraud_detection_features', count(*) from public.v_fraud_detection_features
union all select 'v_customer_lifetime_value_features', count(*) from public.v_customer_lifetime_value_features
union all select 'v_campaign_response_features', count(*) from public.v_campaign_response_features
order by view_name;

-- Monthly distribution for the largest customer/agent/campaign feature sets.
select 'propensity_to_buy_features' as feature_table, snapshot_date, count(*) as row_count
from public.v_propensity_to_buy_features
group by snapshot_date
union all
select 'next_best_product_features', snapshot_date, count(*)
from public.v_next_best_product_features
group by snapshot_date
union all
select 'customer_churn_features', snapshot_date, count(*)
from public.v_customer_churn_features
group by snapshot_date
union all
select 'agent_performance_features', snapshot_date, count(*)
from public.v_agent_performance_features
group by snapshot_date
union all
select 'agent_attrition_features', snapshot_date, count(*)
from public.v_agent_attrition_features
group by snapshot_date
union all
select 'claim_prediction_features', snapshot_date, count(*)
from public.v_claim_prediction_features
group by snapshot_date
union all
select 'customer_lifetime_value_features', snapshot_date, count(*)
from public.v_customer_lifetime_value_features
group by snapshot_date
union all
select 'campaign_response_features', snapshot_date, count(*)
from public.v_campaign_response_features
group by snapshot_date
order by feature_table, snapshot_date;

-- Policy/lead/claim feature sets often have entity-specific snapshot dates.
select 'policy_lapse_features' as feature_table, snapshot_date, count(*) as row_count
from public.v_policy_lapse_features
group by snapshot_date
union all
select 'lead_conversion_features', snapshot_date, count(*)
from public.v_lead_conversion_features
group by snapshot_date
union all
select 'next_best_customer_features', snapshot_date, count(*)
from public.v_next_best_customer_features
group by snapshot_date
union all
select 'fraud_detection_features', date_trunc('month', snapshot_date)::date as snapshot_date, count(*)
from public.v_fraud_detection_features
group by date_trunc('month', snapshot_date)::date
order by feature_table, snapshot_date;
