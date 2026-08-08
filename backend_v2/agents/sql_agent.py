"""
SQL agent — structured prompt -> Gemini (non-streaming) -> validated DuckDB SQL.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from time import perf_counter

import google.generativeai as genai

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend_v2.config import (
    GEMINI_MODEL,
    ROLE_PROMPTS,
    SQL_FORBIDDEN_KEYWORDS,
    SQL_ROW_LIMIT,
    require_api_key,
)
from backend_v2.agents.models import ContextResult, SQLResult

genai.configure(api_key=require_api_key())

DUCKDB_RULES = f"""DuckDB SQL rules:
- One single read-only statement starting with SELECT or WITH.
- DuckDB syntax: date_trunc, strftime, list/struct functions allowed; no Postgres-only extensions.
- Use explicit JOINs and nullif() for denominators.
- Always end with LIMIT {SQL_ROW_LIMIT} (or lower) for row-level output.
- Never use INSERT, UPDATE, DELETE, DROP, ALTER, CREATE, TRUNCATE, ATTACH, PRAGMA, SET, COPY, EXPORT.
- Use ONLY the tables and columns listed in SCHEMA_CONTEXT. Do not invent columns.
- No semicolon at the end.

Data value conventions (this database stores categorical values in lowercase snake_case):
- policies.policy_status: 'active', 'issued', 'renewed', 'lapsed', 'expired', 'cancelled'
- policy_lapse_events.lapse_stage: 'lapsed', 'grace_period', 'reinstated'
- claims.claim_status: 'open', 'approved', 'paid', 'denied'
- For other status/stage/type columns, compare with lower(column) = 'lowercase_value'.
- Lapse rate = lapsed policies / total policies (from policies.policy_status), unless the question asks about lapse events specifically."""


def build_prompt(question: str, role: str, context: ContextResult) -> str:
    """Structured prompt assembled from typed context — not a raw dump."""
    role_header = ROLE_PROMPTS.get(role, ROLE_PROMPTS["Data Analyst"])

    schema_lines: dict[str, list[str]] = {}
    for item in context.schema_context:
        schema_lines.setdefault(item["table"], []).append(str(item["column"]))
    schema_block = "\n".join(
        f"- {table}: {', '.join(columns)}" for table, columns in schema_lines.items()
    ) or "- (no schema context retrieved — use common insurance tables: policies, customers, agents, claims, campaigns, products)"

    glossary_block = "\n".join(
        f"- {g['term']}: {g['definition']}" for g in context.glossary_terms if g.get("term")
    ) or "- (none)"

    examples_block = "\n".join(
        f"- Q: {q['question']}\n  SQL: {q['sql']}"
        for q in context.similar_past_queries
        if q.get("sql")
    ) or "- (none)"

    return f"""You are a senior insurance analytics engineer generating DuckDB SQL.

ROLE_CONTEXT ({role}): {role_header}

QUESTION: {question}

SCHEMA_CONTEXT (only these tables/columns are allowed):
{schema_block}

GLOSSARY (domain definitions relevant to the question):
{glossary_block}

SIMILAR_PAST_QUERIES (style reference only):
{examples_block}

{DUCKDB_RULES}

Return JSON only, no markdown fences, with keys:
{{"sql": "...", "tables_used": ["..."], "columns_used": ["..."], "explanation": "..."}}"""


def _strip_fences(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```(?:json|sql)?", "", text, flags=re.IGNORECASE).strip()
    return re.sub(r"```$", "", text).strip()


def parse_llm_json(text: str) -> dict:
    cleaned = _strip_fences(text)
    try:
        value = json.loads(cleaned)
        return value if isinstance(value, dict) else {}
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
        if match:
            try:
                value = json.loads(match.group(0))
                return value if isinstance(value, dict) else {}
            except json.JSONDecodeError:
                return {}
    return {}


def validate_sql(sql: str) -> tuple[str, list[str]]:
    """Returns (status, errors). status: validated | blocked | empty."""
    errors: list[str] = []
    candidate = _strip_fences(sql).rstrip(";").strip()
    if not candidate:
        return "empty", ["LLM returned empty SQL"]
    head = candidate.lstrip("(").lstrip().lower()
    if not (head.startswith("select") or head.startswith("with")):
        errors.append("SQL must start with SELECT or WITH")
    lowered = re.sub(r"'[^']*'", "''", candidate.lower())  # ignore string literals
    for keyword in SQL_FORBIDDEN_KEYWORDS:
        if re.search(rf"\b{keyword}\b", lowered):
            errors.append(f"Forbidden keyword: {keyword.upper()}")
    if candidate.count(";") > 0:
        errors.append("Multiple statements are not allowed")
    return ("blocked", errors) if errors else ("validated", [])


def enforce_limit(sql: str) -> str:
    """Append/clamp LIMIT to SQL_ROW_LIMIT."""
    match = re.search(r"\blimit\s+(\d+)\s*$", sql, flags=re.IGNORECASE)
    if match:
        if int(match.group(1)) > SQL_ROW_LIMIT:
            return re.sub(r"\blimit\s+\d+\s*$", f"LIMIT {SQL_ROW_LIMIT}", sql, flags=re.IGNORECASE)
        return sql
    return f"{sql}\nLIMIT {SQL_ROW_LIMIT}"


async def generate_sql(question: str, role: str, context: ContextResult) -> SQLResult:
    started = perf_counter()
    result = SQLResult()
    prompt = build_prompt(question, role, context)
    try:
        model = genai.GenerativeModel(GEMINI_MODEL)
        # Streaming intentionally disabled for SQL generation — we need the
        # complete statement before validation.
        response = await model.generate_content_async(
            prompt,
            generation_config={"temperature": 0.0},
        )
        data = parse_llm_json(getattr(response, "text", "") or "")
    except Exception as exc:
        result.validation_status = "blocked"
        result.validation_errors = [f"LLM generation failed: {type(exc).__name__}: {exc}"]
        result.repair_needed = True
        result.generation_time_ms = int((perf_counter() - started) * 1000)
        return result

    sql = _strip_fences(str(data.get("sql", ""))).rstrip(";").strip()
    status, errors = validate_sql(sql)
    if status == "validated":
        sql = enforce_limit(sql)
    result.sql = sql
    result.tables_used = [str(t) for t in data.get("tables_used") or []]
    result.columns_used = [str(c) for c in data.get("columns_used") or []]
    result.validation_status = status
    result.validation_errors = errors
    result.repair_needed = status != "validated"
    result.generation_time_ms = int((perf_counter() - started) * 1000)
    return result
