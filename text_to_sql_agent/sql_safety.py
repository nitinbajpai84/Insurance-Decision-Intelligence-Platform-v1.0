from __future__ import annotations

import re
from dataclasses import dataclass

import sqlglot
from sqlglot import exp


BLOCKED_KEYWORDS = {
    "alter",
    "analyze",
    "attach",
    "call",
    "comment",
    "copy",
    "create",
    "delete",
    "detach",
    "do",
    "drop",
    "execute",
    "grant",
    "insert",
    "listen",
    "merge",
    "notify",
    "refresh",
    "reindex",
    "reset",
    "revoke",
    "security",
    "set",
    "truncate",
    "unlisten",
    "update",
    "vacuum",
}


@dataclass(frozen=True)
class ValidationResult:
    sql: str
    referenced_tables: set[str]


class SqlSafetyError(ValueError):
    pass


def validate_select_sql(sql: str, *, allowed_schemas: set[str], row_limit: int) -> ValidationResult:
    normalized = strip_sql_comments(sql).strip().rstrip(";")
    if not normalized:
        raise SqlSafetyError("Generated SQL is empty")
    if ";" in normalized:
        raise SqlSafetyError("Only one SQL statement is allowed")

    tokens = set(re.findall(r"\b[a-z_][a-z0-9_]*\b", normalized.lower()))
    blocked = sorted(tokens & BLOCKED_KEYWORDS)
    if blocked:
        raise SqlSafetyError(f"Blocked SQL keyword(s): {', '.join(blocked)}")

    try:
        parsed = sqlglot.parse_one(normalized, read="postgres")
    except Exception as exc:
        raise SqlSafetyError(f"SQL parse failed: {exc}") from exc

    if not isinstance(parsed, (exp.Select, exp.Union)):
        raise SqlSafetyError("Only SELECT queries are allowed")
    if list(parsed.find_all((exp.Insert, exp.Update, exp.Delete, exp.Drop, exp.Create, exp.Alter, exp.Command))):
        raise SqlSafetyError("SQL contains a non-read-only operation")

    referenced_tables = set()
    for table in parsed.find_all(exp.Table):
        schema = table.db or "public"
        name = table.name
        if schema not in allowed_schemas:
            raise SqlSafetyError(f"Schema not allowed: {schema}")
        referenced_tables.add(f"{schema}.{name}")

    limited_sql = ensure_outer_limit(normalized, row_limit)
    return ValidationResult(sql=limited_sql, referenced_tables=referenced_tables)


def strip_sql_comments(sql: str) -> str:
    without_block = re.sub(r"/\*.*?\*/", " ", sql, flags=re.DOTALL)
    return re.sub(r"--.*?$", " ", without_block, flags=re.MULTILINE)


def ensure_outer_limit(sql: str, row_limit: int) -> str:
    return f"select * from ({sql}) as text_to_sql_limited_result limit {row_limit}"
