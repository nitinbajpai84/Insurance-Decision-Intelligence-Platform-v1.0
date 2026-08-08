# Data Model And Subject Areas

## Subject Area Summary

| Subject Area | Tables | Business Purpose | Used By Tabs | Used By Models | Used By AI |
|---|---|---|---|---|---|
| Party and Customer | `parties`, `customers`, `addresses` | Identity, customer profile, contact and segmentation. | Home, KYC, AI Intelligence | Propensity, churn, CLV, NBP | Yes |
| Customer Behavior and Engagement | `customer_behavior_daily`, `customer_digital_events`, `customer_engagement_events`, `customer_complaints`, `customer_nps`, `customer_service_requests` | Engagement, complaints, service signals, sentiment. | KYC, Policy Lapse Risk, AI Intelligence | Churn, lapse, propensity, CLV | Yes |
| Product and Policy | `products`, `policies`, `policy_coverages`, `policy_events`, `policy_renewals`, `policy_lapse_events` | Product holdings, coverage, lifecycle and renewal. | KYC, Policy Lapse Risk | Lapse, NBP, CLV | Yes |
| Premium, Billing and Payments | `premiums`, `payments` | Premium billing, paid amounts, failed or late payments. | KYC, Policy Lapse Risk | Lapse, churn, CLV | Yes |
| Agent / Producer Management | `agents`, `agent_movements`, `agent_mapa_metrics`, `agent_calls`, `agent_meetings`, `agent_targets`, `agent_commissions` | Distribution productivity and agent relationship management. | KYA, Agent Performance Tracking | Agent performance, attrition, next best customer | Yes |
| Sales Funnel | `leads`, `opportunities`, `quotes`, `proposals`, `applications`, `underwriting_decisions` | Lead-to-policy conversion and underwriting journey. | Campaigns, Agent Performance | Lead conversion, agent performance | Yes |
| Campaign and Engagement | `campaigns`, `campaign_targets`, `campaign_responses` | Campaign targeting, response, conversion and ROI. | Campaign Effectiveness | Campaign response, propensity | Yes |
| Claims and Fraud Risk | `claims`, `claim_parties`, `claim_assessments`, `claim_fraud_indicators` | Claims profile, loss, fraud indicators. | Claims 360 API, future Claims UI | Claim occurrence, fraud risk | Yes |
| ML Feature Store and Scoring | `*_features`, `model_scores`, `model_predictions`, `next_best_actions`, `model_artifacts`, `model_scoring_jobs` | Model training, scoring, recommendations. | AI Intelligence, Policy Lapse, Agent Performance | All listed models | Yes |
| Semantic Layer and GenAI | `semantic_documents`, `business_glossary`, `kpi_definitions`, `table_catalog`, `column_catalog`, `join_path_catalog`, `model_catalog` | Context grounding for SQL and explanations. | AI Intelligence, Evidence Hub | Context-aware reasoning | Yes |
| Evidence and Audit | `insight_test_snapshots`, `llm_request_log`, `insight_lineage`, `recommendation_evidence`, `context_usage_log`, `model_explanations` | Traceability, diagnostics, explainability. | Insight Evidence Hub | Governance | Yes |

## Party And Customer

| Attribute | Details |
|---|---|
| Business description | Represents people and customer master data used for identity, segmentation, lifecycle, risk tier, and contact preferences. |
| Key tables | `parties`, `customers`, `addresses` |
| Grain | One row per party, customer, or address. |
| Primary keys | `party_id`, `customer_id`, `address_id` |
| Important FKs | `customers.party_id -> parties.party_id`; `addresses.party_id -> parties.party_id` |
| Common joins | `customers -> parties -> addresses`; `customers -> policies`; `customers -> model_scores`; `customers -> next_best_actions` |
| Example questions | Which customer segments have high lapse risk? Which customers have no health product? Which high-CLV customers need action? |

## Customer Behavior And Engagement

| Attribute | Details |
|---|---|
| Key tables | `customer_behavior_daily`, `customer_digital_events`, `customer_engagement_events`, `customer_complaints`, `customer_nps`, `customer_service_requests` |
| Grain | Daily behavior, individual digital event, complaint, NPS response, or service request. |
| Common joins | `customer_id` to `customers`; complaint/service signals to policy and lapse models. |
| Example questions | Which customers have declining engagement? Which unresolved complaints suppress sales actions? |

## Product And Policy

| Attribute | Details |
|---|---|
| Key tables | `products`, `policies`, `policy_coverages`, `policy_events`, `policy_renewals`, `policy_lapse_events` |
| Grain | Product master, policy contract, coverage item, policy lifecycle event, renewal event. |
| Common joins | `policies.product_id -> products.product_id`; `policies.customer_id -> customers.customer_id`; `policies.agent_id -> agents.agent_id` |
| Example questions | What is persistency by product? Which policies renew in 60 days? What premium is at risk? |

## Premium, Billing And Payments

| Attribute | Details |
|---|---|
| Key tables | `premiums`, `payments` |
| Grain | Premium charge or payment transaction. |
| Common joins | `payments.policy_id -> policies.policy_id`; `premiums.policy_id -> policies.policy_id` |
| Example questions | Which lapse-risk policies have missed payments? What is claim ratio by product? |

## Agent / Producer Management

| Attribute | Details |
|---|---|
| Key tables | `agents`, `agent_movements`, `agent_mapa_metrics`, `agent_calls`, `agent_meetings`, `agent_targets`, `agent_commissions`, `agent_training`, `agent_attrition_events` |
| Grain | Agent master, movement history, monthly MAPA metric, interaction, target, commission, training event. |
| Common joins | `agents.party_id -> parties.party_id`; `agent_mapa_metrics.agent_id -> agents.agent_id`; `policies.agent_id -> agents.agent_id` |
| Example questions | Which agents need coaching? Which agents changed territories and improved sales? Which agents are rising stars? |

## Sales Funnel

| Attribute | Details |
|---|---|
| Key tables | `leads`, `opportunities`, `quotes`, `proposals`, `applications`, `underwriting_decisions` |
| Grain | Funnel object or underwriting decision. |
| Common joins | Lead/opportunity to customer, agent, product, campaign. |
| Example questions | Which leads are most likely to convert? What is quote-to-bind rate by agent? |

## Campaign And Engagement

| Attribute | Details |
|---|---|
| Key tables | `campaigns`, `campaign_targets`, `campaign_responses` |
| Grain | Campaign, targeted customer/lead, response event. |
| Common joins | `campaign_responses.campaign_id -> campaigns.campaign_id`; `campaign_targets.customer_id -> customers.customer_id`; `leads.campaign_id -> campaigns.campaign_id` |
| Example questions | Which campaigns generated highest policy conversion? Which channels convert best? |

## Claims And Fraud Risk

| Attribute | Details |
|---|---|
| Key tables | `claims`, `claim_parties`, `claim_assessments`, `claim_fraud_indicators` |
| Grain | Claim, party involved, assessment, fraud signal. |
| Common joins | `claims.policy_id -> policies.policy_id`; `claims.customer_id -> customers.customer_id` |
| Example questions | Which segments have highest claim ratio? Which claims have fraud indicators? |

## Semantic Layer And GenAI

| Attribute | Details |
|---|---|
| Key tables | `semantic_documents`, `business_glossary`, `kpi_definitions`, `table_catalog`, `column_catalog`, `join_path_catalog`, `model_catalog`, `missing_data_rules` |
| Grain | Context document, glossary term, KPI, table/column metadata, join path, model definition. |
| Common joins | Retrieved through vector/hybrid search rather than only relational joins. |
| Example questions | Which tables support lapse risk? How should SQL join customers to policies and payments? |

## Evidence And Audit

| Attribute | Details |
|---|---|
| Key tables | `insight_test_snapshots`, `llm_request_log`, `insight_lineage`, `recommendation_evidence`, `model_explanations`, `context_usage_log` |
| Grain | AI answer snapshot, LLM request, lineage record, evidence item, model explanation, context usage record. |
| Common joins | `insight_lineage -> recommendation_evidence`; `insight_lineage -> context_usage_log`; `insight_test_snapshots` by `insight_id`. |
| Example questions | Why did AI recommend this action? What SQL and context supported the answer? |

