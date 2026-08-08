"""Graph-grounded SQL agent (Prompt 18).

SQL is produced by REASONING over the graph + metric bindings FIRST, then
constrained to the sanctioned data surface. No free-guessed joins, and
off-contract SQL is never executed.

generate_grounded_sql(question, role):
  1. RETRIEVE  — binding_resolver.get_binding_for_question + graph context
  2. GUARD     — no binding => structured 'unsupported_question' (no SQL)
  3. PROMPT    — allowed surface ONLY (view/tables/columns/joins/filters/row_filter)
                 + reference formula_sql + subgraph triples + applicable rules
  4. GENERATE  — Gemini (non-streaming)
  5. VALIDATE  — binding_resolver.validate_sql_against_binding; auto-repair ONCE;
                 refuse if still off-contract
  6. EXECUTE   — (optional) reuse execution_agent, EXPLAIN-first read-only

This module does NOT modify the Prompt-6 sql_agent; it imports its helpers.
"""
from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from time import perf_counter
from typing import Any

import google.generativeai as genai

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend_v2.config import GEMINI_MODEL, require_api_key
from backend_v2.agents.models import ContextResult, ExecutionResult, SQLResult
from backend_v2.agents import execution_agent
from backend_v2.agents.sql_agent import parse_llm_json, _strip_fences  # reuse, do not modify
from graph import binding_resolver
from graph import graph_context_agent
from graph.db_util import robust_connect

DB_PATH = str(PROJECT_ROOT / "database" / "insurance_v2.duckdb")
GROUNDED_ROW_LIMIT = 100

genai.configure(api_key=require_api_key())


@dataclass
class GroundedSQLResult:
    question: str
    role: str
    sql: str = ""
    metrics_used: list[str] = field(default_factory=list)
    binding_ids: list[str] = field(default_factory=list)
    allowed_surface: dict[str, Any] = field(default_factory=dict)
    subgraph_triples: list[str] = field(default_factory=list)
    applicable_rules: list[dict[str, Any]] = field(default_factory=list)
    traversal_path: list[str] | None = None
    validation: dict[str, Any] = field(default_factory=lambda: {"ok": False, "violations": [], "repaired": False})
    row_count: int = 0
    explain_passed: bool = False
    execution_status: str = "not_executed"
    result_preview: list[dict[str, Any]] = field(default_factory=list)
    generation_time_ms: int = 0
    unsupported: bool = False
    suggested_metrics: list[str] = field(default_factory=list)
    note: str = ""

    def to_sql_result(self) -> SQLResult:
        status = "validated" if self.validation.get("ok") else ("unsupported" if self.unsupported else "blocked")
        return SQLResult(
            sql=self.sql,
            tables_used=self.allowed_surface.get("tables", [])[:12],
            columns_used=self.allowed_surface.get("columns", [])[:20],
            validation_status=status,
            validation_errors=self.validation.get("violations", []),
            repair_needed=not self.validation.get("ok"),
            generation_time_ms=self.generation_time_ms,
        )

    def to_evidence(self) -> dict[str, Any]:
        return {
            "metrics_used": self.metrics_used,
            "binding_ids": self.binding_ids,
            "canonical_views": self.allowed_surface.get("views", []),
            "allowed_tables": self.allowed_surface.get("tables", []),
            "subgraph_triples": self.subgraph_triples[:12],
            "applicable_rules": [r.get("name") for r in self.applicable_rules],
            "traversal_path": self.traversal_path,
            "validation": self.validation,
            "grounded": True,
        }


def _binding_ids(con, metric_ids: list[str]) -> list[str]:
    if not metric_ids:
        return []
    ph = ",".join("?" * len(metric_ids))
    rows = con.execute(f"select binding_id from metric_bindings where metric_id in ({ph})", metric_ids).fetchall()
    return [r[0] for r in rows]


def _primary_formula(surface: dict[str, Any]) -> str:
    for b in surface.get("bindings", []):
        if b.get("formula_sql"):
            return b["formula_sql"]
    return ""


def _build_prompt(question: str, role: str, surface: dict[str, Any], gctx, repair: dict | None = None) -> str:
    views = ", ".join(surface.get("views", [])) or "(none — use base tables)"
    tables = "\n".join(f"- {t}" for t in surface.get("tables", [])) or "- (none)"
    columns = "\n".join(f"- {c}" for c in surface.get("columns", [])) or "- (none)"
    joins = "\n".join(f"- {j}" for j in surface.get("joins", [])) or "- (none required)"
    filters = "\n".join(f"- {f}" for f in surface.get("filters", [])) or "- (none)"
    row_filter = surface.get("row_filter_for_role")
    formula = _primary_formula(surface)
    triples = "\n".join(f"- {t}" for t in (gctx.subgraph_summary or [])[:12]) or "- (none)"
    rules = "\n".join(f"- {r.get('name')}: {r.get('action_text')}" for r in (gctx.applicable_rules or [])[:5]) or "- (none)"

    repair_block = ""
    if repair:
        repair_block = (
            "\nYOUR PREVIOUS SQL VIOLATED THE CONTRACT. Fix these violations and "
            "return corrected SQL that uses ONLY the allowed surface:\n"
            + "\n".join(f"- {v}" for v in repair.get("violations", []))
            + f"\nPREVIOUS SQL:\n{repair.get('sql', '')}\n"
        )

    return f"""You are a senior insurance analytics engineer writing DuckDB SQL under a STRICT data contract.

QUESTION: {question}
ROLE: {role}

CANONICAL VIEW (prefer querying this directly): {views}

ALLOWED TABLES/VIEWS (use ONLY these):
{tables}

ALLOWED COLUMNS (use ONLY these; do not invent columns):
{columns}

SANCTIONED JOINS (only join along these paths):
{joins}

DEFAULT FILTERS (apply these unless the question overrides them):
{filters}

ROLE ROW FILTER (MUST be included verbatim in the WHERE clause if present): {row_filter or '(none)'}

REFERENCE FORMULA (the sanctioned way to compute the metric):
{formula or '(none)'}

GRAPH CONTEXT (entity/concept triples):
{triples}

APPLICABLE BUSINESS RULES:
{rules}
{repair_block}
RULES:
- One single read-only SELECT (or WITH ... SELECT). No INSERT/UPDATE/DELETE/DDL.
- Use ONLY the allowed tables/views and columns above.
- GRAIN: pick the allowed table/view whose grain matches the question. If the
  question asks for a breakdown BY an entity (agent / customer / product / region),
  use a granular allowed table/view that actually contains that key column
  (e.g. v_lapse_policy_risk has agent_id/line_of_business/region; agent_performance
  has agent_id) — do NOT GROUP BY a column that a pre-aggregated summary view
  (like v_lapse_risk_summary) does not contain. Use the canonical view only when
  the question is at that view's grain.
- DuckDB date functions: use year(date_col), date_trunc('month', date_col),
  current_date. Do NOT use strftime on a DATE.
- If a ROLE ROW FILTER is given, include it in the WHERE clause exactly.
- End with LIMIT {GROUNDED_ROW_LIMIT} (or lower). No trailing semicolon.

Return JSON only (no markdown fences): {{"sql": "..."}}"""


async def _generate(prompt: str) -> str:
    model = genai.GenerativeModel(GEMINI_MODEL)
    resp = await model.generate_content_async(prompt, generation_config={"temperature": 0.0})
    data = parse_llm_json(getattr(resp, "text", "") or "")
    return _strip_fences(str(data.get("sql", ""))).rstrip(";").strip()


def _enforce_limit(sql: str) -> str:
    if re.search(r"\blimit\s+\d+\s*$", sql, flags=re.IGNORECASE):
        return sql
    return f"{sql}\nLIMIT {GROUNDED_ROW_LIMIT}"


async def generate_grounded_sql(question: str, role: str = "Executive Leadership",
                                *, execute: bool = True) -> GroundedSQLResult:
    started = perf_counter()
    result = GroundedSQLResult(question=question, role=role)

    # 1. RETRIEVE (reason over bindings + graph)
    surface = binding_resolver.get_binding_for_question(question, role)
    try:
        gctx = await graph_context_agent.get_graph_context(question, role)
    except Exception as exc:  # graph context is best-effort
        gctx = graph_context_agent.GraphContext(errors=[f"{type(exc).__name__}: {exc}"])

    result.allowed_surface = surface
    result.metrics_used = surface.get("metric_ids", [])
    result.subgraph_triples = gctx.subgraph_summary or []
    result.applicable_rules = gctx.applicable_rules or []
    result.traversal_path = gctx.traversal_path

    # 2. GUARD — no sanctioned metric => unsupported (do NOT generate SQL)
    if not result.metrics_used:
        con = robust_connect(DB_PATH, read_only=True)
        try:
            suggestions = [r[0].split("::")[-1] for r in con.execute(
                "select metric_id from metric_bindings where status='active' order by metric_id limit 8").fetchall()]
        finally:
            con.close()
        result.unsupported = True
        result.suggested_metrics = suggestions
        result.note = ("No sanctioned metric matches this question, so no SQL was generated. "
                       "I only answer over governed metrics. Closest available metrics: "
                       + ", ".join(suggestions) + ".")
        result.generation_time_ms = int((perf_counter() - started) * 1000)
        return result

    con = robust_connect(DB_PATH, read_only=True)
    try:
        result.binding_ids = _binding_ids(con, result.metrics_used)
    finally:
        con.close()

    # 3-4. PROMPT + GENERATE
    try:
        sql = await _generate(_build_prompt(question, role, surface, gctx))
    except Exception as exc:
        result.validation = {"ok": False, "violations": [f"LLM generation failed: {type(exc).__name__}: {exc}"], "repaired": False}
        result.generation_time_ms = int((perf_counter() - started) * 1000)
        return result
    sql = _enforce_limit(sql)
    result.sql = sql

    # 5. VALIDATE (+ one repair)
    v = binding_resolver.validate_sql_against_binding(sql, surface)
    repaired = False
    if not v["ok"]:
        try:
            fixed = await _generate(_build_prompt(question, role, surface, gctx,
                                                  repair={"violations": v["violations"], "sql": sql}))
            fixed = _enforce_limit(fixed)
            v2 = binding_resolver.validate_sql_against_binding(fixed, surface)
            repaired = True
            if v2["ok"]:
                sql, v = fixed, v2
                result.sql = sql
            else:
                v = v2  # still violating
        except Exception as exc:
            v["violations"].append(f"repair failed: {type(exc).__name__}: {exc}")
    result.validation = {"ok": v["ok"], "violations": v["violations"], "repaired": repaired}
    result.generation_time_ms = int((perf_counter() - started) * 1000)

    # refuse to execute off-contract SQL
    if not v["ok"]:
        result.execution_status = "blocked_off_contract"
        return result

    # 6. EXECUTE (optional) — substitute role placeholder with a real agent for the demo
    if execute:
        exec_sql = _substitute_role_params(result.sql, role)
        ctx = _surface_to_context(surface)
        exec_res: ExecutionResult = await execution_agent.execute_and_validate(exec_sql, ctx)
        result.execution_status = exec_res.execution_status
        result.row_count = exec_res.row_count
        result.explain_passed = exec_res.explain_passed
        result.result_preview = exec_res.rows[:10]
    return result


def _substitute_role_params(sql: str, role: str) -> str:
    """Replace :current_agent with a concrete agent_id so role-scoped SQL runs in the demo."""
    if ":current_agent" not in sql:
        return sql
    con = robust_connect(DB_PATH, read_only=True)
    try:
        row = con.execute("select agent_id from agents limit 1").fetchone()
        agent = row[0] if row else "agt_0000"
    finally:
        con.close()
    return sql.replace(":current_agent", f"'{agent}'")


def _surface_to_context(surface: dict[str, Any]) -> ContextResult:
    """Minimal ContextResult so execution_agent's repair path has schema hints."""
    schema = []
    for c in surface.get("columns", []):
        if "." in c:
            t, col = c.split(".", 1)
            schema.append({"table": t, "column": col, "description": "", "score": 1.0})
    return ContextResult(schema_context=schema)


# compat shim used by the orchestrator (same call shape as sql_agent.generate_sql)
async def generate_sql(question: str, role: str, context: ContextResult) -> SQLResult:
    grounded = await generate_grounded_sql(question, role, execute=False)
    return grounded.to_sql_result()


if __name__ == "__main__":
    import asyncio

    async def _demo():
        for q, r in [("What is our current lapse rate?", "Executive Leadership"),
                     ("What is the average flight delay at Changi?", "Executive Leadership")]:
            g = await generate_grounded_sql(q, r)
            print(f"\nQ: {q}")
            print("  metrics:", g.metrics_used, "| unsupported:", g.unsupported)
            print("  sql:", (g.sql or g.note)[:160])
            print("  validation:", g.validation, "| exec:", g.execution_status, "rows:", g.row_count)
    asyncio.run(_demo())
