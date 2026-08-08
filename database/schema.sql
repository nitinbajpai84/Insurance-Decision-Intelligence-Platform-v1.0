-- ============================================================================
-- Insurance PoC V2.0 — DuckDB Schema
-- Target: DuckDB (insurance_v2.duckdb)
-- Column names are aligned with the V1 synthetic CSV exports in ..\data\
-- so seed_data.py can load them directly by column-name intersection.
-- FK relationships are documented as comments (DuckDB supports FKs, but we
-- keep them as comments so CSV loads are order-independent and tolerant).
-- ============================================================================

-- ---------------------------------------------------------------------------
-- PARTY (shared identity backbone — referenced by customers, agents, addresses)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS parties (
  party_id VARCHAR PRIMARY KEY,
  party_type VARCHAR,                  -- person | organization
  display_name VARCHAR,
  first_name VARCHAR,
  middle_name VARCHAR,
  last_name VARCHAR,
  organization_name VARCHAR,
  date_of_birth DATE,
  tax_id_last4 VARCHAR,
  email VARCHAR,
  phone VARCHAR,
  preferred_contact_method VARCHAR,
  created_at TIMESTAMP,
  updated_at TIMESTAMP
);

-- ===========================================================================
-- CUSTOMER DOMAIN
-- ===========================================================================

CREATE TABLE IF NOT EXISTS customers (
  customer_id VARCHAR PRIMARY KEY,
  party_id VARCHAR,                    -- FK -> parties.party_id
  customer_number VARCHAR,
  customer_segment VARCHAR,            -- e.g. Young family, Established professional
  lifecycle_stage VARCHAR,
  acquisition_date DATE,
  risk_tier VARCHAR,
  engagement_score DOUBLE,
  household_party_id VARCHAR,          -- FK -> households.household_id (party of type household)
  customer_type_code VARCHAR,          -- FK -> customer_type.customer_type_code (V2 addition)
  created_at TIMESTAMP,
  updated_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS households (
  household_id VARCHAR PRIMARY KEY,
  household_name VARCHAR,
  primary_customer_id VARCHAR,         -- FK -> customers.customer_id
  household_segment VARCHAR,
  member_count INTEGER,
  total_annual_premium DOUBLE,         -- SGD
  region VARCHAR,                      -- SG Central | SG East | SG West | SG North | SG North-East
  created_at TIMESTAMP,
  updated_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS household_members (
  household_member_id VARCHAR PRIMARY KEY,
  household_id VARCHAR,                -- FK -> households.household_id
  customer_id VARCHAR,                 -- FK -> customers.customer_id
  relationship_to_head VARCHAR,        -- head | spouse | child | parent | other
  is_primary BOOLEAN,
  joined_date DATE,
  created_at TIMESTAMP,
  updated_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS customer_type (
  customer_type_code VARCHAR PRIMARY KEY,
  type_name VARCHAR,
  description VARCHAR,
  default_risk_tier VARCHAR,
  active_flag BOOLEAN,
  created_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS addresses (
  address_id VARCHAR PRIMARY KEY,
  party_id VARCHAR,                    -- FK -> parties.party_id
  address_type VARCHAR,
  line1 VARCHAR,
  line2 VARCHAR,
  city VARCHAR,
  state_code VARCHAR,
  postal_code VARCHAR,
  country_code VARCHAR,                -- SG for Singapore book
  latitude DOUBLE,
  longitude DOUBLE,
  is_current BOOLEAN,
  effective_date DATE,
  expiration_date DATE,
  created_at TIMESTAMP,
  updated_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS customer_digital_events (
  customer_digital_event_id VARCHAR PRIMARY KEY,
  customer_id VARCHAR,                 -- FK -> customers.customer_id
  party_id VARCHAR,                    -- FK -> parties.party_id
  policy_id VARCHAR,                   -- FK -> policies.policy_id
  campaign_id VARCHAR,                 -- FK -> campaigns.campaign_id
  event_ts TIMESTAMP,
  session_id VARCHAR,
  device_type VARCHAR,
  channel VARCHAR,
  event_name VARCHAR,
  event_category VARCHAR,
  page_name VARCHAR,
  product_id VARCHAR,                  -- FK -> products.product_id
  dwell_seconds INTEGER,
  metadata JSON,
  created_at TIMESTAMP,
  updated_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS customer_behavior_daily (
  customer_behavior_daily_id VARCHAR PRIMARY KEY,
  customer_id VARCHAR,                 -- FK -> customers.customer_id
  behavior_date DATE,
  active_policy_count INTEGER,
  open_claim_count INTEGER,
  payment_missed_count_90d INTEGER,
  digital_event_count INTEGER,
  service_request_count INTEGER,
  complaint_count INTEGER,
  campaign_touch_count INTEGER,
  quote_count_90d INTEGER,
  engagement_score DOUBLE,
  churn_signal_score DOUBLE,
  feature_snapshot JSON,
  created_at TIMESTAMP,
  updated_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS customer_engagement_events (
  customer_engagement_event_id VARCHAR PRIMARY KEY,
  customer_id VARCHAR,                 -- FK -> customers.customer_id
  policy_id VARCHAR,                   -- FK -> policies.policy_id
  claim_id VARCHAR,                    -- FK -> claims.claim_id
  campaign_id VARCHAR,                 -- FK -> campaigns.campaign_id
  agent_id VARCHAR,                    -- FK -> agents.agent_id
  event_ts TIMESTAMP,
  event_type VARCHAR,
  channel VARCHAR,
  sentiment_score DOUBLE,
  duration_seconds INTEGER,
  metadata JSON,
  created_at TIMESTAMP,
  updated_at TIMESTAMP
);

-- Singular name per V2 data model; seeded from V1 customer_satisfaction_surveys.csv
CREATE TABLE IF NOT EXISTS customer_satisfaction_survey (
  customer_satisfaction_survey_id VARCHAR PRIMARY KEY,
  customer_id VARCHAR,                 -- FK -> customers.customer_id
  policy_id VARCHAR,                   -- FK -> policies.policy_id
  claim_id VARCHAR,                    -- FK -> claims.claim_id
  agent_id VARCHAR,                    -- FK -> agents.agent_id
  survey_date DATE,
  survey_type VARCHAR,
  channel VARCHAR,
  satisfaction_score DOUBLE,
  effort_score DOUBLE,
  response_text VARCHAR,
  created_at TIMESTAMP,
  updated_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS customer_service_requests (
  customer_service_request_id VARCHAR PRIMARY KEY,
  customer_id VARCHAR,                 -- FK -> customers.customer_id
  policy_id VARCHAR,                   -- FK -> policies.policy_id
  claim_id VARCHAR,                    -- FK -> claims.claim_id
  assigned_agent_id VARCHAR,           -- FK -> agents.agent_id
  request_ts TIMESTAMP,
  request_type VARCHAR,
  channel VARCHAR,
  priority VARCHAR,
  status VARCHAR,
  first_response_ts TIMESTAMP,
  resolved_ts TIMESTAMP,
  sla_breached BOOLEAN,
  service_summary VARCHAR,
  created_at TIMESTAMP,
  updated_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS customer_complaints (
  customer_complaint_id VARCHAR PRIMARY KEY,
  customer_id VARCHAR,                 -- FK -> customers.customer_id
  policy_id VARCHAR,                   -- FK -> policies.policy_id
  claim_id VARCHAR,                    -- FK -> claims.claim_id
  agent_id VARCHAR,                    -- FK -> agents.agent_id
  complaint_date DATE,
  complaint_channel VARCHAR,
  complaint_category VARCHAR,
  severity VARCHAR,
  status VARCHAR,
  resolution_date DATE,
  resolution_days INTEGER,
  sentiment_score DOUBLE,
  complaint_text VARCHAR,
  created_at TIMESTAMP,
  updated_at TIMESTAMP
);

-- ===========================================================================
-- POLICY DOMAIN
-- ===========================================================================

CREATE TABLE IF NOT EXISTS policies (
  policy_id VARCHAR PRIMARY KEY,
  policy_number VARCHAR,
  customer_id VARCHAR,                 -- FK -> customers.customer_id
  agent_id VARCHAR,                    -- FK -> agents.agent_id
  product_id VARCHAR,                  -- FK -> products.product_id
  opportunity_id VARCHAR,              -- FK -> opportunities.opportunity_id
  prior_policy_id VARCHAR,             -- FK -> policies.policy_id (self)
  policy_status VARCHAR,               -- active | in_force | issued | lapsed | cancelled
  effective_date DATE,
  expiration_date DATE,
  issue_date DATE,
  cancellation_date DATE,
  source_channel VARCHAR,
  payment_plan VARCHAR,
  annual_premium DOUBLE,               -- SGD
  written_premium DOUBLE,              -- SGD
  created_at TIMESTAMP,
  updated_at TIMESTAMP
);

-- Singular name per V2 data model; seeded from V1 policy_coverages.csv
CREATE TABLE IF NOT EXISTS policy_coverage (
  policy_coverage_id VARCHAR PRIMARY KEY,
  policy_id VARCHAR,                   -- FK -> policies.policy_id
  product_id VARCHAR,                  -- FK -> products.product_id
  coverage_code VARCHAR,
  coverage_name VARCHAR,
  coverage_status VARCHAR,
  is_rider BOOLEAN,
  rider_tag VARCHAR,
  limit_amount DOUBLE,
  deductible_amount DOUBLE,
  exposure_basis VARCHAR,
  exposure_value DOUBLE,
  effective_date DATE,
  expiration_date DATE,
  created_at TIMESTAMP,
  updated_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS policy_renewals (
  policy_renewal_id VARCHAR PRIMARY KEY,
  policy_id VARCHAR,                   -- FK -> policies.policy_id
  prior_policy_id VARCHAR,             -- FK -> policies.policy_id
  renewal_policy_id VARCHAR,           -- FK -> policies.policy_id
  customer_id VARCHAR,                 -- FK -> customers.customer_id
  agent_id VARCHAR,                    -- FK -> agents.agent_id
  renewal_cycle_date DATE,
  renewal_offer_date DATE,
  renewal_due_date DATE,
  renewal_status VARCHAR,
  offered_premium DOUBLE,
  expiring_premium DOUBLE,
  premium_change_pct DOUBLE,
  retention_reason VARCHAR,
  created_at TIMESTAMP,
  updated_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS policy_events (
  policy_event_id VARCHAR PRIMARY KEY,
  policy_id VARCHAR,                   -- FK -> policies.policy_id
  customer_id VARCHAR,                 -- FK -> customers.customer_id
  agent_id VARCHAR,                    -- FK -> agents.agent_id
  event_ts TIMESTAMP,
  event_type VARCHAR,
  event_reason VARCHAR,
  source_system VARCHAR,
  old_status VARCHAR,
  new_status VARCHAR,
  premium_delta DOUBLE,
  event_payload JSON,
  created_at TIMESTAMP,
  updated_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS policy_type_config (
  policy_type_code VARCHAR PRIMARY KEY,
  policy_type_name VARCHAR,
  line_of_business VARCHAR,
  default_term_months INTEGER,
  grace_period_days INTEGER,
  min_annual_premium DOUBLE,           -- SGD
  max_sum_assured DOUBLE,              -- SGD
  renewable_flag BOOLEAN,
  rider_allowed_flag BOOLEAN,
  active_flag BOOLEAN,
  created_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS policy_lapse_events (
  policy_lapse_event_id VARCHAR PRIMARY KEY,
  policy_id VARCHAR,                   -- FK -> policies.policy_id
  customer_id VARCHAR,                 -- FK -> customers.customer_id
  agent_id VARCHAR,                    -- FK -> agents.agent_id
  lapse_event_date DATE,
  lapse_stage VARCHAR,
  missed_payment_count INTEGER,
  days_past_due INTEGER,
  reinstatement_date DATE,
  lapse_reason VARCHAR,
  intervention_type VARCHAR,
  created_at TIMESTAMP,
  updated_at TIMESTAMP
);

-- ===========================================================================
-- AGENT DOMAIN
-- ===========================================================================

CREATE TABLE IF NOT EXISTS agents (
  agent_id VARCHAR PRIMARY KEY,
  party_id VARCHAR,                    -- FK -> parties.party_id
  agent_number VARCHAR,
  agency_party_id VARCHAR,             -- FK -> parties.party_id
  license_state VARCHAR,
  license_number VARCHAR,
  channel VARCHAR,                     -- agency | bancassurance | digital | partner
  territory_code VARCHAR,              -- SG East, SG West, ...
  appointment_date DATE,
  termination_date DATE,
  status VARCHAR,
  created_at TIMESTAMP,
  updated_at TIMESTAMP
);

-- V2 monthly rollup; seeded from V1 agent_mapa_metrics.csv
CREATE TABLE IF NOT EXISTS agent_performance (
  agent_performance_id VARCHAR PRIMARY KEY,
  agent_id VARCHAR,                    -- FK -> agents.agent_id
  metric_month DATE,
  leads_count INTEGER,
  contacts_count INTEGER,
  quotes_count INTEGER,
  applications_count INTEGER,
  policies_bound_count INTEGER,
  new_business_premium DOUBLE,         -- SGD
  renewal_premium DOUBLE,              -- SGD
  retained_policy_count INTEGER,
  lapsed_policy_count INTEGER,
  claims_count INTEGER,
  loss_ratio DOUBLE,
  conversion_rate DOUBLE,              -- derived: policies_bound / quotes
  performance_band VARCHAR,            -- derived: Top | Stable | Coaching
  created_at TIMESTAMP,
  updated_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS agent_training (
  agent_training_id VARCHAR PRIMARY KEY,
  agent_id VARCHAR,                    -- FK -> agents.agent_id
  training_code VARCHAR,
  training_name VARCHAR,
  training_category VARCHAR,
  assigned_date DATE,
  completed_date DATE,
  completion_status VARCHAR,
  assessment_score DOUBLE,
  certification_flag BOOLEAN,
  created_at TIMESTAMP,
  updated_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS agent_calls (
  agent_call_id VARCHAR PRIMARY KEY,
  agent_id VARCHAR,                    -- FK -> agents.agent_id
  customer_id VARCHAR,                 -- FK -> customers.customer_id
  lead_id VARCHAR,                     -- FK -> leads.lead_id
  opportunity_id VARCHAR,              -- FK -> opportunities.opportunity_id
  campaign_id VARCHAR,                 -- FK -> campaigns.campaign_id
  call_ts TIMESTAMP,
  call_direction VARCHAR,
  call_outcome VARCHAR,
  duration_seconds INTEGER,
  sentiment_score DOUBLE,
  next_step_date DATE,
  call_notes VARCHAR,
  created_at TIMESTAMP,
  updated_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS agent_meetings (
  agent_meeting_id VARCHAR PRIMARY KEY,
  agent_id VARCHAR,                    -- FK -> agents.agent_id
  customer_id VARCHAR,                 -- FK -> customers.customer_id
  lead_id VARCHAR,                     -- FK -> leads.lead_id
  opportunity_id VARCHAR,              -- FK -> opportunities.opportunity_id
  meeting_ts TIMESTAMP,
  meeting_type VARCHAR,
  meeting_channel VARCHAR,
  meeting_outcome VARCHAR,
  duration_minutes INTEGER,
  product_id VARCHAR,                  -- FK -> products.product_id
  meeting_notes VARCHAR,
  created_at TIMESTAMP,
  updated_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS agent_commissions (
  agent_commission_id VARCHAR PRIMARY KEY,
  agent_id VARCHAR,                    -- FK -> agents.agent_id
  policy_id VARCHAR,                   -- FK -> policies.policy_id
  product_id VARCHAR,                  -- FK -> products.product_id
  commission_period DATE,
  commission_type VARCHAR,
  premium_basis_amount DOUBLE,         -- SGD
  commission_rate DOUBLE,
  commission_amount DOUBLE,            -- SGD
  paid_date DATE,
  chargeback_flag BOOLEAN,
  created_at TIMESTAMP,
  updated_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS agent_targets (
  agent_target_id VARCHAR PRIMARY KEY,
  agent_id VARCHAR,                    -- FK -> agents.agent_id
  target_period_start DATE,
  target_period_end DATE,
  target_type VARCHAR,
  product_id VARCHAR,                  -- FK -> products.product_id
  target_value DOUBLE,
  actual_value DOUBLE,
  attainment_pct DOUBLE,
  created_at TIMESTAMP,
  updated_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS agent_service_events (
  agent_service_event_id VARCHAR PRIMARY KEY,
  agent_id VARCHAR,                    -- FK -> agents.agent_id
  customer_id VARCHAR,                 -- FK -> customers.customer_id
  policy_id VARCHAR,                   -- FK -> policies.policy_id
  event_ts TIMESTAMP,
  event_type VARCHAR,                  -- policy_servicing | claim_support | renewal_follow_up | onboarding
  channel VARCHAR,
  outcome VARCHAR,
  duration_minutes INTEGER,
  notes VARCHAR,
  created_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS agent_assessments (
  agent_assessment_id VARCHAR PRIMARY KEY,
  agent_id VARCHAR,                    -- FK -> agents.agent_id
  assessment_date DATE,
  assessment_type VARCHAR,             -- annual_review | compliance_audit | sales_quality | mystery_shop
  assessor VARCHAR,
  overall_score DOUBLE,                -- 0-100
  compliance_score DOUBLE,
  sales_quality_score DOUBLE,
  customer_outcome_score DOUBLE,
  result_band VARCHAR,                 -- Exceeds | Meets | Needs improvement
  remarks VARCHAR,
  created_at TIMESTAMP
);

-- ===========================================================================
-- SALES DOMAIN
-- ===========================================================================

CREATE TABLE IF NOT EXISTS leads (
  lead_id VARCHAR PRIMARY KEY,
  lead_number VARCHAR,
  party_id VARCHAR,                    -- FK -> parties.party_id
  customer_id VARCHAR,                 -- FK -> customers.customer_id
  campaign_id VARCHAR,                 -- FK -> campaigns.campaign_id
  assigned_agent_id VARCHAR,           -- FK -> agents.agent_id
  product_id VARCHAR,                  -- FK -> products.product_id
  lead_source VARCHAR,
  lead_status VARCHAR,
  received_at TIMESTAMP,
  qualified_at TIMESTAMP,
  score DOUBLE,
  created_at TIMESTAMP,
  updated_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS opportunities (
  opportunity_id VARCHAR PRIMARY KEY,
  opportunity_number VARCHAR,
  lead_id VARCHAR,                     -- FK -> leads.lead_id
  customer_id VARCHAR,                 -- FK -> customers.customer_id
  agent_id VARCHAR,                    -- FK -> agents.agent_id
  campaign_id VARCHAR,                 -- FK -> campaigns.campaign_id
  product_id VARCHAR,                  -- FK -> products.product_id
  opportunity_stage VARCHAR,
  opened_date DATE,
  close_date DATE,
  estimated_premium DOUBLE,            -- SGD
  quoted_premium DOUBLE,               -- SGD
  lost_reason VARCHAR,
  created_at TIMESTAMP,
  updated_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS proposals (
  proposal_id VARCHAR PRIMARY KEY,
  proposal_number VARCHAR,
  quote_id VARCHAR,                    -- FK -> quotes.quote_id
  opportunity_id VARCHAR,              -- FK -> opportunities.opportunity_id
  customer_id VARCHAR,                 -- FK -> customers.customer_id
  agent_id VARCHAR,                    -- FK -> agents.agent_id
  product_id VARCHAR,                  -- FK -> products.product_id
  proposal_date DATE,
  proposal_status VARCHAR,
  proposed_premium DOUBLE,             -- SGD
  proposed_sum_assured DOUBLE,         -- SGD
  proposal_payload JSON,
  created_at TIMESTAMP,
  updated_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS applications (
  application_id VARCHAR PRIMARY KEY,
  application_number VARCHAR,
  proposal_id VARCHAR,                 -- FK -> proposals.proposal_id
  quote_id VARCHAR,                    -- FK -> quotes.quote_id
  opportunity_id VARCHAR,              -- FK -> opportunities.opportunity_id
  customer_id VARCHAR,                 -- FK -> customers.customer_id
  agent_id VARCHAR,                    -- FK -> agents.agent_id
  product_id VARCHAR,                  -- FK -> products.product_id
  application_date DATE,
  application_status VARCHAR,
  requested_premium DOUBLE,            -- SGD
  requested_sum_assured DOUBLE,        -- SGD
  medical_required BOOLEAN,
  application_payload JSON,
  created_at TIMESTAMP,
  updated_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS quotes (
  quote_id VARCHAR PRIMARY KEY,
  quote_number VARCHAR,
  lead_id VARCHAR,                     -- FK -> leads.lead_id
  opportunity_id VARCHAR,              -- FK -> opportunities.opportunity_id
  customer_id VARCHAR,                 -- FK -> customers.customer_id
  agent_id VARCHAR,                    -- FK -> agents.agent_id
  product_id VARCHAR,                  -- FK -> products.product_id
  campaign_id VARCHAR,                 -- FK -> campaigns.campaign_id
  quote_date DATE,
  quote_status VARCHAR,
  quoted_premium DOUBLE,               -- SGD
  sum_assured DOUBLE,                  -- SGD
  quote_channel VARCHAR,
  decline_reason VARCHAR,
  quote_features JSON,
  created_at TIMESTAMP,
  updated_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS claim_parties (
  claim_party_id VARCHAR PRIMARY KEY,
  claim_id VARCHAR,                    -- FK -> claims.claim_id
  party_id VARCHAR,                    -- FK -> parties.party_id
  customer_id VARCHAR,                 -- FK -> customers.customer_id
  role_type VARCHAR,
  relationship_to_insured VARCHAR,
  provider_specialty VARCHAR,
  involvement_notes VARCHAR,
  created_at TIMESTAMP,
  updated_at TIMESTAMP
);

-- ===========================================================================
-- CAMPAIGN DOMAIN
-- ===========================================================================

CREATE TABLE IF NOT EXISTS campaigns (
  campaign_id VARCHAR PRIMARY KEY,
  campaign_code VARCHAR,
  campaign_name VARCHAR,
  campaign_type VARCHAR,
  channel VARCHAR,
  objective VARCHAR,
  target_line_of_business VARCHAR,
  start_date DATE,
  end_date DATE,
  budget_amount DOUBLE,                -- SGD
  status VARCHAR,
  created_at TIMESTAMP,
  updated_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS campaign_responses (
  campaign_response_id VARCHAR PRIMARY KEY,
  campaign_id VARCHAR,                 -- FK -> campaigns.campaign_id
  campaign_target_id VARCHAR,          -- FK -> campaign_targets.campaign_target_id
  customer_id VARCHAR,                 -- FK -> customers.customer_id
  lead_id VARCHAR,                     -- FK -> leads.lead_id
  opportunity_id VARCHAR,              -- FK -> opportunities.opportunity_id
  policy_id VARCHAR,                   -- FK -> policies.policy_id
  response_ts TIMESTAMP,
  response_type VARCHAR,
  conversion_flag BOOLEAN,
  conversion_premium DOUBLE,           -- SGD
  created_at TIMESTAMP,
  updated_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS campaign_targets (
  campaign_target_id VARCHAR PRIMARY KEY,
  campaign_id VARCHAR,                 -- FK -> campaigns.campaign_id
  customer_id VARCHAR,                 -- FK -> customers.customer_id
  lead_id VARCHAR,                     -- FK -> leads.lead_id
  agent_id VARCHAR,                    -- FK -> agents.agent_id
  target_status VARCHAR,
  selected_at TIMESTAMP,
  suppression_reason VARCHAR,
  created_at TIMESTAMP,
  updated_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS next_best_actions (
  next_best_action_id VARCHAR PRIMARY KEY,
  model_prediction_id VARCHAR,         -- FK -> model_predictions.model_prediction_id
  customer_id VARCHAR,                 -- FK -> customers.customer_id
  agent_id VARCHAR,                    -- FK -> agents.agent_id
  policy_id VARCHAR,                   -- FK -> policies.policy_id
  lead_id VARCHAR,                     -- FK -> leads.lead_id
  campaign_id VARCHAR,                 -- FK -> campaigns.campaign_id
  product_id VARCHAR,                  -- FK -> products.product_id
  action_type VARCHAR,
  action_rank INTEGER,
  priority_score DOUBLE,
  expected_value DOUBLE,               -- SGD
  due_date DATE,
  action_status VARCHAR,
  outcome VARCHAR,
  outcome_value DOUBLE,
  action_reason VARCHAR,
  created_at TIMESTAMP,
  updated_at TIMESTAMP
);

-- ===========================================================================
-- CLAIMS DOMAIN
-- ===========================================================================

CREATE TABLE IF NOT EXISTS claims (
  claim_id VARCHAR PRIMARY KEY,
  claim_number VARCHAR,
  policy_id VARCHAR,                   -- FK -> policies.policy_id
  customer_id VARCHAR,                 -- FK -> customers.customer_id
  policy_coverage_id VARCHAR,          -- FK -> policy_coverage.policy_coverage_id
  assigned_agent_id VARCHAR,           -- FK -> agents.agent_id
  loss_date DATE,
  report_date DATE,
  close_date DATE,
  claim_status VARCHAR,
  loss_cause VARCHAR,
  loss_description VARCHAR,
  paid_amount DOUBLE,                  -- SGD
  reserve_amount DOUBLE,               -- SGD
  litigation_flag BOOLEAN,
  catastrophe_flag BOOLEAN,
  created_at TIMESTAMP,
  updated_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS claim_fraud_indicators (
  claim_fraud_indicator_id VARCHAR PRIMARY KEY,
  claim_id VARCHAR,                    -- FK -> claims.claim_id
  customer_id VARCHAR,                 -- FK -> customers.customer_id
  indicator_date DATE,
  indicator_type VARCHAR,
  indicator_source VARCHAR,
  indicator_score DOUBLE,
  severity VARCHAR,
  resolved_flag BOOLEAN,
  resolution_outcome VARCHAR,
  indicator_payload JSON,
  created_at TIMESTAMP,
  updated_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS claim_assessments (
  claim_assessment_id VARCHAR PRIMARY KEY,
  claim_id VARCHAR,                    -- FK -> claims.claim_id
  assessed_by_agent_id VARCHAR,        -- FK -> agents.agent_id
  assessment_date DATE,
  assessment_type VARCHAR,
  severity_score DOUBLE,
  liability_pct DOUBLE,
  estimated_loss_amount DOUBLE,        -- SGD
  recommended_reserve_amount DOUBLE,   -- SGD
  assessment_outcome VARCHAR,
  assessment_notes VARCHAR,
  created_at TIMESTAMP,
  updated_at TIMESTAMP
);

-- ===========================================================================
-- PRODUCT & PAYMENT
-- ===========================================================================

CREATE TABLE IF NOT EXISTS products (
  product_id VARCHAR PRIMARY KEY,
  parent_product_id VARCHAR,           -- FK -> products.product_id (riders)
  product_code VARCHAR,
  product_name VARCHAR,                -- PRU-style names (PRUShield, PRUWealth, ...)
  line_of_business VARCHAR,            -- Health | Savings | Protection | Investment
  product_family VARCHAR,
  product_component_type VARCHAR,      -- base | rider
  rider_category VARCHAR,
  product_version VARCHAR,
  effective_date DATE,
  expiration_date DATE,
  active_flag BOOLEAN,
  created_at TIMESTAMP,
  updated_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS payments (
  payment_id VARCHAR PRIMARY KEY,
  policy_id VARCHAR,                   -- FK -> policies.policy_id
  customer_id VARCHAR,                 -- FK -> customers.customer_id
  payment_date DATE,
  due_date DATE,
  payment_status VARCHAR,
  payment_method VARCHAR,
  billed_amount DOUBLE,                -- SGD
  paid_amount DOUBLE,                  -- SGD
  created_at TIMESTAMP,
  updated_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS premiums (
  premium_id VARCHAR PRIMARY KEY,
  policy_id VARCHAR,                   -- FK -> policies.policy_id
  policy_coverage_id VARCHAR,          -- FK -> policy_coverage.policy_coverage_id
  premium_period_start DATE,
  premium_period_end DATE,
  transaction_date DATE,
  transaction_type VARCHAR,
  written_premium_amount DOUBLE,       -- SGD
  earned_premium_amount DOUBLE,        -- SGD
  tax_fee_amount DOUBLE,               -- SGD
  created_at TIMESTAMP,
  updated_at TIMESTAMP
);

-- ===========================================================================
-- ML / AI LAYER
-- ===========================================================================

CREATE TABLE IF NOT EXISTS model_predictions (
  model_prediction_id VARCHAR PRIMARY KEY,
  model_score_id VARCHAR,              -- FK -> model_scores.model_score_id
  model_name VARCHAR,
  model_version VARCHAR,               -- FK -> model_versions.model_version_id (logical)
  prediction_type VARCHAR,
  entity_type VARCHAR,
  entity_id VARCHAR,
  prediction_ts TIMESTAMP,
  prediction_horizon_days INTEGER,
  predicted_label VARCHAR,
  predicted_value DOUBLE,
  probability DOUBLE,
  confidence_score DOUBLE,
  recommended_product_id VARCHAR,      -- FK -> products.product_id
  prediction_payload JSON,
  created_at TIMESTAMP,
  updated_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS model_features (
  model_feature_id VARCHAR PRIMARY KEY,
  feature_set_name VARCHAR,
  feature_set_version VARCHAR,
  entity_type VARCHAR,
  entity_id VARCHAR,
  customer_id VARCHAR,                 -- FK -> customers.customer_id
  policy_id VARCHAR,                   -- FK -> policies.policy_id
  agent_id VARCHAR,                    -- FK -> agents.agent_id
  lead_id VARCHAR,                     -- FK -> leads.lead_id
  opportunity_id VARCHAR,              -- FK -> opportunities.opportunity_id
  claim_id VARCHAR,                    -- FK -> claims.claim_id
  campaign_id VARCHAR,                 -- FK -> campaigns.campaign_id
  product_id VARCHAR,                  -- FK -> products.product_id
  feature_date DATE,
  prediction_horizon_days INTEGER,
  features JSON,
  label_name VARCHAR,
  label_value VARCHAR,
  data_split VARCHAR,
  feature_hash VARCHAR,
  created_at TIMESTAMP,
  updated_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS model_versions (
  model_version_id VARCHAR PRIMARY KEY,
  model_name VARCHAR,                  -- policy_lapse, propensity_to_buy, ...
  model_version VARCHAR,
  algorithm VARCHAR,
  training_date DATE,
  auc DOUBLE,
  precision_score DOUBLE,
  recall_score DOUBLE,
  feature_set_name VARCHAR,
  status VARCHAR,                      -- production | staging | retired
  registered_by VARCHAR,
  notes VARCHAR,
  created_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS model_scores (
  model_score_id VARCHAR PRIMARY KEY,
  model_name VARCHAR,
  model_version VARCHAR,               -- FK -> model_versions (logical)
  model_feature_id VARCHAR,            -- FK -> model_features.model_feature_id
  entity_type VARCHAR,
  entity_id VARCHAR,
  score_ts TIMESTAMP,
  score_name VARCHAR,
  score_value DOUBLE,
  probability DOUBLE,
  score_band VARCHAR,                  -- LOW | MEDIUM | HIGH | VERY_HIGH
  rank_within_segment INTEGER,
  explanation VARCHAR,
  created_at TIMESTAMP,
  updated_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS underwriting_decisions (
  underwriting_decision_id VARCHAR PRIMARY KEY,
  application_id VARCHAR,              -- FK -> applications.application_id
  customer_id VARCHAR,                 -- FK -> customers.customer_id
  product_id VARCHAR,                  -- FK -> products.product_id
  decision_date DATE,
  decision_status VARCHAR,
  risk_class VARCHAR,
  rating_factor DOUBLE,
  exclusion_applied BOOLEAN,
  underwriting_reason VARCHAR,
  decision_payload JSON,
  created_at TIMESTAMP,
  updated_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS semantic_documents (
  semantic_document_id VARCHAR PRIMARY KEY,
  glossary_id VARCHAR,                 -- FK -> business_glossary.glossary_id
  document_type VARCHAR,               -- table | column | metric | join | glossary | example_question
  source_schema VARCHAR,
  source_table VARCHAR,
  source_column VARCHAR,
  title VARCHAR,
  content VARCHAR,
  tags VARCHAR,
  content_hash VARCHAR,
  embedding_model VARCHAR,
  embedding VARCHAR,                   -- serialized vector; live vectors live in LanceDB (see vector_index_log)
  active_flag BOOLEAN,
  created_at TIMESTAMP,
  updated_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS query_audit_log (
  query_audit_log_id VARCHAR PRIMARY KEY,
  user_id VARCHAR,
  session_id VARCHAR,
  question VARCHAR,
  retrieved_semantic_document_ids VARCHAR,
  generated_sql VARCHAR,
  execution_status VARCHAR,
  safety_decision VARCHAR,
  error_message VARCHAR,
  row_count INTEGER,
  duration_ms INTEGER,
  feedback_rating INTEGER,
  created_at TIMESTAMP,
  updated_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS business_glossary (
  glossary_id VARCHAR PRIMARY KEY,
  term VARCHAR,
  domain VARCHAR,
  definition VARCHAR,
  calculation_sql VARCHAR,
  synonyms VARCHAR,
  owner VARCHAR,
  active_flag BOOLEAN,
  created_at TIMESTAMP,
  updated_at TIMESTAMP
);

-- ===========================================================================
-- NEW FOR V2.0 — agentic AI infrastructure
-- ===========================================================================

CREATE SEQUENCE IF NOT EXISTS seq_vector_index_log START 1;
CREATE TABLE IF NOT EXISTS vector_index_log (
  id BIGINT PRIMARY KEY DEFAULT nextval('seq_vector_index_log'),
  table_name VARCHAR,                  -- source DuckDB table the chunk came from
  record_id VARCHAR,                   -- PK of the source row
  chunk_text VARCHAR,
  embedded_at TIMESTAMP,
  model_used VARCHAR,
  vector_dims INTEGER,
  lance_table VARCHAR                  -- LanceDB table holding the vector
);

CREATE SEQUENCE IF NOT EXISTS seq_agent_reasoning_log START 1;
CREATE TABLE IF NOT EXISTS agent_reasoning_log (
  id BIGINT PRIMARY KEY DEFAULT nextval('seq_agent_reasoning_log'),
  query_id VARCHAR,                    -- trace id correlating one user ask end-to-end
  agent_name VARCHAR,                  -- e.g. intent_classifier | sql_agent | insight_agent
  input_summary VARCHAR,
  output_summary VARCHAR,
  duration_ms INTEGER,
  tokens_used INTEGER,
  cache_hit BOOLEAN,
  created_at TIMESTAMP DEFAULT current_timestamp
);

CREATE SEQUENCE IF NOT EXISTS seq_semantic_cache START 1;
CREATE TABLE IF NOT EXISTS semantic_cache (
  id BIGINT PRIMARY KEY DEFAULT nextval('seq_semantic_cache'),
  question_hash VARCHAR,               -- sha256 of normalized question
  question_text VARCHAR,
  answer_text VARCHAR,
  context_used JSON,
  role VARCHAR,
  similarity_threshold DOUBLE,
  expires_at TIMESTAMP,
  created_at TIMESTAMP DEFAULT current_timestamp
);
