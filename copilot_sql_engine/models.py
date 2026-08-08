from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from copilot_orchestration.models import CopilotIntent, IntentClassification


class SqlEngineRequest(BaseModel):
    question: str = Field(min_length=3, max_length=2000)
    role_code: str | None = None
    business_domain: str | None = None
    include_context: bool = True
    include_debug: bool = False
    row_limit: int = Field(default=500, ge=1, le=5000)
    execute_sql: bool = True


class SqlGenerationResult(BaseModel):
    sql: str
    generation_explanation: str
    referenced_tables_expected: list[str] = Field(default_factory=list)
    columns_used: list[str] = Field(default_factory=list)
    metrics_used: list[str] = Field(default_factory=list)
    models_used: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    confidence_score: float = Field(default=0.0, ge=0.0, le=1.0)


class SqlValidationResult(BaseModel):
    sql: str
    referenced_tables: list[str]
    safety_decision: str


class SqlExecutionResult(BaseModel):
    columns: list[str] = Field(default_factory=list)
    rows: list[dict[str, Any]] = Field(default_factory=list)
    row_count: int = 0
    duration_ms: int | None = None
    execution_status: str
    error_message: str | None = None


class BusinessInsight(BaseModel):
    summary: str
    key_observations: list[str] = Field(default_factory=list)
    caveats: list[str] = Field(default_factory=list)


class GeneratedRecommendation(BaseModel):
    recommendation: str
    reason: str
    priority_score: float = Field(default=0.0, ge=0.0, le=1.0)
    source: str = "sql_result"


class ExplainabilityOutput(BaseModel):
    recommendation: str | None = None
    supporting_facts: list[str] = Field(default_factory=list)
    source_tables: list[str] = Field(default_factory=list)
    source_columns: dict[str, list[str]] = Field(default_factory=dict)
    metrics_used: list[str] = Field(default_factory=list)
    business_rules_used: list[str] = Field(default_factory=list)
    ml_models_used: list[str] = Field(default_factory=list)
    context_documents_used: list[dict[str, Any]] = Field(default_factory=list)
    confidence_score: float = Field(default=0.0, ge=0.0, le=1.0)
    timestamp: str


class SqlEngineResponse(BaseModel):
    question: str
    intent: CopilotIntent
    intent_classification: IntentClassification
    role_code: str | None = None
    sql: str | None = None
    validation: SqlValidationResult | None = None
    execution: SqlExecutionResult
    business_insight: BusinessInsight
    recommendations: list[GeneratedRecommendation]
    explainability: ExplainabilityOutput
    retrieved_context: dict[str, Any] | None = None
    role_context: dict[str, Any] | None = None
    sql_metadata: dict[str, Any] = Field(default_factory=dict)
    lifecycle: list[dict[str, Any]] = Field(default_factory=list)
    timings: dict[str, int] = Field(default_factory=dict)
    provider: dict[str, Any] = Field(default_factory=dict)
    confidence_score: float = Field(ge=0.0, le=1.0)
    answer_status: str = "PENDING"
    strict_sql_validation: dict[str, Any] = Field(default_factory=dict)
    sql_repair: dict[str, Any] | None = None
    result_validation: dict[str, Any] = Field(default_factory=dict)
    actual_tables_allowed: list[str] = Field(default_factory=list)
    actual_columns_allowed: list[str] = Field(default_factory=list)
    debug: dict[str, Any] | None = None
