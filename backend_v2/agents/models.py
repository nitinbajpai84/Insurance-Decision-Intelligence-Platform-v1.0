"""Shared typed results passed between the V2 agents (NOT raw strings)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, AsyncGenerator


@dataclass
class ContextResult:
    cache_hit: bool = False
    cached_answer: str | None = None
    cache_similarity: float = 0.0
    glossary_terms: list[dict[str, Any]] = field(default_factory=list)   # {term, definition}
    semantic_docs: list[dict[str, Any]] = field(default_factory=list)    # {title, chunk, score}
    schema_context: list[dict[str, Any]] = field(default_factory=list)   # {table, column, description}
    similar_past_queries: list[dict[str, Any]] = field(default_factory=list)  # {question, answer, sql}
    total_tokens_estimate: int = 0
    assembly_time_ms: int = 0
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "cache_hit": self.cache_hit,
            "cached_answer": self.cached_answer,
            "cache_similarity": self.cache_similarity,
            "glossary_terms": self.glossary_terms,
            "semantic_docs": self.semantic_docs,
            "schema_context": self.schema_context,
            "similar_past_queries": self.similar_past_queries,
            "total_tokens_estimate": self.total_tokens_estimate,
            "assembly_time_ms": self.assembly_time_ms,
            "errors": self.errors,
        }


@dataclass
class SQLResult:
    sql: str = ""
    tables_used: list[str] = field(default_factory=list)
    columns_used: list[str] = field(default_factory=list)
    validation_status: str = "not_validated"  # validated | blocked | parse_failed | empty
    validation_errors: list[str] = field(default_factory=list)
    repair_needed: bool = False
    generation_time_ms: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "sql": self.sql,
            "tables_used": self.tables_used,
            "columns_used": self.columns_used,
            "validation_status": self.validation_status,
            "validation_errors": self.validation_errors,
            "repair_needed": self.repair_needed,
            "generation_time_ms": self.generation_time_ms,
        }


@dataclass
class ExecutionResult:
    rows: list[dict[str, Any]] = field(default_factory=list)
    columns: list[str] = field(default_factory=list)
    row_count: int = 0
    explain_passed: bool = False
    repaired: bool = False
    repair_sql: str | None = None
    execution_status: str = "not_executed"  # executed | failed | blocked
    error_message: str | None = None
    suspicious_zero_rows: bool = False
    execution_time_ms: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "rows": self.rows[:25],
            "columns": self.columns,
            "row_count": self.row_count,
            "explain_passed": self.explain_passed,
            "repaired": self.repaired,
            "repair_sql": self.repair_sql,
            "execution_status": self.execution_status,
            "error_message": self.error_message,
            "suspicious_zero_rows": self.suspicious_zero_rows,
            "execution_time_ms": self.execution_time_ms,
        }


@dataclass
class InsightResult:
    insight_stream: AsyncGenerator[str, None] | None = None  # streams tokens
    confidence_score: float = 0.0
    key_data_points: list[dict[str, Any]] = field(default_factory=list)
    recommended_action: str = ""
    business_limitations: str = ""
    models_used: list[str] = field(default_factory=list)
    generation_time_ms: int = 0

    def metadata(self) -> dict[str, Any]:
        return {
            "confidence_score": self.confidence_score,
            "key_data_points": self.key_data_points,
            "recommended_action": self.recommended_action,
            "business_limitations": self.business_limitations,
            "models_used": self.models_used,
            "generation_time_ms": self.generation_time_ms,
        }
