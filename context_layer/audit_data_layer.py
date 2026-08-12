"""
One-shot audit: referential integrity + unused-table detection.

Run: venv\\Scripts\\python.exe context_layer\\audit_data_layer.py
Read-only. Writes context_layer/registry/audit_report.json for reference.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from graph.db_util import robust_connect
from backend_v2.config import DUCKDB_PATH

EXCLUDE_PREFIXES = ("model_", "vector_index_log", "__duckpgq")  # ML/system tables, not FK-checked


def main() -> None:
    con = robust_connect(DUCKDB_PATH, read_only=True)

    tables = [r[0] for r in con.execute(
        "select table_name from information_schema.tables "
        "where table_schema = 'main' and table_type = 'BASE TABLE' order by 1").fetchall()]
    views = [r[0] for r in con.execute(
        "select table_name from information_schema.tables "
        "where table_schema = 'main' and table_type = 'VIEW' order by 1").fetchall()]
    all_view_sql = " ".join(
        r[0] or "" for r in con.execute("select sql from duckdb_views() where schema_name='main'").fetchall()
    ).lower()

    # -------------------------------------------------------------------
    # 1. Referential integrity: for every *_id column, check orphan rate
    #    against the table it plausibly references (singular of the prefix).
    # -------------------------------------------------------------------
    fk_cols = con.execute("""
        select table_name, column_name from information_schema.columns
        where table_schema = 'main' and column_name like '%\\_id' escape '\\'
        order by table_name, column_name
    """).fetchall()

    def guess_parent(col: str) -> str | None:
        base = re.sub(r"_id$", "", col)
        for cand in (base, base + "s", base.rstrip("y") + "ies" if base.endswith("y") else None):
            if cand and cand in tables:
                return cand
        return None

    orphan_report = []
    for tbl, col in fk_cols:
        if tbl.startswith(EXCLUDE_PREFIXES) or tbl not in tables:
            continue
        parent = guess_parent(col)
        if not parent or parent == tbl:
            continue
        parent_pk = f"{re.sub(r's$', '', parent)}_id" if f"{re.sub(r's$', '', parent)}_id" in \
            [c[1] for c in fk_cols if c[0] == parent] else col
        try:
            total, orphans = con.execute(f"""
                select count(*),
                       count(*) filter (where c.{col} is not null and p.{parent_pk} is null)
                from {tbl} c
                left join {parent} p on p.{parent_pk} = c.{col}
            """).fetchone()
        except Exception:
            continue
        if total and orphans:
            orphan_report.append({
                "child_table": tbl, "fk_column": col, "parent_table": parent,
                "total_rows": total, "orphan_rows": orphans,
                "orphan_pct": round(100.0 * orphans / total, 2),
            })

    orphan_report.sort(key=lambda r: -r["orphan_pct"])

    # -------------------------------------------------------------------
    # 2. Unused-table detection: cross-reference every table against
    #    view definitions, metric_bindings, initiative_registry.core_tables,
    #    and raw Python source (backend_v2/graph/context_layer).
    # -------------------------------------------------------------------
    binding_tables: set[str] = set()
    for row in con.execute("select allowed_tables from metric_bindings").fetchall():
        for t in (json.loads(row[0]) if row[0] else []):
            binding_tables.add(t.split(".")[-1].lower())

    initiative_tables: set[str] = set()
    for row in con.execute("select core_tables from initiative_registry").fetchall():
        for t in (json.loads(row[0]) if row[0] else []):
            initiative_tables.add(re.sub(r"[^a-z0-9_]", "_", t.lower()))

    py_source = ""
    for d in ("backend_v2", "graph", "context_layer"):
        for f in (PROJECT_ROOT / d).rglob("*.py"):
            if "__pycache__" in str(f):
                continue
            py_source += f.read_text(encoding="utf-8", errors="ignore").lower() + "\n"

    unused = []
    for t in tables:
        if t.startswith(EXCLUDE_PREFIXES):
            continue
        in_view = re.search(rf"\b{re.escape(t)}\b", all_view_sql) is not None
        in_binding = t.lower() in binding_tables
        in_initiative = any(t.lower() in it or it in t.lower() for it in initiative_tables)
        in_source = re.search(rf"\b{re.escape(t)}\b", py_source) is not None
        if not (in_view or in_binding or in_initiative or in_source):
            row_count = con.execute(f"select count(*) from {t}").fetchone()[0]
            unused.append({"table": t, "row_count": row_count})

    con.close()

    report = {
        "summary": {
            "total_base_tables": len(tables), "total_views": len(views),
            "orphan_findings": len(orphan_report), "unused_table_candidates": len(unused),
        },
        "referential_integrity": orphan_report,
        "unused_tables": unused,
    }
    out_path = Path(__file__).parent / "registry" / "audit_report.json"
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(f"tables={len(tables)} views={len(views)}")
    print(f"\n=== REFERENTIAL INTEGRITY: {len(orphan_report)} finding(s) ===")
    for r in orphan_report:
        print(f"  {r['child_table']}.{r['fk_column']} -> {r['parent_table']}: "
              f"{r['orphan_rows']}/{r['total_rows']} orphaned ({r['orphan_pct']}%)")
    print(f"\n=== UNUSED TABLE CANDIDATES: {len(unused)} ===")
    for u in unused:
        print(f"  {u['table']} ({u['row_count']} rows)")
    print(f"\nFull report: {out_path}")


if __name__ == "__main__":
    main()
