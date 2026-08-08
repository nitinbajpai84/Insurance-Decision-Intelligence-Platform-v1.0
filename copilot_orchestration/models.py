from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class CopilotIntent(StrEnum):
    ANALYTICS = "ANALYTICS"
    RECOMMENDATION = "RECOMMENDATION"
    EXPLANATION = "EXPLANATION"
    KPI_LOOKUP = "KPI_LOOKUP"
    CUSTOMER_360 = "CUSTOMER_360"
    AGENT_360 = "AGENT_360"
    CAMPAIGN_360 = "CAMPAIGN_360"
    CLAIMS_360 = "CLAIMS_360"


class RouteTarget(StrEnum):
    TEXT_TO_SQL = "TEXT_TO_SQL"
    NEXT_BEST_ACTION = "NEXT_BEST_ACTION"
    MODEL_EXPLANATION = "MODEL_EXPLANATION"
    ENTITY_360 = "ENTITY_360"
    KPI_SERVICE = "KPI_SERVICE"


class IntentDefinition(BaseModel):
    intent: CopilotIntent
    description: str
    context_sources: list[str]
    tables_required: list[str]
    ml_models_required: list[str]
    sql_generation_requirements: list[str]
    explanation_requirements: list[str]
    default_route: RouteTarget


class IntentClassification(BaseModel):
    intent: CopilotIntent
    confidence_score: float = Field(ge=0.0, le=1.0)
    rationale: str
    matched_signals: list[str] = Field(default_factory=list)
    fallback_intent: CopilotIntent | None = None


class OrchestrationRequest(BaseModel):
    question: str = Field(min_length=3, max_length=2000)
    role_code: str | None = None
    user_id: str | None = None
    session_id: str | None = None
    entity_type: str | None = None
    entity_id: str | None = None
    include_context: bool = True
    execute: bool = False
    row_limit: int = Field(default=500, ge=1, le=5000)


class RetrievalPlan(BaseModel):
    strategy_name: str
    semantic_query: str
    semantic_match_count: int
    business_domain: str | None = None
    include_schema_metadata: bool = False
    include_role_profile: bool = False
    include_model_scores: bool = False
    include_next_best_actions: bool = False
    context_sources: list[str]


class PromptContract(BaseModel):
    system_prompt: str
    user_prompt_template: str
    required_inputs: list[str]
    output_contract: dict[str, Any]


class ApiContract(BaseModel):
    route_target: RouteTarget
    method: str
    path: str
    request_shape: dict[str, Any]
    response_shape: dict[str, Any]


class OrchestrationPlan(BaseModel):
    question: str
    role_code: str | None
    classification: IntentClassification
    intent_definition: IntentDefinition
    retrieval_plan: RetrievalPlan
    prompt_contract: PromptContract
    api_contract: ApiContract
    downstream_services: list[str]
    retrieved_context: dict[str, Any] | None = None
    role_profile: dict[str, Any] | None = None
    execution_note: str

