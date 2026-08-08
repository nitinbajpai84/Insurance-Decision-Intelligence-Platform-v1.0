-- Database-native quality checks for materialized ML feature tables.
-- Run after 007_ml_feature_tables.sql and after refreshing the tables.

create or replace view public.v_ml_feature_row_counts as
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
union all select 'campaign_response_features', count(*) from public.campaign_response_features;

comment on view public.v_ml_feature_row_counts is
  'Row count checks for all physical ML feature tables.';

create or replace view public.v_ml_feature_required_null_checks as
select 'propensity_to_buy_features' as feature_table,
       count(*) filter (where entity_id is null) as entity_id_nulls,
       count(*) filter (where snapshot_date is null) as snapshot_date_nulls,
       count(*) filter (where target_label is null) as target_label_nulls,
       count(*) filter (where training_window_start is null or training_window_end is null) as training_window_nulls,
       count(*) filter (where prediction_window_start is null or prediction_window_end is null) as prediction_window_nulls
from public.propensity_to_buy_features
union all select 'next_best_product_features',
       count(*) filter (where entity_id is null),
       count(*) filter (where snapshot_date is null),
       count(*) filter (where target_label is null),
       count(*) filter (where training_window_start is null or training_window_end is null),
       count(*) filter (where prediction_window_start is null or prediction_window_end is null)
from public.next_best_product_features
union all select 'customer_churn_features',
       count(*) filter (where entity_id is null), count(*) filter (where snapshot_date is null), count(*) filter (where target_label is null),
       count(*) filter (where training_window_start is null or training_window_end is null), count(*) filter (where prediction_window_start is null or prediction_window_end is null)
from public.customer_churn_features
union all select 'policy_lapse_features',
       count(*) filter (where entity_id is null), count(*) filter (where snapshot_date is null), count(*) filter (where target_label is null),
       count(*) filter (where training_window_start is null or training_window_end is null), count(*) filter (where prediction_window_start is null or prediction_window_end is null)
from public.policy_lapse_features
union all select 'agent_performance_features',
       count(*) filter (where entity_id is null), count(*) filter (where snapshot_date is null), count(*) filter (where target_label is null),
       count(*) filter (where training_window_start is null or training_window_end is null), count(*) filter (where prediction_window_start is null or prediction_window_end is null)
from public.agent_performance_features
union all select 'next_best_customer_features',
       count(*) filter (where entity_id is null), count(*) filter (where snapshot_date is null), count(*) filter (where target_label is null),
       count(*) filter (where training_window_start is null or training_window_end is null), count(*) filter (where prediction_window_start is null or prediction_window_end is null)
from public.next_best_customer_features
union all select 'lead_conversion_features',
       count(*) filter (where entity_id is null), count(*) filter (where snapshot_date is null), count(*) filter (where target_label is null),
       count(*) filter (where training_window_start is null or training_window_end is null), count(*) filter (where prediction_window_start is null or prediction_window_end is null)
from public.lead_conversion_features
union all select 'agent_attrition_features',
       count(*) filter (where entity_id is null), count(*) filter (where snapshot_date is null), count(*) filter (where target_label is null),
       count(*) filter (where training_window_start is null or training_window_end is null), count(*) filter (where prediction_window_start is null or prediction_window_end is null)
from public.agent_attrition_features
union all select 'claim_prediction_features',
       count(*) filter (where entity_id is null), count(*) filter (where snapshot_date is null), count(*) filter (where target_label is null),
       count(*) filter (where training_window_start is null or training_window_end is null), count(*) filter (where prediction_window_start is null or prediction_window_end is null)
from public.claim_prediction_features
union all select 'fraud_detection_features',
       count(*) filter (where entity_id is null), count(*) filter (where snapshot_date is null), count(*) filter (where target_label is null),
       count(*) filter (where training_window_start is null or training_window_end is null), count(*) filter (where prediction_window_start is null or prediction_window_end is null)
from public.fraud_detection_features
union all select 'customer_lifetime_value_features',
       count(*) filter (where entity_id is null), count(*) filter (where snapshot_date is null), count(*) filter (where target_label is null),
       count(*) filter (where training_window_start is null or training_window_end is null), count(*) filter (where prediction_window_start is null or prediction_window_end is null)
from public.customer_lifetime_value_features
union all select 'campaign_response_features',
       count(*) filter (where entity_id is null), count(*) filter (where snapshot_date is null), count(*) filter (where target_label is null),
       count(*) filter (where training_window_start is null or training_window_end is null), count(*) filter (where prediction_window_start is null or prediction_window_end is null)
from public.campaign_response_features;

comment on view public.v_ml_feature_required_null_checks is
  'Required-column null checks for all physical ML feature tables.';

create or replace view public.v_ml_feature_window_checks as
select feature_table,
       count(*) filter (
         where training_window_start > training_window_end
            or training_window_end > snapshot_date
            or prediction_window_start < snapshot_date
            or prediction_window_end <= prediction_window_start
       ) as bad_window_rows
from (
  select 'propensity_to_buy_features' as feature_table, entity_id, snapshot_date, training_window_start, training_window_end, prediction_window_start, prediction_window_end from public.propensity_to_buy_features
  union all select 'next_best_product_features', entity_id, snapshot_date, training_window_start, training_window_end, prediction_window_start, prediction_window_end from public.next_best_product_features
  union all select 'customer_churn_features', entity_id, snapshot_date, training_window_start, training_window_end, prediction_window_start, prediction_window_end from public.customer_churn_features
  union all select 'policy_lapse_features', entity_id, snapshot_date, training_window_start, training_window_end, prediction_window_start, prediction_window_end from public.policy_lapse_features
  union all select 'agent_performance_features', entity_id, snapshot_date, training_window_start, training_window_end, prediction_window_start, prediction_window_end from public.agent_performance_features
  union all select 'next_best_customer_features', entity_id, snapshot_date, training_window_start, training_window_end, prediction_window_start, prediction_window_end from public.next_best_customer_features
  union all select 'lead_conversion_features', entity_id, snapshot_date, training_window_start, training_window_end, prediction_window_start, prediction_window_end from public.lead_conversion_features
  union all select 'agent_attrition_features', entity_id, snapshot_date, training_window_start, training_window_end, prediction_window_start, prediction_window_end from public.agent_attrition_features
  union all select 'claim_prediction_features', entity_id, snapshot_date, training_window_start, training_window_end, prediction_window_start, prediction_window_end from public.claim_prediction_features
  union all select 'fraud_detection_features', entity_id, snapshot_date, training_window_start, training_window_end, prediction_window_start, prediction_window_end from public.fraud_detection_features
  union all select 'customer_lifetime_value_features', entity_id, snapshot_date, training_window_start, training_window_end, prediction_window_start, prediction_window_end from public.customer_lifetime_value_features
  union all select 'campaign_response_features', entity_id, snapshot_date, training_window_start, training_window_end, prediction_window_start, prediction_window_end from public.campaign_response_features
) all_windows
group by feature_table;

comment on view public.v_ml_feature_window_checks is
  'Leakage prevention checks. bad_window_rows should be zero for every feature table.';

create or replace view public.v_ml_feature_target_distribution as
select feature_table,
       count(*) as row_count,
       count(target_label) as non_null_targets,
       count(distinct target_label) as distinct_targets,
       min(target_label::numeric) as min_target,
       max(target_label::numeric) as max_target,
       avg(target_label::numeric) as avg_target
from (
  select 'propensity_to_buy_features' as feature_table, target_label from public.propensity_to_buy_features
  union all select 'next_best_product_features', target_label from public.next_best_product_features
  union all select 'customer_churn_features', target_label from public.customer_churn_features
  union all select 'policy_lapse_features', target_label from public.policy_lapse_features
  union all select 'agent_performance_features', target_label from public.agent_performance_features
  union all select 'next_best_customer_features', target_label from public.next_best_customer_features
  union all select 'lead_conversion_features', target_label from public.lead_conversion_features
  union all select 'agent_attrition_features', target_label from public.agent_attrition_features
  union all select 'claim_prediction_features', target_label from public.claim_prediction_features
  union all select 'fraud_detection_features', target_label from public.fraud_detection_features
  union all select 'customer_lifetime_value_features', target_label from public.customer_lifetime_value_features
  union all select 'campaign_response_features', target_label from public.campaign_response_features
) all_targets
group by feature_table;

comment on view public.v_ml_feature_target_distribution is
  'Target label distribution checks for all physical ML feature tables.';
