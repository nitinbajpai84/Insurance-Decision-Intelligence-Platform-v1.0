from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from ai_insight_v11_service import AiInsightV11Request, AiInsightV11Response, ask_ai_insight_v11
from context_retriever_service import ContextRetriever
from copilot_api_gateway.db import connect, json_ready
from copilot_api_gateway.entity360 import (
    agent_360,
    agent_performance_dashboard,
    campaign_360,
    claims_360,
    customer_360,
    recommendations_for_entity,
    policy_lapse_dashboard,
    search_agents,
    search_campaigns,
    search_customers,
)
from copilot_api_gateway.models import (
    AskRequest,
    AskResponse,
    ContextSearchRequest,
    Entity360Response,
    IntentClassifyRequest,
    IntentClassifyResponse,
    LineageResponse,
    RecommendationListResponse,
    RoleDashboardResponse,
    RoleListItem,
    SqlExecuteRequest,
    SqlExecuteResponse,
    SqlValidateRequest,
    SqlValidateResponse,
    TestLLMRequest,
    TestLLMResponse,
)
from copilot_orchestration.classifier import classify_intent
from copilot_sql_engine.engine import run_sql_engine
from copilot_sql_engine.executor import execute_select, json_safe_rows
from copilot_sql_engine.llm_providers import (
    classify_gemini_error,
    gemini_error_action,
    get_llm_provider,
    provider_health,
    response_preview,
)
from copilot_sql_engine.models import SqlEngineRequest
from copilot_sql_engine.safety import SqlValidationError, validate_sql
from copilot_sql_engine.settings import load_sql_engine_settings
from decision_intelligence_service import fetch_decision_intelligence
from insight_snapshot_service import fetch_latest_insight_evidence, save_ai_insight_snapshot, save_insight_snapshot
from role_intelligence_service import fetch_role_profile, fetch_roles
from sql_validation_service import validate_sql_strict


app = FastAPI(
    title="Insurance Decision Intelligence API",
    version="1.0.0",
    description="Unified gateway for intelligence questions, intent classification, context retrieval, SQL safety/execution, 360 views, roles, recommendations, and lineage.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:3000",
        "http://localhost:3000",
        "http://127.0.0.1:3001",
        "http://localhost:3001",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "insurance-decision-intelligence-api"}


@app.get("/health/llm")
def health_llm() -> dict[str, Any]:
    return provider_health()


@app.post("/copilot/test-llm", response_model=TestLLMResponse)
def copilot_test_llm(request: TestLLMRequest) -> TestLLMResponse:
    try:
        response = get_llm_provider(request.task_type).generate(
            request.question,
            task_type=request.task_type,
            temperature=0.1,
        )
        return TestLLMResponse(
            provider_used=response.provider,
            model_used=response.model,
            latency_ms=response.latency_ms,
            answer_preview=response_preview(response.text),
            fallback_used=response.fallback_used,
        )
    except Exception as exc:
        error_message = f"{type(exc).__name__}: {exc}"
        error_category = classify_gemini_error(error_message)
        return TestLLMResponse(
            provider_used="gemini",
            model_used="configured Gemini model unavailable",
            latency_ms=0,
            answer_preview=(
                "Gemini did not return a live LLM response. "
                f"Reason: {error_category}. Deterministic fallback should be used for MVP demo flows."
            ),
            fallback_used=True,
            success_flag=False,
            error_category=error_category,
            error_message=error_message[:1000],
            recommended_action=gemini_error_action(error_category),
        )


@app.post("/copilot/ask", response_model=AskResponse)
def copilot_ask(request: AskRequest) -> AskResponse:
    return intelligence_ask(request)


@app.post("/intelligence/ask", response_model=AskResponse)
def intelligence_ask(request: AskRequest) -> AskResponse:
    try:
        response = run_sql_engine(
            SqlEngineRequest(
                question=request.question,
                role_code=request.role_code,
                business_domain=request.business_domain,
                include_context=request.include_context,
                include_debug=request.include_debug,
                row_limit=request.row_limit,
                execute_sql=request.execute_sql,
            )
        )
        ask_response = AskResponse(**response.model_dump())
        try:
            save_insight_snapshot(question=request.question, role=request.role_code, response=ask_response)
        except Exception:
            pass
        return ask_response
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"intelligence_ask failed: {type(exc).__name__}: {exc}") from exc


@app.post("/intent/classify", response_model=IntentClassifyResponse)
def intent_classify(request: IntentClassifyRequest) -> IntentClassifyResponse:
    return IntentClassifyResponse(**classify_intent(request.question).model_dump())


@app.post("/context/search")
def context_search(request: ContextSearchRequest) -> dict[str, Any]:
    return ContextRetriever().retrieve(
        question=request.question,
        match_count=request.match_count,
        threshold=request.threshold,
        business_domain=request.business_domain,
    )


@app.post("/sql/validate", response_model=SqlValidateResponse)
def sql_validate(request: SqlValidateRequest) -> SqlValidateResponse:
    settings = load_sql_engine_settings()
    try:
        safe = validate_sql(request.sql, allowed_schemas=settings.allowed_schemas, row_limit=request.row_limit)
        return SqlValidateResponse(
            valid=True,
            sql=safe.sql,
            referenced_tables=sorted(safe.referenced_tables),
            safety_decision="allowed_select_or_with",
        )
    except SqlValidationError as exc:
        return SqlValidateResponse(
            valid=False,
            safety_decision="blocked_by_validator",
            error_message=str(exc),
        )


@app.post("/sql/execute", response_model=SqlExecuteResponse)
def sql_execute(request: SqlExecuteRequest) -> SqlExecuteResponse:
    settings = load_sql_engine_settings()
    validation = sql_validate(SqlValidateRequest(sql=request.sql, row_limit=request.row_limit))
    if not validation.valid or not validation.sql:
        return SqlExecuteResponse(validation=validation, execution_status="blocked", error_message=validation.error_message)
    try:
        with connect(settings.database_url) as conn:
            columns, rows, duration_ms = execute_select(
                conn,
                sql=validation.sql,
                timeout_ms=request.timeout_ms or settings.statement_timeout_ms,
            )
        safe_rows = json_safe_rows(rows)
        return SqlExecuteResponse(
            validation=validation,
            columns=columns,
            rows=safe_rows,
            row_count=len(safe_rows),
            duration_ms=duration_ms,
            execution_status="executed",
        )
    except Exception as exc:
        return SqlExecuteResponse(validation=validation, execution_status="failed", error_message=str(exc))


@app.get("/customers/{id}/360", response_model=Entity360Response)
def get_customer_360(id: UUID) -> Entity360Response:
    return Entity360Response(**customer_360(id))


@app.get("/customers/search")
def get_customer_search(q: str = "", limit: int = 10) -> list[dict[str, Any]]:
    return search_customers(q, min(max(limit, 1), 25))


@app.get("/agents/{id}/360", response_model=Entity360Response)
def get_agent_360(id: UUID) -> Entity360Response:
    return Entity360Response(**agent_360(id))


@app.get("/agents/search")
def get_agent_search(q: str = "", limit: int = 10) -> list[dict[str, Any]]:
    return search_agents(q, min(max(limit, 1), 25))


@app.get("/agents/performance-dashboard")
def get_agent_performance_dashboard(
    region: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> dict[str, Any]:
    return agent_performance_dashboard(region=region or None, date_from=date_from or None, date_to=date_to or None)


@app.get("/campaigns/{id}/360", response_model=Entity360Response)
def get_campaign_360(id: UUID) -> Entity360Response:
    return Entity360Response(**campaign_360(id))


@app.get("/campaigns/search")
def get_campaign_search(
    q: str = "",
    limit: int = 10,
    channel: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> list[dict[str, Any]]:
    return search_campaigns(
        q,
        min(max(limit, 1), 25),
        channel=channel or None,
        date_from=date_from or None,
        date_to=date_to or None,
    )


@app.get("/policies/lapse-dashboard")
def get_policy_lapse_dashboard(
    region: str | None = None,
    product: str | None = None,
    segment: str | None = None,
) -> dict[str, Any]:
    return policy_lapse_dashboard(region=region or None, product=product or None, segment=segment or None)


@app.get("/claims/{id}/360", response_model=Entity360Response)
def get_claims_360(id: UUID) -> Entity360Response:
    return Entity360Response(**claims_360(id))


@app.get("/roles", response_model=list[RoleListItem])
def get_roles() -> list[RoleListItem]:
    return [RoleListItem(**row) for row in fetch_roles()]


@app.get("/roles/{role}/dashboard", response_model=RoleDashboardResponse)
def get_role_dashboard(role: str) -> RoleDashboardResponse:
    profile = fetch_role_profile(role)
    return RoleDashboardResponse(
        role_code=profile["role_code"],
        role_name=profile["role_name"],
        primary_objectives=profile.get("primary_objectives") or [],
        kpis=profile.get("kpis") or [],
        dashboard_widgets=profile.get("dashboard_widgets") or [],
        default_questions=profile.get("default_questions") or [],
        default_insights=profile.get("default_insights") or [],
        action_templates=profile.get("action_templates") or [],
    )


@app.get("/intelligence/briefing")
def get_intelligence_briefing(role: str | None = None) -> dict[str, Any]:
    return fetch_decision_intelligence(role)


@app.get("/debug/insight-pipeline")
def debug_insight_pipeline(role: str | None = "executive_leadership", question: str | None = "What revenue is at risk?") -> dict[str, Any]:
    errors: list[str] = []
    response = None
    try:
        response = run_sql_engine(
            SqlEngineRequest(
                question=question or "What revenue is at risk?",
                role_code=role,
                include_context=True,
                include_debug=True,
                row_limit=10,
                execute_sql=True,
            )
        )
    except Exception as exc:
        errors.append(f"{type(exc).__name__}: {exc}")

    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute("select count(*) as count from public.semantic_documents")
            context_documents_count = cur.fetchone()["count"]
            cur.execute("select count(*) as count from public.business_glossary")
            glossary_entries_count = cur.fetchone()["count"]

    retrieved_count = 0
    if response and response.retrieved_context:
        retrieved_count = sum(len(value) for value in response.retrieved_context.values() if isinstance(value, list))

    return {
        "role_received": bool(role),
        "role_config_loaded": bool(response and response.role_context) or bool(fetch_decision_intelligence(role)),
        "context_documents_count": retrieved_count or context_documents_count,
        "semantic_documents_total": context_documents_count,
        "glossary_entries_count": glossary_entries_count,
        "sql_generated": bool(response and response.sql),
        "sql_validated": bool(response and response.validation),
        "sql_executed": bool(response and response.execution.execution_status == "executed"),
        "rows_returned": response.execution.row_count if response else 0,
        "model_scores_used": bool(response and response.explainability.ml_models_used),
        "insight_generated": bool(response and response.business_insight.summary),
        "timings": response.timings if response else {},
        "provider": response.provider if response else {},
        "errors": errors,
    }


@app.get("/debug/actual-schema-catalog")
def debug_actual_schema_catalog() -> dict[str, Any]:
    with connect() as conn:
        with conn.cursor() as cur:
            try:
                cur.execute(
                    """
                    select snapshot_id, snapshot_timestamp, schema_name, table_count, column_count,
                           relationship_count, status
                    from public.cld_actual_schema_snapshot
                    order by snapshot_timestamp desc
                    limit 1
                    """
                )
                snapshot = cur.fetchone()
            except Exception:
                snapshot = None
            if not snapshot:
                return {
                    "status": "missing",
                    "message": "Actual schema catalog has not been built. Run scripts/build_actual_schema_catalog.py.",
                    "table_count": 0,
                    "column_count": 0,
                    "relationship_count": 0,
                    "top_tables": [],
                }
            cur.execute(
                """
                select full_table_name, business_domain, estimated_row_count
                from public.cld_actual_table_catalog
                where snapshot_id = %s
                order by estimated_row_count desc nulls last, full_table_name
                limit 20
                """,
                (snapshot["snapshot_id"],),
            )
            top_tables = cur.fetchall()
    return {
        "status": snapshot["status"],
        "snapshot_id": str(snapshot["snapshot_id"]),
        "last_snapshot_timestamp": snapshot["snapshot_timestamp"],
        "schema_name": snapshot["schema_name"],
        "table_count": snapshot["table_count"],
        "column_count": snapshot["column_count"],
        "relationship_count": snapshot["relationship_count"],
        "top_tables": json_ready([dict(row) for row in top_tables]),
    }


@app.get("/debug/sql-context-health")
def debug_sql_context_health() -> dict[str, Any]:
    with connect() as conn:
        with conn.cursor() as cur:
            counts: dict[str, Any] = {}
            for name, query in {
                "verified_context_count": "select count(*) as count from public.cld_verified_sql_context_documents where sql_usable = true",
                "embedding_count": "select count(*) as count from public.cld_verified_sql_context_documents where embedding is not null",
                "missing_embedding_count": "select count(*) as count from public.cld_verified_sql_context_documents where sql_usable = true and embedding is null",
                "invalid_context_count": "select count(*) as count from public.cld_context_validation_results where classification = 'invalid_schema_reference'",
                "planned_only_context_count": "select count(*) as count from public.cld_context_validation_results where classification = 'planned_only'",
            }.items():
                try:
                    cur.execute(query)
                    counts[name] = cur.fetchone()["count"]
                except Exception:
                    counts[name] = None
    return counts


@app.post("/debug/validate-sql")
def debug_validate_sql(request: SqlValidateRequest) -> dict[str, Any]:
    settings = load_sql_engine_settings()
    with connect(settings.database_url) as conn:
        result = validate_sql_strict(
            conn,
            sql=request.sql,
            allowed_schemas=settings.allowed_schemas,
            row_limit=request.row_limit,
            statement_timeout_ms=settings.statement_timeout_ms,
        )
    return result.to_dict()


@app.get("/debug/demo-question-health")
def debug_demo_question_health() -> dict[str, Any]:
    with connect() as conn:
        with conn.cursor() as cur:
            try:
                cur.execute(
                    """
                    select
                      count(*) as total,
                      count(*) filter (where is_validated = true) as validated,
                      count(*) filter (where is_validated = false) as failed,
                      max(last_validated_at) as last_validation_timestamp
                    from public.cld_demo_question_catalog
                    """
                )
                row = cur.fetchone()
            except Exception:
                return {
                    "status": "missing",
                    "message": "Demo question catalog has not been built. Run scripts/smoke_test_demo_questions.py.",
                    "total_demo_questions": 0,
                    "validated_count": 0,
                    "failed_count": 0,
                    "last_validation_timestamp": None,
                }
    return {
        "status": "available",
        "total_demo_questions": row["total"],
        "validated_count": row["validated"],
        "failed_count": row["failed"],
        "last_validation_timestamp": row["last_validation_timestamp"],
    }


@app.post("/ai-insight-v11/ask", response_model=AiInsightV11Response)
def ai_insight_v11_ask(request: AiInsightV11Request) -> AiInsightV11Response:
    try:
        response = ask_ai_insight_v11(request)
        try:
            response.insight_id = str(save_ai_insight_snapshot(response))
        except Exception:
            response.technical_warnings = list(
                dict.fromkeys(
                    response.technical_warnings
                    + ["Insight evidence snapshot could not be stored for this run."]
                )
            )
        return response
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"ai_insight_v11_ask failed: {type(exc).__name__}: {exc}") from exc


@app.get("/debug/latest-insight-evidence")
def debug_latest_insight_evidence(insight_id: UUID | None = None) -> dict[str, Any]:
    try:
        return fetch_latest_insight_evidence(insight_id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"debug_latest_insight_evidence failed: {type(exc).__name__}: {exc}") from exc


@app.get("/recommendations/{entity_id}", response_model=RecommendationListResponse)
def get_recommendations(entity_id: UUID) -> RecommendationListResponse:
    payload = recommendations_for_entity(entity_id)
    return RecommendationListResponse(**payload)


@app.get("/lineage/{insight_id}", response_model=LineageResponse)
def get_lineage(insight_id: UUID) -> LineageResponse:
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select
                  il.*,
                  coalesce(e.evidence, '[]'::jsonb) as evidence,
                  coalesce(c.context_usage, '[]'::jsonb) as context_usage
                from public.insight_lineage il
                left join lateral (
                  select jsonb_agg(to_jsonb(re) order by re.display_order, re.created_at) as evidence
                  from public.recommendation_evidence re
                  where re.insight_lineage_id = il.insight_lineage_id
                ) e on true
                left join lateral (
                  select jsonb_agg(to_jsonb(cul) order by cul.created_at) as context_usage
                  from public.context_usage_log cul
                  where cul.insight_lineage_id = il.insight_lineage_id
                ) c on true
                where il.insight_lineage_id = %s
                """,
                (str(insight_id),),
            )
            row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail=f"Lineage not found: {insight_id}")
    return LineageResponse(insight_id=insight_id, lineage=json_ready(dict(row)))
