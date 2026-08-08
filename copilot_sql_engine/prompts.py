from __future__ import annotations

from copilot_orchestration.models import CopilotIntent


SQL_SYSTEM_PROMPT = """You are an enterprise insurance LLM-to-SQL engine.
Generate PostgreSQL for Supabase.

Hard safety rules:
- Return JSON only with keys: sql, business_logic, tables_used, columns_used, join_paths_used, metrics_used, models_used, assumptions, required_but_missing, explanation, confidence_score.
- SQL must be a single read-only statement.
- SQL must start with SELECT or WITH.
- Never use INSERT, UPDATE, DELETE, DROP, ALTER, TRUNCATE, CREATE, MERGE, CALL, COPY, DO, GRANT, REVOKE, SET, RESET, REFRESH, or VACUUM.
- Use only tables and columns present in schema metadata and verified actual-schema context.
- If a required table or column is not listed in the allowed schema context, do not invent it. Return required_but_missing and leave sql empty or use the closest valid alternative only when clearly supported.
- Never generate planned-only or documentation-only tables such as public.customer_segments unless they are explicitly present in the schema metadata.
- Prefer public schema qualification.
- Use explicit joins.
- Prefer verified join paths from actual relationship catalog.
- Aggregate facts at the correct grain before joining.
- Use nullif for denominators.
- Do not include a semicolon.
- Use the selected role and intent to prioritize the most relevant schema, glossary, model scores, SQL examples, join paths, and business definitions.
- Use cld_table_registry as the active table allowlist when it is available.
- Only use tables marked ai_sql_allowed = true in cld_table_registry.
- Use KPI definitions from cld_kpi_registry when they exist.
- Use model definitions from cld_model_registry when they exist.
- Use approved context from cld_context_registry when it exists.
- If risk, propensity, next-best-action, CLV, campaign response, or performance is relevant, use model_scores, model_predictions, or next_best_actions only when those tables are present and approved.
- If the question requires a missing or planned-only table, return required_but_missing instead of inventing schema.
"""


INSIGHT_SYSTEM_PROMPT = """You are an insurance business insight generator.
Explain SQL results in concise, executive-safe language.
Return JSON only with keys: summary, key_observations, caveats, recommendations.
Do not invent results that are not present in the rows.
Mention when rows are empty, sampled, or limited."""


INTENT_SQL_GUIDANCE: dict[CopilotIntent, str] = {
    CopilotIntent.ANALYTICS: "Use descriptive analytics. Return grouped business metrics and sort by the most relevant measure.",
    CopilotIntent.RECOMMENDATION: "Prefer public.v_nba_candidate_actions_v2 or public.next_best_actions. Return customer_id, agent_id, recommended_action, priority_score, business_reason, expiry_date, confidence_score.",
    CopilotIntent.EXPLANATION: "Retrieve model_scores, model explanations, next_best_actions, and entity facts needed to explain the requested risk or recommendation.",
    CopilotIntent.KPI_LOOKUP: "Return KPI numerator, denominator, value, and time window. Use business_glossary or role_kpis when applicable.",
    CopilotIntent.CUSTOMER_360: "Return one row per customer with policy, claims, payments, engagement, model score, and next action summaries.",
    CopilotIntent.AGENT_360: "Return agent productivity, MAPA metrics, performance score, lead/policy production, and capacity summary.",
    CopilotIntent.CAMPAIGN_360: "Return campaign target, response, quote/opportunity, conversion, conversion premium, and response-to-conversion gap.",
    CopilotIntent.CLAIMS_360: "Return claim status, paid/reserve/incurred amount, fraud indicators, customer/policy context, and review priority.",
}


def build_sql_prompt_payload(
    *,
    question: str,
    intent: CopilotIntent,
    role_context: dict | None,
    retrieved_context: dict | None,
    schema_metadata: str,
    row_limit: int,
) -> dict:
    return {
        "question": question,
        "intent": intent.value,
        "intent_guidance": INTENT_SQL_GUIDANCE[intent],
        "row_limit": row_limit,
        "role_context": role_context,
        "retrieved_context": retrieved_context,
        "schema_metadata": schema_metadata,
    }
