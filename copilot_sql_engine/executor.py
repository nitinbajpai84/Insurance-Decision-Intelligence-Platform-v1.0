from __future__ import annotations

import time
from typing import Any

import psycopg
from psycopg.rows import dict_row


def connect(database_url: str):
    return psycopg.connect(database_url, row_factory=dict_row, connect_timeout=30)


def execute_select(conn, *, sql: str, timeout_ms: int) -> tuple[list[str], list[dict[str, Any]], int]:
    start = time.perf_counter()
    with conn.transaction():
        with conn.cursor() as cur:
            cur.execute("set transaction read only")
            cur.execute("select set_config('statement_timeout', %s, true)", (f"{timeout_ms}ms",))
            # Generated SQL is already validated and is executed without
            # parameters. Escape literal percent signs so psycopg doesn't treat
            # LIKE '%text%' patterns as client-side placeholders.
            cur.execute(escape_literal_percent_signs(sql))
            rows = cur.fetchall()
            columns = [desc.name for desc in cur.description] if cur.description else []
    duration_ms = int((time.perf_counter() - start) * 1000)
    return columns, [dict(row) for row in rows], duration_ms


def escape_literal_percent_signs(sql: str) -> str:
    return sql.replace("%", "%%")


def json_safe_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    safe: list[dict[str, Any]] = []
    for row in rows:
        safe.append({key: json_safe_value(value) for key, value in row.items()})
    return safe


def json_safe_value(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)
