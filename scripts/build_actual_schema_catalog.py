from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

import psycopg
from dotenv import load_dotenv
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb


CATALOG_DDL = """
create extension if not exists pgcrypto;

create table if not exists public.cld_actual_schema_snapshot (
  snapshot_id uuid primary key,
  snapshot_timestamp timestamp with time zone not null,
  schema_name text not null,
  table_count int not null default 0,
  column_count int not null default 0,
  relationship_count int not null default 0,
  status text not null default 'created',
  created_at timestamp with time zone not null default now()
);

create table if not exists public.cld_actual_table_catalog (
  table_catalog_id uuid primary key,
  snapshot_id uuid references public.cld_actual_schema_snapshot(snapshot_id) on delete cascade,
  schema_name text not null,
  table_name text not null,
  full_table_name text not null,
  table_type text,
  estimated_row_count bigint,
  business_domain text,
  business_description text,
  table_grain text,
  primary_key_columns jsonb not null default '[]'::jsonb,
  is_sql_allowed boolean not null default true,
  is_planned_only boolean not null default false,
  created_at timestamp with time zone not null default now(),
  updated_at timestamp with time zone not null default now()
);

create table if not exists public.cld_actual_column_catalog (
  column_catalog_id uuid primary key,
  snapshot_id uuid references public.cld_actual_schema_snapshot(snapshot_id) on delete cascade,
  schema_name text not null,
  table_name text not null,
  column_name text not null,
  data_type text,
  is_nullable boolean,
  ordinal_position int,
  business_name text,
  business_description text,
  semantic_type text,
  is_metric boolean not null default false,
  is_dimension boolean not null default false,
  is_join_key boolean not null default false,
  is_pii boolean not null default false,
  example_values jsonb not null default '[]'::jsonb,
  is_sql_allowed boolean not null default true,
  created_at timestamp with time zone not null default now(),
  updated_at timestamp with time zone not null default now()
);

create table if not exists public.cld_actual_relationship_catalog (
  relationship_id uuid primary key,
  snapshot_id uuid references public.cld_actual_schema_snapshot(snapshot_id) on delete cascade,
  source_schema text not null,
  source_table text not null,
  source_column text not null,
  target_schema text not null,
  target_table text not null,
  target_column text not null,
  constraint_name text,
  relationship_type text,
  business_description text,
  is_verified boolean not null default true,
  created_at timestamp with time zone not null default now()
);

create table if not exists public.cld_actual_join_path_catalog (
  join_path_id uuid primary key,
  business_domain text,
  question_type text,
  source_table text not null,
  target_table text not null,
  join_sql text not null,
  join_reason text,
  confidence_score numeric,
  is_verified boolean not null default true,
  created_at timestamp with time zone not null default now()
);

create index if not exists idx_cld_actual_table_catalog_schema_table
  on public.cld_actual_table_catalog(schema_name, table_name);
create index if not exists idx_cld_actual_table_catalog_full_name
  on public.cld_actual_table_catalog(full_table_name);
create index if not exists idx_cld_actual_column_catalog_schema_table_column
  on public.cld_actual_column_catalog(schema_name, table_name, column_name);
create index if not exists idx_cld_actual_relationship_source
  on public.cld_actual_relationship_catalog(source_schema, source_table, source_column);
create index if not exists idx_cld_actual_relationship_target
  on public.cld_actual_relationship_catalog(target_schema, target_table, target_column);
create index if not exists idx_cld_actual_join_path_tables
  on public.cld_actual_join_path_catalog(source_table, target_table);
"""


@dataclass
class CatalogSummary:
    snapshot_id: str
    schemas: list[str]
    tables_found: int
    columns_found: int
    relationships_found: int
    join_paths_created: int
    tables_excluded: list[str]
    errors: list[str]


def connect(database_url: str):
    return psycopg.connect(database_url, row_factory=dict_row, connect_timeout=30)


def infer_domain(table_name: str) -> str:
    name = table_name.lower()
    if any(token in name for token in ["customer", "party", "address", "engagement", "complaint", "nps", "satisfaction", "service"]):
        return "Customer"
    if any(token in name for token in ["policy", "premium", "payment", "product", "coverage", "renewal", "lapse"]):
        return "Policy"
    if any(token in name for token in ["agent", "mapa", "commission", "training", "movement", "target", "meeting", "call"]):
        return "Agent"
    if any(token in name for token in ["campaign", "lead", "opportun", "quote", "proposal", "application"]):
        return "Sales and Campaign"
    if "claim" in name or "fraud" in name:
        return "Claims"
    if any(token in name for token in ["model", "feature", "score", "prediction", "next_best"]):
        return "ML Decisioning"
    if any(token in name for token in ["semantic", "glossary", "catalog", "context", "insight", "lineage", "evidence", "llm"]):
        return "AI Governance"
    return "General Insurance"


def infer_grain(table_name: str, primary_keys: list[str]) -> str:
    if primary_keys:
        return f"One row per {', '.join(primary_keys)}."
    stem = table_name[:-1] if table_name.endswith("s") else table_name
    return f"One row per {stem.replace('_', ' ')} record."


def infer_semantic_type(column_name: str, data_type: str) -> str:
    col = column_name.lower()
    dtype = (data_type or "").lower()
    if col.endswith("_id") or col == "id" or col.endswith("_uuid"):
        return "identifier"
    if col.endswith("_at") or "date" in col or "timestamp" in dtype:
        return "date"
    if any(token in col for token in ["amount", "premium", "commission", "sum_assured", "income", "cost", "budget", "roi", "clv"]):
        return "amount"
    if any(token in col for token in ["score", "rate", "ratio", "pct", "probability", "confidence"]):
        return "score"
    if "status" in col or "stage" in col:
        return "status"
    if dtype in {"json", "jsonb"}:
        return "json"
    if dtype in {"numeric", "decimal", "double precision", "real", "integer", "bigint", "smallint"}:
        return "metric"
    if "text" in dtype or "character" in dtype:
        return "text"
    return "dimension"


def business_name(column_name: str) -> str:
    return column_name.replace("_", " ").title()


def read_tables(cur, schemas: list[str]) -> list[dict[str, Any]]:
    cur.execute(
        """
        select
          t.table_schema as schema_name,
          t.table_name,
          t.table_type,
          coalesce(c.reltuples::bigint, 0) as estimated_row_count
        from information_schema.tables t
        left join pg_catalog.pg_namespace n on n.nspname = t.table_schema
        left join pg_catalog.pg_class c on c.relnamespace = n.oid and c.relname = t.table_name
        where t.table_schema = any(%s)
          and t.table_type in ('BASE TABLE', 'VIEW')
          and t.table_name not like 'pg_%%'
          and t.table_name not like '_prisma_%%'
        order by t.table_schema, t.table_name
        """,
        (schemas,),
    )
    return [dict(row) for row in cur.fetchall()]


def read_columns(cur, schemas: list[str]) -> list[dict[str, Any]]:
    cur.execute(
        """
        select
          table_schema as schema_name,
          table_name,
          column_name,
          case when data_type = 'USER-DEFINED' then udt_name else data_type end as data_type,
          is_nullable = 'YES' as is_nullable,
          ordinal_position
        from information_schema.columns
        where table_schema = any(%s)
          and table_name not like 'pg_%%'
        order by table_schema, table_name, ordinal_position
        """,
        (schemas,),
    )
    return [dict(row) for row in cur.fetchall()]


def read_primary_keys(cur, schemas: list[str]) -> dict[tuple[str, str], list[str]]:
    cur.execute(
        """
        select
          kcu.table_schema as schema_name,
          kcu.table_name,
          kcu.column_name
        from information_schema.table_constraints tc
        join information_schema.key_column_usage kcu
          on tc.constraint_name = kcu.constraint_name
         and tc.table_schema = kcu.table_schema
         and tc.table_name = kcu.table_name
        where tc.constraint_type = 'PRIMARY KEY'
          and tc.table_schema = any(%s)
        order by kcu.table_schema, kcu.table_name, kcu.ordinal_position
        """,
        (schemas,),
    )
    keys: dict[tuple[str, str], list[str]] = {}
    for row in cur.fetchall():
        keys.setdefault((row["schema_name"], row["table_name"]), []).append(row["column_name"])
    return keys


def read_foreign_keys(cur, schemas: list[str]) -> list[dict[str, Any]]:
    cur.execute(
        """
        select
          kcu.table_schema as source_schema,
          kcu.table_name as source_table,
          kcu.column_name as source_column,
          ccu.table_schema as target_schema,
          ccu.table_name as target_table,
          ccu.column_name as target_column,
          tc.constraint_name
        from information_schema.table_constraints tc
        join information_schema.key_column_usage kcu
          on tc.constraint_name = kcu.constraint_name
         and tc.table_schema = kcu.table_schema
        join information_schema.constraint_column_usage ccu
          on ccu.constraint_name = tc.constraint_name
         and ccu.table_schema = tc.table_schema
        where tc.constraint_type = 'FOREIGN KEY'
          and kcu.table_schema = any(%s)
        order by source_schema, source_table, source_column
        """,
        (schemas,),
    )
    return [dict(row) for row in cur.fetchall()]


def create_snapshot(database_url: str, schemas: list[str]) -> CatalogSummary:
    errors: list[str] = []
    snapshot_id = str(uuid4())
    created_at = datetime.now(timezone.utc)
    excluded: list[str] = []

    with connect(database_url) as conn:
        with conn.cursor() as cur:
            cur.execute(CATALOG_DDL)
            tables = read_tables(cur, schemas)
            columns = read_columns(cur, schemas)
            pks = read_primary_keys(cur, schemas)
            fks = read_foreign_keys(cur, schemas)

            cur.execute(
                """
                insert into public.cld_actual_schema_snapshot (
                  snapshot_id, snapshot_timestamp, schema_name, table_count, column_count,
                  relationship_count, status, created_at
                ) values (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (snapshot_id, created_at, ",".join(schemas), len(tables), len(columns), len(fks), "created", created_at),
            )

            for table in tables:
                key = (table["schema_name"], table["table_name"])
                primary_keys = pks.get(key, [])
                cur.execute(
                    """
                    insert into public.cld_actual_table_catalog (
                      table_catalog_id, snapshot_id, schema_name, table_name, full_table_name,
                      table_type, estimated_row_count, business_domain, business_description,
                      table_grain, primary_key_columns, is_sql_allowed, is_planned_only,
                      created_at, updated_at
                    ) values (
                      %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, true, false, %s, %s
                    )
                    """,
                    (
                        str(uuid4()),
                        snapshot_id,
                        table["schema_name"],
                        table["table_name"],
                        f'{table["schema_name"]}.{table["table_name"]}',
                        table["table_type"],
                        table["estimated_row_count"],
                        infer_domain(table["table_name"]),
                        f'Actual {table["table_name"].replace("_", " ")} data found in Supabase metadata.',
                        infer_grain(table["table_name"], primary_keys),
                        Jsonb(primary_keys),
                        created_at,
                        created_at,
                    ),
                )

            fk_columns = {(fk["source_schema"], fk["source_table"], fk["source_column"]) for fk in fks}
            for column in columns:
                semantic_type = infer_semantic_type(column["column_name"], column["data_type"])
                is_metric = semantic_type in {"amount", "score", "metric"}
                is_join_key = (
                    (column["schema_name"], column["table_name"], column["column_name"]) in fk_columns
                    or column["column_name"].lower().endswith("_id")
                )
                is_pii = column["column_name"].lower() in {"email", "phone", "phone_number", "mobile", "display_name", "first_name", "last_name"}
                cur.execute(
                    """
                    insert into public.cld_actual_column_catalog (
                      column_catalog_id, snapshot_id, schema_name, table_name, column_name,
                      data_type, is_nullable, ordinal_position, business_name, business_description,
                      semantic_type, is_metric, is_dimension, is_join_key, is_pii,
                      example_values, is_sql_allowed, created_at, updated_at
                    ) values (
                      %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                      %s, %s, %s, %s, '[]'::jsonb, true, %s, %s
                    )
                    """,
                    (
                        str(uuid4()),
                        snapshot_id,
                        column["schema_name"],
                        column["table_name"],
                        column["column_name"],
                        column["data_type"],
                        column["is_nullable"],
                        column["ordinal_position"],
                        business_name(column["column_name"]),
                        f'Actual column {column["column_name"]} on {column["schema_name"]}.{column["table_name"]}.',
                        semantic_type,
                        is_metric,
                        not is_metric,
                        is_join_key,
                        is_pii,
                        created_at,
                        created_at,
                    ),
                )

            for fk in fks:
                join_sql = (
                    f'{fk["source_schema"]}.{fk["source_table"]}.{fk["source_column"]} = '
                    f'{fk["target_schema"]}.{fk["target_table"]}.{fk["target_column"]}'
                )
                cur.execute(
                    """
                    insert into public.cld_actual_relationship_catalog (
                      relationship_id, snapshot_id, source_schema, source_table, source_column,
                      target_schema, target_table, target_column, constraint_name,
                      relationship_type, business_description, is_verified, created_at
                    ) values (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'foreign_key', %s, true, %s)
                    """,
                    (
                        str(uuid4()),
                        snapshot_id,
                        fk["source_schema"],
                        fk["source_table"],
                        fk["source_column"],
                        fk["target_schema"],
                        fk["target_table"],
                        fk["target_column"],
                        fk["constraint_name"],
                        f'Verified foreign key join path: {join_sql}.',
                        created_at,
                    ),
                )
                cur.execute(
                    """
                    insert into public.cld_actual_join_path_catalog (
                      join_path_id, business_domain, question_type, source_table, target_table,
                      join_sql, join_reason, confidence_score, is_verified, created_at
                    ) values (%s, %s, 'verified_fk_join', %s, %s, %s, %s, 1.0, true, %s)
                    """,
                    (
                        str(uuid4()),
                        infer_domain(fk["source_table"]),
                        f'{fk["source_schema"]}.{fk["source_table"]}',
                        f'{fk["target_schema"]}.{fk["target_table"]}',
                        join_sql,
                        "Actual foreign key discovered from information_schema.",
                        created_at,
                    ),
                )

            cur.execute("update public.cld_actual_schema_snapshot set status = 'completed' where snapshot_id = %s", (snapshot_id,))
        conn.commit()

    return CatalogSummary(
        snapshot_id=snapshot_id,
        schemas=schemas,
        tables_found=len(tables),
        columns_found=len(columns),
        relationships_found=len(fks),
        join_paths_created=len(fks),
        tables_excluded=excluded,
        errors=errors,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build actual Supabase schema catalog tables from information_schema.")
    parser.add_argument("--env-file", default=".env")
    parser.add_argument("--schemas", default="public")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    load_dotenv(args.env_file, override=True)
    database_url = os.getenv("SUPABASE_DB_URL", "").strip()
    if not database_url:
        raise SystemExit("SUPABASE_DB_URL is required")
    schemas = [item.strip() for item in args.schemas.split(",") if item.strip()]
    summary = create_snapshot(database_url, schemas)
    print(json.dumps(summary.__dict__, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
