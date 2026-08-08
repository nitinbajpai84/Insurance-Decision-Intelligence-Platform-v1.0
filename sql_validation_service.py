from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

import sqlglot
from psycopg.rows import dict_row
from sqlglot import exp

from copilot_sql_engine.executor import escape_literal_percent_signs
from copilot_sql_engine.safety import SqlValidationError, strip_sql_comments, validate_sql


UNSAFE_FUNCTIONS = {
    "pg_sleep",
    "dblink",
    "lo_import",
    "lo_export",
    "pg_read_file",
    "pg_read_binary_file",
    "pg_ls_dir",
    "current_setting",
    "set_config",
}


@dataclass
class StrictSqlValidationResult:
    is_valid: bool
    validation_status: str
    sql: str | None = None
    tables_used: list[str] = field(default_factory=list)
    columns_used: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    explain_passed: bool = False
    explain_error: str | None = None
    missing_tables: list[str] = field(default_factory=list)
    missing_columns: list[str] = field(default_factory=list)
    repaired: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "is_valid": self.is_valid,
            "validation_status": self.validation_status,
            "sql": self.sql,
            "tables_used": self.tables_used,
            "columns_used": self.columns_used,
            "errors": self.errors,
            "explain_passed": self.explain_passed,
            "explain_error": self.explain_error,
            "missing_tables": self.missing_tables,
            "missing_columns": self.missing_columns,
            "repaired": self.repaired,
        }


def validate_sql_strict(
    conn,
    *,
    sql: str,
    allowed_schemas: set[str],
    allowed_tables: set[str] | None = None,
    row_limit: int,
    statement_timeout_ms: int = 5000,
) -> StrictSqlValidationResult:
    try:
        safe = validate_sql(sql, allowed_schemas=allowed_schemas, row_limit=row_limit)
    except SqlValidationError as exc:
        return StrictSqlValidationResult(
            is_valid=False,
            validation_status="SQL_VALIDATION_FAILED",
            errors=[str(exc)],
        )

    normalized = strip_sql_comments(sql).strip().rstrip(";").strip()
    try:
        parsed = sqlglot.parse_one(normalized, read="postgres")
    except Exception as exc:
        return StrictSqlValidationResult(
            is_valid=False,
            validation_status="SQL_PARSE_FAILED",
            errors=[f"SQL parse failed: {exc}"],
        )

    unsafe = sorted(
        {
            fn.name.lower()
            for fn in parsed.find_all(exp.Func)
            if getattr(fn, "name", None) and fn.name.lower() in UNSAFE_FUNCTIONS
        }
    )
    if unsafe:
        return StrictSqlValidationResult(
            is_valid=False,
            validation_status="SQL_VALIDATION_FAILED",
            sql=safe.sql,
            tables_used=sorted(safe.referenced_tables),
            errors=[f"Unsafe SQL function(s): {', '.join(unsafe)}"],
        )

    latest_snapshot_id = latest_actual_schema_snapshot_id(conn)
    actual_tables = fetch_actual_tables(conn, latest_snapshot_id, allowed_schemas)
    missing_tables = sorted(table for table in safe.referenced_tables if table not in actual_tables)
    if missing_tables:
        return StrictSqlValidationResult(
            is_valid=False,
            validation_status="SQL_VALIDATION_FAILED",
            sql=safe.sql,
            tables_used=sorted(safe.referenced_tables),
            errors=[f"Missing table(s) in actual Supabase schema: {', '.join(missing_tables)}"],
            missing_tables=missing_tables,
        )

    if allowed_tables is not None:
        disallowed_tables = sorted(table for table in safe.referenced_tables if table not in allowed_tables)
        if disallowed_tables:
            return StrictSqlValidationResult(
                is_valid=False,
                validation_status="SQL_VALIDATION_FAILED",
                sql=safe.sql,
                tables_used=sorted(safe.referenced_tables),
                errors=[f"Table(s) are not in the approved AI SQL allowlist: {', '.join(disallowed_tables)}"],
                missing_tables=disallowed_tables,
            )

    column_refs = extract_column_references(parsed)
    actual_columns = fetch_actual_columns(conn, latest_snapshot_id, allowed_schemas)
    alias_to_table = extract_alias_to_table(parsed)
    missing_columns = find_missing_columns(column_refs, alias_to_table, actual_columns)
    if missing_columns:
        return StrictSqlValidationResult(
            is_valid=False,
            validation_status="SQL_VALIDATION_FAILED",
            sql=safe.sql,
            tables_used=sorted(safe.referenced_tables),
            columns_used=sorted(column_refs),
            errors=[f"Missing column(s) in actual Supabase schema: {', '.join(missing_columns)}"],
            missing_columns=missing_columns,
        )

    explain_ok, explain_error = explain_sql(conn, safe.sql, statement_timeout_ms)
    if not explain_ok:
        return StrictSqlValidationResult(
            is_valid=False,
            validation_status="SQL_EXPLAIN_FAILED",
            sql=safe.sql,
            tables_used=sorted(safe.referenced_tables),
            columns_used=sorted(column_refs),
            errors=[explain_error or "EXPLAIN failed"],
            explain_passed=False,
            explain_error=explain_error,
        )

    return StrictSqlValidationResult(
        is_valid=True,
        validation_status="VALIDATED",
        sql=safe.sql,
        tables_used=sorted(safe.referenced_tables),
        columns_used=sorted(column_refs),
        explain_passed=True,
    )


def latest_actual_schema_snapshot_id(conn) -> str | None:
    try:
        with cursor_dict(conn) as cur:
            cur.execute(
                """
                select snapshot_id
                from public.cld_actual_schema_snapshot
                where status in ('created', 'completed')
                order by snapshot_timestamp desc
                limit 1
                """
            )
            row = cur.fetchone()
            return str(row["snapshot_id"]) if row else None
    except Exception:
        return None


def fetch_actual_tables(conn, snapshot_id: str | None, allowed_schemas: set[str]) -> set[str]:
    with cursor_dict(conn) as cur:
        if snapshot_id:
            cur.execute(
                """
                select full_table_name
                from public.cld_actual_table_catalog
                where snapshot_id = %s
                  and schema_name = any(%s)
                  and is_sql_allowed = true
                  and is_planned_only = false
                """,
                (snapshot_id, list(allowed_schemas)),
            )
        else:
            cur.execute(
                """
                select table_schema || '.' || table_name as full_table_name
                from information_schema.tables
                where table_schema = any(%s)
                  and table_type in ('BASE TABLE', 'VIEW')
                """,
                (list(allowed_schemas),),
            )
        return {row["full_table_name"] for row in cur.fetchall()}


def fetch_actual_columns(conn, snapshot_id: str | None, allowed_schemas: set[str]) -> dict[str, set[str]]:
    with cursor_dict(conn) as cur:
        if snapshot_id:
            cur.execute(
                """
                select schema_name, table_name, column_name
                from public.cld_actual_column_catalog
                where snapshot_id = %s
                  and schema_name = any(%s)
                  and is_sql_allowed = true
                """,
                (snapshot_id, list(allowed_schemas)),
            )
        else:
            cur.execute(
                """
                select table_schema as schema_name, table_name, column_name
                from information_schema.columns
                where table_schema = any(%s)
                """,
                (list(allowed_schemas),),
            )
        actual: dict[str, set[str]] = {}
        for row in cur.fetchall():
            actual.setdefault(f"{row['schema_name']}.{row['table_name']}", set()).add(row["column_name"])
        return actual


def cursor_dict(conn):
    try:
        return conn.cursor(row_factory=dict_row)
    except TypeError:
        return conn.cursor()


def extract_alias_to_table(parsed: exp.Expression) -> dict[str, str]:
    alias_map: dict[str, str] = {}
    cte_aliases = {cte.alias for cte in parsed.find_all(exp.CTE) if cte.alias}
    for table in parsed.find_all(exp.Table):
        if table.name in cte_aliases:
            continue
        full_name = f"{table.db or 'public'}.{table.name}"
        alias_map[table.name] = full_name
        if table.alias:
            alias_map[table.alias] = full_name
    return alias_map


def extract_column_references(parsed: exp.Expression) -> set[str]:
    columns: set[str] = set()
    for column in parsed.find_all(exp.Column):
        name = column.name
        table = column.table
        if name == "*":
            continue
        if table:
            columns.add(f"{table}.{name}")
        else:
            columns.add(name)
    return columns


def find_missing_columns(
    column_refs: set[str],
    alias_to_table: dict[str, str],
    actual_columns: dict[str, set[str]],
) -> list[str]:
    missing: list[str] = []
    for ref in sorted(column_refs):
        if "." not in ref:
            # Unqualified columns are left to EXPLAIN because SQLGlot cannot
            # safely infer the target table when aliases/CTEs are involved.
            continue
        table_or_alias, column = ref.rsplit(".", 1)
        full_table = alias_to_table.get(table_or_alias, table_or_alias)
        if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*\.[a-zA-Z_][a-zA-Z0-9_]*$", full_table):
            continue
        if full_table in actual_columns and column not in actual_columns[full_table]:
            missing.append(f"{full_table}.{column}")
    return missing


def explain_sql(conn, sql: str, statement_timeout_ms: int) -> tuple[bool, str | None]:
    try:
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute("set transaction read only")
                cur.execute("select set_config('statement_timeout', %s, true)", (f"{statement_timeout_ms}ms",))
                cur.execute(f"explain {escape_literal_percent_signs(sql)}")
                cur.fetchall()
        return True, None
    except Exception as exc:
        try:
            conn.rollback()
        except Exception:
            pass
        return False, str(exc)
