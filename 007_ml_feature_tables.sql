-- Materialized feature tables for insurance ML models.
-- Run after 006_ml_feature_engineering_views.sql.
--
-- These are physical tables, not PostgreSQL materialized views, so the
-- refresh process can truncate/insert/analyze them in a controlled Python
-- orchestration job. Each table is created from its corresponding
-- leakage-safe v_* feature view with no initial data.

create table if not exists public.propensity_to_buy_features as
select * from public.v_propensity_to_buy_features with no data;
comment on table public.propensity_to_buy_features is
  'Materialized customer-level propensity to buy features. Features use only records before snapshot_date; target_label uses future product purchase outcomes after snapshot_date.';
create index if not exists idx_ptb_features_entity_snapshot on public.propensity_to_buy_features (entity_id, snapshot_date);
create index if not exists idx_ptb_features_target on public.propensity_to_buy_features (target_label);
create index if not exists idx_ptb_features_segment_snapshot on public.propensity_to_buy_features (customer_segment, snapshot_date);

create table if not exists public.next_best_product_features as
select * from public.v_next_best_product_features with no data;
comment on table public.next_best_product_features is
  'Materialized customer-product candidate features for next-best-product modelling. Candidate history is measured before snapshot_date; target_label uses future purchases of the candidate product.';
create index if not exists idx_nbp_features_entity_snapshot on public.next_best_product_features (entity_id, snapshot_date);
create index if not exists idx_nbp_features_customer_snapshot on public.next_best_product_features (customer_id, snapshot_date);
create index if not exists idx_nbp_features_candidate_snapshot on public.next_best_product_features (candidate_product_id, snapshot_date);
create index if not exists idx_nbp_features_target on public.next_best_product_features (target_label);

create table if not exists public.customer_churn_features as
select * from public.v_customer_churn_features with no data;
comment on table public.customer_churn_features is
  'Materialized customer-level churn features. Engagement, payment, complaint, and policy signals stop at snapshot_date; target_label is future churn/lapse/complaint behavior.';
create index if not exists idx_churn_features_entity_snapshot on public.customer_churn_features (entity_id, snapshot_date);
create index if not exists idx_churn_features_target on public.customer_churn_features (target_label);
create index if not exists idx_churn_features_segment_snapshot on public.customer_churn_features (customer_segment, snapshot_date);

create table if not exists public.policy_lapse_features as
select * from public.v_policy_lapse_features with no data;
comment on table public.policy_lapse_features is
  'Materialized active-policy lapse features. Premium, payment, claim, renewal, and policy-event features are restricted to the pre-snapshot period; target_label is future lapse within the prediction window.';
create index if not exists idx_lapse_features_entity_snapshot on public.policy_lapse_features (entity_id, snapshot_date);
create index if not exists idx_lapse_features_customer_snapshot on public.policy_lapse_features (customer_id, snapshot_date);
create index if not exists idx_lapse_features_agent_snapshot on public.policy_lapse_features (agent_id, snapshot_date);
create index if not exists idx_lapse_features_product_snapshot on public.policy_lapse_features (product_id, snapshot_date);
create index if not exists idx_lapse_features_target on public.policy_lapse_features (target_label);

create table if not exists public.agent_performance_features as
select * from public.v_agent_performance_features with no data;
comment on table public.agent_performance_features is
  'Materialized agent-month performance features. MAPA, activity, training, and commission inputs are historical as of snapshot_date; target_label is future production above target.';
create index if not exists idx_agent_perf_features_entity_snapshot on public.agent_performance_features (entity_id, snapshot_date);
create index if not exists idx_agent_perf_features_territory_snapshot on public.agent_performance_features (territory_code, snapshot_date);
create index if not exists idx_agent_perf_features_target on public.agent_performance_features (target_label);

create table if not exists public.next_best_customer_features as
select * from public.v_next_best_customer_features with no data;
comment on table public.next_best_customer_features is
  'Materialized agent-customer candidate features for next-best-customer ranking. Agent and customer signals are historical as of snapshot_date; target_label is future sale by that agent to that customer.';
create index if not exists idx_nbc_features_entity_snapshot on public.next_best_customer_features (entity_id, snapshot_date);
create index if not exists idx_nbc_features_agent_snapshot on public.next_best_customer_features (agent_id, snapshot_date);
create index if not exists idx_nbc_features_customer_snapshot on public.next_best_customer_features (customer_id, snapshot_date);
create index if not exists idx_nbc_features_target on public.next_best_customer_features (target_label);

create table if not exists public.lead_conversion_features as
select * from public.v_lead_conversion_features with no data;
comment on table public.lead_conversion_features is
  'Materialized lead conversion features. Lead, campaign, engagement, and agent features are anchored at snapshot_date; target_label is conversion after snapshot_date.';
create index if not exists idx_lead_features_entity_snapshot on public.lead_conversion_features (entity_id, snapshot_date);
create index if not exists idx_lead_features_customer_snapshot on public.lead_conversion_features (customer_id, snapshot_date);
create index if not exists idx_lead_features_agent_snapshot on public.lead_conversion_features (agent_id, snapshot_date);
create index if not exists idx_lead_features_campaign_snapshot on public.lead_conversion_features (campaign_id, snapshot_date);
create index if not exists idx_lead_features_target on public.lead_conversion_features (target_label);

create table if not exists public.agent_attrition_features as
select * from public.v_agent_attrition_features with no data;
comment on table public.agent_attrition_features is
  'Materialized agent attrition features. Activity, movement, training, and commission trends stop at snapshot_date; target_label is future attrition event.';
create index if not exists idx_agent_attr_features_entity_snapshot on public.agent_attrition_features (entity_id, snapshot_date);
create index if not exists idx_agent_attr_features_territory_snapshot on public.agent_attrition_features (territory_code, snapshot_date);
create index if not exists idx_agent_attr_features_target on public.agent_attrition_features (target_label);

create table if not exists public.claim_prediction_features as
select * from public.v_claim_prediction_features with no data;
comment on table public.claim_prediction_features is
  'Materialized policy-level claim prediction features. Policy, customer, premium, and prior-claim signals are historical as of snapshot_date; target_label is future claim occurrence.';
create index if not exists idx_claim_pred_features_entity_snapshot on public.claim_prediction_features (entity_id, snapshot_date);
create index if not exists idx_claim_pred_features_customer_snapshot on public.claim_prediction_features (customer_id, snapshot_date);
create index if not exists idx_claim_pred_features_target on public.claim_prediction_features (target_label);

create table if not exists public.fraud_detection_features as
select * from public.v_fraud_detection_features with no data;
comment on table public.fraud_detection_features is
  'Materialized claim-level fraud detection features. Only information available at claim report time or before is used; target_label is subsequent fraud investigation outcome.';
create index if not exists idx_fraud_features_entity_snapshot on public.fraud_detection_features (entity_id, snapshot_date);
create index if not exists idx_fraud_features_policy_snapshot on public.fraud_detection_features (policy_id, snapshot_date);
create index if not exists idx_fraud_features_customer_snapshot on public.fraud_detection_features (customer_id, snapshot_date);
create index if not exists idx_fraud_features_target on public.fraud_detection_features (target_label);

create table if not exists public.customer_lifetime_value_features as
select * from public.v_customer_lifetime_value_features with no data;
comment on table public.customer_lifetime_value_features is
  'Materialized customer-level lifetime value features. Historical value and behavior are measured before snapshot_date; target_label is future net value in the prediction window.';
create index if not exists idx_clv_features_entity_snapshot on public.customer_lifetime_value_features (entity_id, snapshot_date);
create index if not exists idx_clv_features_segment_snapshot on public.customer_lifetime_value_features (customer_segment, snapshot_date);
create index if not exists idx_clv_features_target on public.customer_lifetime_value_features (target_label);

create table if not exists public.campaign_response_features as
select * from public.v_campaign_response_features with no data;
comment on table public.campaign_response_features is
  'Materialized campaign-target response features. Customer, campaign, and prior response signals are historical as of snapshot_date; target_label is future campaign response or conversion.';
create index if not exists idx_campaign_resp_features_entity_snapshot on public.campaign_response_features (entity_id, snapshot_date);
create index if not exists idx_campaign_resp_features_customer_snapshot on public.campaign_response_features (customer_id, snapshot_date);
create index if not exists idx_campaign_resp_features_campaign_snapshot on public.campaign_response_features (campaign_id, snapshot_date);
create index if not exists idx_campaign_resp_features_target on public.campaign_response_features (target_label);
