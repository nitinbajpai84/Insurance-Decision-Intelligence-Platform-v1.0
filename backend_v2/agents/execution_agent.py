"""
Execution agent — EXPLAIN-first read-only execution against DuckDB with
one-shot Gemini auto-repair (mirrors V1's strict-validate + repair_sql_once).
"""
from __future__ import annotations

import sys
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from time import perf_counter
from typing import Any

import duckdb
import google.generativeai as genai

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend_v2.config import DUCKDB_CONFIG, DUCKDB_PATH, GEMINI_MODEL, SQL_ROW_LIMIT, require_api_key
from backend_v2.agents.models import ContextResult, ExecutionResult
from backend_v2.agents.sql_agent import enforce_limit, parse_llm_json, validate_sql

genai.configure(api_key=require_api_key())


def _json_safe(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def _run_sql(sql: str) -> tuple[list[dict[str, Any]], list[str], bool]:
    """EXPLAIN then execute on a read-only connection. Returns (rows, columns, explain_passed)."""
    conn = duckdb.connect(DUCKDB_PATH, read_only=True, config=DUCKDB_CONFIG)
    try:
        conn.execute(f"EXPLAIN {sql}")  # plan check mirrors V1's Supabase EXPLAIN gate
        explain_passed = True
        cursor = conn.execute(sql)
        columns = [d[0] for d in cursor.description or []]
        raw = cursor.fetchmany(SQL_ROW_LIMIT)
        rows = [{c: _json_safe(v) for c, v in zip(columns, r)} for r in raw]
        return rows, columns, explain_passed
    finally:
        conn.close()


async def _repair_sql(failed_sql: str, error: str, context: ContextResult) -> str | None:
    """One Gemini repair attempt with the execution error + schema context."""
    schema_lines: dict[str, list[str]] = {}
    for item in context.schema_context:
        schema_lines.setdefault(str(item.get("table")), []).append(str(item.get("column")))
    schema_block = "\n".join(f"- {t}: {', '.join(c)}" for t, c in schema_lines.items()) or "- (none)"
    prompt = f"""You are repairing DuckDB SQL for an insurance analytics app.
The SQL below failed. Fix it using ONLY tables/columns in ALLOWED_SCHEMA.
Return JSON only: {{"sql": "..."}} — single SELECT/WITH statement, no semicolon,
end with LIMIT {SQL_ROW_LIMIT}.

ERROR: {error}

FAILED_SQL:
{failed_sql}

ALLOWED_SCHEMA:
{schema_block}"""
    try:
        model = genai.GenerativeModel(GEMINI_MODEL)
        response = await model.generate_content_async(prompt, generation_config={"temperature": 0.0})
        data = parse_llm_json(getattr(response, "text", "") or "")
        sql = str(data.get("sql", "")).strip().rstrip(";")
        status, _ = validate_sql(sql)
        return enforce_limit(sql) if (sql and status == "validated") else None
    except Exception:
        return None


async def execute_and_validate(sql: str, context: ContextResult) -> ExecutionResult:
    started = perf_counter()
    result = ExecutionResult()

    status, errors = validate_sql(sql)
    if status != "validated":
        result.execution_status = "blocked"
        result.error_message = "; ".join(errors)
        result.execution_time_ms = int((perf_counter() - started) * 1000)
        return result

    import asyncio

    active_sql = enforce_limit(sql)
    try:
        rows, columns, explain_passed = await asyncio.to_thread(_run_sql, active_sql)
    except Exception as exc:
        # One auto-repair pass with the error fed back to Gemini
        repaired_sql = await _repair_sql(active_sql, f"{type(exc).__name__}: {exc}", context)
        if repaired_sql:
            try:
                rows, columns, explain_passed = await asyncio.to_thread(_run_sql, repaired_sql)
                result.repaired = True
                result.repair_sql = repaired_sql
            except Exception as exc2:
                result.execution_status = "failed"
                result.error_message = f"original: {exc}; repaired: {exc2}"
                result.execution_time_ms = int((perf_counter() - started) * 1000)
                return result
        else:
            result.execution_status = "failed"
            result.error_message = f"{type(exc).__name__}: {exc}"
            result.execution_time_ms = int((perf_counter() - started) * 1000)
            return result

    result.rows = rows
    result.columns = columns
    result.row_count = len(rows)
    result.explain_passed = explain_passed
    result.execution_status = "executed"
    # 0 rows = suspicious (V1 flags this as PARTIAL) — surfaced to the insight agent
    result.suspicious_zero_rows = result.row_count == 0
    # Column sanity: at least one column should look like a business field
    business_markers = ("premium", "count", "rate", "ratio", "amount", "score", "name",
                        "number", "id", "value", "total", "conversion", "lapse")
    if columns and not any(any(m in c.lower() for m in business_markers) for c in columns):
        result.suspicious_zero_rows = result.suspicious_zero_rows or False
        result.error_message = (result.error_message or "") + " Columns do not resemble expected business fields."
    result.execution_time_ms = int((perf_counter() - started) * 1000)
    return result
