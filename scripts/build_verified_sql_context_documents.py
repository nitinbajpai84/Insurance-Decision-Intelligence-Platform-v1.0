from __future__ import annotations

import argparse
import json
import os
from typing import Any
from uuid import uuid4

import psycopg
from dotenv import load_dotenv
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb


DDL = """
create extension if not exists vector;
create extension if not exists pgcrypto;

create table if not exists public.cld_verified_sql_context_documents (
  context_id uuid primary key,
  title text not null,
  document_type text not null,
  business_domain text,
  content text not null,
  related_tables jsonb not null default '[]'::jsonb,
  related_columns jsonb not null default '[]'::jsonb,
  related_join_paths jsonb not null default '[]'::jsonb,
  related_models jsonb not null default '[]'::jsonb,
  example_questions jsonb not null default '[]'::jsonb,
  sql_examples jsonb not null default '[]'::jsonb,
  sql_usable boolean not null default true,
  embedding vector(768),
  embedding_model text,
  created_at timestamp with time zone not null default now(),
  updated_at timestamp with time zone not null default now()
);

create index if not exists idx_cld_verified_sql_context_sql_usable
  on public.cld_verified_sql_context_documents(sql_usable, document_type);
"""


def connect(database_url: str):
    return psycopg.connect(database_url, row_factory=dict_row, connect_timeout=30)


def latest_snapshot_id(cur) -> str:
    cur.execute(
        "select snapshot_id from public.cld_actual_schema_snapshot order by snapshot_timestamp desc limit 1"
    )
    row = cur.fetchone()
    if not row:
        raise RuntimeError("No actual schema snapshot found. Run build_actual_schema_catalog.py first.")
    return str(row["snapshot_id"])


def build_documents(database_url: str) -> dict[str, Any]:
    with connect(database_url) as conn:
        with conn.cursor() as cur:
            cur.execute(DDL)
            snapshot_id = latest_snapshot_id(cur)
            cur.execute(
                """
                delete from public.cld_verified_sql_context_documents
                where document_type in ('actual_table_description', 'actual_column_description', 'verified_join_path')
                """
            )
            created = 0

            cur.execute(
                """
                select t.*, coalesce(jsonb_agg(c.column_name order by c.ordinal_position)
                  filter (where c.column_name is not null), '[]'::jsonb) as columns
                from public.cld_actual_table_catalog t
                left join public.cld_actual_column_catalog c
                  on c.snapshot_id = t.snapshot_id
                 and c.schema_name = t.schema_name
                 and c.table_name = t.table_name
                where t.snapshot_id = %s
                  and t.is_sql_allowed = true
                  and t.is_planned_only = false
                group by t.table_catalog_id, t.snapshot_id, t.schema_name, t.table_name,
                         t.full_table_name, t.table_type, t.estimated_row_count, t.business_domain,
                         t.business_description, t.table_grain, t.primary_key_columns,
                         t.is_sql_allowed, t.is_planned_only, t.created_at, t.updated_at
                order by t.full_table_name
                """,
                (snapshot_id,),
            )
            for row in cur.fetchall():
                columns = list(row["columns"] or [])
                content = (
                    f"Actual table: {row['full_table_name']}\n"
                    f"Business domain: {row['business_domain'] or 'General Insurance'}\n"
                    f"Description: {row['business_description'] or ''}\n"
                    f"Grain: {row['table_grain'] or ''}\n"
                    f"Columns: {', '.join(columns)}\n"
                    "SQL rule: This is a real Supabase table and may be used for read-only SELECT/WITH SQL."
                )
                cur.execute(
                    """
                    insert into public.cld_verified_sql_context_documents (
                      context_id, title, document_type, business_domain, content,
                      related_tables, related_columns, sql_usable, created_at, updated_at
                    ) values (%s, %s, 'actual_table_description', %s, %s, %s::jsonb, %s::jsonb, true, now(), now())
                    """,
                    (
                        str(uuid4()),
                        f"Actual table {row['full_table_name']}",
                        row["business_domain"],
                        content,
                        Jsonb([row["full_table_name"]]),
                        Jsonb([f"{row['full_table_name']}.{column}" for column in columns]),
                    ),
                )
                created += 1

            cur.execute(
                """
                select *
                from public.cld_actual_relationship_catalog
                where snapshot_id = %s and is_verified = true
                order by source_schema, source_table, source_column
                """,
                (snapshot_id,),
            )
            for row in cur.fetchall():
                source = f"{row['source_schema']}.{row['source_table']}"
                target = f"{row['target_schema']}.{row['target_table']}"
                join_sql = f"{source}.{row['source_column']} = {target}.{row['target_column']}"
                content = (
                    f"Verified join path from actual foreign key metadata.\n"
                    f"Source: {source}.{row['source_column']}\n"
                    f"Target: {target}.{row['target_column']}\n"
                    f"Join SQL: {join_sql}\n"
                    "SQL rule: Prefer this join when both tables are needed."
                )
                cur.execute(
                    """
                    insert into public.cld_verified_sql_context_documents (
                      context_id, title, document_type, business_domain, content,
                      related_tables, related_columns, related_join_paths, sql_usable, created_at, updated_at
                    ) values (%s, %s, 'verified_join_path', %s, %s, %s::jsonb, %s::jsonb, %s::jsonb, true, now(), now())
                    """,
                    (
                        str(uuid4()),
                        f"Verified join {source} to {target}",
                        row.get("business_description") or "Verified Join",
                        content,
                        Jsonb([source, target]),
                        Jsonb([f"{source}.{row['source_column']}", f"{target}.{row['target_column']}"]),
                        Jsonb([join_sql]),
                    ),
                )
                created += 1
        conn.commit()
    return {"snapshot_id": snapshot_id, "verified_context_documents_created": created}


def main() -> int:
    parser = argparse.ArgumentParser(description="Build verified SQL context documents from actual schema catalog.")
    parser.add_argument("--env-file", default=".env")
    args = parser.parse_args()
    load_dotenv(args.env_file, override=True)
    print(json.dumps(build_documents(os.environ["SUPABASE_DB_URL"]), indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
