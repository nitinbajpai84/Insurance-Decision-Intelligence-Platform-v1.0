from __future__ import annotations

import os
from datetime import datetime, timezone
from time import perf_counter
from typing import Any

from context_retriever_service import ContextRetriever
from copilot_sql_engine.cache import cache_get_or_set
from copilot_orchestration.classifier import classify_intent
from copilot_orchestration.intents import INTENT_DEFINITIONS
from copilot_sql_engine.executor import connect, execute_select, json_safe_rows
from copilot_sql_engine.generator import MockSqlProvider, build_sql_provider
from copilot_sql_engine.models import (
    BusinessInsight,
    ExplainabilityOutput,
    GeneratedRecommendation,
    SqlEngineRequest,
    SqlEngineResponse,
    SqlExecutionResult,
    SqlValidationResult,
)
from copilot_sql_engine.safety import SqlValidationError, validate_sql
from copilot_sql_engine.settings import load_sql_engine_settings
from role_intelligence_service import fetch_role_profile
from result_validation_service import validate_result_relevance
from sql_repair_service import repair_sql_once
from sql_validation_service import validate_sql_strict
from table_governance_service import load_ai_sql_allowlist, load_context_rows, load_kpi_rows, load_model_rows, load_table_registry_rows
from text_to_sql_agent.schema import fetch_schema_metadata


def run_sql_engine(request: SqlEngineRequest) -> SqlEngineResponse:
    total_started = perf_counter()
    timings: dict[str, int] = {}
    settings = load_sql_engine_settings()
    provider = build_sql_provider(settings)
    row_limit = min(request.row_limit, settings.row_limit, 5000)

    started = perf_counter()
    classification = classify_intent(request.question)
    timings["intent_classification_ms"] = elapsed_ms(started)
    intent_definition = INTENT_DEFINITIONS[classification.intent]
    started = perf_counter()
    retrieved_context, context_error = maybe_retrieve_context(request)
    timings["context_retrieval_ms"] = elapsed_ms(started)
    started = perf_counter()
    role_context, role_error = maybe_retrieve_role_context(request.role_code)
    timings["role_context_ms"] = elapsed_ms(started)

    with connect(settings.database_url) as conn:
        approved_tables = load_ai_sql_allowlist(conn, settings.allowed_schemas)
        governance_context = build_governance_context(
            conn,
            approved_tables=approved_tables,
            allowed_schemas=settings.allowed_schemas,
        )
        started = perf_counter()
        schema_metadata, schema_cache_hit, schema_cache_latency_ms = cache_get_or_set(
            f"schema_metadata:{','.join(sorted(settings.allowed_schemas))}:{','.join(sorted(approved_tables))}",
            lambda: fetch_schema_metadata(
                conn,
                schemas=settings.allowed_schemas,
                allowed_tables=approved_tables or None,
            ),
        )
        timings["schema_metadata_ms"] = elapsed_ms(started)
        if governance_context:
            if retrieved_context is None:
                retrieved_context = {}
            retrieved_context = {
                **retrieved_context,
                "_governance": governance_context,
            }
        generation_error = None
        try:
            started = perf_counter()
            generation = provider.generate_sql(
                question=request.question,
                intent=classification.intent,
                role_context=role_context,
                retrieved_context=retrieved_context,
                schema_metadata=schema_metadata,
                row_limit=row_limit,
            )
            timings["sql_generation_ms"] = elapsed_ms(started)
            if not generation.sql.strip():
                raise ValueError("LLM returned empty SQL")
        except Exception as exc:
            timings["sql_generation_ms"] = elapsed_ms(started)
            generation_error = f"{type(exc).__name__}: {exc}"
            started = perf_counter()
            generation = MockSqlProvider().generate_sql(
                question=request.question,
                intent=classification.intent,
                role_context=role_context,
                retrieved_context=retrieved_context,
                schema_metadata=schema_metadata,
                row_limit=row_limit,
            )
            timings["fallback_sql_generation_ms"] = elapsed_ms(started)

        started = perf_counter()
        strict_validation = validate_sql_strict(
            conn,
            sql=generation.sql,
            allowed_schemas=settings.allowed_schemas,
            allowed_tables=approved_tables or None,
            row_limit=row_limit,
            statement_timeout_ms=settings.statement_timeout_ms,
        )
        timings["sql_validation_ms"] = elapsed_ms(started)
        repair_result = None
        if not strict_validation.is_valid:
            started = perf_counter()
            repair_result = repair_sql_once(
                question=request.question,
                role_code=request.role_code,
                failed_sql=generation.sql,
                validation_error="; ".join(strict_validation.errors),
                allowed_schema_context=build_allowed_schema_context(
                    conn,
                    settings.allowed_schemas,
                    allowed_tables=approved_tables or None,
                ),
                business_context={"retrieved_context": retrieved_context, "role_context": role_context},
                row_limit=row_limit,
            )
            timings["sql_repair_ms"] = elapsed_ms(started)
            if repair_result.repair_status == "REPAIRED" and repair_result.sql:
                generation.sql = repair_result.sql
                started = perf_counter()
                strict_validation = validate_sql_strict(
                    conn,
                    sql=generation.sql,
                    allowed_schemas=settings.allowed_schemas,
                    allowed_tables=approved_tables or None,
                    row_limit=row_limit,
                    statement_timeout_ms=settings.statement_timeout_ms,
                )
                strict_validation.repaired = True
                timings["sql_repair_validation_ms"] = elapsed_ms(started)

        if not strict_validation.is_valid or not strict_validation.sql:
            return unsupported_response(
                request=request,
                classification=classification,
                retrieved_context=retrieved_context,
                role_context=role_context,
                generation=generation,
                strict_validation=strict_validation.to_dict(),
                repair_result=repair_result.to_dict() if repair_result else None,
                context_error=context_error,
                role_error=role_error,
                generation_error=generation_error,
                timings=timings,
            )

        validation = SqlValidationResult(
            sql=strict_validation.sql,
            referenced_tables=strict_validation.tables_used,
            safety_decision="validated_against_actual_schema",
        )

        if request.execute_sql:
            try:
                started = perf_counter()
                columns, rows, duration_ms = execute_select(
                    conn,
                    sql=validation.sql,
                    timeout_ms=settings.statement_timeout_ms,
                )
                timings["sql_execution_ms"] = elapsed_ms(started)
                safe_rows = json_safe_rows(rows)
                execution = SqlExecutionResult(
                    columns=columns,
                    rows=safe_rows,
                    row_count=len(safe_rows),
                    duration_ms=duration_ms,
                    execution_status="executed",
                )
            except Exception as exc:
                timings["sql_execution_ms"] = elapsed_ms(started)
                execution = SqlExecutionResult(execution_status="failed", error_message=str(exc))
        else:
            execution = SqlExecutionResult(execution_status="not_executed")

    if execution.execution_status == "executed":
        started = perf_counter()
        result_validation = validate_result_relevance(
            question=request.question,
            role_code=request.role_code,
            intent=classification.intent,
            generated_sql=validation.sql,
            execution_status=execution.execution_status,
            row_count=execution.row_count,
            result_preview=execution.rows[:25],
            retrieved_context=retrieved_context,
            missing_requirements=(repair_result.missing_requirements if repair_result else []),
        )
        timings["result_validation_ms"] = elapsed_ms(started)
        insight_error = None
        if result_validation.can_generate_business_insight:
            try:
                started = perf_counter()
                insight, recommendations = provider.generate_insight(
                    question=request.question,
                    intent=classification.intent,
                    sql=validation.sql,
                    rows=execution.rows,
                    retrieved_context=retrieved_context,
                )
                timings["insight_generation_ms"] = elapsed_ms(started)
            except Exception as exc:
                timings["insight_generation_ms"] = elapsed_ms(started)
                insight_error = f"{type(exc).__name__}: {exc}"
                started = perf_counter()
                insight, recommendations = MockSqlProvider().generate_insight(
                    question=request.question,
                    intent=classification.intent,
                    sql=validation.sql,
                    rows=execution.rows,
                    retrieved_context=retrieved_context,
                )
                timings["fallback_insight_generation_ms"] = elapsed_ms(started)
        else:
            insight = BusinessInsight(
                summary="This question cannot be answered with the current available schema and validated SQL result.",
                key_observations=[],
                caveats=result_validation.limitations,
            )
            recommendations = []
    else:
        insight_error = None
        result_validation = validate_result_relevance(
            question=request.question,
            role_code=request.role_code,
            intent=classification.intent,
            generated_sql=validation.sql if validation else None,
            execution_status=execution.execution_status,
            row_count=execution.row_count,
            result_preview=[],
            retrieved_context=retrieved_context,
        )
        insight = BusinessInsight(
            summary="SQL was generated and validated but not executed successfully.",
            key_observations=[],
            caveats=[execution.error_message] if execution.error_message else ["Execution was disabled."],
        )
        recommendations = []

    confidence = calculate_confidence(
        classification_confidence=classification.confidence_score,
        generation_confidence=generation.confidence_score,
        has_context=bool(retrieved_context),
        execution=execution,
    )
    explainability = build_explainability_output(
        request=request,
        referenced_tables=validation.referenced_tables,
        intent_definition=intent_definition,
        retrieved_context=retrieved_context,
        recommendations=recommendations,
        confidence_score=confidence,
        role_context=role_context,
    )
    timings["total_latency_ms"] = elapsed_ms(total_started)
    sql_metadata = build_sql_metadata(
        sql=validation.sql,
        generation=generation,
        validation=validation,
        execution=execution,
        explainability=explainability,
    )
    lifecycle = build_lifecycle(
        retrieved_context=retrieved_context,
        validation=validation,
        execution=execution,
        insight=insight,
    )

    return SqlEngineResponse(
        question=request.question,
        intent=classification.intent,
        intent_classification=classification,
        role_code=request.role_code,
        sql=validation.sql,
        validation=validation,
        execution=execution,
        business_insight=insight,
        recommendations=recommendations,
        explainability=explainability,
        retrieved_context=retrieved_context if request.include_context else None,
        role_context=role_context,
        sql_metadata=sql_metadata,
        lifecycle=lifecycle,
        timings=timings,
        provider=parse_provider_metadata(
            generation.generation_explanation,
            generation_error=generation_error,
            insight_error=insight_error,
        ),
        confidence_score=confidence,
        answer_status=result_validation.answer_status,
        strict_sql_validation=strict_validation.to_dict(),
        sql_repair=repair_result.to_dict() if repair_result else None,
        result_validation=result_validation.to_dict(),
        actual_tables_allowed=strict_validation.tables_used,
        actual_columns_allowed=strict_validation.columns_used,
        debug={
            "generation_explanation": generation.generation_explanation,
            "expected_tables": generation.referenced_tables_expected,
            "context_error": context_error,
            "role_error": role_error,
            "generation_error": generation_error,
            "insight_error": insight_error,
            "strict_sql_validation": strict_validation.to_dict(),
            "sql_repair": repair_result.to_dict() if repair_result else None,
            "result_validation": result_validation.to_dict(),
            "schema_cache_hit": schema_cache_hit,
            "schema_cache_latency_ms": schema_cache_latency_ms,
        }
        if request.include_debug
        else None,
    )


def elapsed_ms(started: float) -> int:
    return int(round((perf_counter() - started) * 1000))


def build_lifecycle(
    *,
    retrieved_context: dict[str, Any] | None,
    validation: SqlValidationResult | None,
    execution: SqlExecutionResult,
    insight: BusinessInsight | None,
) -> list[dict[str, Any]]:
    context_count = sum(len(value) for value in (retrieved_context or {}).values() if isinstance(value, list))
    return [
        {"step": "Context retrieved", "status": "complete" if context_count > 0 else "warning", "detail": f"{context_count} documents"},
        {"step": "SQL generated", "status": "complete" if validation and validation.sql else "failed", "detail": "Read-only query prepared"},
        {"step": "SQL validated", "status": "complete" if validation else "failed", "detail": validation.safety_decision if validation else "Blocked"},
        {"step": "SQL executed", "status": "complete" if execution.execution_status == "executed" else execution.execution_status, "detail": f"{execution.row_count} rows"},
        {"step": "Insight generated", "status": "complete" if insight and insight.summary else "warning", "detail": "Business explanation ready" if insight else "No insight"},
    ]


def build_sql_metadata(
    *,
    sql: str,
    generation,
    validation: SqlValidationResult,
    execution: SqlExecutionResult,
    explainability: ExplainabilityOutput,
) -> dict[str, Any]:
    return {
        "tables_used": validation.referenced_tables or generation.referenced_tables_expected,
        "columns_used": generation.columns_used or flatten_source_columns(explainability.source_columns),
        "metrics_used": generation.metrics_used or explainability.metrics_used,
        "models_used": generation.models_used or explainability.ml_models_used,
        "assumptions": generation.assumptions,
        "validation_status": validation.safety_decision,
        "execution_status": execution.execution_status,
        "execution_time_ms": execution.duration_ms,
        "row_count": execution.row_count,
        "sql_confidence": confidence_band(generation.confidence_score),
    }


def flatten_source_columns(source_columns: dict[str, list[str]]) -> list[str]:
    return [f"{table}.{column}" for table, columns in source_columns.items() for column in columns]


def confidence_band(value: float) -> str:
    if value >= 0.75:
        return "High"
    if value >= 0.5:
        return "Medium"
    return "Low"


def parse_provider_metadata(
    explanation: str,
    *,
    generation_error: str | None = None,
    insight_error: str | None = None,
) -> dict[str, Any]:
    provider = {"provider_used": "configured", "model_used": "configured", "fallback_used": False}
    for chunk in explanation.split(";"):
        clean = chunk.strip().strip(".")
        key, sep, value = clean.partition("=")
        key = key.strip().lower()
        value = value.strip()
        if key == "provider":
            provider["provider_used"] = value
        elif key == "model":
            provider["model_used"] = value
        elif key == "fallback_used":
            provider["fallback_used"] = value.lower() == "true"
        elif key == "latency_ms":
            try:
                provider["llm_latency_ms"] = int(value)
            except ValueError:
                pass
    configured_provider = os.getenv("LLM_PROVIDER", "gemini").strip() or "gemini"
    configured_model = os.getenv("GEMINI_MODEL_SQL", os.getenv("TEXT2SQL_MODEL", "gemini-2.5-flash-lite")).strip()
    if provider["provider_used"] == "configured":
        provider["provider_used"] = configured_provider
    if provider["model_used"] == "configured":
        provider["model_used"] = configured_model
    combined_error = f"{generation_error or ''} {insight_error or ''}".strip()
    if combined_error:
        lowered = combined_error.lower()
        if "prepayment credits are depleted" in lowered or "billing" in lowered:
            provider["provider_used"] = f"{configured_provider} (billing fallback)"
        elif "resource_exhausted" in lowered or "quota" in lowered:
            provider["provider_used"] = f"{configured_provider} (quota fallback)"
        else:
            provider["provider_used"] = f"{configured_provider} (fallback)"
        provider["model_used"] = f"{configured_model} + deterministic fallback"
        provider["fallback_used"] = True
    return provider


def maybe_retrieve_context(request: SqlEngineRequest) -> tuple[dict[str, Any] | None, str | None]:
    if not request.include_context:
        return None, None
    try:
        key = f"context:{request.business_domain or ''}:{request.question.strip().lower()}"
        context, cache_hit, latency_ms = cache_get_or_set(
            key,
            lambda: ContextRetriever().retrieve(
                question=request.question,
                match_count=12,
                threshold=0.0,
                business_domain=request.business_domain,
            ),
        )
        context["_cache"] = {"hit": cache_hit, "latency_ms": latency_ms}
        return context, None
    except Exception as exc:
        return None, str(exc)


def maybe_retrieve_role_context(role_code: str | None) -> tuple[dict[str, Any] | None, str | None]:
    if not role_code:
        return None, None
    try:
        role_context, cache_hit, latency_ms = cache_get_or_set(f"role:{role_code}", lambda: fetch_role_profile(role_code))
        role_context["_cache"] = {"hit": cache_hit, "latency_ms": latency_ms}
        return role_context, None
    except Exception as exc:
        return None, str(exc)


def build_governance_context(
    conn,
    *,
    approved_tables: set[str],
    allowed_schemas: set[str],
) -> dict[str, Any]:
    table_rows = load_table_registry_rows(conn, allowed_schemas)
    kpi_rows = load_kpi_rows(conn, allowed_schemas)
    model_rows = load_model_rows(conn, allowed_schemas)
    context_rows = load_context_rows(conn, allowed_schemas)
    if not table_rows and not kpi_rows and not model_rows and not context_rows and not approved_tables:
        return {}
    active_table_rows = [row for row in table_rows if str(row.get("classification_label", "")).startswith("ACT_")]
    return {
        "allowed_tables": sorted(approved_tables),
        "active_tables": [
            {
                "schema_name": row.get("schema_name"),
                "table_name": row.get("table_name"),
                "classification_label": row.get("classification_label"),
                "table_role": row.get("table_role"),
                "business_domain": row.get("business_domain"),
                "ai_sql_allowed": row.get("ai_sql_allowed"),
                "context_allowed": row.get("context_allowed"),
                "reason": row.get("reason"),
            }
            for row in active_table_rows[:40]
        ],
        "kpis": [
            {
                "kpi_name": row.get("kpi_name"),
                "business_definition": row.get("business_definition"),
                "formula": row.get("formula"),
                "business_domain": row.get("business_domain"),
                "authoritative_tables": row.get("authoritative_tables"),
                "status": row.get("status"),
                "missing_data_points": row.get("missing_data_points"),
            }
            for row in kpi_rows[:25]
        ],
        "models": [
            {
                "model_name": row.get("model_name"),
                "business_purpose": row.get("business_purpose"),
                "score_table": row.get("score_table"),
                "score_column": row.get("score_column"),
                "registry_status": row.get("registry_status"),
                "missing_data_points": row.get("missing_data_points"),
            }
            for row in model_rows[:25]
        ],
        "approved_context": [
            {
                "context_type": row.get("context_type"),
                "title": row.get("title"),
                "business_domain": row.get("business_domain"),
                "sql_usable": row.get("sql_usable"),
            }
            for row in context_rows[:20]
        ],
        "guardrail_summary": [
            "Use only ACT tables that are ai_sql_allowed=true.",
            "If a table or column is missing, return required_but_missing and avoid hallucination.",
            "Do not reference TRUN tables, planned-only tables, or invented columns.",
        ],
    }


def build_allowed_schema_context(
    conn,
    allowed_schemas: set[str],
    limit_tables: int = 140,
    allowed_tables: set[str] | None = None,
) -> str:
    try:
        with conn.cursor() as cur:
            snapshot_id = None
            try:
                cur.execute(
                    """
                    select snapshot_id
                    from public.cld_actual_schema_snapshot
                    where status in ('created', 'completed')
                    order by snapshot_timestamp desc
                    limit 1
                    """
                )
                row = cur.fetchone()
                snapshot_id = row["snapshot_id"] if row else None
            except Exception:
                snapshot_id = None

            if snapshot_id:
                cur.execute(
                    """
                    select
                      t.full_table_name,
                      t.business_domain,
                      coalesce(t.business_description, '') as business_description,
                      coalesce(jsonb_agg(c.column_name order by c.ordinal_position)
                        filter (where c.column_name is not null), '[]'::jsonb) as columns
                    from public.cld_actual_table_catalog t
                    left join public.cld_actual_column_catalog c
                      on c.snapshot_id = t.snapshot_id
                     and c.schema_name = t.schema_name
                     and c.table_name = t.table_name
                     and c.is_sql_allowed = true
                    where t.snapshot_id = %s
                      and t.schema_name = any(%s)
                      and t.is_sql_allowed = true
                      and t.is_planned_only = false
                      and (%s::text[] is null or t.full_table_name = any(%s))
                    group by t.full_table_name, t.business_domain, t.business_description
                    order by t.full_table_name
                    limit %s
                    """,
                    (
                        snapshot_id,
                        list(allowed_schemas),
                        list(allowed_tables) if allowed_tables else None,
                        list(allowed_tables) if allowed_tables else None,
                        limit_tables,
                    ),
                )
            else:
                cur.execute(
                    """
                    select
                      table_schema || '.' || table_name as full_table_name,
                      null::text as business_domain,
                      ''::text as business_description,
                      jsonb_agg(column_name order by ordinal_position) as columns
                    from information_schema.columns
                    where table_schema = any(%s)
                      and (%s::text[] is null or table_schema || '.' || table_name = any(%s))
                    group by table_schema, table_name
                    order by table_schema, table_name
                    limit %s
                    """,
                    (
                        list(allowed_schemas),
                        list(allowed_tables) if allowed_tables else None,
                        list(allowed_tables) if allowed_tables else None,
                        limit_tables,
                    ),
                )
            rows = cur.fetchall()
    except Exception:
        return ""

    lines = []
    for row in rows:
        columns = row["columns"] or []
        lines.append(
            f"Table {row['full_table_name']} ({row.get('business_domain') or 'Actual schema'}): "
            f"{', '.join(columns)}"
        )
    return "\n".join(lines)


def calculate_confidence(
    *,
    classification_confidence: float,
    generation_confidence: float,
    has_context: bool,
    execution: SqlExecutionResult,
) -> float:
    value = 0.25 + (0.25 * classification_confidence) + (0.25 * generation_confidence)
    if has_context:
        value += 0.10
    if execution.execution_status == "executed":
        value += 0.10
        if execution.row_count > 0:
            value += 0.05
    elif execution.execution_status == "failed":
        value -= 0.25
    return round(min(1.0, max(0.0, value)), 6)


def flatten_context_documents(retrieved_context: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not retrieved_context:
        return []
    docs: list[dict[str, Any]] = []
    for bucket in ["business_context", "schema_context", "metric_context", "model_context"]:
        for item in retrieved_context.get(bucket, []) or []:
            docs.append(
                {
                    "semantic_document_id": item.get("semantic_document_id"),
                    "title": item.get("title"),
                    "document_type": item.get("document_type"),
                    "business_domain": item.get("business_domain"),
                    "score": item.get("score"),
                }
            )
    return docs[:10]


def build_explainability_output(
    *,
    request: SqlEngineRequest,
    referenced_tables: list[str],
    intent_definition,
    retrieved_context: dict[str, Any] | None,
    recommendations: list[GeneratedRecommendation],
    confidence_score: float,
    role_context: dict[str, Any] | None,
) -> ExplainabilityOutput:
    source_columns = {
        table: ["See generated SQL projection and joins for selected columns."]
        for table in referenced_tables
    }
    metrics = sorted(
        {
            metric
            for context in (retrieved_context or {}).values()
            if isinstance(context, list)
            for item in context
            if isinstance(item, dict)
            for metric in item.get("related_metrics", []) or []
        }
    )
    if role_context:
        for kpi in role_context.get("kpis", []) or []:
            if isinstance(kpi, dict) and kpi.get("kpi_code"):
                metrics.append(str(kpi["kpi_code"]))
    recommendation = recommendations[0].recommendation if recommendations else None
    supporting_facts = []
    if recommendations:
        supporting_facts.append(recommendations[0].reason)
    supporting_facts.append(f"Intent classified as {intent_definition.intent.value}.")
    supporting_facts.append(f"SQL validated as read-only SELECT/WITH over {len(referenced_tables)} table(s).")
    return ExplainabilityOutput(
        recommendation=recommendation,
        supporting_facts=supporting_facts,
        source_tables=referenced_tables,
        source_columns=source_columns,
        metrics_used=sorted(set(metrics))[:20],
        business_rules_used=intent_definition.sql_generation_requirements,
        ml_models_used=intent_definition.ml_models_required,
        context_documents_used=flatten_context_documents(retrieved_context),
        confidence_score=confidence_score,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


def blocked_response(
    *,
    request: SqlEngineRequest,
    classification,
    retrieved_context: dict[str, Any] | None,
    role_context: dict[str, Any] | None,
    error: str,
    generated_sql: str,
    debug_errors: list[str | None],
    timings: dict[str, int] | None = None,
) -> SqlEngineResponse:
    execution = SqlExecutionResult(execution_status="blocked", error_message=error)
    confidence = 0.0
    timings = timings or {}
    timings["total_latency_ms"] = timings.get("total_latency_ms", 0)
    return SqlEngineResponse(
        question=request.question,
        intent=classification.intent,
        intent_classification=classification,
        role_code=request.role_code,
        sql=generated_sql,
        validation=None,
        execution=execution,
        business_insight=BusinessInsight(
            summary="Generated SQL was blocked by safety validation.",
            key_observations=[],
            caveats=[error],
        ),
        recommendations=[],
        explainability=ExplainabilityOutput(
            recommendation=None,
            supporting_facts=["SQL safety validator blocked the generated query."],
            source_tables=[],
            source_columns={},
            metrics_used=[],
            business_rules_used=["Only SELECT and WITH statements are allowed."],
            ml_models_used=[],
            context_documents_used=flatten_context_documents(retrieved_context),
            confidence_score=confidence,
            timestamp=datetime.now(timezone.utc).isoformat(),
        ),
        retrieved_context=retrieved_context if request.include_context else None,
        role_context=role_context,
        sql_metadata={
            "tables_used": [],
            "columns_used": [],
            "metrics_used": [],
            "models_used": [],
            "assumptions": [],
            "validation_status": "blocked_by_validator",
            "execution_status": "blocked",
            "row_count": 0,
            "sql_confidence": "Low",
            "corrected_sql_attempt": None,
            "fallback_query": None,
        },
        lifecycle=[
            {"step": "Context retrieved", "status": "complete" if retrieved_context else "warning", "detail": "Context retrieval attempted"},
            {"step": "SQL generated", "status": "complete" if generated_sql else "failed", "detail": "Query generated"},
            {"step": "SQL validated", "status": "failed", "detail": error},
            {"step": "SQL executed", "status": "blocked", "detail": "Execution skipped"},
            {"step": "Insight generated", "status": "warning", "detail": "Validation failure explanation only"},
        ],
        timings=timings,
        provider={"provider_used": "configured", "model_used": "configured", "fallback_used": False},
        confidence_score=confidence,
        debug={"errors": [item for item in debug_errors if item]} if request.include_debug else None,
    )


def unsupported_response(
    *,
    request: SqlEngineRequest,
    classification,
    retrieved_context: dict[str, Any] | None,
    role_context: dict[str, Any] | None,
    generation,
    strict_validation: dict[str, Any],
    repair_result: dict[str, Any] | None,
    context_error: str | None,
    role_error: str | None,
    generation_error: str | None,
    timings: dict[str, int],
) -> SqlEngineResponse:
    errors = strict_validation.get("errors") or ["Generated SQL could not be validated against the actual schema."]
    missing = list(strict_validation.get("missing_tables") or []) + list(strict_validation.get("missing_columns") or [])
    if repair_result:
        missing.extend(repair_result.get("missing_requirements") or [])
    reason = "; ".join(str(item) for item in errors)
    execution = SqlExecutionResult(execution_status="blocked", error_message=reason)
    result_validation = {
        "answer_status": "NOT_SUPPORTED",
        "validation_status": "NOT_SUPPORTED",
        "does_result_answer_question": False,
        "result_quality_score": 0.0,
        "reason": "This question cannot be answered with the current available schema.",
        "missing_data_points": list(dict.fromkeys([str(item) for item in missing])),
        "limitations": [reason],
        "can_generate_business_insight": False,
        "publish_allowed": False,
    }
    return SqlEngineResponse(
        question=request.question,
        intent=classification.intent,
        intent_classification=classification,
        role_code=request.role_code,
        sql=generation.sql,
        validation=None,
        execution=execution,
        business_insight=BusinessInsight(
            summary="This question cannot be answered with the current available schema.",
            key_observations=[
                "The generated SQL did not pass validation against the actual Supabase schema.",
                "No business insight was published because the SQL was not executable.",
            ],
            caveats=list(dict.fromkeys([str(item) for item in missing] or [reason])),
        ),
        recommendations=[
            GeneratedRecommendation(
                recommendation="Ask a supported question using actual tables such as customers, policies, agents, campaigns, claims, model_scores, or next_best_actions.",
                reason="The SQL validator found schema references that are not available in Supabase.",
                priority_score=0.65,
                source="schema_validator",
            )
        ],
        explainability=ExplainabilityOutput(
            recommendation=None,
            supporting_facts=["SQL failed strict actual-schema validation.", reason],
            source_tables=strict_validation.get("tables_used") or [],
            source_columns={},
            metrics_used=generation.metrics_used or [],
            business_rules_used=["Use only tables and columns from cld_actual_* catalog or information_schema."],
            ml_models_used=generation.models_used or [],
            context_documents_used=flatten_context_documents(retrieved_context),
            confidence_score=0.0,
            timestamp=datetime.now(timezone.utc).isoformat(),
        ),
        retrieved_context=retrieved_context if request.include_context else None,
        role_context=role_context,
        sql_metadata={
            "tables_used": strict_validation.get("tables_used") or [],
            "columns_used": strict_validation.get("columns_used") or [],
            "metrics_used": generation.metrics_used or [],
            "models_used": generation.models_used or [],
            "assumptions": generation.assumptions or [],
            "validation_status": strict_validation.get("validation_status") or "SQL_VALIDATION_FAILED",
            "execution_status": "blocked",
            "row_count": 0,
            "sql_confidence": "Low",
            "required_but_missing": result_validation["missing_data_points"],
        },
        lifecycle=[
            {"step": "Context retrieved", "status": "complete" if retrieved_context else "warning", "detail": "Context retrieval attempted"},
            {"step": "SQL generated", "status": "complete" if generation.sql else "failed", "detail": "Candidate SQL generated"},
            {"step": "SQL validated", "status": "failed", "detail": reason},
            {"step": "SQL repair attempted", "status": "complete" if repair_result else "skipped", "detail": (repair_result or {}).get("repair_status", "No repair")},
            {"step": "SQL executed", "status": "blocked", "detail": "Execution skipped"},
            {"step": "Result validated", "status": "failed", "detail": "No executable result"},
            {"step": "Insight generated", "status": "blocked", "detail": "No fake insight published"},
        ],
        timings=timings,
        provider=parse_provider_metadata(generation.generation_explanation, generation_error=generation_error, insight_error=None),
        confidence_score=0.0,
        answer_status="NOT_SUPPORTED",
        strict_sql_validation=strict_validation,
        sql_repair=repair_result,
        result_validation=result_validation,
        actual_tables_allowed=strict_validation.get("tables_used") or [],
        actual_columns_allowed=strict_validation.get("columns_used") or [],
        debug={
            "context_error": context_error,
            "role_error": role_error,
            "generation_error": generation_error,
            "strict_sql_validation": strict_validation,
            "sql_repair": repair_result,
            "result_validation": result_validation,
        }
        if request.include_debug
        else None,
    )
