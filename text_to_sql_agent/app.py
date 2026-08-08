from __future__ import annotations

from fastapi import FastAPI, HTTPException

from embedding_pipeline.config import load_settings as load_embedding_settings
from embedding_pipeline.db import connect
from embedding_pipeline.providers import build_provider

from .audit import create_audit_log, json_safe_rows, update_audit_log
from .executor import execute_readonly_query
from .llm import build_text_provider
from .models import HealthResponse, QueryRequest, QueryResponse
from .retrieval import retrieve_semantic_context
from .schema import fetch_schema_metadata
from .settings import load_agent_settings
from .sql_safety import SqlSafetyError, validate_select_sql


app = FastAPI(title="Insurance Analytics Text-to-SQL Agent", version="0.1.0")


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", service="insurance-text-to-sql")


@app.post("/query", response_model=QueryResponse)
def query(request: QueryRequest) -> QueryResponse:
    settings = load_agent_settings()
    embedding_settings = load_embedding_settings()
    embedding_provider = build_provider(embedding_settings)
    text_provider = build_text_provider(settings)
    row_limit = min(request.row_limit or settings.row_limit, 5000)

    with connect(settings.database_url) as conn:
        audit_id = None
        try:
            semantic_context = retrieve_semantic_context(
                conn,
                provider=embedding_provider,
                question=request.question,
                match_count=settings.semantic_match_count,
                threshold=settings.semantic_threshold,
                business_domain=request.business_domain,
                expected_dimensions=settings.embedding_dimensions,
            )
            audit_id = create_audit_log(
                conn,
                question=request.question,
                semantic_document_ids=[item.semantic_document_id for item in semantic_context],
            )
            schema_metadata = fetch_schema_metadata(conn, schemas=settings.allowed_schemas)
            generated_sql, generation_note = text_provider.generate_sql(
                question=request.question,
                semantic_context=semantic_context,
                schema_metadata=schema_metadata,
                row_limit=row_limit,
            )
            validation = validate_select_sql(
                generated_sql,
                allowed_schemas=settings.allowed_schemas,
                row_limit=row_limit,
            )
            update_audit_log(
                conn,
                audit_id=audit_id,
                generated_sql=validation.sql,
                execution_status="validated",
                safety_decision="allowed_select",
            )
            columns, rows, duration_ms = execute_readonly_query(
                conn,
                sql=validation.sql,
                timeout_ms=settings.statement_timeout_ms,
            )
            safe_rows = json_safe_rows(rows)
            insight = text_provider.explain_results(
                question=request.question,
                sql=validation.sql,
                rows=safe_rows,
                semantic_context=semantic_context,
            )
            update_audit_log(
                conn,
                audit_id=audit_id,
                generated_sql=validation.sql,
                execution_status="executed",
                safety_decision="allowed_select",
                row_count=len(rows),
                duration_ms=duration_ms,
            )
            return QueryResponse(
                question=request.question,
                sql=validation.sql,
                columns=columns,
                rows=safe_rows,
                row_count=len(rows),
                execution_status="executed",
                business_insight=insight,
                semantic_context=semantic_context,
                audit_id=audit_id,
                debug={
                    "generation_note": generation_note,
                    "referenced_tables": sorted(validation.referenced_tables),
                    "duration_ms": duration_ms,
                }
                if request.include_debug
                else None,
            )
        except SqlSafetyError as exc:
            update_audit_log(
                conn,
                audit_id=audit_id,
                generated_sql=locals().get("generated_sql"),
                execution_status="blocked",
                safety_decision="blocked_by_validator",
                error_message=str(exc),
            )
            raise HTTPException(status_code=400, detail=f"Unsafe SQL blocked: {exc}") from exc
        except Exception as exc:
            update_audit_log(
                conn,
                audit_id=audit_id,
                generated_sql=locals().get("generated_sql"),
                execution_status="failed",
                safety_decision="failed",
                error_message=str(exc),
            )
            raise HTTPException(status_code=500, detail=str(exc)) from exc
