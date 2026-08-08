# Active Table Report

These tables are preserved for the demo and/or runtime because they are referenced by the app, model logic, context retrieval, or governance layer.

| table | classification | role | ai_sql_allowed | reason |
| --- | --- | --- | --- | --- |
| public.addresses | ACT_EMBEDDING_CONTEXT | technical_log | False | Referenced by backend; Referenced by SQL examples; Referenced by semantic/context docs |
| public.agent_attrition_events | ACT_EMBEDDING_CONTEXT | technical_log | False | Referenced by backend; Referenced by SQL examples; Referenced by semantic/context docs; Referenced by model context |
| public.agent_attrition_features | ACT_EMBEDDING_CONTEXT | technical_log | False | Referenced by backend; Referenced by SQL examples; Referenced by semantic/context docs; Referenced by model context |
| public.agent_calls | ACT_EMBEDDING_CONTEXT | technical_log | False | Referenced by backend; Referenced by SQL examples; Referenced by semantic/context docs; Referenced by model context |
| public.agent_commissions | ACT_EMBEDDING_CONTEXT | technical_log | False | Referenced by backend; Referenced by SQL examples; Referenced by semantic/context docs; Referenced by model context; Referenced by demo catalog |
| public.agent_mapa_metrics | ACT_EMBEDDING_CONTEXT | analytical_feature | True | Referenced by backend; Referenced by SQL examples; Referenced by semantic/context docs; Referenced by model context; Referenced by demo catalog |
| public.agent_meetings | ACT_EMBEDDING_CONTEXT | technical_log | False | Referenced by backend; Referenced by SQL examples; Referenced by semantic/context docs; Referenced by model context |
| public.agent_movements | ACT_EMBEDDING_CONTEXT | technical_log | False | Referenced by backend; Referenced by SQL examples; Referenced by semantic/context docs; Referenced by demo catalog |
| public.agent_performance_features | ACT_EMBEDDING_CONTEXT | technical_log | False | Referenced by backend; Referenced by SQL examples; Referenced by semantic/context docs; Referenced by model context |
| public.agent_targets | ACT_EMBEDDING_CONTEXT | technical_log | False | Referenced by backend; Referenced by SQL examples; Referenced by semantic/context docs; Referenced by model context |
| public.agent_training | ACT_EMBEDDING_CONTEXT | technical_log | False | Referenced by backend; Referenced by SQL examples; Referenced by semantic/context docs; Referenced by model context |
| public.agents | ACT_AUTHORITATIVE_SOURCE | authoritative_source | True | Referenced by backend; Referenced by SQL examples; Referenced by semantic/context docs; Referenced by model context; Referenced by demo catalog |
| public.applications | ACT_EMBEDDING_CONTEXT | technical_log | False | Referenced by backend; Referenced by SQL examples; Referenced by semantic/context docs; Referenced by model context |
| public.business_glossary | ACT_SYSTEM_REQUIRED | semantic_context | True | Core governance or ML control table required for demo and/or runtime. |
| public.campaign_response_features | ACT_EMBEDDING_CONTEXT | technical_log | False | Referenced by backend; Referenced by SQL examples; Referenced by semantic/context docs; Referenced by model context |
| public.campaign_responses | ACT_EMBEDDING_CONTEXT | analytical_feature | True | Referenced by backend; Referenced by SQL examples; Referenced by semantic/context docs; Referenced by model context; Referenced by demo catalog |
| public.campaign_targets | ACT_EMBEDDING_CONTEXT | analytical_feature | True | Referenced by backend; Referenced by SQL examples; Referenced by semantic/context docs; Referenced by model context; Referenced by demo catalog |
| public.campaigns | ACT_AUTHORITATIVE_SOURCE | authoritative_source | True | Referenced by backend; Referenced by SQL examples; Referenced by semantic/context docs; Referenced by model context; Referenced by demo catalog |
| public.claim_assessments | ACT_EMBEDDING_CONTEXT | analytical_feature | True | Referenced by backend; Referenced by SQL examples; Referenced by semantic/context docs; Referenced by model context |
| public.claim_fraud_indicators | ACT_EMBEDDING_CONTEXT | analytical_feature | True | Referenced by backend; Referenced by SQL examples; Referenced by semantic/context docs; Referenced by model context |
| public.claim_parties | ACT_EMBEDDING_CONTEXT | technical_log | False | Referenced by backend; Referenced by SQL examples; Referenced by semantic/context docs; Referenced by model context |
| public.claim_prediction_features | ACT_EMBEDDING_CONTEXT | technical_log | False | Referenced by backend; Referenced by SQL examples; Referenced by semantic/context docs; Referenced by model context |
| public.claims | ACT_AUTHORITATIVE_SOURCE | authoritative_source | True | Referenced by backend; Referenced by SQL examples; Referenced by semantic/context docs; Referenced by model context |
| public.cld_actual_column_catalog | ACT_EMBEDDING_CONTEXT | system_required | True | Referenced by backend; Referenced by semantic/context docs |
| public.cld_actual_join_path_catalog | ACT_EMBEDDING_CONTEXT | system_required | True | Referenced by backend; Referenced by semantic/context docs |
| public.cld_actual_relationship_catalog | ACT_EMBEDDING_CONTEXT | system_required | True | Referenced by backend; Referenced by semantic/context docs |
| public.cld_actual_schema_snapshot | ACT_EMBEDDING_CONTEXT | system_required | True | Referenced by backend; Referenced by semantic/context docs |
| public.cld_actual_table_catalog | ACT_EMBEDDING_CONTEXT | system_required | True | Referenced by backend; Referenced by semantic/context docs |
| public.cld_agent_performance_summary | ACT_EMBEDDING_CONTEXT | system_required | True | Referenced by backend; Referenced by semantic/context docs; Referenced by demo catalog |
| public.cld_ai_insight_run_log | ACT_EMBEDDING_CONTEXT | system_required | True | Referenced by backend; Referenced by semantic/context docs |
| public.cld_ai_validation_results | ACT_EMBEDDING_CONTEXT | system_required | True | Referenced by backend; Referenced by semantic/context docs |
| public.cld_campaign_effectiveness_summary | ACT_EMBEDDING_CONTEXT | system_required | True | Referenced by backend; Referenced by semantic/context docs |
| public.cld_context_registry | ACT_SYSTEM_REQUIRED | semantic_context | True | Core governance or ML control table required for demo and/or runtime. |
| public.cld_context_usage_log | ACT_EMBEDDING_CONTEXT | system_required | True | Referenced by backend; Referenced by semantic/context docs |
| public.cld_context_validation_results | ACT_EMBEDDING_CONTEXT | system_required | True | Referenced by backend; Referenced by semantic/context docs |
| public.cld_customer_360_features | ACT_EMBEDDING_CONTEXT | system_required | True | Referenced by backend; Referenced by semantic/context docs |
| public.cld_demo_question_catalog | ACT_EMBEDDING_CONTEXT | system_required | True | Referenced by backend; Referenced by semantic/context docs; Referenced by demo catalog |
| public.cld_insight_snapshots | ACT_EMBEDDING_CONTEXT | system_required | True | Referenced by backend; Referenced by semantic/context docs |
| public.cld_kpi_registry | ACT_SYSTEM_REQUIRED | semantic_context | True | Core governance or ML control table required for demo and/or runtime. |
| public.cld_llm_request_log | ACT_EMBEDDING_CONTEXT | system_required | True | Referenced by backend; Referenced by semantic/context docs |
| public.cld_llm_skill_registry | ACT_SYSTEM_REQUIRED | semantic_context | True | Core governance or ML control table required for demo and/or runtime. |
| public.cld_model_registry | ACT_SYSTEM_REQUIRED | semantic_context | True | Core governance or ML control table required for demo and/or runtime. |
| public.cld_policy_lapse_summary | ACT_EMBEDDING_CONTEXT | system_required | True | Referenced by backend; Referenced by semantic/context docs |
| public.cld_sql_guardrail_rules | ACT_SYSTEM_REQUIRED | system_required | True | Core governance or ML control table required for demo and/or runtime. |
| public.cld_sql_validation_log | ACT_EMBEDDING_CONTEXT | system_required | True | Referenced by backend; Referenced by semantic/context docs |
| public.cld_table_cleanup_report | ACT_EMBEDDING_CONTEXT | system_required | True | Referenced by backend; Referenced by SQL examples; Referenced by semantic/context docs; Referenced by demo catalog |
| public.cld_table_registry | ACT_SYSTEM_REQUIRED | system_required | True | Core governance or ML control table required for demo and/or runtime. |
| public.cld_verified_sql_context_documents | ACT_EMBEDDING_CONTEXT | system_required | True | Referenced by backend; Referenced by semantic/context docs |
| public.column_catalog | ACT_EMBEDDING_CONTEXT | technical_log | False | Referenced by backend; Referenced by SQL examples; Referenced by semantic/context docs |
| public.context_usage_log | ACT_SYSTEM_REQUIRED | evidence_log | True | Core governance or ML control table required for demo and/or runtime. |
| public.customer_behavior_daily | ACT_EMBEDDING_CONTEXT | analytical_feature | True | Referenced by backend; Referenced by SQL examples; Referenced by semantic/context docs; Referenced by model context |
| public.customer_churn_features | ACT_EMBEDDING_CONTEXT | technical_log | False | Referenced by backend; Referenced by SQL examples; Referenced by semantic/context docs; Referenced by model context |
| public.customer_complaints | ACT_EMBEDDING_CONTEXT | technical_log | False | Referenced by backend; Referenced by SQL examples; Referenced by semantic/context docs; Referenced by model context |
| public.customer_digital_events | ACT_EMBEDDING_CONTEXT | analytical_feature | True | Referenced by backend; Referenced by SQL examples; Referenced by semantic/context docs; Referenced by model context |
| public.customer_engagement_events | ACT_EMBEDDING_CONTEXT | analytical_feature | True | Referenced by backend; Referenced by SQL examples; Referenced by semantic/context docs |
| public.customer_lifetime_value_features | ACT_MODEL_OUTPUT | model_output | True | Referenced by backend; Referenced by SQL examples; Referenced by semantic/context docs; Referenced by model context |
| public.customer_nps | ACT_EMBEDDING_CONTEXT | technical_log | False | Referenced by backend; Referenced by SQL examples; Referenced by semantic/context docs; Referenced by model context |
| public.customer_satisfaction_surveys | ACT_EMBEDDING_CONTEXT | technical_log | False | Referenced by backend; Referenced by SQL examples; Referenced by semantic/context docs; Referenced by model context |
| public.customer_service_requests | ACT_EMBEDDING_CONTEXT | technical_log | False | Referenced by backend; Referenced by SQL examples; Referenced by semantic/context docs; Referenced by model context |
| public.customers | ACT_AUTHORITATIVE_SOURCE | authoritative_source | True | Referenced by backend; Referenced by SQL examples; Referenced by semantic/context docs; Referenced by model context; Referenced by demo catalog |
| public.fraud_detection_features | ACT_MODEL_OUTPUT | model_output | True | Referenced by backend; Referenced by SQL examples; Referenced by semantic/context docs; Referenced by model context |
| public.insight_lineage | ACT_SYSTEM_REQUIRED | evidence_log | True | Core governance or ML control table required for demo and/or runtime. |
| public.insight_templates | ACT_EMBEDDING_CONTEXT | technical_log | False | Referenced by backend; Referenced by SQL examples; Referenced by semantic/context docs |
| public.insight_test_snapshots | ACT_EMBEDDING_CONTEXT | technical_log | False | Referenced by backend; Referenced by SQL examples; Referenced by semantic/context docs |
| public.join_path_catalog | ACT_EMBEDDING_CONTEXT | technical_log | False | Referenced by backend; Referenced by SQL examples; Referenced by semantic/context docs |
| public.kpi_definitions | ACT_EMBEDDING_CONTEXT | technical_log | False | Referenced by backend; Referenced by SQL examples; Referenced by semantic/context docs |
| public.lead_conversion_features | ACT_EMBEDDING_CONTEXT | technical_log | False | Referenced by backend; Referenced by SQL examples; Referenced by semantic/context docs; Referenced by model context |
| public.leads | ACT_AUTHORITATIVE_SOURCE | authoritative_source | True | Referenced by backend; Referenced by SQL examples; Referenced by semantic/context docs; Referenced by model context |
| public.llm_request_log | ACT_EMBEDDING_CONTEXT | technical_log | False | Referenced by backend; Referenced by SQL examples; Referenced by semantic/context docs |
| public.missing_data_rules | ACT_EMBEDDING_CONTEXT | technical_log | False | Referenced by backend; Referenced by SQL examples; Referenced by semantic/context docs |
| public.ml_training_labels | ACT_EMBEDDING_CONTEXT | technical_log | False | Referenced by backend; Referenced by SQL examples; Referenced by semantic/context docs; Referenced by model context |
| public.model_artifacts | ACT_MODEL_OUTPUT | model_output | True | Referenced by backend; Referenced by SQL examples; Referenced by semantic/context docs; Referenced by model context |
| public.model_catalog | ACT_MODEL_OUTPUT | model_output | True | Referenced by backend; Referenced by SQL examples; Referenced by semantic/context docs |
| public.model_explanations | ACT_SYSTEM_REQUIRED | model_output | True | Core governance or ML control table required for demo and/or runtime. |
| public.model_features | ACT_MODEL_OUTPUT | model_output | True | Referenced by backend; Referenced by SQL examples; Referenced by semantic/context docs; Referenced by model context |
| public.model_predictions | ACT_SYSTEM_REQUIRED | model_output | True | Core governance or ML control table required for demo and/or runtime. |
| public.model_scores | ACT_SYSTEM_REQUIRED | model_output | True | Core governance or ML control table required for demo and/or runtime. |
| public.model_scoring_jobs | ACT_MODEL_OUTPUT | model_output | True | Referenced by backend; Referenced by SQL examples; Referenced by semantic/context docs; Referenced by model context |
| public.nba_decision_audit | ACT_EMBEDDING_CONTEXT | technical_log | False | Referenced by backend; Referenced by SQL examples; Referenced by semantic/context docs; Referenced by model context |
| public.next_best_actions | ACT_SYSTEM_REQUIRED | model_output | True | Core governance or ML control table required for demo and/or runtime. |
| public.next_best_customer_features | ACT_MODEL_OUTPUT | model_output | True | Referenced by backend; Referenced by SQL examples; Referenced by semantic/context docs; Referenced by model context |
| public.next_best_product_features | ACT_MODEL_OUTPUT | model_output | True | Referenced by backend; Referenced by SQL examples; Referenced by semantic/context docs; Referenced by model context |
| public.opportunities | ACT_AUTHORITATIVE_SOURCE | authoritative_source | True | Referenced by backend; Referenced by SQL examples; Referenced by semantic/context docs; Referenced by model context; Referenced by demo catalog |
| public.parties | ACT_AUTHORITATIVE_SOURCE | authoritative_source | True | Referenced by backend; Referenced by SQL examples; Referenced by semantic/context docs; Referenced by model context; Referenced by demo catalog |
| public.payments | ACT_AUTHORITATIVE_SOURCE | authoritative_source | True | Referenced by backend; Referenced by SQL examples; Referenced by semantic/context docs; Referenced by model context |
| public.policies | ACT_AUTHORITATIVE_SOURCE | authoritative_source | True | Referenced by frontend; Referenced by backend; Referenced by SQL examples; Referenced by semantic/context docs; Referenced by model context; Referenced by demo catalog |
| public.policy_coverages | ACT_EMBEDDING_CONTEXT | technical_log | False | Referenced by backend; Referenced by SQL examples; Referenced by semantic/context docs; Referenced by model context |
| public.policy_events | ACT_EMBEDDING_CONTEXT | analytical_feature | True | Referenced by backend; Referenced by SQL examples; Referenced by semantic/context docs; Referenced by model context |
| public.policy_lapse_events | ACT_EMBEDDING_CONTEXT | analytical_feature | True | Referenced by backend; Referenced by SQL examples; Referenced by semantic/context docs; Referenced by model context |
| public.policy_lapse_features | ACT_EMBEDDING_CONTEXT | technical_log | False | Referenced by backend; Referenced by SQL examples; Referenced by semantic/context docs; Referenced by model context |
| public.policy_renewals | ACT_EMBEDDING_CONTEXT | analytical_feature | True | Referenced by backend; Referenced by SQL examples; Referenced by semantic/context docs; Referenced by model context |
| public.premiums | ACT_AUTHORITATIVE_SOURCE | authoritative_source | True | Referenced by backend; Referenced by SQL examples; Referenced by semantic/context docs; Referenced by model context |
| public.products | ACT_AUTHORITATIVE_SOURCE | authoritative_source | True | Referenced by frontend; Referenced by backend; Referenced by SQL examples; Referenced by semantic/context docs; Referenced by model context; Referenced by demo catalog |
| public.propensity_to_buy_features | ACT_MODEL_OUTPUT | model_output | True | Referenced by backend; Referenced by SQL examples; Referenced by semantic/context docs; Referenced by model context |
| public.proposals | ACT_EMBEDDING_CONTEXT | technical_log | False | Referenced by backend; Referenced by SQL examples; Referenced by semantic/context docs; Referenced by model context |
| public.query_audit_log | ACT_EMBEDDING_CONTEXT | technical_log | False | Referenced by backend; Referenced by SQL examples; Referenced by semantic/context docs |
| public.quotes | ACT_EMBEDDING_CONTEXT | technical_log | False | Referenced by backend; Referenced by SQL examples; Referenced by semantic/context docs; Referenced by model context |
| public.recommendation_evidence | ACT_SYSTEM_REQUIRED | evidence_log | True | Core governance or ML control table required for demo and/or runtime. |
| public.role_action_templates | ACT_EMBEDDING_CONTEXT | technical_log | False | Referenced by backend; Referenced by SQL examples; Referenced by semantic/context docs |
| public.role_dashboard_widgets | ACT_EMBEDDING_CONTEXT | technical_log | False | Referenced by backend; Referenced by SQL examples; Referenced by semantic/context docs |
| public.role_default_questions | ACT_EMBEDDING_CONTEXT | technical_log | False | Referenced by backend; Referenced by SQL examples; Referenced by semantic/context docs |
| public.role_definitions | ACT_EMBEDDING_CONTEXT | technical_log | False | Referenced by backend; Referenced by SQL examples; Referenced by semantic/context docs |
| public.role_kpis | ACT_EMBEDDING_CONTEXT | technical_log | False | Referenced by backend; Referenced by SQL examples; Referenced by semantic/context docs |
| public.semantic_documents | ACT_SYSTEM_REQUIRED | semantic_context | True | Core governance or ML control table required for demo and/or runtime. |
| public.table_catalog | ACT_EMBEDDING_CONTEXT | technical_log | False | Referenced by backend; Referenced by SQL examples; Referenced by semantic/context docs |
| public.underwriting_decisions | ACT_EMBEDDING_CONTEXT | technical_log | False | Referenced by backend; Referenced by SQL examples; Referenced by semantic/context docs; Referenced by model context |
| public.v_agent_attrition_features | ACT_EMBEDDING_CONTEXT | technical_log | False | Referenced by backend; Referenced by SQL examples; Referenced by semantic/context docs; Referenced by model context |
| public.v_agent_performance_features | ACT_EMBEDDING_CONTEXT | technical_log | False | Referenced by backend; Referenced by SQL examples; Referenced by semantic/context docs; Referenced by model context |
| public.v_campaign_response_features | ACT_EMBEDDING_CONTEXT | technical_log | False | Referenced by backend; Referenced by SQL examples; Referenced by semantic/context docs; Referenced by model context |
| public.v_claim_prediction_features | ACT_EMBEDDING_CONTEXT | technical_log | False | Referenced by backend; Referenced by SQL examples; Referenced by semantic/context docs; Referenced by model context |
| public.v_customer_churn_features | ACT_EMBEDDING_CONTEXT | technical_log | False | Referenced by backend; Referenced by SQL examples; Referenced by semantic/context docs; Referenced by model context |
| public.v_customer_lifetime_value_features | ACT_EMBEDDING_CONTEXT | technical_log | False | Referenced by backend; Referenced by SQL examples; Referenced by semantic/context docs; Referenced by model context |
| public.v_fraud_detection_features | ACT_EMBEDDING_CONTEXT | technical_log | False | Referenced by backend; Referenced by SQL examples; Referenced by semantic/context docs; Referenced by model context |
| public.v_latest_model_scores | ACT_EMBEDDING_CONTEXT | technical_log | False | Referenced by backend; Referenced by SQL examples; Referenced by semantic/context docs; Referenced by model context |
| public.v_lead_conversion_features | ACT_EMBEDDING_CONTEXT | technical_log | False | Referenced by backend; Referenced by SQL examples; Referenced by semantic/context docs; Referenced by model context |
| public.v_ml_feature_required_null_checks | ACT_EMBEDDING_CONTEXT | technical_log | False | Referenced by backend; Referenced by SQL examples; Referenced by semantic/context docs; Referenced by model context |
| public.v_ml_feature_row_counts | ACT_EMBEDDING_CONTEXT | technical_log | False | Referenced by backend; Referenced by SQL examples; Referenced by semantic/context docs; Referenced by model context |
| public.v_ml_feature_target_distribution | ACT_EMBEDDING_CONTEXT | technical_log | False | Referenced by backend; Referenced by SQL examples; Referenced by semantic/context docs; Referenced by model context |
| public.v_ml_feature_window_checks | ACT_EMBEDDING_CONTEXT | technical_log | False | Referenced by backend; Referenced by SQL examples; Referenced by semantic/context docs; Referenced by model context |
| public.v_ml_monthly_snapshots | ACT_EMBEDDING_CONTEXT | technical_log | False | Referenced by backend; Referenced by SQL examples; Referenced by semantic/context docs; Referenced by model context |
| public.v_nba_agent_capacity_v2 | ACT_EMBEDDING_CONTEXT | technical_log | False | Referenced by backend; Referenced by SQL examples; Referenced by semantic/context docs |
| public.v_nba_candidate_actions_v2 | ACT_EMBEDDING_CONTEXT | technical_log | False | Referenced by backend; Referenced by SQL examples; Referenced by semantic/context docs; Referenced by model context |
| public.v_nba_customer_decision_context_v2 | ACT_EMBEDDING_CONTEXT | technical_log | False | Referenced by backend; Referenced by SQL examples; Referenced by semantic/context docs; Referenced by model context |
| public.v_nba_latest_customer_scores_v2 | ACT_EMBEDDING_CONTEXT | technical_log | False | Referenced by backend; Referenced by SQL examples; Referenced by semantic/context docs |
| public.v_new_business_premium_by_rider | ACT_EMBEDDING_CONTEXT | technical_log | False | Referenced by backend; Referenced by SQL examples; Referenced by semantic/context docs |
| public.v_next_best_customer_features | ACT_EMBEDDING_CONTEXT | technical_log | False | Referenced by backend; Referenced by SQL examples; Referenced by semantic/context docs; Referenced by model context |
| public.v_next_best_product_features | ACT_EMBEDDING_CONTEXT | technical_log | False | Referenced by backend; Referenced by SQL examples; Referenced by semantic/context docs; Referenced by model context |
| public.v_policy_lapse_features | ACT_EMBEDDING_CONTEXT | technical_log | False | Referenced by backend; Referenced by SQL examples; Referenced by semantic/context docs; Referenced by model context |
| public.v_policy_rider_tags | ACT_EMBEDDING_CONTEXT | technical_log | False | Referenced by backend; Referenced by SQL examples; Referenced by semantic/context docs |
| public.v_propensity_to_buy_features | ACT_EMBEDDING_CONTEXT | technical_log | False | Referenced by backend; Referenced by SQL examples; Referenced by semantic/context docs; Referenced by model context |
| public.v_recommendation_explainability | ACT_EMBEDDING_CONTEXT | technical_log | False | Referenced by backend; Referenced by SQL examples; Referenced by semantic/context docs |
| public.v_role_intelligence_profile | ACT_EMBEDDING_CONTEXT | technical_log | False | Referenced by backend; Referenced by SQL examples; Referenced by semantic/context docs |

