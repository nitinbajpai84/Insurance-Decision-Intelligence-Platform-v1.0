from __future__ import annotations

import argparse
import json
import os
import re
from typing import Any
from uuid import uuid4

import psycopg
from dotenv import load_dotenv
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb


DDL = """
create extension if not exists pgcrypto;

create table if not exists public.cld_context_validation_results (
  validation_id uuid primary key,
  context_source text not null,
  context_id text,
  title text,
  referenced_tables jsonb not null default '[]'::jsonb,
  referenced_columns jsonb not null default '[]'::jsonb,
  missing_tables jsonb not null default '[]'::jsonb,
  missing_columns jsonb not null default '[]'::jsonb,
  classification text not null,
  validation_status text not null,
  created_at timestamp with time zone not null default now()
);

create index if not exists idx_cld_context_validation_source
  on public.cld_context_validation_results(context_source, validation_status);
"""


TABLE_REF_RE = re.compile(r"\b(?:public\.)?([a-z][a-z0-9_]{2,})\b", re.IGNORECASE)
COLUMN_REF_RE = re.compile(r"\b(?:public\.)?([a-z][a-z0-9_]{2,})\.([a-z][a-z0-9_]{2,})\b", re.IGNORECASE)


def connect(database_url: str):
    return psycopg.connect(database_url, row_factory=dict_row, connect_timeout=30)


def latest_snapshot_id(cur) -> str | None:
    cur.execute(
        """
        select snapshot_id
        from public.cld_actual_schema_snapshot
        order by snapshot_timestamp desc
        limit 1
        """
    )
    row = cur.fetchone()
    return str(row["snapshot_id"]) if row else None


def actual_schema(cur, snapshot_id: str | None) -> tuple[set[str], dict[str, set[str]]]:
    if snapshot_id:
        cur.execute(
            "select full_table_name, table_name from public.cld_actual_table_catalog where snapshot_id = %s and is_planned_only = false",
            (snapshot_id,),
        )
        table_rows = cur.fetchall()
        cur.execute(
            "select schema_name, table_name, column_name from public.cld_actual_column_catalog where snapshot_id = %s",
            (snapshot_id,),
        )
        column_rows = cur.fetchall()
    else:
        cur.execute("select table_schema || '.' || table_name as full_table_name, table_name from information_schema.tables where table_schema = 'public'")
        table_rows = cur.fetchall()
        cur.execute("select table_schema as schema_name, table_name, column_name from information_schema.columns where table_schema = 'public'")
        column_rows = cur.fetchall()
    tables = {row["full_table_name"] for row in table_rows} | {f"public.{row['table_name']}" for row in table_rows}
    columns: dict[str, set[str]] = {}
    for row in column_rows:
        columns.setdefault(f"{row['schema_name']}.{row['table_name']}", set()).add(row["column_name"])
    return tables, columns


def fetch_context_rows(cur) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    sources = [
        ("semantic_documents", "semantic_document_id", "title", "content"),
        ("business_glossary", "business_glossary_id", "term", "business_definition"),
        ("kpi_definitions", "kpi_definition_id", "kpi_name", "business_definition"),
        ("model_catalog", "model_catalog_id", "model_name", "business_purpose"),
    ]
    for table, id_col, title_col, content_col in sources:
        cur.execute("savepoint context_source_check")
        try:
            cur.execute(
                f"""
                select '{table}' as context_source,
                       {id_col}::text as context_id,
                       {title_col}::text as title,
                       coalesce({content_col}::text, '') as content
                from public.{table}
                limit 5000
                """
            )
            rows.extend(dict(row) for row in cur.fetchall())
        except Exception:
            cur.execute("rollback to savepoint context_source_check")
        finally:
            cur.execute("release savepoint context_source_check")
            continue
    return rows


def extract_refs(text: str, known_tables: set[str]) -> tuple[list[str], list[str]]:
    column_refs = sorted({f"public.{m.group(1).lower()}.{m.group(2).lower()}" for m in COLUMN_REF_RE.finditer(text or "")})
    table_candidates = {f"public.{m.group(1).lower()}" for m in TABLE_REF_RE.finditer(text or "")}
    table_refs = sorted(candidate for candidate in table_candidates if candidate in known_tables or "_" in candidate)
    return table_refs, column_refs


def audit(database_url: str) -> dict[str, Any]:
    with connect(database_url) as conn:
        with conn.cursor() as cur:
            cur.execute(DDL)
            cur.execute("delete from public.cld_context_validation_results")
            snapshot_id = latest_snapshot_id(cur)
            known_tables, known_columns = actual_schema(cur, snapshot_id)
            context_rows = fetch_context_rows(cur)
            inserted = 0
            invalid = 0
            for row in context_rows:
                text = f"{row.get('title') or ''}\n{row.get('content') or ''}"
                referenced_tables, referenced_columns = extract_refs(text, known_tables)
                missing_tables = sorted(table for table in referenced_tables if table not in known_tables)
                missing_columns = []
                for ref in referenced_columns:
                    table_name, column_name = ref.rsplit(".", 1)
                    if table_name in known_columns and column_name not in known_columns[table_name]:
                        missing_columns.append(ref)
                classification = "sql_usable"
                if missing_tables or missing_columns:
                    classification = "invalid_schema_reference"
                    invalid += 1
                elif not referenced_tables:
                    classification = "business_only"
                cur.execute(
                    """
                    insert into public.cld_context_validation_results (
                      validation_id, context_source, context_id, title, referenced_tables,
                      referenced_columns, missing_tables, missing_columns, classification,
                      validation_status, created_at
                    ) values (%s, %s, %s, %s, %s::jsonb, %s::jsonb, %s::jsonb, %s::jsonb, %s, %s, now())
                    """,
                    (
                        str(uuid4()),
                        row["context_source"],
                        row.get("context_id"),
                        row.get("title"),
                        Jsonb(referenced_tables),
                        Jsonb(referenced_columns),
                        Jsonb(missing_tables),
                        Jsonb(missing_columns),
                        classification,
                        "failed" if classification == "invalid_schema_reference" else "passed",
                    ),
                )
                inserted += 1
        conn.commit()
    return {"snapshot_id": snapshot_id, "contexts_checked": inserted, "invalid_contexts": invalid}


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit semantic context against actual schema catalog.")
    parser.add_argument("--env-file", default=".env")
    args = parser.parse_args()
    load_dotenv(args.env_file, override=True)
    print(json.dumps(audit(os.environ["SUPABASE_DB_URL"]), indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
