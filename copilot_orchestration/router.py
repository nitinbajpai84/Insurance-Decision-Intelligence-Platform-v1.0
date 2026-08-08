from __future__ import annotations

from copilot_orchestration.classifier import classify_intent
from copilot_orchestration.intents import INTENT_DEFINITIONS
from copilot_orchestration.models import (
    ApiContract,
    CopilotIntent,
    OrchestrationPlan,
    OrchestrationRequest,
    RouteTarget,
)
from copilot_orchestration.prompts import get_prompt_contract
from copilot_orchestration.retrieval import build_retrieval_plan, retrieve_context


DOWNSTREAM_BY_ROUTE: dict[RouteTarget, list[str]] = {
    RouteTarget.TEXT_TO_SQL: ["text_to_sql_agent.app:/query", "context_retriever_service:/retrieve-context"],
    RouteTarget.NEXT_BEST_ACTION: ["nba_engine.api:/customers/{customer_id}/next-best-action", "context_retriever_service:/retrieve-context"],
    RouteTarget.MODEL_EXPLANATION: ["text_to_sql_agent.app:/query", "context_retriever_service:/retrieve-context"],
    RouteTarget.ENTITY_360: ["text_to_sql_agent.app:/query", "context_retriever_service:/retrieve-context"],
    RouteTarget.KPI_SERVICE: ["text_to_sql_agent.app:/query", "role_intelligence_service:/api/roles/{role_code}/profile"],
}


def build_api_contract(intent: CopilotIntent, route: RouteTarget) -> ApiContract:
    if route == RouteTarget.NEXT_BEST_ACTION:
        return ApiContract(
            route_target=route,
            method="GET",
            path="/customers/{customer_id}/next-best-action",
            request_shape={"customer_id": "uuid optional for customer-specific requests", "persist": "boolean", "retrieve_context": "boolean"},
            response_shape={"recommended_action": "string", "priority_score": "number", "business_reason": "string", "context_used": ["object"]},
        )
    if route == RouteTarget.KPI_SERVICE:
        return ApiContract(
            route_target=route,
            method="POST",
            path="/query",
            request_shape={"question": "string", "business_domain": "string optional", "row_limit": "integer"},
            response_shape={"sql": "string", "rows": ["object"], "business_insight": "string", "semantic_context": ["object"]},
        )
    if route == RouteTarget.ENTITY_360:
        return ApiContract(
            route_target=route,
            method="POST",
            path="/query",
            request_shape={"question": "string", "entity_type": "string optional", "entity_id": "uuid optional"},
            response_shape={"summary": "object", "sql": "string", "rows": ["object"], "business_insight": "string"},
        )
    if route == RouteTarget.MODEL_EXPLANATION:
        return ApiContract(
            route_target=route,
            method="POST",
            path="/query",
            request_shape={"question": "string", "include_debug": "boolean"},
            response_shape={"explanation": "string", "top_drivers": ["string"], "evidence": ["object"], "semantic_context": ["object"]},
        )
    return ApiContract(
        route_target=route,
        method="POST",
        path="/query",
        request_shape={"question": "string", "business_domain": "string optional", "row_limit": "integer", "include_debug": "boolean"},
        response_shape={"sql": "string", "columns": ["string"], "rows": ["object"], "business_insight": "string"},
    )


def build_orchestration_plan(request: OrchestrationRequest) -> OrchestrationPlan:
    classification = classify_intent(request.question)
    definition = INTENT_DEFINITIONS[classification.intent]
    retrieval_plan = build_retrieval_plan(
        intent=classification.intent,
        question=request.question,
        role_code=request.role_code,
        definition=definition,
    )
    prompt_contract = get_prompt_contract(classification.intent)
    api_contract = build_api_contract(classification.intent, definition.default_route)

    retrieved_context = None
    role_profile = None
    execution_note = "Plan generated. Downstream execution is disabled for this MVP orchestration endpoint."
    if request.include_context:
        retrieved_context, role_profile = retrieve_context(retrieval_plan, request.role_code)
        execution_note = "Plan generated with pgvector context retrieval. Set execute=true in a future executor endpoint to call downstream services."

    return OrchestrationPlan(
        question=request.question,
        role_code=request.role_code,
        classification=classification,
        intent_definition=definition,
        retrieval_plan=retrieval_plan,
        prompt_contract=prompt_contract,
        api_contract=api_contract,
        downstream_services=DOWNSTREAM_BY_ROUTE[definition.default_route],
        retrieved_context=retrieved_context,
        role_profile=role_profile,
        execution_note=execution_note,
    )

