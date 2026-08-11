"""
Insight agent — STREAMS the business answer from Gemini token by token.

generate_insight returns an InsightResult whose insight_stream is an async
generator; the orchestrator/SSE layer forwards tokens to the client as they
arrive. Metadata (key data points, recommended action, limitations) is
computed deterministically from the SQL result so it is available before the
stream finishes.
"""
from __future__ import annotations

import sys
from pathlib import Path
from time import perf_counter
from typing import Any, AsyncGenerator

import google.generativeai as genai

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend_v2.config import GEMINI_MODEL, ROLE_PROMPTS, require_api_key
from backend_v2.agents.models import ContextResult, ExecutionResult, InsightResult, SQLResult

genai.configure(api_key=require_api_key())

MAX_PROMPT_ROWS = 10


def _format_rows(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "(query returned 0 rows)"
    lines = []
    for row in rows[:MAX_PROMPT_ROWS]:
        lines.append(", ".join(f"{k}={v}" for k, v in row.items()))
    return "\n".join(lines)


def _format_rules(rules: list[dict[str, Any]] | None) -> str:
    """Governed decision_rules (thresholds, escalation actions) as a hard
    constraint block. Without this, the LLM invents its own cut-offs (e.g.
    "flagged agents below 70%") that no one in the business owns or can
    change — see docs/context-layer/DESIGN.md norms discussion."""
    if not rules:
        return "- (no governed rule matched this question — say so; do not invent a threshold)"
    lines = []
    for r in rules:
        thresholds = r.get("threshold_json") or {}
        th_text = ", ".join(f"{k} = {v}" for k, v in thresholds.items()) or "(no numeric threshold)"
        lines.append(
            f"- [{r.get('name')}] {th_text} -> {r.get('action_text')} "
            f"(owner: {r.get('assigned_role') or 'unassigned'}, rule_id: {r.get('rule_id')})"
        )
    return "\n".join(lines)


def build_prompt(
    question: str,
    role: str,
    context: ContextResult,
    sql_result: SQLResult,
    exec_result: ExecutionResult,
    applicable_rules: list[dict[str, Any]] | None = None,
) -> str:
    glossary_block = "\n".join(
        f"- {g['term']}: {g['definition']}" for g in context.glossary_terms if g.get("term")
    ) or "- (none)"
    rules_block = _format_rules(applicable_rules)
    return f"""You are answering for a {role} at a Singapore life & health insurer.
Role guidance: {ROLE_PROMPTS.get(role, ROLE_PROMPTS["Data Analyst"])}

QUESTION: {question}

SQL THAT WAS RUN:
{sql_result.sql}

KEY RESULT ROWS (max {MAX_PROMPT_ROWS} of {exec_result.row_count}):
{_format_rows(exec_result.rows)}

GLOSSARY DEFINITIONS USED:
{glossary_block}

GOVERNED THRESHOLDS AND ESCALATION RULES (business-owned, versioned in the context layer):
{rules_block}

INSTRUCTIONS:
- Answer in clear business language for the role above.
- Cite specific numbers from the result rows (amounts are SGD).
- If you reference a threshold, cut-off, or escalation trigger, you MUST use the exact
  value from GOVERNED THRESHOLDS above and name the rule it came from — never invent
  or approximate a threshold yourself. If no governed rule covers the question, say
  plainly that no threshold is currently governed for it, instead of guessing one.
- Flag any data limitations (zero rows, sampled rows, synthetic data).
- End with one clearly labelled "Recommended action:" line.
- Do not invent numbers that are not in the result rows or the governed thresholds."""


def extract_key_data_points(
    rows: list[dict[str, Any]], tables_used: list[str]
) -> list[dict[str, Any]]:
    """Deterministic key facts from the first rows — no LLM involved."""
    points: list[dict[str, Any]] = []
    source_table = tables_used[0] if tables_used else "query_result"
    for row in rows[:3]:
        for column, value in row.items():
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                points.append({
                    "label": column.replace("_", " "),
                    "value": value,
                    "source_table": source_table,
                    "source_column": column,
                })
        if len(points) >= 6:
            break
    return points[:6]


def derive_limitations(exec_result: ExecutionResult, context: ContextResult) -> str:
    notes = ["Synthetic PoC data — validate before production decisions."]
    if exec_result.suspicious_zero_rows:
        notes.append("Query returned 0 rows for the current filters; the answer may be incomplete.")
    if exec_result.repaired:
        notes.append("SQL required automatic repair before executing.")
    if context.errors:
        notes.append("Some context retrieval steps failed; answer uses partial context.")
    return " ".join(notes)


async def generate_insight(
    question: str,
    role: str,
    context: ContextResult,
    sql_result: SQLResult,
    exec_result: ExecutionResult,
    applicable_rules: list[dict[str, Any]] | None = None,
) -> InsightResult:
    started = perf_counter()
    result = InsightResult(
        key_data_points=extract_key_data_points(exec_result.rows, sql_result.tables_used),
        business_limitations=derive_limitations(exec_result, context),
        models_used=[GEMINI_MODEL, "gemini-embedding-001"],
    )
    # Confidence: execution success + rows + context coverage
    confidence = 0.35
    if exec_result.execution_status == "executed":
        confidence += 0.25
        if exec_result.row_count > 0:
            confidence += 0.15
    if context.schema_context:
        confidence += 0.15
    if not exec_result.repaired:
        confidence += 0.10
    result.confidence_score = round(min(1.0, confidence), 3)

    prompt = build_prompt(question, role, context, sql_result, exec_result, applicable_rules)

    async def stream_tokens() -> AsyncGenerator[str, None]:
        collected: list[str] = []
        try:
            model = genai.GenerativeModel(GEMINI_MODEL)
            response = await model.generate_content_async(
                prompt,
                generation_config={"temperature": 0.2},
                stream=True,  # token-by-token streaming
            )
            async for chunk in response:
                token = getattr(chunk, "text", "") or ""
                if token:
                    collected.append(token)
                    yield token
        except Exception as exc:
            fallback = (
                f"(Live LLM streaming unavailable: {type(exc).__name__}.) "
                f"The query executed with {exec_result.row_count} rows; "
                f"see key data points for the headline numbers."
            )
            collected.append(fallback)
            yield fallback
        finally:
            full_text = "".join(collected)
            for line in reversed(full_text.splitlines()):
                if "recommended action" in line.lower():
                    # Strip the label and any markdown emphasis (**, *) bleeding
                    # in from a "**Recommended action:**" heading.
                    action = line.split(":", 1)[-1]
                    result.recommended_action = action.strip().strip("*").strip()
                    break
            result.generation_time_ms = int((perf_counter() - started) * 1000)

    result.insight_stream = stream_tokens()
    return result
