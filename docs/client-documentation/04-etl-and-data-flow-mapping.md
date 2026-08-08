# ETL And Data Flow Mapping

## Flow Inventory

| Flow | Source | Target | Status | Evidence |
|---|---|---|---:|---|
| Synthetic data generation to Supabase | `generate_synthetic_insurance_data.py` CSV outputs | Core and ML tables | Implemented | `generate_synthetic_insurance_data.py`, `README_SYNTHETIC_DATA.md` |
| Core data to feature views | Operational tables | `v_*_features` views | Implemented | `006_ml_feature_engineering_views.sql` |
| Feature views to physical feature tables | `v_*_features` views | `*_features` tables | Implemented | `007_ml_feature_tables.sql`, `009_refresh_ml_feature_tables.sql` |
| Feature tables to model scores | Feature tables | `model_scores`, `model_predictions`, `next_best_actions` | Implemented / demo-oriented | `ml_scoring_pipeline.py` |
| Semantic documents to embeddings | `semantic_documents` rows | `semantic_documents.embedding` | Implemented | `embed_semantic_documents.py`, `embedding_pipeline/` |
| Question to SQL | User question and context | Validated SQL | Implemented | `copilot_sql_engine/`, `ai_insight_v11_service.py` |
| SQL result to business insight | SQL result rows | Insight response | Implemented / partially LLM-dependent | `ai_insight_v11_service.py` |
| Insight to Evidence Hub | AI response | `insight_test_snapshots` evidence payload | Implemented | `insight_snapshot_service.py` |

## Major Data Flow Mapping

| Source Table / Object | Target Table / Object | Transformation | Business Rule | Used For |
|---|---|---|---|---|
| CSV synthetic output | Core tables | Direct table load following FK order | Preserve referential integrity | Demo data foundation |
| `payments` | `policy_lapse_features` | Missed payment count, late payment signals | Missed payments increase lapse risk | Policy lapse model, Policy Lapse Risk tab |
| `customer_complaints` | `customer_churn_features`, `policy_lapse_features` | Complaint count and unresolved complaint flag | Unresolved complaints increase churn/lapse and suppress sales actions | Churn, lapse, next best action |
| `customer_behavior_daily` | `propensity_to_buy_features`, `customer_churn_features`, `customer_lifetime_value_features` | Engagement, visit, login, digital behavior summaries | High engagement increases propensity; declining engagement increases churn risk | AI Intelligence, KYC |
| `policy_events`, `policy_renewals` | `policy_lapse_features` | Premium increases, renewal windows, lifecycle changes | Renewal within 60 days prioritizes retention conversation | Policy Lapse Risk |
| `agent_mapa_metrics` | `agent_performance_features`, `next_best_customer_features` | Meetings, activities, proposals, applications, bound policies, premium | Higher MAPA activity correlates with conversion and performance | Agent Performance, KYA |
| `campaign_targets`, `campaign_responses` | `campaign_response_features` | Delivery, open, click, response, conversion counts | Responders have higher conversion probability | Campaign Effectiveness |
| `leads`, `opportunities`, `policies` | `lead_conversion_features`, `campaign_response_features` | Funnel conversion and issued policy metrics | Campaign and lead follow-up depends on conversion stage | Campaign and sales funnel |
| `claims`, `claim_fraud_indicators` | `claim_prediction_features`, `fraud_detection_features` | Claim history and fraud signal counts | Prior claims and fraud indicators affect risk | Claims and fraud analytics |
| `semantic_documents` | `semantic_documents.embedding` | Provider-generated vector embeddings | Relevant context improves SQL and reduces hallucination | AI Intelligence |
| AI Insight response | `insight_test_snapshots` | Persist generated SQL, rows, context, models, limitations | Every AI answer should be traceable | Insight Evidence Hub |

## Refresh Pattern

The feature tables are physical tables created with no data in `007_ml_feature_tables.sql`. They are populated from views using:

```sql
truncate table public.next_best_product_features;
insert into public.next_best_product_features
select * from public.v_next_best_product_features;
analyze public.next_best_product_features;
```

The full refresh script is `009_refresh_ml_feature_tables.sql`. For SQL Editor timeout scenarios, `012_ml_feature_chunk_refresh_helpers.sql` provides snapshot and date-range refresh helper functions.

## Data Quality Checks

| Check | Status | Evidence |
|---|---:|---|
| Row count checks | Implemented | `008_ml_feature_quality_checks.sql`, `refresh_ml_feature_tables.py` |
| Required null checks | Implemented | `008_ml_feature_quality_checks.sql` |
| Window integrity / leakage checks | Implemented | `008_ml_feature_quality_checks.sql`, `refresh_ml_feature_tables.py` |
| Target distribution checks | Implemented | `008_ml_feature_quality_checks.sql` |
| Synthetic referential validation | Implemented | `validate_synthetic_data.py` |
| Production data contract tests | Planned / Recommended | Not found as a production framework |

## ETL / ELT Frequency

| Flow | Current MVP Frequency | Production Recommendation |
|---|---|---|
| Synthetic data generation | Manual | Replace with source-system feeds |
| Feature refresh | Manual SQL or Python job | Scheduled daily/monthly with observability |
| Model scoring | Manual batch scoring | Scheduled batch and event-based scoring |
| Embeddings | Manual embedding pipeline | Scheduled on semantic document changes |
| Evidence snapshot | Runtime when AI insight runs | Runtime plus retention policies |

