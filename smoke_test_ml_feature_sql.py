"""Static smoke test for ML feature SQL scripts.

This checks that every index column in 007_ml_feature_tables.sql exists in the
corresponding view defined in 006_ml_feature_engineering_views.sql. It catches
the class of Supabase errors where a table is created from a view and a later
index references a column not exposed by that view.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path


VIEW_FILE = Path("006_ml_feature_engineering_views.sql")
TABLE_FILE = Path("007_ml_feature_tables.sql")


def top_level_keyword(text: str, keyword: str, start: int = 0) -> int:
    depth = 0
    in_single_quote = False
    keyword_lower = keyword.lower()
    i = start

    while i < len(text):
        char = text[i]
        if char == "'":
            in_single_quote = not in_single_quote
            i += 1
            continue

        if not in_single_quote:
            if char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
            elif depth == 0 and text[i : i + len(keyword_lower)].lower() == keyword_lower:
                before = text[i - 1] if i else " "
                after = text[i + len(keyword_lower)] if i + len(keyword_lower) < len(text) else " "
                if not (before.isalnum() or before == "_") and not (after.isalnum() or after == "_"):
                    return i
        i += 1

    return -1


def split_top_level_csv(text: str) -> list[str]:
    parts: list[str] = []
    depth = 0
    in_single_quote = False
    start = 0

    for i, char in enumerate(text):
        if char == "'":
            in_single_quote = not in_single_quote
        elif not in_single_quote:
            if char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
            elif char == "," and depth == 0:
                parts.append(text[start:i].strip())
                start = i + 1

    parts.append(text[start:].strip())
    return parts


def projected_column_name(expression: str) -> str | None:
    normalized = re.sub(r"\s+", " ", expression.strip())
    alias_match = re.search(r"\bas\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*$", normalized, re.IGNORECASE)
    if alias_match:
        return alias_match.group(1)

    simple_match = re.search(r"(?:[a-zA-Z_][a-zA-Z0-9_]*\.)?([a-zA-Z_][a-zA-Z0-9_]*)\s*$", normalized)
    if simple_match and "(" not in normalized:
        return simple_match.group(1)

    return None


def parse_view_columns(sql_text: str) -> dict[str, set[str]]:
    view_columns: dict[str, set[str]] = {}
    pattern = re.compile(
        r"create\s+or\s+replace\s+view\s+public\.(v_[a-zA-Z0-9_]+)\s+as\s+",
        re.IGNORECASE,
    )

    for match in pattern.finditer(sql_text):
        view_name = match.group(1)
        body_start = match.end()
        comment_match = re.search(
            r"\ncomment\s+on\s+view\s+public\." + re.escape(view_name),
            sql_text[body_start:],
            re.IGNORECASE,
        )
        body = sql_text[body_start : body_start + comment_match.start()] if comment_match else sql_text[body_start:]
        select_pos = top_level_keyword(body, "select")
        from_pos = top_level_keyword(body, "from", select_pos + len("select"))
        if select_pos < 0 or from_pos < 0:
            raise ValueError(f"Could not parse SELECT list for {view_name}")

        columns = {
            name
            for name in (
                projected_column_name(part)
                for part in split_top_level_csv(body[select_pos + len("select") : from_pos])
            )
            if name
        }
        view_columns[view_name] = columns

    return view_columns


def parse_table_sources(sql_text: str) -> dict[str, str]:
    return {
        match.group(1): match.group(2)
        for match in re.finditer(
            r"create\s+table\s+if\s+not\s+exists\s+public\.([a-zA-Z0-9_]+)\s+as\s+select\s+\*\s+from\s+public\.([a-zA-Z0-9_]+)",
            sql_text,
            re.IGNORECASE,
        )
    }


def parse_index_columns(sql_text: str) -> list[tuple[str, list[str]]]:
    indexes: list[tuple[str, list[str]]] = []
    for match in re.finditer(
        r"create\s+index\s+if\s+not\s+exists\s+\S+\s+on\s+public\.([a-zA-Z0-9_]+)\s*\(([^)]+)\)",
        sql_text,
        re.IGNORECASE,
    ):
        table_name = match.group(1)
        columns = [column.strip().split()[0] for column in match.group(2).split(",")]
        indexes.append((table_name, columns))
    return indexes


def main() -> int:
    views_sql = VIEW_FILE.read_text(encoding="utf-8")
    tables_sql = TABLE_FILE.read_text(encoding="utf-8")

    view_columns = parse_view_columns(views_sql)
    table_sources = parse_table_sources(tables_sql)
    errors: list[str] = []

    for table_name, index_columns in parse_index_columns(tables_sql):
        view_name = table_sources.get(table_name)
        if not view_name:
            errors.append(f"{table_name}: no source view found")
            continue

        available_columns = view_columns.get(view_name, set())
        for column in index_columns:
            if column not in available_columns:
                errors.append(
                    f"{table_name}: index column '{column}' is missing from {view_name}. "
                    f"Available columns: {sorted(available_columns)}"
                )

    if errors:
        print("SMOKE TEST FAILED")
        for error in errors:
            print(f"- {error}")
        return 1

    print("SMOKE TEST PASSED")
    for table_name, view_name in table_sources.items():
        print(f"- {table_name} <- {view_name}: {len(view_columns.get(view_name, []))} columns")
    return 0


if __name__ == "__main__":
    sys.exit(main())
