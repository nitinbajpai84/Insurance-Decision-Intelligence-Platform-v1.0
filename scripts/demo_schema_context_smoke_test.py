#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from governance_audit_utils import GOVERNANCE_DIR, connect, ensure_doc_dirs
from copilot_sql_engine.engine import run_sql_engine
from copilot_sql_engine.prompts import SQL_SYSTEM_PROMPT
from copilot_sql_engine.models import SqlEngineRequest
from copilot_sql_engine.settings import load_sql_engine_settings
from sql_validation_service import validate_sql_strict


REPORT_DIR = ROOT / "docs" / "demo"
RESULTS_PATH = REPORT_DIR / "demo_schema_context_smoke_test_results.json"
REPORT_PATH = REPORT_DIR / "demo_schema_context_smoke_test_report.md"


DEMO_QUESTIONS = [
    ("Agency Manager", "Which agents have the highest premium at risk?"),
    ("Campaign Manager", "Which campaigns generated the highest policy conversion?"),
    ("Insurance Agent", "Which customers are likely to lapse in the next 90 days?"),
    ("Sales Director", "Which products are declining in new sales?"),
    ("Insurance Agent", "Which customers should agents contact this week?"),
    ("Executive Leadership", "What are the top risks to revenue this month?"),
    ("Campaign Manager", "Show campaign conversion rate by channel."),
    ("Insurance Agent", "Show SQL for lapse risk by product."),
]


def query_scalar(conn, sql: str, params: tuple[Any, ...] = ()) -> int:
    with conn.cursor() as cur:
        cur.execute(sql, params)
        row = cur.fetchone()
        if row is None:
            return 0
        if isinstance(row, dict):
            return int(next(iter(row.values())))
        return int(row[0])


def fetch_table_allowlist(conn) -> set[str]:
    with conn.cursor() as cur:
        cur.execute(
            """
            select schema_name || '.' || table_name as full_table_name
            from public.cld_table_registry
            where ai_sql_allowed = true
            order by schema_name, table_name
            """
        )
        rows = cur.fetchall()
        if rows and isinstance(rows[0], dict):
            return {str(row["full_table_name"]) for row in rows}
        return {str(row[0]) for row in rows}


def fetch_trun_tables(conn) -> set[str]:
    with conn.cursor() as cur:
        cur.execute(
            """
            select schema_name || '.' || table_name as full_table_name
            from public.cld_table_registry
            where classification_label like 'TRUN_%'
            """
        )
        rows = cur.fetchall()
        if rows and isinstance(rows[0], dict):
            return {str(row["full_table_name"]) for row in rows}
        return {str(row[0]) for row in rows}


def fetch_non_act_context_tables(conn, allowlist: set[str]) -> list[dict[str, Any]]:
    with conn.cursor() as cur:
        cur.execute(
            """
            select context_id::text, title, context_type, related_tables
            from public.cld_context_registry
            where sql_usable = true
            """
        )
        rows = [dict(row) for row in cur.fetchall()]
    invalid: list[dict[str, Any]] = []
    for row in rows:
        tables = [str(value) for value in (row.get("related_tables") or [])]
        if any(table not in allowlist for table in tables if table):
            invalid.append(row)
    return invalid


def fetch_invalid_kpis(conn) -> list[dict[str, Any]]:
    allowlist = fetch_table_allowlist(conn)
    with conn.cursor() as cur:
        cur.execute("select kpi_name, authoritative_tables from public.cld_kpi_registry")
        rows = [dict(row) for row in cur.fetchall()]
    invalid: list[dict[str, Any]] = []
    for row in rows:
        tables = [str(value) for value in (row.get("authoritative_tables") or [])]
        if any(table not in allowlist for table in tables if table):
            invalid.append(row)
    return invalid


def fetch_invalid_models(conn) -> list[dict[str, Any]]:
    allowlist = fetch_table_allowlist(conn)
    with conn.cursor() as cur:
        cur.execute("select model_name, score_table, registry_status, required_source_tables from public.cld_model_registry where ai_sql_allowed = true")
        rows = [dict(row) for row in cur.fetchall()]
    invalid: list[dict[str, Any]] = []
    for row in rows:
        score_table = str(row.get("score_table") or "")
        required = [str(value) for value in (row.get("required_source_tables") or [])]
        if score_table not in allowlist or any(table not in allowlist for table in required if table):
            invalid.append(row)
    return invalid


def run_demo_questions() -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for role, question in DEMO_QUESTIONS:
        response = run_sql_engine(
            SqlEngineRequest(
                question=question,
                role_code=role,
                include_context=True,
                include_debug=True,
                row_limit=25,
                execute_sql=False,
            )
        )
        strict = response.strict_sql_validation or {}
        result = {
            "role": role,
            "question": question,
            "answer_status": response.answer_status,
            "sql": response.sql or "",
            "sql_validation_status": strict.get("validation_status"),
            "missing_tables": strict.get("missing_tables") or [],
            "missing_columns": strict.get("missing_columns") or [],
            "confidence_score": response.confidence_score,
            "provider": response.provider,
            "demo_safe": bool(response.sql) and "TRUN_" not in (response.sql or "").upper(),
        }
        result["passed"] = (
            result["answer_status"] in {"SUPPORTED", "PARTIAL", "NOT_SUPPORTED"}
            and result["demo_safe"]
            and result["sql_validation_status"] not in {"SQL_VALIDATION_FAILED", "SQL_PARSE_FAILED"}
        )
        results.append(result)
    return results


def write_report(results: list[dict[str, Any]], summary: dict[str, Any]) -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS_PATH.write_text(
        json.dumps(
            {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "summary": summary,
                "results": results,
            },
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    lines = [
        "# Demo Schema/Context Smoke Test Report",
        "",
        f"- Generated at: {datetime.now(timezone.utc).isoformat()}",
        f"- Table registry status: {'present' if summary['table_registry_exists'] else 'missing'}",
        f"- KPI registry status: {'present' if summary['kpi_registry_exists'] else 'missing'}",
        f"- Model registry status: {'present' if summary['model_registry_exists'] else 'missing'}",
        f"- Context registry status: {'present' if summary['context_registry_exists'] else 'missing'}",
        f"- ACT allowlisted tables: {summary['allowed_table_count']}",
        f"- TRUN tables: {summary['trun_table_count']}",
        "",
        "## Registry Checks",
        "",
        "| Check | Status | Details |",
        "|---|---|---|",
    ]
    for check in summary["checks"]:
        lines.append(f"| {check['name']} | {check['status']} | {check['details']} |")
    lines.extend(
        [
            "",
            "## Demo Questions",
            "",
            "| Role | Question | Passed | Validation | Answer Status |",
            "|---|---|---|---|---|",
        ]
    )
    for result in results:
        lines.append(
            f"| {result['role']} | {result['question']} | {'YES' if result['passed'] else 'NO'} | {result['sql_validation_status']} | {result['answer_status']} |"
        )
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke test the governance layer and demo-safe text-to-SQL path.")
    parser.add_argument("--env-file", default=".env")
    args = parser.parse_args()

    settings = load_sql_engine_settings(args.env_file)
    ensure_doc_dirs()

    with connect(settings.database_url) as conn:
        table_registry_exists = query_scalar(
            conn,
            """
            select count(*) > 0
            from information_schema.tables
            where table_schema = 'public' and table_name = 'cld_table_registry'
            """,
        ) > 0
        kpi_registry_exists = query_scalar(
            conn,
            """
            select count(*) > 0
            from information_schema.tables
            where table_schema = 'public' and table_name = 'cld_kpi_registry'
            """,
        ) > 0
        model_registry_exists = query_scalar(
            conn,
            """
            select count(*) > 0
            from information_schema.tables
            where table_schema = 'public' and table_name = 'cld_model_registry'
            """,
        ) > 0
        context_registry_exists = query_scalar(
            conn,
            """
            select count(*) > 0
            from information_schema.tables
            where table_schema = 'public' and table_name = 'cld_context_registry'
            """,
        ) > 0

        allowed_tables = fetch_table_allowlist(conn) if table_registry_exists else set()
        trun_tables = fetch_trun_tables(conn) if table_registry_exists else set()
        invalid_context = fetch_non_act_context_tables(conn, allowed_tables) if context_registry_exists else []
        invalid_kpis = fetch_invalid_kpis(conn) if kpi_registry_exists else []
        invalid_models = fetch_invalid_models(conn) if model_registry_exists else []

    prompt_ok = "ai_sql_allowed" in SQL_SYSTEM_PROMPT and "cld_table_registry" in SQL_SYSTEM_PROMPT and "cld_kpi_registry" in SQL_SYSTEM_PROMPT
    fake_sql_result = None
    with connect(settings.database_url) as conn:
        fake_sql_result = validate_sql_strict(
            conn,
            sql="select * from public.this_table_does_not_exist limit 5",
            allowed_schemas=settings.allowed_schemas,
            allowed_tables=allowed_tables or None,
            row_limit=25,
            statement_timeout_ms=settings.statement_timeout_ms,
        )

    demo_results = run_demo_questions()
    checks = [
        {
            "name": "table_registry_exists",
            "status": "PASS" if table_registry_exists else "FAIL",
            "details": "cld_table_registry is available" if table_registry_exists else "cld_table_registry is missing",
        },
        {
            "name": "kpi_registry_exists",
            "status": "PASS" if kpi_registry_exists else "FAIL",
            "details": "cld_kpi_registry is available" if kpi_registry_exists else "cld_kpi_registry is missing",
        },
        {
            "name": "model_registry_exists",
            "status": "PASS" if model_registry_exists else "FAIL",
            "details": "cld_model_registry is available" if model_registry_exists else "cld_model_registry is missing",
        },
        {
            "name": "context_registry_exists",
            "status": "PASS" if context_registry_exists else "FAIL",
            "details": "cld_context_registry is available" if context_registry_exists else "cld_context_registry is missing",
        },
        {
            "name": "prompt_guardrails_present",
            "status": "PASS" if prompt_ok else "FAIL",
            "details": "SQL_SYSTEM_PROMPT contains allowlist guardrails" if prompt_ok else "SQL_SYSTEM_PROMPT missing guardrail text",
        },
        {
            "name": "fake_table_validation",
            "status": "PASS" if not fake_sql_result.is_valid and "does_not_exist" in " ".join(fake_sql_result.errors).lower() else "FAIL",
            "details": "; ".join(fake_sql_result.errors) if fake_sql_result.errors else "Unexpected validation result",
        },
        {
            "name": "no_trun_tables_in_context",
            "status": "PASS" if not invalid_context else "FAIL",
            "details": "No SQL-usable context rows include TRUN tables" if not invalid_context else f"{len(invalid_context)} context rows reference non-ACT tables",
        },
        {
            "name": "kpis_use_act_tables",
            "status": "PASS" if not invalid_kpis else "FAIL",
            "details": "All KPI rows reference ACT tables" if not invalid_kpis else f"{len(invalid_kpis)} KPI rows reference non-ACT tables",
        },
        {
            "name": "models_use_act_tables",
            "status": "PASS" if not invalid_models else "FAIL",
            "details": "All model rows reference ACT tables" if not invalid_models else f"{len(invalid_models)} model rows are not ACT-aligned",
        },
        {
            "name": "allowlist_loaded",
            "status": "PASS" if allowed_tables else "FAIL",
            "details": f"{len(allowed_tables)} AI SQL allowlisted tables loaded",
        },
    ]
    summary = {
        "table_registry_exists": table_registry_exists,
        "kpi_registry_exists": kpi_registry_exists,
        "model_registry_exists": model_registry_exists,
        "context_registry_exists": context_registry_exists,
        "allowed_table_count": len(allowed_tables),
        "trun_table_count": len(trun_tables),
        "checks": checks,
        "demo_question_results": demo_results,
    }
    write_report(demo_results, summary)
    print(json.dumps(summary, indent=2, default=str))
    return 0 if all(check["status"] == "PASS" for check in checks) and all(result["passed"] for result in demo_results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
