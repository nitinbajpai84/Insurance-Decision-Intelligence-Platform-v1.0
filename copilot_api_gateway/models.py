from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from copilot_orchestration.models import IntentClassification
from copilot_sql_engine.models import SqlEngineResponse


class AskRequest(BaseModel):
    question: str = Field(min_length=3, max_length=2000)
    role_code: str | None = None
    business_domain: str | None = None
    include_context: bool = True
    include_debug: bool = False
    row_limit: int = Field(default=500, ge=1, le=5000)
    execute_sql: bool = True


class TestLLMRequest(BaseModel):
    question: str = Field(min_length=3, max_length=2000)
    task_type: str = "general"


class TestLLMResponse(BaseModel):
    provider_used: str
    model_used: str
    latency_ms: int
    answer_preview: str
    fallback_used: bool
    success_flag: bool = True
    error_category: str | None = None
    error_message: str | None = None
    recommended_action: str | None = None


class AskResponse(SqlEngineResponse):
    pass


class IntentClassifyRequest(BaseModel):
    question: str = Field(min_length=3, max_length=2000)


class IntentClassifyResponse(IntentClassification):
    pass


class ContextSearchRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    match_count: int = Field(default=8, ge=1, le=50)
    threshold: float = Field(default=0.0, ge=-1.0, le=1.0)
    business_domain: str | None = None


class SqlValidateRequest(BaseModel):
    sql: str = Field(min_length=1)
    row_limit: int = Field(default=500, ge=1, le=5000)


class SqlValidateResponse(BaseModel):
    valid: bool
    sql: str | None = None
    referenced_tables: list[str] = Field(default_factory=list)
    safety_decision: str
    error_message: str | None = None


class SqlExecuteRequest(BaseModel):
    sql: str = Field(min_length=1)
    row_limit: int = Field(default=500, ge=1, le=5000)
    timeout_ms: int | None = Field(default=None, ge=100, le=60000)


class SqlExecuteResponse(BaseModel):
    validation: SqlValidateResponse
    columns: list[str] = Field(default_factory=list)
    rows: list[dict[str, Any]] = Field(default_factory=list)
    row_count: int = 0
    duration_ms: int | None = None
    execution_status: str
    error_message: str | None = None


class Entity360Response(BaseModel):
    entity_type: str
    entity_id: UUID
    summary: dict[str, Any] = Field(default_factory=dict)
    sections: dict[str, Any] = Field(default_factory=dict)
    generated_at: str


class RoleListItem(BaseModel):
    role_code: str
    role_name: str
    role_category: str
    description: str


class RoleDashboardResponse(BaseModel):
    role_code: str
    role_name: str
    primary_objectives: list[str]
    kpis: list[dict[str, Any]]
    dashboard_widgets: list[dict[str, Any]]
    default_questions: list[dict[str, Any]]
    default_insights: list[str]
    action_templates: list[dict[str, Any]]


class RecommendationListResponse(BaseModel):
    entity_id: UUID
    recommendations: list[dict[str, Any]]


class LineageResponse(BaseModel):
    insight_id: UUID
    lineage: dict[str, Any]
