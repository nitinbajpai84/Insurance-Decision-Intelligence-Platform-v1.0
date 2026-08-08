"""Static smoke test for GenAI context-layer SQL.

The Supabase SQL editor catches runtime DDL errors late. This script checks
that 017_genai_context_layer_pgvector.sql creates every semantic_documents
column later referenced by its functions/indexes and by the sample seed script.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path


BASE_SCHEMA = Path("001_insurance_analytics_mvp_schema.sql")
CONTEXT_DDL = Path("017_genai_context_layer_pgvector.sql")
CONTEXT_SEED = Path("018_seed_insurance_copilot_context_documents.sql")


def base_semantic_columns(sql_text: str) -> set[str]:
    match = re.search(
        r"create\s+table\s+public\.semantic_documents\s*\((.*?)\n\);",
        sql_text,
        re.IGNORECASE | re.DOTALL,
    )
    if not match:
        raise ValueError("Could not find public.semantic_documents DDL in base schema.")
    columns: set[str] = set()
    for line in match.group(1).splitlines():
        line = line.strip().rstrip(",")
        if not line or line.lower().startswith(("unique ", "check ", "foreign ", "primary ")):
            continue
        name = line.split()[0].strip('"')
        columns.add(name)
    return columns


def added_semantic_columns(sql_text: str) -> set[str]:
    return set(re.findall(r"add\s+column\s+if\s+not\s+exists\s+([a-zA-Z_][a-zA-Z0-9_]*)", sql_text, re.IGNORECASE))


def referenced_sd_columns(sql_text: str) -> set[str]:
    return set(re.findall(r"\bsd\.([a-zA-Z_][a-zA-Z0-9_]*)", sql_text))


def inserted_seed_columns(sql_text: str) -> set[str]:
    match = re.search(
        r"insert\s+into\s+public\.semantic_documents\s*\((.*?)\)\s*values",
        sql_text,
        re.IGNORECASE | re.DOTALL,
    )
    if not match:
        raise ValueError("Could not find semantic_documents insert column list.")
    return {column.strip() for column in match.group(1).replace("\n", " ").split(",")}


def allowed_document_types(sql_text: str) -> set[str]:
    match = re.search(
        r"add\s+constraint\s+semantic_documents_document_type_check.*?document_type\s+in\s*\((.*?)\)\s*\);",
        sql_text,
        re.IGNORECASE | re.DOTALL,
    )
    if not match:
        raise ValueError("Could not find semantic_documents_document_type_check constraint.")
    return set(re.findall(r"'([^']+)'", match.group(1)))


def seeded_document_types(sql_text: str) -> set[str]:
    # The first value in each seed tuple is document_type.
    return set(re.findall(r"\(\s*\n\s*'([^']+)'\s*,\s*\n\s*'public'", sql_text))


def main() -> int:
    base_sql = BASE_SCHEMA.read_text(encoding="utf-8")
    ddl_sql = CONTEXT_DDL.read_text(encoding="utf-8")
    seed_sql = CONTEXT_SEED.read_text(encoding="utf-8")

    available_columns = base_semantic_columns(base_sql) | added_semantic_columns(ddl_sql)
    referenced_columns = referenced_sd_columns(ddl_sql)
    seed_columns = inserted_seed_columns(seed_sql)
    allowed_types = allowed_document_types(ddl_sql)
    seed_types = seeded_document_types(seed_sql)

    errors: list[str] = []

    missing_references = sorted(referenced_columns - available_columns)
    if missing_references:
        errors.append(f"017 references missing semantic_documents columns: {missing_references}")

    missing_seed_columns = sorted(seed_columns - available_columns)
    if missing_seed_columns:
        errors.append(f"018 inserts missing semantic_documents columns: {missing_seed_columns}")

    disallowed_types = sorted(seed_types - allowed_types)
    if disallowed_types:
        errors.append(f"018 uses document_type values not allowed by 017 constraint: {disallowed_types}")

    if errors:
        print("CONTEXT SQL SMOKE TEST FAILED")
        for error in errors:
            print(f"- {error}")
        return 1

    print("CONTEXT SQL SMOKE TEST PASSED")
    print(f"- semantic_documents available columns checked: {len(available_columns)}")
    print(f"- DDL sd.* references checked: {len(referenced_columns)}")
    print(f"- seed insert columns checked: {len(seed_columns)}")
    print(f"- seed document types checked: {sorted(seed_types)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
