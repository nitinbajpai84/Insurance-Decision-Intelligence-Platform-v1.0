from __future__ import annotations

from typing import Any


def has_table(conn, schema_name: str, table_name: str) -> bool:
    with conn.cursor() as cur:
        cur.execute(
            """
            select exists (
              select 1
              from information_schema.tables
              where table_schema = %s
                and table_name = %s
            ) as present
            """,
            (schema_name, table_name),
        )
        row = cur.fetchone()
        if not row:
            return False
        if isinstance(row, dict):
            return bool(row.get("present"))
        return bool(row[0])


def governance_registry_exists(conn) -> bool:
    return has_table(conn, "public", "cld_table_registry")


def load_ai_sql_allowlist(conn, allowed_schemas: set[str]) -> set[str]:
    if not governance_registry_exists(conn):
        return set()
    with conn.cursor() as cur:
        cur.execute(
            """
            select schema_name || '.' || table_name as full_table_name
            from public.cld_table_registry
            where coalesce(ai_sql_allowed, false) = true
              and schema_name = any(%s)
            """,
            (list(allowed_schemas),),
        )
        allowlist: set[str] = set()
        for row in cur.fetchall():
            if not row:
                continue
            if isinstance(row, dict):
                value = row.get("full_table_name")
            else:
                value = row[0]
            if value:
                allowlist.add(str(value))
        return allowlist


def load_table_registry_rows(conn, allowed_schemas: set[str]) -> list[dict[str, Any]]:
    if not governance_registry_exists(conn):
        return []
    with conn.cursor() as cur:
        cur.execute(
            """
            select *
            from public.cld_table_registry
            where schema_name = any(%s)
            order by schema_name, table_name
            """,
            (list(allowed_schemas),),
        )
        columns = [desc[0] for desc in cur.description or []]
        rows = cur.fetchall()
        if rows and isinstance(rows[0], dict):
            return [dict(row) for row in rows]
        return [dict(zip(columns, row)) for row in rows]


def load_kpi_rows(conn, allowed_schemas: set[str]) -> list[dict[str, Any]]:
    if not has_table(conn, "public", "cld_kpi_registry"):
        return []
    with conn.cursor() as cur:
        cur.execute("select * from public.cld_kpi_registry order by kpi_name")
        rows = cur.fetchall()
        if rows and isinstance(rows[0], dict):
            return [dict(row) for row in rows]
        columns = [desc[0] for desc in cur.description or []]
        return [dict(zip(columns, row)) for row in rows]


def load_model_rows(conn, allowed_schemas: set[str]) -> list[dict[str, Any]]:
    if not has_table(conn, "public", "cld_model_registry"):
        return []
    with conn.cursor() as cur:
        cur.execute("select * from public.cld_model_registry order by model_name")
        rows = cur.fetchall()
        if rows and isinstance(rows[0], dict):
            return [dict(row) for row in rows]
        columns = [desc[0] for desc in cur.description or []]
        return [dict(zip(columns, row)) for row in rows]


def load_context_rows(conn, allowed_schemas: set[str]) -> list[dict[str, Any]]:
    if not has_table(conn, "public", "cld_context_registry"):
        return []
    with conn.cursor() as cur:
        cur.execute("select * from public.cld_context_registry order by context_type, title")
        rows = cur.fetchall()
        if rows and isinstance(rows[0], dict):
            return [dict(row) for row in rows]
        columns = [desc[0] for desc in cur.description or []]
        return [dict(zip(columns, row)) for row in rows]


def load_guardrail_rows(conn) -> list[dict[str, Any]]:
    if not has_table(conn, "public", "cld_sql_guardrail_rules"):
        return []
    with conn.cursor() as cur:
        cur.execute("select * from public.cld_sql_guardrail_rules order by rule_name")
        rows = cur.fetchall()
        if rows and isinstance(rows[0], dict):
            return [dict(row) for row in rows]
        columns = [desc[0] for desc in cur.description or []]
        return [dict(zip(columns, row)) for row in rows]
