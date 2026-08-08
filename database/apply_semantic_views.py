"""Apply database/semantic_views.sql to the V2 DuckDB and verify each view.

- Executes the whole SQL file in one transaction (CREATE OR REPLACE VIEW only).
- Verifies every public view (v_home_kpis ... v_lapse_hotspots) returns rows.
- If a graph concept_nodes table exists (Prompt 10), registers each view as a
  concept/metric node; otherwise skips gracefully.

Usage:
    venv\\Scripts\\python.exe database\\apply_semantic_views.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import duckdb

SCRIPT_DIR = Path(__file__).resolve().parent
SQL_FILE = SCRIPT_DIR / "semantic_views.sql"

# The 10 public views the data-product APIs depend on.
PUBLIC_VIEWS = [
    "v_home_kpis",
    "v_customer_360",
    "v_customer_policies",
    "v_customer_recommended_action",
    "v_agent_360",
    "v_agent_mapa",
    "v_agent_leaderboard",
    "v_campaign_effectiveness",
    "v_lapse_risk_summary",
    "v_lapse_hotspots",
]

# Drop order: dependents FIRST, helper views LAST. Dropping with CASCADE up front
# clears any stale/cached view signatures (the cause of the
# "Contents of view were altered: types don't match" BinderException) before the
# views are recreated fresh.
DROP_ORDER = [
    # public views (depend on the helper views below)
    "v_lapse_hotspots",
    "v_lapse_risk_summary",
    "v_campaign_effectiveness",
    "v_agent_leaderboard",
    "v_agent_mapa",
    "v_agent_360",
    "v_customer_recommended_action",
    "v_customer_policies",
    "v_customer_360",
    "v_home_kpis",
    # helper views (depended upon by the public views)
    "v_lapse_policy_risk",
    "v_policy_sum_assured",
    "v_customer_propensity",
    "v_policy_lapse_score",
]


def _duckdb_path() -> str:
    import os

    env = os.environ.get("DUCKDB_PATH", "").strip()
    if env:
        return env
    for p in (SCRIPT_DIR / ".env", SCRIPT_DIR.parent / ".env"):
        if p.exists():
            for line in p.read_text(encoding="utf-8", errors="ignore").splitlines():
                if line.strip().startswith("DUCKDB_PATH="):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
    return str(SCRIPT_DIR / "insurance_v2.duckdb")


def _all_created_views(sql: str) -> list[str]:
    return re.findall(r"create\s+or\s+replace\s+view\s+([a-zA-Z0-9_]+)", sql, flags=re.IGNORECASE)


def register_concept_nodes(con: duckdb.DuckDBPyConnection, views: list[str]) -> str:
    """Register each view as a concept node if a graph concept_nodes table exists."""
    tables = {r[0] for r in con.execute(
        "select table_name from information_schema.tables where table_name ilike '%concept_node%'"
    ).fetchall()}
    target = next((t for t in ("concept_nodes", "graph_concept_nodes") if t in tables), None)
    if not target:
        return "skipped (no concept_nodes table — Prompt 10 graph not present)"
    cols = {r[0] for r in con.execute(
        f"select column_name from information_schema.columns where table_name='{target}'"
    ).fetchall()}
    id_col = "node_id" if "node_id" in cols else ("concept_id" if "concept_id" in cols else None)
    name_col = "name" if "name" in cols else ("node_name" if "node_name" in cols else "label")
    type_col = "node_type" if "node_type" in cols else ("type" if "type" in cols else None)
    if not id_col:
        return f"skipped (table {target} has no recognizable id column)"
    n = 0
    for v in views:
        try:
            payload = {id_col: f"metric::{v}", name_col: v}
            if type_col:
                payload[type_col] = "metric_view"
            cols_list = ", ".join(payload.keys())
            ph = ", ".join(["?"] * len(payload))
            con.execute(
                f"insert into {target} ({cols_list}) values ({ph}) "
                f"on conflict do nothing",
                list(payload.values()),
            )
            n += 1
        except Exception:
            pass
    return f"registered {n} view(s) into {target}"


def main() -> int:
    if not SQL_FILE.exists():
        print(f"ERROR: {SQL_FILE} not found", file=sys.stderr)
        return 2
    sql = SQL_FILE.read_text(encoding="utf-8")
    db = _duckdb_path()
    print(f"[apply] db={db}")

    con = duckdb.connect(db, read_only=False)
    try:
        # Pre-drop every view (dependents first) so no cached signature survives.
        for v in DROP_ORDER:
            con.execute(f"drop view if exists {v} cascade")
        con.commit()
        print(f"[apply] pre-dropped {len(DROP_ORDER)} view(s) in dependency order")

        con.execute(sql)
        con.commit()
        created = _all_created_views(sql)
        print(f"[apply] executed — {len(created)} view(s) created/replaced")

        print("[verify] row counts for the 10 public views:")
        failures = 0
        for v in PUBLIC_VIEWS:
            try:
                n = con.execute(f"select count(*) from {v}").fetchone()[0]
                flag = "OK " if n > 0 else "ZERO"
                if n == 0:
                    failures += 1
                print(f"   {flag} {v}: {n} rows")
            except Exception as exc:
                failures += 1
                print(f"   ERR {v}: {type(exc).__name__}: {exc}")

        print(f"[graph] {register_concept_nodes(con, created)}")
        con.commit()

        if failures:
            print(f"[result] {failures} view(s) failed/empty")
            return 1
        print("[result] all 10 public views created and non-empty [OK]")
        return 0
    finally:
        con.close()


if __name__ == "__main__":
    raise SystemExit(main())
