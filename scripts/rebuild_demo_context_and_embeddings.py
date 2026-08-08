#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from embedding_pipeline.config import load_settings
from embedding_pipeline.db import vector_literal
from embedding_pipeline.providers import build_provider
from governance_audit_utils import (
    CONTEXT_DIR,
    GOVERNANCE_DIR,
    build_guardrail_rows,
    build_kpi_registry_rows,
    build_model_registry_rows,
    connect,
    ensure_doc_dirs,
    ensure_governance_tables,
    json_dump,
    markdown_table,
)
from table_governance_service import load_table_registry_rows

ROLE_PRIORITIES = {
    "insurance_agent": "HIGH",
    "agency_manager": "HIGH",
    "campaign_manager": "HIGH",
    "claims_manager": "MEDIUM",
    "sales_director": "HIGH",
    "executive_leadership": "HIGH",
    "data_analyst": "MEDIUM",
}


def get_table_columns(conn, schema_name: str, table_name: str) -> list[str]:
    with conn.cursor() as cur:
        cur.execute(
            """
            select column_name
            from information_schema.columns
            where table_schema = %s and table_name = %s
            order by ordinal_position
            """,
            (schema_name, table_name),
        )
        return [str(row["column_name"]) for row in cur.fetchall()]


def get_foreign_key_paths(conn, allowed_schemas: set[str]) -> list[dict[str, Any]]:
    with conn.cursor() as cur:
        cur.execute(
            """
            select
              tc.table_schema,
              tc.table_name,
              kcu.column_name,
              ccu.table_schema as foreign_table_schema,
              ccu.table_name as foreign_table_name,
              ccu.column_name as foreign_column_name
            from information_schema.table_constraints tc
            join information_schema.key_column_usage kcu
              on tc.constraint_name = kcu.constraint_name
             and tc.table_schema = kcu.table_schema
             and tc.table_name = kcu.table_name
            join information_schema.constraint_column_usage ccu
              on ccu.constraint_name = tc.constraint_name
            where tc.constraint_type = 'FOREIGN KEY'
              and tc.table_schema = any(%s)
            order by tc.table_schema, tc.table_name, kcu.ordinal_position
            """,
            (list(allowed_schemas),),
        )
        return [
            {
                "table_schema": row["table_schema"],
                "table_name": row["table_name"],
                "column_name": row["column_name"],
                "foreign_table_schema": row["foreign_table_schema"],
                "foreign_table_name": row["foreign_table_name"],
                "foreign_column_name": row["foreign_column_name"],
            }
            for row in cur.fetchall()
        ]


def get_glossary_rows(conn) -> list[dict[str, Any]]:
    try:
        with conn.cursor() as cur:
            cur.execute("select * from public.business_glossary order by 1 limit 50")
            rows = cur.fetchall()
            columns = [desc[0] for desc in cur.description or []]
            return [dict(zip(columns, row)) for row in rows]
    except Exception:
        conn.rollback()
        return []


def get_role_profiles() -> list[dict[str, Any]]:
    from role_intelligence_service import fetch_roles, fetch_role_profile

    profiles: list[dict[str, Any]] = []
    for role in fetch_roles():
        role_code = role.get("role_code")
        if not role_code:
            continue
        try:
            profiles.append(fetch_role_profile(role_code))
        except Exception:
            continue
    return profiles


def context_key(context_type: str, title: str) -> tuple[str, str]:
    return context_type.lower().strip(), title.lower().strip()


def fetch_latest_context_id(conn, context_type: str, title: str) -> str | None:
    with conn.cursor() as cur:
        cur.execute(
            """
            select context_id::text
            from public.cld_context_registry
            where lower(context_type) = lower(%s)
              and lower(title) = lower(%s)
            order by updated_at desc, created_at desc
            limit 1
            """,
            (context_type, title),
        )
        row = cur.fetchone()
        return str(row["context_id"]) if row else None


def upsert_context_row(conn, row: dict[str, Any]) -> None:
    existing_id = fetch_latest_context_id(conn, row["context_type"], row["title"])
    if existing_id:
        with conn.cursor() as cur:
            cur.execute(
                """
                update public.cld_context_registry
                set business_domain = %s,
                    content = %s,
                    related_tables = %s::jsonb,
                    related_columns = %s::jsonb,
                    related_kpis = %s::jsonb,
                    related_models = %s::jsonb,
                    sql_usable = %s,
                    business_only = %s,
                    demo_priority = %s,
                    embedding_status = %s,
                    updated_at = now()
                where lower(context_type) = lower(%s)
                  and lower(title) = lower(%s)
                """,
                (
                    row["business_domain"],
                    row["content"],
                    json.dumps(row["related_tables"]),
                    json.dumps(row["related_columns"]),
                    json.dumps(row["related_kpis"]),
                    json.dumps(row["related_models"]),
                    row["sql_usable"],
                    row["business_only"],
                    row["demo_priority"],
                    row["embedding_status"],
                    row["context_type"],
                    row["title"],
                ),
            )
    else:
        with conn.cursor() as cur:
            cur.execute(
                """
                insert into public.cld_context_registry (
                  context_id, context_type, title, business_domain, content,
                  related_tables, related_columns, related_kpis, related_models,
                  sql_usable, business_only, demo_priority, embedding_status,
                  created_at, updated_at
                )
                values (
                  %s, %s, %s, %s, %s,
                  %s::jsonb, %s::jsonb, %s::jsonb, %s::jsonb,
                  %s, %s, %s, %s,
                  now(), now()
                )
                """,
                (
                    str(uuid4()),
                    row["context_type"],
                    row["title"],
                    row["business_domain"],
                    row["content"],
                    json.dumps(row["related_tables"]),
                    json.dumps(row["related_columns"]),
                    json.dumps(row["related_kpis"]),
                    json.dumps(row["related_models"]),
                    row["sql_usable"],
                    row["business_only"],
                    row["demo_priority"],
                    row["embedding_status"],
                ),
            )


def build_context_rows(
    conn,
    *,
    table_rows: list[dict[str, Any]],
    kpi_rows: list[dict[str, Any]],
    model_rows: list[dict[str, Any]],
    allowed_schemas: set[str],
) -> list[dict[str, Any]]:
    active_tables = [row for row in table_rows if str(row["classification_label"]).startswith("ACT_") and row.get("ai_sql_allowed")]
    active_table_names = {row["full_table_name"] for row in active_tables}
    fk_paths = get_foreign_key_paths(conn, allowed_schemas)
    glossary_rows = get_glossary_rows(conn)
    role_profiles = get_role_profiles()
    rows: list[dict[str, Any]] = []

    for row in active_tables:
        columns = row.get("primary_key_columns") or []
        if not columns:
            columns = get_table_columns(conn, row["schema_name"], row["table_name"])[:5]
        rows.append(
            {
                "context_type": "table_context",
                "title": f"{row['full_table_name']} table context",
                "business_domain": str(row.get("business_domain") or row["table_role"] or "general"),
                "content": f"{row['full_table_name']} is classified as {row['classification_label']} ({row['table_role']}). It is {row.get('recommendation') or row.get('recommended_action') or 'REVIEW_REQUIRED'} because {row.get('reason', '')}. Key columns: {', '.join(columns[:8])}.",
                "related_tables": [row["full_table_name"]],
                "related_columns": columns[:8],
                "related_kpis": row.get("authoritative_for_kpis") or [],
                "related_models": row.get("used_by_models_list") or [],
                "sql_usable": bool(row.get("ai_sql_allowed")),
                "business_only": not bool(row.get("ai_sql_allowed")),
                "demo_priority": "HIGH" if row.get("used_by_demo") else row.get("truncate_risk_level", "MEDIUM"),
                "embedding_status": "PENDING",
            }
        )

        for column_name in (get_table_columns(conn, row["schema_name"], row["table_name"])[:3]):
            rows.append(
                {
                    "context_type": "column_context",
                    "title": f"{row['full_table_name']}.{column_name}",
                    "business_domain": str(row.get("business_domain") or row["table_role"] or "general"),
                    "content": f"Column {column_name} belongs to {row['full_table_name']}. Use it only when the question clearly requires {column_name} level detail. The table is classified as {row['classification_label']}.",
                    "related_tables": [row["full_table_name"]],
                    "related_columns": [column_name],
                    "related_kpis": row.get("authoritative_for_kpis") or [],
                    "related_models": row.get("used_by_models_list") or [],
                "sql_usable": bool(row.get("ai_sql_allowed")),
                "business_only": not bool(row.get("ai_sql_allowed")),
                "demo_priority": "MEDIUM",
                "embedding_status": "PENDING",
            }
            )

    def tables_sql_ready(tables: list[str]) -> bool:
        return bool(tables) and all(table in active_table_names for table in tables)

    for row in kpi_rows:
        related_tables = [table for table in row["authoritative_tables"] if table in active_table_names]
        rows.append(
            {
                "context_type": "kpi_context",
                "title": row["kpi_name"],
                "business_domain": row["business_domain"],
                "content": f"Business definition: {row['business_definition']}. Formula: {row['formula']}. SQL notes: {row['sql_generation_notes']}.",
                "related_tables": related_tables,
                "related_columns": row["required_columns"],
                "related_kpis": [row["kpi_name"]],
                "related_models": [],
                "sql_usable": row.get("status") == "ACTUAL" and tables_sql_ready(related_tables) and len(related_tables) == len(row["authoritative_tables"]),
                "business_only": row.get("status") != "ACTUAL" or len(related_tables) != len(row["authoritative_tables"]),
                "demo_priority": row["demo_priority"],
                "embedding_status": "PENDING",
            }
        )

    for row in model_rows:
        related_tables = [table for table in row["required_source_tables"] + [row["score_table"]] if table in active_table_names]
        related_table_set = set(related_tables)
        expected_table_set = set(row["required_source_tables"] + [row["score_table"]])
        rows.append(
            {
                "context_type": "model_context",
                "title": row["model_name"],
                "business_domain": row["entity_type"],
                "content": f"Model purpose: {row['business_purpose']}. Score table: {row['score_table']}. Score column: {row['score_column']}. Interpretation: {row['score_interpretation']}.",
                "related_tables": related_tables,
                "related_columns": [row["score_column"]],
                "related_kpis": [],
                "related_models": [row["model_name"]],
                "sql_usable": bool(row["ai_sql_allowed"]) and row["registry_status"] == "ACTUAL" and related_table_set == expected_table_set,
                "business_only": not bool(row["ai_sql_allowed"]) or row["registry_status"] != "ACTUAL" or related_table_set != expected_table_set,
                "demo_priority": row["demo_priority"],
                "embedding_status": "PENDING",
            }
        )

    for fk in fk_paths[:120]:
        related_tables = [
            f"{fk['table_schema']}.{fk['table_name']}",
            f"{fk['foreign_table_schema']}.{fk['foreign_table_name']}",
        ]
        sql_usable = all(table in active_table_names for table in related_tables)
        rows.append(
            {
                "context_type": "join_path_context",
                "title": f"{fk['table_schema']}.{fk['table_name']} -> {fk['foreign_table_schema']}.{fk['foreign_table_name']}",
                "business_domain": "governance",
                "content": f"Join path: {fk['table_schema']}.{fk['table_name']}.{fk['column_name']} references {fk['foreign_table_schema']}.{fk['foreign_table_name']}.{fk['foreign_column_name']}. Use this path for explicit joins and grain-safe aggregation.",
                "related_tables": related_tables,
                "related_columns": [fk["column_name"], fk["foreign_column_name"]],
                "related_kpis": [],
                "related_models": [],
                "sql_usable": sql_usable,
                "business_only": not sql_usable,
                "demo_priority": "MEDIUM",
                "embedding_status": "PENDING",
            }
        )

    demo_questions = [
        "Which agents have the highest premium at risk?",
        "Which campaigns generated the highest policy conversion?",
        "Which customers are likely to lapse in the next 90 days?",
        "Which products are declining in new sales?",
        "Which customers should agents contact this week?",
        "What are the top risks to revenue this month?",
        "Show campaign conversion rate by channel.",
        "Show SQL for lapse risk by product.",
    ]
    for question in demo_questions:
        rows.append(
            {
                "context_type": "demo_question_context",
                "title": question,
                "business_domain": "demo",
                "content": f"Validated demo question: {question}. Answer must be grounded in actual ACT tables and validated SQL or return NOT_SUPPORTED.",
                "related_tables": [row["full_table_name"] for row in active_tables[:8]],
                "related_columns": [],
                "related_kpis": [row["kpi_name"] for row in kpi_rows[:5]],
                "related_models": [row["model_name"] for row in model_rows[:5]],
                "sql_usable": True,
                "business_only": False,
                "demo_priority": "HIGH",
                "embedding_status": "PENDING",
            }
        )

    for row in glossary_rows[:40]:
        title = str(
            row.get("term")
            or row.get("title")
            or row.get("business_term")
            or row.get("glossary_term")
            or row.get("name")
            or row.get("id")
        )
        definition = str(
            row.get("definition")
            or row.get("business_definition")
            or row.get("description")
            or row.get("content")
            or ""
        )
        if not title or not definition:
            continue
        rows.append(
            {
                "context_type": "business_glossary_context",
                "title": title,
                "business_domain": str(row.get("business_domain") or "business"),
                "content": definition,
                "related_tables": [],
                "related_columns": [],
                "related_kpis": [],
                "related_models": [],
                "sql_usable": False,
                "business_only": True,
                "demo_priority": "MEDIUM",
                "embedding_status": "PENDING",
            }
        )

    for profile in role_profiles:
        role_code = str(profile.get("role_code") or "").strip()
        role_name = str(profile.get("role_name") or role_code or "Role")
        if not role_code:
            continue
        rows.append(
            {
                "context_type": "role_context",
                "title": role_name,
                "business_domain": "role",
                "content": f"Role {role_name} focuses on {', '.join(profile.get('primary_objectives') or [])}. KPIs: {', '.join(item.get('kpi_name', str(item)) if isinstance(item, dict) else str(item) for item in profile.get('kpis') or [])}.",
                "related_tables": [],
                "related_columns": [],
                "related_kpis": [item.get("kpi_name", str(item)) if isinstance(item, dict) else str(item) for item in profile.get("kpis") or []],
                "related_models": [],
                "sql_usable": False,
                "business_only": True,
                "demo_priority": ROLE_PRIORITIES.get(role_code, "MEDIUM"),
                "embedding_status": "PENDING",
            }
        )

    rows.append(
        {
            "context_type": "guardrail_context",
            "title": "Text-to-SQL guardrails",
            "business_domain": "governance",
            "content": "The assistant must only generate SQL using ACT tables marked ai_sql_allowed=true, must not invent missing physical tables or columns, and must return NOT_SUPPORTED when evidence is missing.",
            "related_tables": [row["full_table_name"] for row in active_tables if row.get("ai_sql_allowed")][:25],
            "related_columns": [],
            "related_kpis": [row["kpi_name"] for row in kpi_rows[:10]],
            "related_models": [row["model_name"] for row in model_rows[:10]],
            "sql_usable": True,
            "business_only": False,
            "demo_priority": "HIGH",
            "embedding_status": "PENDING",
        }
    )
    return rows


def fetch_existing_context_ids(conn, context_type: str, title: str) -> str | None:
    with conn.cursor() as cur:
        cur.execute(
            """
            select context_id::text
            from public.cld_context_registry
            where lower(context_type) = lower(%s)
              and lower(title) = lower(%s)
            order by updated_at desc, created_at desc
            limit 1
            """,
            (context_type, title),
        )
        row = cur.fetchone()
        return str(row["context_id"]) if row else None


def context_text(spec: dict[str, Any]) -> str:
    payload = {
        "title": spec["title"],
        "context_type": spec["context_type"],
        "business_domain": spec["business_domain"],
        "content": spec["content"],
        "related_tables": spec["related_tables"],
        "related_columns": spec["related_columns"],
        "related_kpis": spec["related_kpis"],
        "related_models": spec["related_models"],
        "sql_usable": spec["sql_usable"],
        "business_only": spec["business_only"],
        "demo_priority": spec["demo_priority"],
    }
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def upsert_context_row_with_embedding(conn, spec: dict[str, Any], vector: list[float], model_name: str) -> None:
    existing_id = fetch_existing_context_ids(conn, spec["context_type"], spec["title"])
    vector_value = vector_literal(vector)
    if existing_id:
        with conn.cursor() as cur:
            cur.execute(
                """
                update public.cld_context_registry
                set business_domain = %s,
                    content = %s,
                    related_tables = %s::jsonb,
                    related_columns = %s::jsonb,
                    related_kpis = %s::jsonb,
                    related_models = %s::jsonb,
                    sql_usable = %s,
                    business_only = %s,
                    demo_priority = %s,
                    embedding_status = %s,
                    embedding = %s::vector,
                    embedding_model = %s,
                    updated_at = now()
                where lower(context_type) = lower(%s)
                  and lower(title) = lower(%s)
                """,
                (
                    spec["business_domain"],
                    spec["content"],
                    json.dumps(spec["related_tables"]),
                    json.dumps(spec["related_columns"]),
                    json.dumps(spec["related_kpis"]),
                    json.dumps(spec["related_models"]),
                    spec["sql_usable"],
                    spec["business_only"],
                    spec["demo_priority"],
                    "READY",
                    vector_value,
                    model_name,
                    spec["context_type"],
                    spec["title"],
                ),
            )
    else:
        with conn.cursor() as cur:
            cur.execute(
                """
                insert into public.cld_context_registry (
                  context_id, context_type, title, business_domain, content,
                  related_tables, related_columns, related_kpis, related_models,
                  sql_usable, business_only, demo_priority, embedding_status,
                  embedding, embedding_model, created_at, updated_at
                )
                values (
                  %s, %s, %s, %s, %s,
                  %s::jsonb, %s::jsonb, %s::jsonb, %s::jsonb,
                  %s, %s, %s, %s,
                  %s::vector, %s, now(), now()
                )
                """,
                (
                    str(uuid4()),
                    spec["context_type"],
                    spec["title"],
                    spec["business_domain"],
                    spec["content"],
                    json.dumps(spec["related_tables"]),
                    json.dumps(spec["related_columns"]),
                    json.dumps(spec["related_kpis"]),
                    json.dumps(spec["related_models"]),
                    spec["sql_usable"],
                    spec["business_only"],
                    spec["demo_priority"],
                    "READY",
                    vector_value,
                    model_name,
                ),
            )


def write_report(outputs_dir: Path, summary: dict[str, Any]) -> None:
    outputs_dir.mkdir(parents=True, exist_ok=True)
    json_dump(outputs_dir / "context_rebuild_report.json", summary)
    md = [
        "# Context Rebuild Report",
        "",
        f"- Generated at: {summary['generated_at']}",
        f"- Context rows processed: {summary['context_rows_processed']}",
        f"- Embeddings written: {summary['embeddings_written']}",
        f"- Embeddings skipped: {summary['embeddings_skipped']}",
        f"- Embedding model: {summary['embedding_model']}",
        f"- Embedding dimensions: {summary['embedding_dimensions']}",
        "",
        "## Context Types",
        "",
        markdown_table(["context_type", "count"], [[k, v] for k, v in sorted(summary["by_type"].items())]),
        "",
        "## SQL Usability",
        "",
        markdown_table(["status", "count"], [[k, v] for k, v in sorted(summary["by_sql_usable"].items())]),
        "",
    ]
    (outputs_dir / "context_rebuild_report.md").write_text("\n".join(md) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Rebuild demo context and embeddings from governance registries.")
    parser.add_argument("--env-file", default=".env")
    parser.add_argument("--schemas", default="public")
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    settings = load_settings(args.env_file)
    provider = build_provider(settings)
    allowed_schemas = {item.strip() for item in args.schemas.split(",") if item.strip()}

    ensure_doc_dirs()
    with connect(settings.database_url) as conn:
        ensure_governance_tables(conn)
        table_rows = [
            {
                **row,
                "full_table_name": f"{row['schema_name']}.{row['table_name']}",
            }
            for row in load_table_registry_rows(conn, allowed_schemas)
        ]
        kpi_rows = build_kpi_registry_rows(
            {row["full_table_name"] for row in table_rows},
            {row["full_table_name"] for row in table_rows if str(row["classification_label"]).startswith("ACT_")},
        )
        model_rows = build_model_registry_rows(
            {row["full_table_name"] for row in table_rows},
            {row["full_table_name"] for row in table_rows if str(row["classification_label"]).startswith("ACT_")},
        )
        context_specs = build_context_rows(
            conn,
            table_rows=table_rows,
            kpi_rows=kpi_rows,
            model_rows=model_rows,
            allowed_schemas=allowed_schemas,
        )
        if args.limit > 0:
            context_specs = context_specs[: args.limit]

        texts = [context_text(spec) for spec in context_specs]
        embeddings = []
        for i in range(0, len(texts), max(1, settings.batch_size)):
            batch = texts[i : i + max(1, settings.batch_size)]
            result = provider.embed_batch(batch)
            if result.dimensions != settings.embedding_dimensions:
                raise ValueError(
                    f"Embedding dimension mismatch. Expected {settings.embedding_dimensions}, got {result.dimensions}."
                )
            embeddings.extend(result.vectors)
        if embeddings and len(embeddings) != len(context_specs):
            raise ValueError("Embedding count mismatch.")

        embeddings_written = 0
        embeddings_skipped = 0
        for spec, vector in zip(context_specs, embeddings, strict=False):
            if not vector:
                embeddings_skipped += 1
                continue
            upsert_context_row_with_embedding(conn, spec, vector, provider.model_name)
            embeddings_written += 1
        conn.commit()

    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "context_rows_processed": len(context_specs),
        "embeddings_written": embeddings_written,
        "embeddings_skipped": embeddings_skipped,
        "embedding_model": provider.model_name,
        "embedding_dimensions": settings.embedding_dimensions,
        "by_type": {},
        "by_sql_usable": {},
    }
    for spec in context_specs:
        summary["by_type"][spec["context_type"]] = summary["by_type"].get(spec["context_type"], 0) + 1
        sql_key = "sql_usable" if spec["sql_usable"] else "business_only"
        summary["by_sql_usable"][sql_key] = summary["by_sql_usable"].get(sql_key, 0) + 1

    write_report(CONTEXT_DIR, summary)
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
