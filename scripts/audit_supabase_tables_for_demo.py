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
from governance_audit_utils import (
    CONTEXT_DIR,
    GOVERNANCE_DIR,
    LLM_HARNESS_DIR,
    KPI_DEFINITIONS,
    MODEL_DEFINITIONS,
    build_table_audit_rows,
    csv_dump,
    ensure_doc_dirs,
    ensure_governance_tables,
    json_dump,
    markdown_table,
    connect,
    utc_now,
)


def ensure_seed_reference_rows(conn, table_rows: list[dict[str, Any]]) -> None:
    existing_tables = {row["full_table_name"] for row in table_rows}
    active_tables = {row["full_table_name"] for row in table_rows if str(row["classification_label"]).startswith("ACT_")}
    allowlisted_tables = {row["full_table_name"] for row in table_rows if row.get("ai_sql_allowed")}

    upsert_rows(
        conn,
        "public.cld_table_registry",
        build_table_registry_db_rows(table_rows),
        conflict_columns=["schema_name", "table_name"],
    )

    kpi_rows = build_kpi_registry_rows(existing_tables, allowlisted_tables)
    model_rows = build_model_registry_rows(existing_tables, allowlisted_tables)
    context_rows = build_context_registry_rows(table_rows, kpi_rows, model_rows)
    skill_rows = build_skill_rows(table_rows, kpi_rows, model_rows)
    guardrail_rows = build_guardrail_rows()

    upsert_rows(conn, "public.cld_kpi_registry", kpi_rows, conflict_columns=["kpi_name"])
    upsert_rows(conn, "public.cld_model_registry", model_rows, conflict_columns=["model_name"])
    upsert_rows(conn, "public.cld_context_registry", context_rows, conflict_columns=["context_id"])
    upsert_rows(conn, "public.cld_llm_skill_registry", skill_rows, conflict_columns=["skill_name"])
    upsert_rows(conn, "public.cld_sql_guardrail_rules", guardrail_rows, conflict_columns=["rule_name"])

    summary = {
        "generated_at": utc_now(),
        "total_tables": len(table_rows),
        "active_tables": sum(1 for row in table_rows if str(row["classification_label"]).startswith("ACT_")),
        "truncate_candidates": sum(1 for row in table_rows if str(row["classification_label"]).startswith("TRUN_")),
        "kpis": len(kpi_rows),
        "models": len(model_rows),
        "context_rows": len(context_rows),
        "skills": len(skill_rows),
        "guardrails": len(guardrail_rows),
    }
    upsert_cleanup_report(conn, summary)


def build_table_registry_db_rows(table_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in table_rows:
        rows.append(
            {
                "schema_name": row["schema_name"],
                "table_name": row["table_name"],
                "classification_label": row["classification_label"],
                "table_role": row["table_role"],
                "business_domain": row.get("business_domain"),
                "authoritative_for_kpis": row.get("authoritative_for_kpis") or [],
                "used_by_tabs": row.get("used_by_tabs") or [],
                "used_by_models": row.get("used_by_models_list") or [],
                "used_by_ai_sql": bool(row.get("used_by_ai_sql")),
                "used_by_context": bool(row.get("used_by_context")),
                "used_by_embeddings": bool(row.get("has_vector_columns") or row.get("used_by_context")),
                "used_by_evidence_hub": bool(row.get("used_by_demo")),
                "demo_required": bool(row.get("used_by_demo")),
                "ai_sql_allowed": bool(row.get("ai_sql_allowed")),
                "context_allowed": bool(row.get("context_allowed")),
                "truncate_candidate": bool(row.get("truncate_candidate")),
                "truncate_risk_level": row.get("truncate_risk_level", "LOW"),
                "recommendation": row.get("recommended_action", "REVIEW_REQUIRED"),
                "reason": row.get("reason", ""),
                "confidence_score": row.get("confidence_score", 0.0),
                "row_count": row.get("row_count", 0),
                "total_size_bytes": row.get("total_size_bytes", 0),
                "index_size_bytes": row.get("index_size_bytes", 0),
                "column_count": row.get("column_count", 0),
                "primary_key_columns": row.get("primary_key_columns") or [],
                "foreign_keys": row.get("foreign_keys") or [],
                "has_vector_columns": bool(row.get("has_vector_columns")),
                "used_by_frontend": bool(row.get("used_by_frontend")),
                "used_by_backend": bool(row.get("used_by_backend")),
                "used_by_demo": bool(row.get("used_by_demo")),
                "used_by_ai_prompt": bool(row.get("used_by_ai_sql") or row.get("used_by_context") or row.get("used_by_demo")),
                "risk_if_truncated": row.get("risk_if_truncated", "UNKNOWN"),
                "manual_review_required": bool(row.get("manual_review_required")),
                "status": row.get("status", "ACTUAL"),
                "missing_data_points": row.get("missing_data_points") or [],
                "fallback_formula": row.get("fallback_formula") or [],
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
            }
        )
    return rows


def build_kpi_registry_rows(existing_tables: set[str], active_tables: set[str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in KPI_DEFINITIONS:
        tables = list(dict.fromkeys([table for table in item["authoritative_tables"] if table in existing_tables and table in active_tables]))
        missing = [table for table in item["authoritative_tables"] if table not in existing_tables]
        status = item.get("status", "ACTUAL")
        if missing and not tables:
            status = "PARTIAL"
        elif len(tables) != len(item["authoritative_tables"]):
            status = "PARTIAL"
        row = {
            "kpi_id": str(uuid4()),
            "kpi_name": item["kpi_name"],
            "business_definition": item["business_definition"],
            "formula": item["formula"],
            "business_domain": item["business_domain"],
            "grain": item["grain"],
            "authoritative_tables": tables,
            "required_columns": item["required_columns"],
            "allowed_join_paths": item["allowed_join_paths"],
            "used_by_tabs": item["used_by_tabs"],
            "used_by_roles": item["used_by_roles"],
            "sql_generation_notes": item["sql_generation_notes"],
            "demo_priority": item["demo_priority"],
            "status": status,
            "missing_data_points": missing if missing else item.get("missing_data_points", []),
            "fallback_formula": item.get("fallback_formula") or "",
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }
        rows.append(row)
    return rows


def build_model_registry_rows(existing_tables: set[str], active_tables: set[str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in MODEL_DEFINITIONS:
        required = [table for table in item["required_source_tables"] if table in existing_tables and table in active_tables]
        missing = [table for table in item["required_source_tables"] if table not in existing_tables]
        score_table_exists = item["score_table"] in existing_tables
        registry_status = item.get("registry_status", "PLANNED")
        required_all_available = len(required) == len(item["required_source_tables"])
        score_table_allowed = item["score_table"] in active_tables
        ai_sql_allowed = bool(item.get("ai_sql_allowed", False) and score_table_exists and score_table_allowed and required_all_available)
        if not score_table_exists:
            registry_status = "PLANNED"
        elif missing or not required_all_available or item["score_table"] not in active_tables:
            registry_status = "PARTIAL"
        else:
            registry_status = "ACTUAL"
        rows.append(
            {
                "model_id": str(uuid4()),
                "model_name": item["model_name"],
                "model_type": item["model_type"],
                "entity_type": item["entity_type"],
                "business_purpose": item["business_purpose"],
                "score_table": item["score_table"],
                "score_column": item["score_column"],
                "score_interpretation": item["score_interpretation"],
                "required_source_tables": required,
                "feature_sources": item["feature_sources"],
                "used_by_tabs": item["used_by_tabs"],
                "used_by_roles": item["used_by_roles"],
                "ai_sql_allowed": ai_sql_allowed,
                "demo_priority": item["demo_priority"],
                "limitation_notes": item["limitation_notes"],
                "registry_status": registry_status,
                "missing_data_points": missing if missing else item.get("missing_data_points", []),
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
            }
        )
    return rows


def build_context_registry_rows(table_rows: list[dict[str, Any]], kpi_rows: list[dict[str, Any]], model_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    table_lookup = {row["full_table_name"]: row for row in table_rows}
    active_tables = [row for row in table_rows if str(row["classification_label"]).startswith("ACT_") and row.get("ai_sql_allowed")]
    active_table_names = {row["full_table_name"] for row in active_tables}
    for row in active_tables[:200]:
        rows.append(
            {
                "context_id": str(uuid4()),
                "context_type": "table_context",
                "title": f"{row['table_name']} table context",
                "business_domain": row["full_table_name"].split(".", 1)[1].replace("_", " "),
                "content": f"Table {row['full_table_name']} is classified as {row['classification_label']} and is used for {row['table_role']}. Reason: {row['reason']}.",
                "related_tables": [row["full_table_name"]],
                "related_columns": row.get("primary_key_columns", [])[:3],
                "related_kpis": row.get("authoritative_for_kpis", []),
                "related_models": row.get("used_by_models_list", []),
                "sql_usable": bool(row.get("ai_sql_allowed")),
                "business_only": not bool(row.get("ai_sql_allowed")),
                "demo_priority": "HIGH" if row.get("used_by_demo") else "MEDIUM",
                "embedding_status": "PENDING",
                "embedding": None,
                "embedding_model": None,
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
            }
        )

    for row in kpi_rows:
        related_tables = [table for table in row["authoritative_tables"] if table in active_table_names]
        rows.append(
            {
                "context_id": str(uuid4()),
                "context_type": "kpi_context",
                "title": row["kpi_name"],
                "business_domain": row["business_domain"],
                "content": f"Business definition: {row['business_definition']}. Formula: {row['formula']}. SQL notes: {row['sql_generation_notes']}.",
                "related_tables": related_tables,
                "related_columns": row["required_columns"],
                "related_kpis": [row["kpi_name"]],
                "related_models": [],
                "sql_usable": row.get("status") == "ACTUAL" and bool(related_tables) and len(related_tables) == len(row["authoritative_tables"]),
                "business_only": row.get("status") != "ACTUAL" or len(related_tables) != len(row["authoritative_tables"]),
                "demo_priority": row["demo_priority"],
                "embedding_status": "PENDING",
                "embedding": None,
                "embedding_model": None,
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
            }
        )

    for row in model_rows:
        related_tables = [table for table in row["required_source_tables"] + [row["score_table"]] if table in active_table_names]
        all_tables_sql_ready = len(related_tables) == len(set(row["required_source_tables"] + [row["score_table"]]))
        rows.append(
            {
                "context_id": str(uuid4()),
                "context_type": "model_context",
                "title": row["model_name"],
                "business_domain": row["entity_type"],
                "content": f"Model purpose: {row['business_purpose']}. Score table: {row['score_table']}. Interpretation: {row['score_interpretation']}.",
                "related_tables": related_tables,
                "related_columns": [row["score_column"]],
                "related_kpis": [],
                "related_models": [row["model_name"]],
                "sql_usable": bool(row["ai_sql_allowed"]) and row["registry_status"] == "ACTUAL" and all_tables_sql_ready,
                "business_only": not bool(row["ai_sql_allowed"]) or row["registry_status"] != "ACTUAL" or not all_tables_sql_ready,
                "demo_priority": row["demo_priority"],
                "embedding_status": "PENDING",
                "embedding": None,
                "embedding_model": None,
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
            }
        )

    rows.append(
        {
            "context_id": str(uuid4()),
            "context_type": "guardrail_context",
            "title": "Text-to-SQL guardrails",
            "business_domain": "governance",
            "content": "LLM must only use ACT tables marked ai_sql_allowed=true, must not invent missing tables or columns, and must return NOT_SUPPORTED when evidence is missing.",
            "related_tables": [row["full_table_name"] for row in active_tables if row.get("ai_sql_allowed")],
            "related_columns": [],
            "related_kpis": [row["kpi_name"] for row in kpi_rows[:10]],
            "related_models": [row["model_name"] for row in model_rows[:10]],
            "sql_usable": True,
            "business_only": False,
            "demo_priority": "HIGH",
            "embedding_status": "PENDING",
            "embedding": None,
            "embedding_model": None,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }
    )
    return rows


def build_skill_rows(table_rows: list[dict[str, Any]], kpi_rows: list[dict[str, Any]], model_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    active_tables = [row["full_table_name"] for row in table_rows if str(row["classification_label"]).startswith("ACT_") and row.get("ai_sql_allowed")]
    return [
        {
            "skill_id": str(uuid4()),
            "skill_name": "llm_system_instructions",
            "purpose": "Core enterprise text-to-SQL guardrails.",
            "instructions": "Use only approved ACT tables, never invent physical schema, and return NOT_SUPPORTED when evidence is incomplete.",
            "allowed_tables": active_tables,
            "allowed_kpis": [row["kpi_name"] for row in kpi_rows],
            "allowed_models": [row["model_name"] for row in model_rows if row.get("ai_sql_allowed")],
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        },
        {
            "skill_id": str(uuid4()),
            "skill_name": "hallucination_prevention_rules",
            "purpose": "Block unsupported SQL and unsupported explanations.",
            "instructions": "If a required table or column is unavailable, say what is missing and suggest the closest supported question.",
            "allowed_tables": active_tables,
            "allowed_kpis": [],
            "allowed_models": [],
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        },
    ]


def build_guardrail_rows() -> list[dict[str, Any]]:
    return [
        {
            "rule_id": str(uuid4()),
            "rule_name": "allowlisted_select_only",
            "severity": "HIGH",
            "applies_to": "text_to_sql",
            "rule_text": "Generate only SELECT or WITH queries and restrict references to ACT tables with ai_sql_allowed=true.",
            "enabled": True,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        },
        {
            "rule_id": str(uuid4()),
            "rule_name": "no_planned_tables",
            "severity": "HIGH",
            "applies_to": "text_to_sql",
            "rule_text": "Do not use planned-only or TRUN tables in SQL generation.",
            "enabled": True,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        },
    ]


def upsert_rows(conn, table: str, rows: list[dict[str, Any]], conflict_columns: list[str]) -> None:
    if not rows:
        return
    columns = list(rows[0].keys())
    quoted_columns = ", ".join(columns)
    placeholders = ", ".join([f"%({column})s" for column in columns])
    update_columns = [column for column in columns if column not in conflict_columns]
    update_clause = ", ".join(f"{column} = excluded.{column}" for column in update_columns)
    sql = f"""
        insert into {table} ({quoted_columns})
        values ({placeholders})
        on conflict ({', '.join(conflict_columns)})
        do update set {update_clause}
    """
    with conn.cursor() as cur:
        for row in rows:
            params = {
                key: json.dumps(value) if isinstance(value, (list, dict)) else value
                for key, value in row.items()
            }
            cur.execute(sql, params)
    conn.commit()


def upsert_cleanup_report(conn, summary: dict[str, Any]) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            insert into public.cld_table_cleanup_report (report_id, generated_at, total_tables, active_tables, truncate_candidates, report_json, created_at)
            values (%s, %s, %s, %s, %s, %s::jsonb, %s)
            """,
            (
                str(uuid4()),
                datetime.now(timezone.utc),
                summary["total_tables"],
                summary["active_tables"],
                summary["truncate_candidates"],
                json.dumps(summary),
                datetime.now(timezone.utc),
            ),
        )
    conn.commit()


def build_report_payload(table_rows: list[TableAuditRow]) -> dict[str, Any]:
    active = [row for row in table_rows if row.classification_label.startswith("ACT_")]
    truncate = [row for row in table_rows if row.classification_label.startswith("TRUN_")]
    by_classification: dict[str, int] = {}
    for row in table_rows:
        by_classification[row.classification_label] = by_classification.get(row.classification_label, 0) + 1
    return {
        "generated_at": utc_now(),
        "total_tables_scanned": len(table_rows),
        "active_tables": len(active),
        "truncate_candidates": len(truncate),
        "by_classification": by_classification,
        "rows": [asdict(row) for row in table_rows],
    }


def write_outputs(report: dict[str, Any]) -> None:
    ensure_doc_dirs()
    rows = report["rows"]
    csv_dump(GOVERNANCE_DIR / "table_inventory_report.csv", rows, list(rows[0].keys()) if rows else [])
    json_dump(GOVERNANCE_DIR / "table_inventory_report.json", report)

    md_rows = [
        [
            row["classification_label"],
            row["full_table_name"],
            row["recommended_action"],
            row["row_count"],
            row["used_by_frontend"],
            row["used_by_backend"],
            row["used_by_ai_sql"],
            row["used_by_context"],
            row["used_by_models"],
            row["reason"],
        ]
        for row in rows
    ]
    md = [
        "# Table Inventory Report",
        "",
        f"- Generated at: {report['generated_at']}",
        f"- Total tables scanned: {report['total_tables_scanned']}",
        f"- Active tables: {report['active_tables']}",
        f"- Truncate candidates: {report['truncate_candidates']}",
        "",
        markdown_table(
            ["classification", "table", "action", "rows", "frontend", "backend", "ai_sql", "context", "models", "reason"],
            md_rows,
        ),
        "",
    ]
    (GOVERNANCE_DIR / "table_inventory_report.md").write_text("\n".join(md) + "\n", encoding="utf-8")

    active_rows = [row for row in rows if row["classification_label"].startswith("ACT_")]
    truncate_rows = [row for row in rows if row["classification_label"].startswith("TRUN_")]
    active_md = [
        "# Active Table Report",
        "",
        "These tables are preserved for the demo and/or runtime because they are referenced by the app, model logic, context retrieval, or governance layer.",
        "",
        markdown_table(
            ["table", "classification", "role", "ai_sql_allowed", "reason"],
            [
                [
                    row["full_table_name"],
                    row["classification_label"],
                    row["table_role"],
                    row["ai_sql_allowed"],
                    row["reason"],
                ]
                for row in active_rows
            ],
        ),
        "",
    ]
    (GOVERNANCE_DIR / "active_table_report.md").write_text("\n".join(active_md) + "\n", encoding="utf-8")

    truncate_md = [
        "# Truncate Candidate Report",
        "",
        "Review these candidates manually before any cleanup action. No data is truncated by this repository.",
        "",
        markdown_table(
            ["table", "classification", "risk", "action", "reason"],
            [
                [
                    row["full_table_name"],
                    row["classification_label"],
                    row["risk_if_truncated"],
                    row["recommended_action"],
                    row["reason"],
                ]
                for row in truncate_rows
            ],
        ),
        "",
    ]
    (GOVERNANCE_DIR / "truncate_candidate_report.md").write_text("\n".join(truncate_md) + "\n", encoding="utf-8")
    csv_dump(GOVERNANCE_DIR / "truncate_candidate_report.csv", truncate_rows, list(truncate_rows[0].keys()) if truncate_rows else [])

    sql_lines = [
        "-- REVIEW ONLY. DO NOT RUN WITHOUT MANUAL APPROVAL.",
        "-- This file lists candidate cleanup statements for manual review only.",
        "",
    ]
    for row in truncate_rows:
        sql_lines.extend(
            [
                f"-- Candidate: {row['classification_label']} {row['full_table_name']}",
                f"-- Reason: {row['reason']}",
                f"-- Risk: {row['risk_if_truncated']}",
                f"-- Recommended action: {row['recommended_action']}",
                f"-- TRUNCATE TABLE {row['full_table_name']};",
                "",
            ]
        )
    (GOVERNANCE_DIR / "review_only_truncate_candidates.sql").write_text("\n".join(sql_lines) + "\n", encoding="utf-8")

    final_report = [
        "# Final Table Governance Report",
        "",
        f"- Generated at: {report['generated_at']}",
        f"- Total tables scanned: {report['total_tables_scanned']}",
        f"- Total ACT tables: {report['active_tables']}",
        f"- Total TRUN candidates: {report['truncate_candidates']}",
        "",
        "## Tables by Category",
        "",
    ]
    for key, value in sorted(report["by_classification"].items()):
        final_report.append(f"- {key}: {value}")
    final_report.extend(
        [
            "",
            "## Demo Safety",
            "",
            "- No existing business table was dropped, truncated, deleted, or altered.",
            "- AI SQL will be restricted to tables marked `ai_sql_allowed = true` in `cld_table_registry`.",
            "- TRUN tables are report labels only and are excluded from SQL generation.",
            "",
        ]
    )
    (GOVERNANCE_DIR / "final_table_governance_report.md").write_text("\n".join(final_report) + "\n", encoding="utf-8")


def write_prompt_docs() -> None:
    ensure_doc_dirs()
    harness_docs = {
        "llm_system_instructions.md": """# LLM System Instructions\n\nThe LLM must only generate SQL using tables marked `ai_sql_allowed = true` in `cld_table_registry` and columns verified from the actual Supabase schema. If a required table or column is not available, the LLM must say what is missing and suggest the closest supported question. The LLM must not invent physical tables, columns, models, or KPIs.\n""",
        "sql_generation_skill.md": """# SQL Generation Skill\n\nGenerate read-only SELECT or WITH queries only. Use approved active tables, explicit joins, null-safe denominators, and validated join paths. Prefer the latest model score per entity.\n""",
        "context_retrieval_skill.md": """# Context Retrieval Skill\n\nRetrieve table, KPI, model, join-path, and demo-question context only from approved ACT tables and SQL-usable governance context. Exclude TRUN tables and planned-only tables.\n""",
        "kpi_interpretation_skill.md": """# KPI Interpretation Skill\n\nExplain KPIs in insurance business language. Use authoritative KPI formulas from `cld_kpi_registry` and mark partial results when source data is missing.\n""",
        "model_usage_skill.md": """# Model Usage Skill\n\nUse model outputs only when the model registry marks the model as actual and AI SQL allowed. Do not reference planned-only models in SQL.\n""",
        "missing_data_handling_skill.md": """# Missing Data Handling Skill\n\nWhen a required source table, column, or model is unavailable, return `NOT_SUPPORTED` or `PARTIAL` and list the missing data points. Do not fabricate fallback columns.\n""",
        "evidence_generation_skill.md": """# Evidence Generation Skill\n\nEvery recommendation must list source tables, source columns, metrics used, model names, and context documents used. Keep the explanation grounded in the executed SQL result.\n""",
        "demo_mode_guardrails.md": """# Demo Mode Guardrails\n\nUse only demo-safe, validated questions. Do not expose secrets or generate destructive SQL. Prefer concise business-safe output over technical detail.\n""",
        "role_based_answering_skill.md": """# Role-Based Answering Skill\n\nTailor answers to the selected role. Use the role profile, KPI registry, and approved context to keep results relevant to the user's insurance function.\n""",
        "hallucination_prevention_rules.md": """# Hallucination Prevention Rules\n\nDo not invent tables, columns, metrics, models, or business results. If the data is missing, say so clearly and suggest the nearest supported question.\n""",
    }
    for filename, content in harness_docs.items():
        (LLM_HARNESS_DIR / filename).write_text(content.strip() + "\n", encoding="utf-8")

    master_prompt = """# Master Text-to-SQL Prompt Template\n\n## Role\n{{role}}\n\n## User Question\n{{question}}\n\n## Intent\n{{intent}}\n\n## Allowed Active Tables Only\n{{allowed_active_tables}}\n\n## Allowed Columns Only\n{{allowed_columns}}\n\n## KPI Registry Entries\n{{kpi_registry_entries}}\n\n## Model Registry Entries\n{{model_registry_entries}}\n\n## Verified Join Paths\n{{verified_join_paths}}\n\n## SQL Generation Rules\n- Generate only SELECT or WITH statements.\n- Use only ACT tables with `ai_sql_allowed = true`.\n- Do not use TRUN tables.\n- Do not invent missing tables, columns, KPIs, or models.\n- Use the latest record per entity when score tables are involved.\n- Add LIMIT for detail-level queries.\n\n## Missing Data Rules\n- If a required physical table is missing, respond with `NOT_SUPPORTED`.\n- If a required column is missing, explain the missing column and offer the closest supported question.\n- If a KPI or model is partial, mark the answer partial.\n\n## Output JSON Contract\n```json\n{\n  \"answerability\": \"SUPPORTED | PARTIAL | NOT_SUPPORTED\",\n  \"sql\": \"\",\n  \"business_logic\": \"\",\n  \"tables_used\": [],\n  \"columns_used\": [],\n  \"kpis_used\": [],\n  \"models_used\": [],\n  \"missing_tables\": [],\n  \"missing_columns\": [],\n  \"missing_data_points\": [],\n  \"assumptions\": [],\n  \"confidence_score\": 0.0\n}\n```\n"""
    (LLM_HARNESS_DIR / "master_text_to_sql_prompt_template.md").write_text(master_prompt, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit Supabase tables for demo governance.")
    parser.add_argument("--env-file", default=".env")
    parser.add_argument("--schemas", default="public")
    parser.add_argument("--no-db-write", action="store_true")
    args = parser.parse_args()

    settings = load_settings(args.env_file)
    allowed_schemas = {item.strip() for item in args.schemas.split(",") if item.strip()}

    ensure_doc_dirs()
    write_prompt_docs()

    with connect(settings.database_url) as conn:
        ensure_governance_tables(conn)
        table_audit_rows = build_table_audit_rows(conn, allowed_schemas=allowed_schemas, repo_root=ROOT)
        report = build_report_payload(table_audit_rows)
        write_outputs(report)
        if not args.no_db_write:
            ensure_seed_reference_rows(
                conn,
                [asdict(row) for row in table_audit_rows],
            )

    print(json.dumps(
        {
            "generated_at": report["generated_at"],
            "total_tables_scanned": report["total_tables_scanned"],
            "active_tables": report["active_tables"],
            "truncate_candidates": report["truncate_candidates"],
            "report_dir": str(GOVERNANCE_DIR),
        },
        indent=2,
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
