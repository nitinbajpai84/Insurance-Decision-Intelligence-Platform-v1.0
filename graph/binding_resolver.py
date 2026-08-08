"""Binding resolver — map a question to metric bindings and enforce the contract.

  get_binding_for_question(question, role) -> merged "allowed surface"
  validate_sql_against_binding(sql, allowed_surface) -> {ok, violations}
  explain_binding(metric_id) -> human-readable contract (Evidence Hub)

The validator uses sqlglot to parse the SQL, then enforces:
  * read-only (no INSERT/UPDATE/DELETE/DDL)
  * every referenced table/view is in the allowed surface (CTEs excluded)
  * qualified columns resolve to an allowed fully-qualified column
  * any role row_filter required for a referenced table is present in the SQL
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

import sqlglot
from sqlglot import exp

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from graph.db_util import robust_connect

DB_PATH = str(PROJECT_ROOT / "database" / "insurance_v2.duckdb")
WRITE_NODES = (exp.Insert, exp.Update, exp.Delete, exp.Drop, exp.Create, exp.Alter, exp.Command)


# ---------------------------------------------------------------------------
# Retrieval: question -> metric_ids (vector + light graph expansion)
# ---------------------------------------------------------------------------
def _vector_metric_ids(question: str, con, k: int = 6) -> list[str]:
    bound = {r[0] for r in con.execute("select metric_id from metric_bindings where status='active'").fetchall()}
    hits: list[str] = []
    try:
        import lancedb
        from embeddings.vector_search import LANCEDB_PATH, embed_text
        vec = embed_text(question)
        tbl = lancedb.connect(LANCEDB_PATH).open_table("insurance_glossary_vectors")
        rows = tbl.search(vec).distance_type("cosine").limit(40).to_list()
        for r in rows:
            rid = r.get("record_id")
            if rid in bound and rid not in hits:
                hits.append(rid)
            if len(hits) >= k:
                break
    except Exception as exc:  # pragma: no cover
        print(f"[binding_resolver] vector recall unavailable: {type(exc).__name__}: {exc}", file=sys.stderr)
    # keyword fallback / augmentation
    ql = question.lower()
    for mid in bound:
        name = mid.split("::", 1)[-1].replace("_", " ")
        if name in ql and mid not in hits:
            hits.append(mid)
    # light graph expansion: metrics that share an edge with a matched metric
    if hits:
        ph = ",".join("?" * len(hits))
        try:
            nbr = con.execute(
                f"select distinct dst_node_id from graph_edges where src_node_id in ({ph}) and dst_node_id like 'metric::%' "
                f"union select distinct src_node_id from graph_edges where dst_node_id in ({ph}) and src_node_id like 'metric::%'",
                hits + hits).fetchall()
            for (m,) in nbr:
                if m in bound and m not in hits:
                    hits.append(m)
        except Exception:
            pass
    return hits[:k]


def _load_binding(con, metric_id: str) -> dict[str, Any] | None:
    r = con.execute(
        "select metric_id, canonical_view, allowed_tables, allowed_columns, required_joins, "
        "default_filters, grain, formula_sql, sample_question from metric_bindings where metric_id=?",
        [metric_id]).fetchone()
    if not r:
        return None
    return {
        "metric_id": r[0], "canonical_view": r[1],
        "allowed_tables": json.loads(r[2]) if r[2] else [],
        "allowed_columns": json.loads(r[3]) if r[3] else [],
        "required_joins": json.loads(r[4]) if r[4] else [],
        "default_filters": json.loads(r[5]) if r[5] else [],
        "grain": r[6], "formula_sql": r[7], "sample_question": r[8],
    }


def _role_row_filters(con, role: str, tables: list[str]) -> dict[str, str]:
    if not tables:
        return {}
    ph = ",".join("?" * len(tables))
    rows = con.execute(
        f"select table_name, row_filter from table_access_policy where role=? and table_name in ({ph}) "
        f"and row_filter is not null", [role] + tables).fetchall()
    return {t: f for t, f in rows}


def get_binding_for_question(question: str, role: str = "Executive Leadership") -> dict[str, Any]:
    con = robust_connect(DB_PATH, read_only=True)
    try:
        metric_ids = _vector_metric_ids(question, con)
        bindings = [b for b in (_load_binding(con, m) for m in metric_ids) if b]
        views, tables, columns, joins, filters = set(), set(), set(), set(), set()
        grain = None
        for b in bindings:
            if b["canonical_view"]:
                views.add(b["canonical_view"])
            tables.update(b["allowed_tables"])
            columns.update(b["allowed_columns"])
            joins.update(b["required_joins"])
            filters.update(b["default_filters"])
            grain = grain or b["grain"]
        row_filters = _role_row_filters(con, role, sorted(tables))
        return {
            "question": question, "role": role,
            "metric_ids": [b["metric_id"] for b in bindings],
            "views": sorted(views), "tables": sorted(tables), "columns": sorted(columns),
            "joins": sorted(joins), "filters": sorted(filters), "grain": grain,
            "row_filters": row_filters,
            "row_filter_for_role": next(iter(row_filters.values()), None),
            "bindings": bindings,
        }
    finally:
        con.close()


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------
def _alias_to_table(parsed: exp.Expression) -> dict[str, str]:
    """Map every table alias (and bare name) to its real table name."""
    m: dict[str, str] = {}
    for t in parsed.find_all(exp.Table):
        real = t.name
        alias = t.alias_or_name
        m[alias] = real
        m[real] = real
    return m


def validate_sql_against_binding(sql: str, allowed_surface: dict[str, Any]) -> dict[str, Any]:
    violations: list[str] = []
    try:
        parsed = sqlglot.parse_one(sql, read="duckdb")
    except Exception as exc:
        return {"ok": False, "violations": [f"unparseable SQL: {type(exc).__name__}: {exc}"]}

    # 1. read-only
    if any(isinstance(n, WRITE_NODES) for n in parsed.walk()):
        violations.append("statement is not read-only (contains DML/DDL)")

    allowed_tables = {t.lower() for t in allowed_surface.get("tables", [])}
    allowed_views = {v.lower() for v in allowed_surface.get("views", [])}
    allowed_all_rel = allowed_tables | allowed_views
    allowed_cols = {c.lower() for c in allowed_surface.get("columns", [])}
    allowed_col_basenames = {c.split(".")[-1].lower() for c in allowed_cols}
    cte_names = {c.alias_or_name.lower() for c in parsed.find_all(exp.CTE)}
    alias_map = _alias_to_table(parsed)

    # 2. tables
    for t in parsed.find_all(exp.Table):
        name = t.name.lower()
        if name in cte_names:
            continue
        if name not in allowed_all_rel:
            violations.append(f"table/view not in allowed surface: {t.name}")

    # 3. columns (qualified -> resolve alias; check fully-qualified; unqualified -> basename)
    for col in parsed.find_all(exp.Column):
        cname = col.name.lower()
        tref = (col.table or "").lower()
        if tref:
            real = alias_map.get(tref, tref)
            if real in cte_names:
                continue
            fq = f"{real}.{cname}"
            if real in allowed_all_rel and fq not in allowed_cols:
                violations.append(f"column not in allowed surface: {real}.{col.name}")
        else:
            if allowed_col_basenames and cname not in allowed_col_basenames:
                # only flag if it's clearly a data column (skip common aggregate aliases)
                violations.append(f"unqualified column not in allowed surface: {col.name}")

    # 4. role row_filter required for referenced tables
    referenced = {t.name.lower() for t in parsed.find_all(exp.Table)} - cte_names
    sql_l = sql.lower()
    for table, rfilter in (allowed_surface.get("row_filters") or {}).items():
        if table.lower() in referenced:
            key_col = re.split(r"[ =]", rfilter.strip(), 1)[0].lower()  # e.g. 'agent_id'
            if key_col and key_col not in sql_l:
                violations.append(f"missing required role row_filter on {table}: {rfilter}")

    return {"ok": len(violations) == 0, "violations": violations}


def explain_binding(metric_id: str) -> str:
    con = robust_connect(DB_PATH, read_only=True)
    try:
        b = _load_binding(con, metric_id)
        if not b:
            return f"No binding found for {metric_id}."
        name = con.execute("select name from concept_nodes where node_id=?", [metric_id]).fetchone()
        label = name[0] if name else metric_id
        view = b["canonical_view"] or "(base tables)"
        tables = ", ".join(b["allowed_tables"][:8]) or "—"
        joins = "; ".join(b["required_joins"]) or "none"
        filters = "; ".join(b["default_filters"]) or "none"
        return (
            f"To answer questions about **{label}** ({b['grain']} grain) we use **{view}** "
            f"= `{b['formula_sql']}` over tables [{tables}] joined by [{joins}] filtered by [{filters}]."
        )
    finally:
        con.close()


if __name__ == "__main__":
    q = " ".join(sys.argv[1:]) or "what is the lapse rate and premium at risk?"
    surface = get_binding_for_question(q, role="Executive Leadership")
    print("QUESTION:", q)
    print("metrics:", surface["metric_ids"])
    print("views:", surface["views"])
    print("tables:", surface["tables"][:10])
    print("row_filter_for_role:", surface["row_filter_for_role"])
