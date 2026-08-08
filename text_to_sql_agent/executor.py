from __future__ import annotations

import time
from typing import Any


def execute_readonly_query(conn, *, sql: str, timeout_ms: int) -> tuple[list[str], list[dict[str, Any]], int]:
    start = time.perf_counter()
    with conn.transaction():
        with conn.cursor() as cur:
            cur.execute("set transaction read only")
            cur.execute("select set_config('statement_timeout', %s, true)", (f"{timeout_ms}ms",))
            # Generated SELECT SQL is already validated and is executed without
            # parameters. Escape literal percent signs so psycopg doesn't treat
            # LIKE '%text%' patterns as client-side placeholders.
            cur.execute(escape_literal_percent_signs(sql))
            rows = cur.fetchall()
            columns = [desc.name for desc in cur.description] if cur.description else []
    duration_ms = int((time.perf_counter() - start) * 1000)
    return columns, rows, duration_ms


def escape_literal_percent_signs(sql: str) -> str:
    return sql.replace("%", "%%")
