from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from psycopg.types.json import Jsonb

from copilot_api_gateway.db import connect, json_ready


INSIGHT_SNAPSHOT_DDL = """
create extension if not exists pgcrypto;

create table if not exists public.insight_test_snapshots (
  snapshot_id uuid primary key default gen_random_uuid(),
  test_run_id uuid not null,
  role varchar(100),
  question text not null,
  intent varchar(100),
  retrieved_context jsonb,
  generated_sql text,
  sql_validation_status varchar(100),
  sql_execution_status varchar(100),
  row_count int,
  result_preview jsonb,
  models_used jsonb,
  tables_used jsonb,
  columns_used jsonb,
  key_data_points jsonb,
  business_data_limitations jsonb,
  context_limitations jsonb,
  model_limitations jsonb,
  technical_warnings jsonb,
  provider_used varchar(100),
  model_used varchar(200),
  fallback_used boolean,
  gemini_available boolean,
  gemini_quota_exhausted boolean,
  final_answer text,
  business_insight text,
  recommendations jsonb,
  confidence_score numeric,
  latency_ms int,
  error_message text,
  created_at timestamp with time zone not null default now()
);

create index if not exists idx_insight_test_snapshots_run on public.insight_test_snapshots(test_run_id);
create index if not exists idx_insight_test_snapshots_role on public.insight_test_snapshots(role);
create index if not exists idx_insight_test_snapshots_created on public.insight_test_snapshots(created_at desc);

alter table public.insight_test_snapshots add column if not exists key_data_points jsonb;
alter table public.insight_test_snapshots add column if not exists business_data_limitations jsonb;
alter table public.insight_test_snapshots add column if not exists context_limitations jsonb;
alter table public.insight_test_snapshots add column if not exists model_limitations jsonb;
alter table public.insight_test_snapshots add column if not exists technical_warnings jsonb;
alter table public.insight_test_snapshots add column if not exists provider_used varchar(100);
alter table public.insight_test_snapshots add column if not exists model_used varchar(200);
alter table public.insight_test_snapshots add column if not exists fallback_used boolean;
alter table public.insight_test_snapshots add column if not exists gemini_available boolean;
alter table public.insight_test_snapshots add column if not exists gemini_quota_exhausted boolean;
alter table public.insight_test_snapshots add column if not exists final_answer text;
alter table public.insight_test_snapshots add column if not exists answer_status varchar(100);
alter table public.insight_test_snapshots add column if not exists strict_sql_validation jsonb;
alter table public.insight_test_snapshots add column if not exists sql_repair jsonb;
alter table public.insight_test_snapshots add column if not exists result_validation jsonb;
alter table public.insight_test_snapshots add column if not exists actual_tables_allowed jsonb;
alter table public.insight_test_snapshots add column if not exists actual_columns_allowed jsonb;

create table if not exists public.cld_ai_insight_run_log (
  insight_run_id uuid primary key default gen_random_uuid(),
  role text,
  question text not null,
  intent text,
  retrieved_context jsonb,
  actual_tables_allowed jsonb,
  actual_columns_allowed jsonb,
  generated_sql text,
  sql_validation_status text,
  sql_validation_errors jsonb,
  sql_repair_attempted boolean,
  repaired_sql text,
  sql_execution_status text,
  row_count int,
  result_preview jsonb,
  result_validation_status text,
  result_validation_output jsonb,
  final_answer jsonb,
  answer_status text,
  business_data_limitations jsonb,
  context_limitations jsonb,
  model_limitations jsonb,
  technical_warnings jsonb,
  provider_used text,
  model_used text,
  fallback_used boolean,
  latency_ms int,
  created_at timestamp with time zone not null default now()
);

create index if not exists idx_cld_ai_insight_run_log_created
  on public.cld_ai_insight_run_log(created_at desc);
"""


def ensure_snapshot_table() -> None:
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(INSIGHT_SNAPSHOT_DDL)
        conn.commit()


def save_insight_snapshot(
    *,
    question: str,
    role: str | None,
    response: Any | None,
    test_run_id: UUID | str | None = None,
    error_message: str | None = None,
) -> UUID:
    ensure_snapshot_table()
    payload = to_dict(response) if response is not None else {}
    snapshot_id = uuid4()
    run_id = UUID(str(test_run_id)) if test_run_id else uuid4()
    validation = payload.get("validation") or {}
    execution = payload.get("execution") or {}
    insight = payload.get("business_insight") or {}
    explainability = payload.get("explainability") or {}
    sql_metadata = payload.get("sql_metadata") or {}
    strict_sql_validation = payload.get("strict_sql_validation") or {}
    sql_repair = payload.get("sql_repair") or {}
    result_validation = payload.get("result_validation") or {}
    provider = payload.get("provider") or {}
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                insert into public.insight_test_snapshots (
                  snapshot_id, test_run_id, role, question, intent, retrieved_context,
                  generated_sql, sql_validation_status, sql_execution_status, row_count,
                  result_preview, models_used, tables_used, columns_used, business_insight,
                  recommendations, confidence_score, latency_ms, error_message,
                  provider_used, model_used, fallback_used, final_answer, answer_status,
                  strict_sql_validation, sql_repair, result_validation, actual_tables_allowed,
                  actual_columns_allowed, created_at
                )
                values (
                  %(snapshot_id)s, %(test_run_id)s, %(role)s, %(question)s, %(intent)s, %(retrieved_context)s,
                  %(generated_sql)s, %(sql_validation_status)s, %(sql_execution_status)s, %(row_count)s,
                  %(result_preview)s::jsonb, %(models_used)s::jsonb, %(tables_used)s::jsonb, %(columns_used)s::jsonb,
                  %(business_insight)s, %(recommendations)s::jsonb, %(confidence_score)s, %(latency_ms)s,
                  %(error_message)s, %(provider_used)s, %(model_used)s, %(fallback_used)s,
                  %(final_answer)s, %(answer_status)s, %(strict_sql_validation)s::jsonb,
                  %(sql_repair)s::jsonb, %(result_validation)s::jsonb,
                  %(actual_tables_allowed)s::jsonb, %(actual_columns_allowed)s::jsonb,
                  %(created_at)s
                )
                """,
                {
                    "snapshot_id": snapshot_id,
                    "test_run_id": run_id,
                    "role": role or payload.get("role_code"),
                    "question": question,
                    "intent": str(payload.get("intent") or ""),
                    "retrieved_context": Jsonb(json_ready(payload.get("retrieved_context"))),
                    "generated_sql": payload.get("sql"),
                    "sql_validation_status": validation.get("safety_decision") or sql_metadata.get("validation_status"),
                    "sql_execution_status": execution.get("execution_status") or sql_metadata.get("execution_status"),
                    "row_count": execution.get("row_count") or sql_metadata.get("row_count") or 0,
                    "result_preview": Jsonb(json_ready((execution.get("rows") or [])[:10])),
                    "models_used": Jsonb(json_ready(sql_metadata.get("models_used") or explainability.get("ml_models_used") or [])),
                    "tables_used": Jsonb(json_ready(sql_metadata.get("tables_used") or explainability.get("source_tables") or [])),
                    "columns_used": Jsonb(json_ready(sql_metadata.get("columns_used") or explainability.get("source_columns") or {})),
                    "business_insight": insight.get("summary"),
                    "recommendations": Jsonb(json_ready(payload.get("recommendations") or [])),
                    "confidence_score": payload.get("confidence_score"),
                    "latency_ms": (payload.get("timings") or {}).get("total_latency_ms"),
                    "error_message": error_message or execution.get("error_message"),
                    "provider_used": provider.get("provider_used"),
                    "model_used": provider.get("model_used"),
                    "fallback_used": provider.get("fallback_used"),
                    "final_answer": insight.get("summary"),
                    "answer_status": payload.get("answer_status"),
                    "strict_sql_validation": Jsonb(json_ready(strict_sql_validation)),
                    "sql_repair": Jsonb(json_ready(sql_repair)),
                    "result_validation": Jsonb(json_ready(result_validation)),
                    "actual_tables_allowed": Jsonb(json_ready(payload.get("actual_tables_allowed") or [])),
                    "actual_columns_allowed": Jsonb(json_ready(payload.get("actual_columns_allowed") or [])),
                    "created_at": datetime.now(timezone.utc),
                },
            )
            cur.execute(
                """
                insert into public.cld_ai_insight_run_log (
                  insight_run_id, role, question, intent, retrieved_context,
                  actual_tables_allowed, actual_columns_allowed, generated_sql,
                  sql_validation_status, sql_validation_errors, sql_repair_attempted,
                  repaired_sql, sql_execution_status, row_count, result_preview,
                  result_validation_status, result_validation_output, final_answer,
                  answer_status, business_data_limitations, context_limitations,
                  model_limitations, technical_warnings, provider_used, model_used,
                  fallback_used, latency_ms, created_at
                ) values (
                  %(insight_run_id)s, %(role)s, %(question)s, %(intent)s, %(retrieved_context)s::jsonb,
                  %(actual_tables_allowed)s::jsonb, %(actual_columns_allowed)s::jsonb, %(generated_sql)s,
                  %(sql_validation_status)s, %(sql_validation_errors)s::jsonb, %(sql_repair_attempted)s,
                  %(repaired_sql)s, %(sql_execution_status)s, %(row_count)s, %(result_preview)s::jsonb,
                  %(result_validation_status)s, %(result_validation_output)s::jsonb, %(final_answer)s::jsonb,
                  %(answer_status)s, %(business_data_limitations)s::jsonb, %(context_limitations)s::jsonb,
                  %(model_limitations)s::jsonb, %(technical_warnings)s::jsonb, %(provider_used)s, %(model_used)s,
                  %(fallback_used)s, %(latency_ms)s, %(created_at)s
                )
                """,
                {
                    "insight_run_id": uuid4(),
                    "role": role or payload.get("role_code"),
                    "question": question,
                    "intent": str(payload.get("intent") or ""),
                    "retrieved_context": Jsonb(json_ready(payload.get("retrieved_context"))),
                    "actual_tables_allowed": Jsonb(json_ready(payload.get("actual_tables_allowed") or [])),
                    "actual_columns_allowed": Jsonb(json_ready(payload.get("actual_columns_allowed") or [])),
                    "generated_sql": payload.get("sql"),
                    "sql_validation_status": strict_sql_validation.get("validation_status")
                    or validation.get("safety_decision")
                    or sql_metadata.get("validation_status"),
                    "sql_validation_errors": Jsonb(json_ready(strict_sql_validation.get("errors") or [])),
                    "sql_repair_attempted": bool(sql_repair),
                    "repaired_sql": sql_repair.get("sql"),
                    "sql_execution_status": execution.get("execution_status") or sql_metadata.get("execution_status"),
                    "row_count": execution.get("row_count") or sql_metadata.get("row_count") or 0,
                    "result_preview": Jsonb(json_ready((execution.get("rows") or [])[:10])),
                    "result_validation_status": result_validation.get("validation_status") or result_validation.get("answer_status"),
                    "result_validation_output": Jsonb(json_ready(result_validation)),
                    "final_answer": Jsonb({"summary": insight.get("summary"), "recommendations": payload.get("recommendations") or []}),
                    "answer_status": payload.get("answer_status"),
                    "business_data_limitations": Jsonb(json_ready(insight.get("caveats") or [])),
                    "context_limitations": Jsonb(json_ready(result_validation.get("limitations") or [])),
                    "model_limitations": Jsonb([]),
                    "technical_warnings": Jsonb(json_ready(execution.get("error_message") and [execution.get("error_message")] or [])),
                    "provider_used": provider.get("provider_used"),
                    "model_used": provider.get("model_used"),
                    "fallback_used": provider.get("fallback_used"),
                    "latency_ms": (payload.get("timings") or {}).get("total_latency_ms"),
                    "created_at": datetime.now(timezone.utc),
                },
            )
        conn.commit()
    return snapshot_id


def save_ai_insight_snapshot(response: Any, test_run_id: UUID | str | None = None) -> UUID:
    ensure_snapshot_table()
    payload = to_dict(response)
    snapshot_id = uuid4()
    run_id = UUID(str(test_run_id)) if test_run_id else uuid4()
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                insert into public.insight_test_snapshots (
                  snapshot_id, test_run_id, role, question, intent, retrieved_context,
                  generated_sql, sql_validation_status, sql_execution_status, row_count,
                  result_preview, models_used, tables_used, columns_used, key_data_points,
                  business_data_limitations, context_limitations, model_limitations, technical_warnings,
                  provider_used, model_used, fallback_used, gemini_available, gemini_quota_exhausted,
                  final_answer, business_insight, recommendations, confidence_score, latency_ms,
                  error_message, created_at
                )
                values (
                  %(snapshot_id)s, %(test_run_id)s, %(role)s, %(question)s, %(intent)s, %(retrieved_context)s::jsonb,
                  %(generated_sql)s, %(sql_validation_status)s, %(sql_execution_status)s, %(row_count)s,
                  %(result_preview)s::jsonb, %(models_used)s::jsonb, %(tables_used)s::jsonb, %(columns_used)s::jsonb, %(key_data_points)s::jsonb,
                  %(business_data_limitations)s::jsonb, %(context_limitations)s::jsonb, %(model_limitations)s::jsonb, %(technical_warnings)s::jsonb,
                  %(provider_used)s, %(model_used)s, %(fallback_used)s, %(gemini_available)s, %(gemini_quota_exhausted)s,
                  %(final_answer)s::jsonb, %(business_insight)s, %(recommendations)s::jsonb, %(confidence_score)s, %(latency_ms)s,
                  %(error_message)s, %(created_at)s
                )
                """,
                {
                    "snapshot_id": snapshot_id,
                    "test_run_id": run_id,
                    "role": payload.get("role"),
                    "question": payload.get("question"),
                    "intent": payload.get("intent") or "",
                    "retrieved_context": Jsonb(json_ready(payload.get("related_context") or [])),
                    "generated_sql": payload.get("generated_sql"),
                    "sql_validation_status": payload.get("sql_validation_status"),
                    "sql_execution_status": payload.get("sql_execution_status"),
                    "row_count": payload.get("row_count") or 0,
                    "result_preview": Jsonb(json_ready(payload.get("result_preview") or [])),
                    "models_used": Jsonb(json_ready(payload.get("models_used") or [])),
                    "tables_used": Jsonb(json_ready(payload.get("related_tables") or [])),
                    "columns_used": Jsonb(json_ready(payload.get("related_columns") or [])),
                    "key_data_points": Jsonb(json_ready(payload.get("key_data_points") or [])),
                    "business_data_limitations": Jsonb(json_ready(payload.get("business_data_limitations") or [])),
                    "context_limitations": Jsonb(json_ready(payload.get("context_limitations") or [])),
                    "model_limitations": Jsonb(json_ready(payload.get("model_limitations") or [])),
                    "technical_warnings": Jsonb(json_ready(payload.get("technical_warnings") or [])),
                    "provider_used": payload.get("provider_used"),
                    "model_used": payload.get("model_used"),
                    "fallback_used": payload.get("fallback_used"),
                    "gemini_available": payload.get("gemini_available"),
                    "gemini_quota_exhausted": payload.get("gemini_quota_exhausted"),
                    "final_answer": Jsonb({"answer_summary": payload.get("answer_summary")}),
                    "business_insight": payload.get("answer_summary"),
                    "recommendations": Jsonb(json_ready(payload.get("recommendations") or [])),
                    "confidence_score": payload.get("confidence_score"),
                    "latency_ms": payload.get("latency_ms"),
                    "error_message": None,
                    "created_at": datetime.now(timezone.utc),
                },
            )
        conn.commit()
    return snapshot_id


def fetch_latest_insight_evidence(insight_id: str | UUID | None = None) -> dict[str, Any]:
    ensure_snapshot_table()
    with connect() as conn:
        with conn.cursor() as cur:
            if insight_id:
                cur.execute("select * from public.insight_test_snapshots where snapshot_id = %s", (str(insight_id),))
            else:
                cur.execute("select * from public.insight_test_snapshots order by created_at desc limit 1")
            row = cur.fetchone()
            cur.execute(
                """
                select snapshot_id, role, question, provider_used, model_used, fallback_used,
                       sql_validation_status, confidence_score, created_at
                from public.insight_test_snapshots
                order by created_at desc
                limit 10
                """
            )
            recent = cur.fetchall()
    if not row:
        return {"insight_id": None, "recent_insight_runs": [json_ready(dict(item)) for item in recent]}
    payload = json_ready(dict(row))
    tables = payload.get("tables_used") or []
    columns = payload.get("columns_used") or []
    models = payload.get("models_used") or []
    facts = payload.get("key_data_points") or []
    return {
        "insight_id": payload.get("snapshot_id"),
        "role": payload.get("role"),
        "question": payload.get("question"),
        "timestamp": payload.get("created_at"),
        "recent_insight_runs": [json_ready(dict(item)) for item in recent],
        "related_tables": [table_evidence(table, payload.get("question")) for table in tables],
        "related_columns": columns,
        "semantic_context": payload.get("retrieved_context") or [],
        "data_lineage": build_lineage(payload),
        "underlying_models": models,
        "sql_evidence": {
            "generated_sql": payload.get("generated_sql"),
            "validation_status": payload.get("sql_validation_status"),
            "strict_sql_validation": payload.get("strict_sql_validation") or {},
            "sql_repair": payload.get("sql_repair") or {},
            "execution_status": payload.get("sql_execution_status"),
            "execution_time": payload.get("latency_ms"),
            "row_count": payload.get("row_count"),
            "tables_used": payload.get("actual_tables_allowed") or tables,
            "columns_used": payload.get("actual_columns_allowed") or columns,
            "metrics_used": [fact.get("metric") for fact in facts if isinstance(fact, dict)],
        },
        "result_validation": payload.get("result_validation") or {},
        "answer_status": payload.get("answer_status"),
        "related_facts": facts,
        "limitations": {
            "business_data_limitations": payload.get("business_data_limitations") or [],
            "context_limitations": payload.get("context_limitations") or [],
            "model_limitations": payload.get("model_limitations") or [],
            "technical_warnings": payload.get("technical_warnings") or [],
        },
        "technical_diagnostics": {
            "provider_used": payload.get("provider_used"),
            "model_used": payload.get("model_used"),
            "gemini_available": payload.get("gemini_available"),
            "gemini_quota_exhausted": payload.get("gemini_quota_exhausted"),
            "fallback_used": payload.get("fallback_used"),
            "latency_ms": payload.get("latency_ms"),
            "technical_warnings": payload.get("technical_warnings") or [],
        },
        "final_answer": final_answer_text(payload),
        "recommendations": payload.get("recommendations") or [],
        "confidence_score": payload.get("confidence_score"),
    }


def table_evidence(table: str, question: str | None) -> dict[str, Any]:
    table_name = str(table).split(".")[-1]
    subject = table_name.split("_")[0].title()
    return {
        "schema_name": "public" if "." not in str(table) else str(table).split(".")[0],
        "table_name": table_name,
        "subject_area": subject,
        "business_description": f"{table_name.replace('_', ' ').title()} source data used for the insight.",
        "why_it_was_used": f"Referenced by generated SQL for: {question or 'latest insight'}.",
        "row_count": None,
    }


def build_lineage(payload: dict[str, Any]) -> list[dict[str, str]]:
    model_names = []
    for model in payload.get("models_used") or []:
        if isinstance(model, dict):
            model_names.append(str(model.get("model_name") or ""))
        elif model:
            model_names.append(str(model))
    return [
        {"step": "source data", "detail": ", ".join(payload.get("tables_used") or []) or "No source table captured"},
        {"step": "feature / aggregation layer", "detail": "Generated SQL projection, joins, filters, groups, and aggregates"},
        {"step": "model score if used", "detail": ", ".join([item for item in model_names if item]) or "No model score required"},
        {"step": "generated SQL", "detail": payload.get("sql_validation_status") or "not validated"},
        {"step": "result preview", "detail": f"{payload.get('row_count') or 0} rows returned"},
        {"step": "final insight", "detail": final_answer_text(payload)},
        {"step": "recommendation", "detail": f"{len(payload.get('recommendations') or [])} recommendation(s) generated"},
    ]


def final_answer_text(payload: dict[str, Any]) -> str:
    final_answer = payload.get("final_answer")
    if isinstance(final_answer, dict):
        return str(final_answer.get("answer_summary") or final_answer.get("summary") or "")
    if final_answer:
        return str(final_answer)
    return str(payload.get("business_insight") or "")


def to_dict(response: Any) -> dict[str, Any]:
    if response is None:
        return {}
    if isinstance(response, dict):
        return response
    if hasattr(response, "model_dump"):
        return response.model_dump(mode="json")
    return {}
