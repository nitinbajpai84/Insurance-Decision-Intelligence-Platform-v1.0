-- Optional baseline model artifact registry for scoring smoke tests.
-- Replace these rule_based artifacts with real trained joblib/pickle artifacts
-- once model training is complete.

insert into public.model_artifacts (
  model_name, model_version, artifact_uri, artifact_format, feature_table,
  entity_type, score_name, model_type, training_metrics, feature_columns,
  active_flag, promoted_at
)
values
  (
    'propensity_to_buy', 'baseline_001', 'rule://baseline/propensity_to_buy', 'rule_based',
    'propensity_to_buy_features', 'customer', 'propensity_to_buy', 'classification',
    '{"auc": null, "purpose": "baseline scoring smoke test", "rule_weights": {"engagement_score": 0.04, "digital_events_90d": 0.2, "quote_requests_180d": 0.8, "positive_campaign_responses_prior": 0.5, "missed_payment_count_prior": -0.4}}'::jsonb,
    '[]'::jsonb, true, now()
  ),
  (
    'next_best_product', 'baseline_001', 'rule://baseline/next_best_product', 'rule_based',
    'next_best_product_features', 'customer', 'next_best_product', 'ranking',
    '{"purpose": "baseline scoring smoke test", "rule_weights": {"engagement_score": 0.04, "product_digital_interest_count": 0.7, "prior_quote_count": 0.8, "positive_campaign_responses_prior": 0.5, "prior_same_product_count": -0.6}}'::jsonb,
    '[]'::jsonb, true, now()
  ),
  (
    'customer_churn', 'baseline_001', 'rule://baseline/customer_churn', 'rule_based',
    'customer_churn_features', 'customer', 'customer_churn_risk', 'classification',
    '{"purpose": "baseline scoring smoke test", "rule_weights": {"missed_payments_180d": 0.9, "complaints_365d": 0.8, "sla_breaches_prior": 0.7, "avg_nps_prior": -0.2, "tenure_days": -0.001}}'::jsonb,
    '[]'::jsonb, true, now()
  ),
  (
    'policy_lapse', 'baseline_001', 'rule://baseline/policy_lapse', 'rule_based',
    'policy_lapse_features', 'policy', 'policy_lapse_risk', 'classification',
    '{"purpose": "baseline scoring smoke test", "rule_weights": {"missed_payment_count_prior": 0.9, "complaint_count_prior": 0.7, "latest_premium_change_pct": 0.4, "policy_tenure_days": -0.001}}'::jsonb,
    '[]'::jsonb, true, now()
  ),
  (
    'agent_performance', 'baseline_001', 'rule://baseline/agent_performance', 'rule_based',
    'agent_performance_features', 'agent', 'agent_performance', 'classification',
    '{"purpose": "baseline scoring smoke test", "rule_weights": {"calls_90d": 0.2, "meetings_90d": 0.4, "quotes_180d": 0.4, "bound_180d": 0.9, "nbp_180d": 0.00005, "avg_target_attainment_prior": 0.6}}'::jsonb,
    '[]'::jsonb, true, now()
  ),
  (
    'next_best_customer', 'baseline_001', 'rule://baseline/next_best_customer', 'rule_based',
    'next_best_customer_features', 'agent', 'next_best_customer', 'ranking',
    '{"purpose": "baseline scoring smoke test", "rule_weights": {"customer_engagement_score": 0.05, "prior_agent_calls": 0.3, "prior_agent_meetings": 0.5, "prior_lead_count": 0.4, "prior_customer_policy_count": 0.2}}'::jsonb,
    '[]'::jsonb, true, now()
  ),
  (
    'lead_conversion', 'baseline_001', 'rule://baseline/lead_conversion', 'rule_based',
    'lead_conversion_features', 'lead', 'lead_conversion', 'classification',
    '{"purpose": "baseline scoring smoke test", "rule_weights": {"lead_score": 0.06, "customer_engagement_score": 0.03, "calls_before_snapshot": 0.3, "meetings_before_snapshot": 0.5, "quotes_before_snapshot": 0.9}}'::jsonb,
    '[]'::jsonb, true, now()
  ),
  (
    'agent_attrition', 'baseline_001', 'rule://baseline/agent_attrition', 'rule_based',
    'agent_attrition_features', 'agent', 'agent_attrition_risk', 'classification',
    '{"purpose": "baseline scoring smoke test", "rule_weights": {"commissions_180d": -0.00003, "prior_commissions_180d": 0.00001, "chargebacks_prior": 0.7, "completed_training_prior": -0.2, "avg_target_attainment_prior": -0.6}}'::jsonb,
    '[]'::jsonb, true, now()
  ),
  (
    'claim_prediction', 'baseline_001', 'rule://baseline/claim_prediction', 'rule_based',
    'claim_prediction_features', 'customer', 'claim_occurrence_risk', 'classification',
    '{"purpose": "baseline scoring smoke test", "rule_weights": {"active_policy_count": 0.4, "active_annual_premium": 0.00002, "prior_claim_count": 0.9, "prior_incurred_claims": 0.00003, "rider_count": 0.2}}'::jsonb,
    '[]'::jsonb, true, now()
  ),
  (
    'fraud_detection', 'baseline_001', 'rule://baseline/fraud_detection', 'rule_based',
    'fraud_detection_features', 'claim', 'fraud_risk', 'classification',
    '{"purpose": "baseline scoring smoke test", "rule_weights": {"paid_amount": 0.00004, "reserve_amount": 0.00003, "report_lag_days": 0.08, "prior_customer_claim_count": 0.8, "prior_fraud_indicators": 1.2}}'::jsonb,
    '[]'::jsonb, true, now()
  ),
  (
    'customer_lifetime_value', 'baseline_001', 'rule://baseline/customer_lifetime_value', 'rule_based',
    'customer_lifetime_value_features', 'customer', 'customer_lifetime_value', 'regression',
    '{"purpose": "baseline scoring smoke test", "rule_weights": {"prior_policy_count": 100, "prior_earned_premium": 0.7, "prior_incurred_claims": -0.4, "complaint_count_prior": -50, "tenure_days": 0.05}}'::jsonb,
    '[]'::jsonb, true, now()
  ),
  (
    'campaign_response', 'baseline_001', 'rule://baseline/campaign_response', 'rule_based',
    'campaign_response_features', 'campaign', 'campaign_response', 'classification',
    '{"purpose": "baseline scoring smoke test", "rule_weights": {"engagement_score": 0.04, "prior_positive_responses": 0.7, "digital_events_90d": 0.2, "complaint_count_prior": -0.4}}'::jsonb,
    '[]'::jsonb, true, now()
  )
on conflict (model_name, model_version) do update
set artifact_uri = excluded.artifact_uri,
    artifact_format = excluded.artifact_format,
    feature_table = excluded.feature_table,
    entity_type = excluded.entity_type,
    score_name = excluded.score_name,
    model_type = excluded.model_type,
    training_metrics = excluded.training_metrics,
    feature_columns = excluded.feature_columns,
    active_flag = true,
    promoted_at = now(),
    updated_at = now();

select model_name, model_version, feature_table, entity_type, score_name, model_type, active_flag
from public.model_artifacts
where model_version = 'baseline_001'
order by model_name;
