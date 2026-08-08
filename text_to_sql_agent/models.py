from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    question: str = Field(..., min_length=3, max_length=2000)
    business_domain: str | None = None
    row_limit: int | None = Field(default=None, ge=1, le=5000)
    include_debug: bool = False


class SemanticContextItem(BaseModel):
    semantic_document_id: str
    title: str
    document_type: str
    business_domain: str | None
    content: str
    related_tables: list[str]
    related_metrics: list[str]
    example_questions: list[str]
    similarity: float | None = None


class QueryResponse(BaseModel):
    question: str
    sql: str
    columns: list[str]
    rows: list[dict[str, Any]]
    row_count: int
    execution_status: str
    business_insight: str
    semantic_context: list[SemanticContextItem]
    audit_id: str | None = None
    debug: dict[str, Any] | None = None


class HealthResponse(BaseModel):
    status: str
    service: str
