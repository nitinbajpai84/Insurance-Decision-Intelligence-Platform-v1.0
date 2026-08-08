from __future__ import annotations

from copilot_orchestration.models import CopilotIntent, IntentDefinition, RouteTarget


INTENT_DEFINITIONS: dict[CopilotIntent, IntentDefinition] = {
    CopilotIntent.ANALYTICS: IntentDefinition(
        intent=CopilotIntent.ANALYTICS,
        description="Aggregated descriptive or diagnostic analysis across insurance facts and dimensions.",
        context_sources=["semantic_documents", "business_glossary", "schema_metadata", "role_kpis"],
        tables_required=["policies", "premiums", "claims", "campaigns", "campaign_responses", "agents", "customers", "products"],
        ml_models_required=[],
        sql_generation_requirements=[
            "Generate one read-only SELECT statement.",
            "Use explicit joins and aggregate before joining facts at different grains.",
            "Use nullif for ratio denominators.",
            "Return grouped metrics with clear aliases.",
        ],
        explanation_requirements=[
            "Explain the top drivers and caveats.",
            "Mention filters, time window, and grain.",
            "Avoid claiming causality from descriptive analytics.",
        ],
        default_route=RouteTarget.TEXT_TO_SQL,
    ),
    CopilotIntent.RECOMMENDATION: IntentDefinition(
        intent=CopilotIntent.RECOMMENDATION,
        description="Operational next-best-action or prioritized work queue request.",
        context_sources=["next_best_actions", "model_scores", "model_predictions", "semantic_documents", "role_action_templates"],
        tables_required=["next_best_actions", "customers", "agents", "policies", "products", "model_scores", "model_predictions", "customer_complaints", "payments"],
        ml_models_required=["propensity_to_buy", "policy_lapse", "customer_churn", "next_best_product", "lead_conversion", "campaign_response", "customer_lifetime_value", "agent_performance"],
        sql_generation_requirements=[
            "Prefer existing next_best_actions and v_nba_candidate_actions_v2 before generating custom SQL.",
            "Filter to active recommendations and non-expired actions.",
            "Respect marketing opt-out and unresolved complaint suppressions.",
            "Order by priority_score desc and expiry_date asc.",
        ],
        explanation_requirements=[
            "Explain the recommendation rule, model scores used, and suppression reason if any.",
            "Provide agent-safe suggested next step.",
            "Include confidence score and expiry date.",
        ],
        default_route=RouteTarget.NEXT_BEST_ACTION,
    ),
    CopilotIntent.EXPLANATION: IntentDefinition(
        intent=CopilotIntent.EXPLANATION,
        description="Reason or driver explanation for a model score, action, customer risk, or business outcome.",
        context_sources=["model_scores", "model_predictions", "semantic_documents", "business_glossary", "next_best_actions"],
        tables_required=["model_scores", "model_predictions", "next_best_actions", "customers", "policies", "claims", "payments", "customer_engagement_events"],
        ml_models_required=["policy_lapse", "customer_churn", "propensity_to_buy", "fraud_risk", "claims_prediction", "agent_performance", "campaign_response"],
        sql_generation_requirements=[
            "Retrieve the latest model score and explanation payload for the requested entity.",
            "Join only entity-specific facts needed to support the explanation.",
            "Do not infer feature importance if not present; state unavailable.",
        ],
        explanation_requirements=[
            "Use model top reasons first, then supporting business facts.",
            "Distinguish model signal from business rule.",
            "Use plain-language caveats about synthetic/model-driven outputs.",
        ],
        default_route=RouteTarget.MODEL_EXPLANATION,
    ),
    CopilotIntent.KPI_LOOKUP: IntentDefinition(
        intent=CopilotIntent.KPI_LOOKUP,
        description="Definition or current value request for a governed KPI.",
        context_sources=["role_kpis", "business_glossary", "semantic_documents", "schema_metadata"],
        tables_required=["business_glossary", "role_kpis", "policies", "premiums", "claims", "campaign_responses", "agent_mapa_metrics"],
        ml_models_required=[],
        sql_generation_requirements=[
            "Use governed KPI calculation when present.",
            "Return numerator, denominator, KPI value, and time window where applicable.",
            "Use nullif for ratios.",
        ],
        explanation_requirements=[
            "Give KPI definition and formula.",
            "Explain time window and denominator.",
            "State if the KPI is role-specific or enterprise-wide.",
        ],
        default_route=RouteTarget.KPI_SERVICE,
    ),
    CopilotIntent.CUSTOMER_360: IntentDefinition(
        intent=CopilotIntent.CUSTOMER_360,
        description="Customer profile, lifecycle, policies, claims, engagement, scores, and actions.",
        context_sources=["customers", "policies", "claims", "payments", "customer_engagement_events", "model_scores", "next_best_actions", "semantic_documents"],
        tables_required=["customers", "parties", "policies", "products", "claims", "payments", "customer_complaints", "customer_engagement_events", "model_scores", "next_best_actions"],
        ml_models_required=["propensity_to_buy", "policy_lapse", "customer_churn", "next_best_product", "customer_lifetime_value", "campaign_response"],
        sql_generation_requirements=[
            "Require or infer a customer identifier or filter.",
            "Return customer summary at customer grain.",
            "Separate policy, claim, payment, engagement, and action sections.",
        ],
        explanation_requirements=[
            "Summarize relationship, risk, opportunity, and next action.",
            "Highlight unresolved complaints and payment issues before sales opportunities.",
        ],
        default_route=RouteTarget.ENTITY_360,
    ),
    CopilotIntent.AGENT_360: IntentDefinition(
        intent=CopilotIntent.AGENT_360,
        description="Agent productivity, book, MAPA metrics, movement, performance, targets, and coaching needs.",
        context_sources=["agents", "agent_mapa_metrics", "agent_movements", "model_scores", "next_best_actions", "semantic_documents"],
        tables_required=["agents", "parties", "agent_mapa_metrics", "agent_movements", "agent_targets", "agent_commissions", "policies", "leads", "model_scores", "next_best_actions"],
        ml_models_required=["agent_performance", "agent_attrition", "next_best_customer", "lead_conversion"],
        sql_generation_requirements=[
            "Require or infer agent identifier, territory, agency, or manager scope.",
            "Use monthly MAPA trends for productivity.",
            "Include capacity and performance score if available.",
        ],
        explanation_requirements=[
            "Summarize production, activity, conversion, retention, and coaching opportunities.",
            "Call out movement history if territory or agency changed.",
        ],
        default_route=RouteTarget.ENTITY_360,
    ),
    CopilotIntent.CAMPAIGN_360: IntentDefinition(
        intent=CopilotIntent.CAMPAIGN_360,
        description="Campaign performance, targeting, response, conversion, attribution, and follow-up actions.",
        context_sources=["campaigns", "campaign_targets", "campaign_responses", "leads", "opportunities", "policies", "model_scores", "semantic_documents"],
        tables_required=["campaigns", "campaign_targets", "campaign_responses", "leads", "opportunities", "policies", "products", "model_scores", "next_best_actions"],
        ml_models_required=["campaign_response", "lead_conversion", "propensity_to_buy", "next_best_product"],
        sql_generation_requirements=[
            "Return funnel counts from target to response to opportunity to policy conversion.",
            "Include conversion premium and conversion rate.",
            "Handle opt-out and suppression counts separately.",
        ],
        explanation_requirements=[
            "Explain response versus conversion gap.",
            "Identify segments or agents needing follow-up.",
        ],
        default_route=RouteTarget.ENTITY_360,
    ),
    CopilotIntent.CLAIMS_360: IntentDefinition(
        intent=CopilotIntent.CLAIMS_360,
        description="Claims profile, severity, reserves, fraud indicators, claimant impact, and operational review.",
        context_sources=["claims", "claim_assessments", "claim_fraud_indicators", "model_scores", "policies", "customers", "semantic_documents"],
        tables_required=["claims", "claim_parties", "claim_assessments", "claim_fraud_indicators", "policies", "customers", "products", "model_scores"],
        ml_models_required=["claims_prediction", "fraud_risk", "customer_churn", "customer_lifetime_value"],
        sql_generation_requirements=[
            "Require or infer claim identifier, status, severity, product, or segment.",
            "Keep claim metrics at claim grain unless aggregating by segment.",
            "Include paid, reserve, incurred, status, and fraud indicators where available.",
        ],
        explanation_requirements=[
            "Explain severity, fraud signal, customer impact, and recommended review action.",
            "Avoid making definitive fraud claims; describe risk indicators.",
        ],
        default_route=RouteTarget.ENTITY_360,
    ),
}
