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


class SqlValidationError(ValueError):
    pass


@dataclass(frozen=True)
class SafeSql:
    sql: str
    referenced_tables: set[str]


def strip_sql_comments(sql: str) -> str:
    without_block = re.sub(r"/\*.*?\*/", " ", sql, flags=re.DOTALL)
    return re.sub(r"--.*?$", " ", without_block, flags=re.MULTILINE)


def validate_sql(sql: str, *, allowed_schemas: set[str], row_limit: int) -> SafeSql:
    normalized = strip_sql_comments(sql).strip().rstrip(";").strip()
    if not normalized:
        raise SqlValidationError("SQL is empty")
    if ";" in normalized:
        raise SqlValidationError("Only one SQL statement is allowed")

    first_token = re.match(r"^\s*([a-zA-Z_]+)", normalized)
    if not first_token or first_token.group(1).lower() not in {"select", "with"}:
        raise SqlValidationError("Only SELECT or WITH statements are allowed")

    tokens = set(re.findall(r"\b[a-z_][a-z0-9_]*\b", normalized.lower()))
    blocked = sorted(tokens & BLOCKED_KEYWORDS)
    if blocked:
        raise SqlValidationError(f"Blocked SQL keyword(s): {', '.join(blocked)}")

    try:
        parsed = sqlglot.parse_one(normalized, read="postgres")
    except Exception as exc:
        raise SqlValidationError(f"SQL parse failed: {exc}") from exc

    if not isinstance(parsed, exp.Select):
        raise SqlValidationError("Only SELECT/WITH queries are allowed")

    blocked_nodes = (
        exp.Insert,
        exp.Update,
        exp.Delete,
        exp.Drop,
        exp.Create,
        exp.Alter,
        exp.Command,
        exp.Merge,
    )
    if list(parsed.find_all(blocked_nodes)):
        raise SqlValidationError("SQL contains a non-read-only operation")

    referenced_tables: set[str] = set()
    cte_aliases = {cte.alias for cte in parsed.find_all(exp.CTE) if cte.alias}
    for table in parsed.find_all(exp.Table):
        if table.name in cte_aliases:
            continue
        schema = table.db or "public"
        if schema not in allowed_schemas:
            raise SqlValidationError(f"Schema not allowed: {schema}")
        referenced_tables.add(f"{schema}.{table.name}")

    return SafeSql(sql=ensure_outer_limit(normalized, row_limit), referenced_tables=referenced_tables)


def ensure_outer_limit(sql: str, row_limit: int) -> str:
    return f"select * from ({sql}) as intelligence_sql_limited_result limit {row_limit}"
