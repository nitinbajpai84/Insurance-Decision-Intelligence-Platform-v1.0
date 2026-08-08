from __future__ import annotations

from typing import Any

from context_retriever_service import ContextRetriever
from role_intelligence_service import fetch_role_profile

from copilot_orchestration.models import CopilotIntent, IntentDefinition, RetrievalPlan


DOMAIN_BY_INTENT: dict[CopilotIntent, str | None] = {
    CopilotIntent.ANALYTICS: None,
    CopilotIntent.RECOMMENDATION: "next_best_action",
    CopilotIntent.EXPLANATION: None,
    CopilotIntent.KPI_LOOKUP: None,
    CopilotIntent.CUSTOMER_360: "customer",
    CopilotIntent.AGENT_360: "agent",
    CopilotIntent.CAMPAIGN_360: "campaign",
    CopilotIntent.CLAIMS_360: "claims",
}


def build_retrieval_plan(
    *,
    intent: CopilotIntent,
    question: str,
    role_code: str | None,
    definition: IntentDefinition,
) -> RetrievalPlan:
    include_schema = intent in {
        CopilotIntent.ANALYTICS,
        CopilotIntent.KPI_LOOKUP,
        CopilotIntent.CUSTOMER_360,
        CopilotIntent.AGENT_360,
        CopilotIntent.CAMPAIGN_360,
        CopilotIntent.CLAIMS_360,
    }
    include_scores = bool(definition.ml_models_required)
    return RetrievalPlan(
        strategy_name=f"{intent.lower()}_hybrid_retrieval",
        semantic_query=build_semantic_query(question, role_code, definition),
        semantic_match_count=12 if intent in {CopilotIntent.ANALYTICS, CopilotIntent.KPI_LOOKUP} else 8,
        business_domain=DOMAIN_BY_INTENT[intent],
        include_schema_metadata=include_schema,
        include_role_profile=role_code is not None,
        include_model_scores=include_scores,
        include_next_best_actions=intent in {CopilotIntent.RECOMMENDATION, CopilotIntent.CUSTOMER_360},
        context_sources=definition.context_sources,
    )


def build_semantic_query(question: str, role_code: str | None, definition: IntentDefinition) -> str:
    parts = [
        f"question: {question}",
        f"intent: {definition.intent}",
        f"context sources: {', '.join(definition.context_sources)}",
        f"tables: {', '.join(definition.tables_required[:8])}",
    ]
    if role_code:
        parts.append(f"role: {role_code}")
    if definition.ml_models_required:
        parts.append(f"models: {', '.join(definition.ml_models_required)}")
    return "\n".join(parts)


def retrieve_context(plan: RetrievalPlan, role_code: str | None) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    role_profile = None
    if plan.include_role_profile and role_code:
        role_profile = fetch_role_profile(role_code)

    retriever = ContextRetriever()
    retrieved_context = retriever.retrieve(
        question=plan.semantic_query,
        match_count=plan.semantic_match_count,
        threshold=0.0,
        business_domain=plan.business_domain,
    )
    return retrieved_context, role_profile

