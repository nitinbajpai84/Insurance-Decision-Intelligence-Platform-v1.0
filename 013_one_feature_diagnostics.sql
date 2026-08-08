-- One-feature-at-a-time diagnostics.
-- Use this instead of selecting large UNION blocks in 011 when the Supabase SQL
-- Editor times out. Run one section at a time.

set statement_timeout = '2min';

-- Propensity to buy
select snapshot_date, count(*) as row_count
from public.v_propensity_to_buy_features
group by snapshot_date
order by snapshot_date;

-- Next best product
select snapshot_date, count(*) as row_count
from public.v_next_best_product_features
group by snapshot_date
order by snapshot_date;

-- Customer churn
select snapshot_date, count(*) as row_count
from public.v_customer_churn_features
group by snapshot_date
order by snapshot_date;

-- Policy lapse
select snapshot_date, count(*) as row_count
from public.v_policy_lapse_features
group by snapshot_date
order by snapshot_date;

-- Agent performance
select snapshot_date, count(*) as row_count
from public.v_agent_performance_features
group by snapshot_date
order by snapshot_date;

-- Next best customer
select snapshot_date, count(*) as row_count
from public.v_next_best_customer_features
group by snapshot_date
order by snapshot_date;

-- Lead conversion
select snapshot_date, count(*) as row_count
from public.v_lead_conversion_features
group by snapshot_date
order by snapshot_date;

-- Agent attrition
select snapshot_date, count(*) as row_count
from public.v_agent_attrition_features
group by snapshot_date
order by snapshot_date;

-- Claim prediction
select snapshot_date, count(*) as row_count
from public.v_claim_prediction_features
group by snapshot_date
order by snapshot_date;

-- Fraud detection, grouped to month because snapshot_date is claim report date.
select date_trunc('month', snapshot_date)::date as snapshot_month, count(*) as row_count
from public.v_fraud_detection_features
group by date_trunc('month', snapshot_date)::date
order by snapshot_month;

-- Customer lifetime value
select snapshot_date, count(*) as row_count
from public.v_customer_lifetime_value_features
group by snapshot_date
order by snapshot_date;

-- Campaign response
select snapshot_date, count(*) as row_count
from public.v_campaign_response_features
group by snapshot_date
order by snapshot_date;
