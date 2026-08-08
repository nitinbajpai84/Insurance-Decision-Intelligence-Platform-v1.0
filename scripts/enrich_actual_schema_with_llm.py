from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

import psycopg
from dotenv import load_dotenv
from psycopg.rows import dict_row

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from copilot_sql_engine.llm_providers import get_llm_provider


def connect(database_url: str):
    return psycopg.connect(database_url, row_factory=dict_row, connect_timeout=30)


def latest_snapshot_id(cur) -> str:
    cur.execute(
        """
        select snapshot_id
        from public.cld_actual_schema_snapshot
        order by snapshot_timestamp desc
        limit 1
        """
    )
    row = cur.fetchone()
    if not row:
        raise RuntimeError("No cld_actual_schema_snapshot found. Run scripts/build_actual_schema_catalog.py first.")
    return str(row["snapshot_id"])


def fallback_table_description(table_name: str, columns: list[str]) -> dict[str, Any]:
    name = table_name.replace("_", " ")
    if "customer" in table_name:
        domain = "Customer"
    elif "policy" in table_name or "premium" in table_name or "payment" in table_name:
        domain = "Policy"
    elif "agent" in table_name:
        domain = "Agent"
    elif "campaign" in table_name or "lead" in table_name or "opportun" in table_name:
        domain = "Sales and Campaign"
    elif "claim" in table_name or "fraud" in table_name:
        domain = "Claims"
    elif "model" in table_name or "feature" in table_name or "score" in table_name:
        domain = "ML Decisioning"
    else:
        domain = "Insurance Operations"
    return {
        "business_domain": domain,
        "business_description": f"Actual Supabase table containing {name} records for the Insurance Decision Intelligence Platform.",
        "table_grain": f"One row per {name} record.",
        "example_questions": [
            f"Show {name} by month.",
            f"Which {name} records need attention?",
        ],
    }


def fallback_column_description(column_name: str, data_type: str) -> dict[str, Any]:
    name = column_name.replace("_", " ").title()
    lower = column_name.lower()
    semantic_type = "dimension"
    if lower.endswith("_id") or lower == "id":
        semantic_type = "identifier"
    elif "date" in lower or lower.endswith("_at"):
        semantic_type = "date"
    elif any(token in lower for token in ["amount", "premium", "commission", "cost", "budget"]):
        semantic_type = "amount"
    elif any(token in lower for token in ["score", "rate", "ratio", "pct"]):
        semantic_type = "score"
    elif "status" in lower:
        semantic_type = "status"
    elif data_type in {"numeric", "integer", "bigint", "double precision"}:
        semantic_type = "metric"
    return {
        "business_name": name,
        "business_description": f"Actual column {name} used as a {semantic_type} field.",
        "semantic_type": semantic_type,
        "is_metric": semantic_type in {"amount", "score", "metric"},
        "is_dimension": semantic_type not in {"amount", "score", "metric"},
        "is_join_key": lower.endswith("_id"),
    }


def llm_table_description(table_name: str, columns: list[dict[str, Any]]) -> dict[str, Any] | None:
    prompt = {
        "task": "Enrich actual insurance schema table. Do not invent physical tables or columns.",
        "table_name": table_name,
        "columns": columns,
        "return_json_keys": ["business_domain", "business_description", "table_grain", "example_questions"],
    }
    try:
        response = get_llm_provider("schema_enrichment").generate(
            json.dumps(prompt, ensure_ascii=False, default=str),
            task_type="schema_enrichment",
            temperature=0.0,
        )
        text = response.text.strip()
        start, end = text.find("{"), text.rfind("}")
        return json.loads(text[start : end + 1]) if start >= 0 and end > start else None
    except Exception:
        return None


def enrich(database_url: str, *, use_llm: bool, limit: int | None) -> dict[str, Any]:
    with connect(database_url) as conn:
        with conn.cursor() as cur:
            snapshot_id = latest_snapshot_id(cur)
            cur.execute(
                """
                select t.schema_name, t.table_name, jsonb_agg(jsonb_build_object(
                         'column_name', c.column_name,
                         'data_type', c.data_type,
                         'semantic_type', c.semantic_type
                       ) order by c.ordinal_position) as columns
                from public.cld_actual_table_catalog t
                join public.cld_actual_column_catalog c
                  on c.snapshot_id = t.snapshot_id
                 and c.schema_name = t.schema_name
                 and c.table_name = t.table_name
                where t.snapshot_id = %s
                group by t.schema_name, t.table_name
                order by t.schema_name, t.table_name
                limit %s
                """,
                (snapshot_id, limit or 10000),
            )
            tables = cur.fetchall()
            for table in tables:
                columns = list(table["columns"] or [])
                enrichment = llm_table_description(table["table_name"], columns) if use_llm else None
                enrichment = enrichment or fallback_table_description(table["table_name"], [c["column_name"] for c in columns])
                cur.execute(
                    """
                    update public.cld_actual_table_catalog
                    set business_domain = %s,
                        business_description = %s,
                        table_grain = %s,
                        updated_at = now()
                    where snapshot_id = %s and schema_name = %s and table_name = %s
                    """,
                    (
                        enrichment.get("business_domain"),
                        enrichment.get("business_description"),
                        enrichment.get("table_grain"),
                        snapshot_id,
                        table["schema_name"],
                        table["table_name"],
                    ),
                )
                for column in columns:
                    col = fallback_column_description(column["column_name"], column.get("data_type") or "")
                    cur.execute(
                        """
                        update public.cld_actual_column_catalog
                        set business_name = %s,
                            business_description = %s,
                            semantic_type = %s,
                            is_metric = %s,
                            is_dimension = %s,
                            is_join_key = %s,
                            updated_at = now()
                        where snapshot_id = %s and schema_name = %s and table_name = %s and column_name = %s
                        """,
                        (
                            col["business_name"],
                            col["business_description"],
                            col["semantic_type"],
                            col["is_metric"],
                            col["is_dimension"],
                            col["is_join_key"],
                            snapshot_id,
                            table["schema_name"],
                            table["table_name"],
                            column["column_name"],
                        ),
                    )
        conn.commit()
    return {"snapshot_id": snapshot_id, "tables_enriched": len(tables), "llm_used": use_llm}


def main() -> int:
    parser = argparse.ArgumentParser(description="Enrich actual schema catalog descriptions.")
    parser.add_argument("--env-file", default=".env")
    parser.add_argument("--use-llm", action="store_true")
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()
    load_dotenv(args.env_file, override=True)
    result = enrich(os.environ["SUPABASE_DB_URL"], use_llm=args.use_llm, limit=args.limit)
    print(json.dumps(result, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
