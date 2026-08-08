from __future__ import annotations

from copilot_orchestration.models import CopilotIntent, PromptContract


SYSTEM_PROMPT_BASE = """You are an Insurance Decision Intelligence Copilot.
Classify the business intent, retrieve only relevant insurance context, and produce safe, role-aware outputs.
Respect data access scope. Use ACORD-inspired business language without claiming proprietary ACORD definitions.
For SQL, generate read-only PostgreSQL SELECT statements only."""


PROMPT_CONTRACTS: dict[CopilotIntent, PromptContract] = {
    CopilotIntent.ANALYTICS: PromptContract(
        system_prompt=SYSTEM_PROMPT_BASE,
        user_prompt_template=(
            "Answer the analytics question using retrieved semantic context and schema metadata.\n"
            "Question: {question}\nRole: {role_code}\nReturn SQL, result summary, caveats, and follow-up questions."
        ),
        required_inputs=["question", "semantic_context", "schema_metadata", "role_profile"],
        output_contract={"sql": "string", "business_insight": "string", "follow_up_questions": ["string"]},
    ),
    CopilotIntent.RECOMMENDATION: PromptContract(
        system_prompt=SYSTEM_PROMPT_BASE,
        user_prompt_template=(
            "Recommend prioritized next-best-actions using model scores, active actions, suppressions, and role action templates.\n"
            "Question: {question}\nRole: {role_code}\nReturn action list with reason, confidence, model evidence, and suggested message."
        ),
        required_inputs=["question", "next_best_actions", "model_scores", "role_action_templates", "semantic_context"],
        output_contract={"actions": ["object"], "suppression_notes": ["string"], "follow_up_questions": ["string"]},
    ),
    CopilotIntent.EXPLANATION: PromptContract(
        system_prompt=SYSTEM_PROMPT_BASE,
        user_prompt_template=(
            "Explain the requested risk, score, recommendation, or outcome using model reasons first and business facts second.\n"
            "Question: {question}\nRole: {role_code}\nReturn explanation, top drivers, evidence, caveats, and next step."
        ),
        required_inputs=["question", "model_scores", "model_predictions", "entity_facts", "semantic_context"],
        output_contract={"explanation": "string", "top_drivers": ["string"], "evidence": ["object"], "caveats": ["string"]},
    ),
    CopilotIntent.KPI_LOOKUP: PromptContract(
        system_prompt=SYSTEM_PROMPT_BASE,
        user_prompt_template=(
            "Return the governed KPI definition and current value if requested.\n"
            "Question: {question}\nRole: {role_code}\nReturn formula, SQL, value, time window, and caveats."
        ),
        required_inputs=["question", "role_kpis", "business_glossary", "semantic_context", "schema_metadata"],
        output_contract={"kpi_name": "string", "definition": "string", "formula": "string", "sql": "string", "value": "number"},
    ),
    CopilotIntent.CUSTOMER_360: PromptContract(
        system_prompt=SYSTEM_PROMPT_BASE,
        user_prompt_template="Build a customer 360 summary with policies, claims, payments, engagement, scores, and actions.\nQuestion: {question}",
        required_inputs=["customer", "policies", "claims", "payments", "model_scores", "next_best_actions"],
        output_contract={"customer_summary": "object", "risks": ["string"], "opportunities": ["string"], "actions": ["object"]},
    ),
    CopilotIntent.AGENT_360: PromptContract(
        system_prompt=SYSTEM_PROMPT_BASE,
        user_prompt_template="Build an agent 360 summary with MAPA productivity, book, pipeline, movement, performance score, and coaching actions.\nQuestion: {question}",
        required_inputs=["agent", "agent_mapa_metrics", "agent_movements", "model_scores", "next_best_actions"],
        output_contract={"agent_summary": "object", "performance": "object", "coaching_actions": ["object"]},
    ),
    CopilotIntent.CAMPAIGN_360: PromptContract(
        system_prompt=SYSTEM_PROMPT_BASE,
        user_prompt_template="Build a campaign 360 view with target, response, conversion, attribution, and follow-up actions.\nQuestion: {question}",
        required_inputs=["campaign", "campaign_targets", "campaign_responses", "leads", "opportunities", "policies", "model_scores"],
        output_contract={"campaign_summary": "object", "funnel": ["object"], "follow_up_actions": ["object"]},
    ),
    CopilotIntent.CLAIMS_360: PromptContract(
        system_prompt=SYSTEM_PROMPT_BASE,
        user_prompt_template="Build a claims 360 view with claim status, severity, reserves, fraud indicators, customer impact, and review actions.\nQuestion: {question}",
        required_inputs=["claim", "policy", "customer", "claim_fraud_indicators", "model_scores"],
        output_contract={"claim_summary": "object", "risk_indicators": ["string"], "review_actions": ["object"]},
    ),
}


def get_prompt_contract(intent: CopilotIntent) -> PromptContract:
    return PROMPT_CONTRACTS[intent]

