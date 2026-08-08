#!/usr/bin/env python3
"""
Insurance PoC V2.0 — LanceDB table setup.

Creates the five vector tables used by the V2 agentic stack. Idempotent:
existing tables are detected and skipped, so this can run on every deploy.

Vector dimension is 3072 (gemini-embedding-001 default output).

Run:  venv\\Scripts\\python.exe embeddings\\lance_setup.py
"""
from __future__ import annotations

import os
from pathlib import Path

import lancedb
import pyarrow as pa
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

VECTOR_DIMS = 3072
LANCEDB_PATH = os.environ.get(
    "LANCEDB_PATH", str(PROJECT_ROOT / "lance_store")
)


def _vector_field() -> pa.Field:
    return pa.field("vector", pa.list_(pa.float32(), VECTOR_DIMS))


TABLE_SCHEMAS: dict[str, pa.Schema] = {
    # a. Business glossary terms (KPIs, definitions)
    "insurance_glossary_vectors": pa.schema([
        pa.field("id", pa.string()),
        pa.field("term", pa.string()),
        pa.field("definition", pa.string()),
        pa.field("business_context", pa.string()),
        pa.field("subject_area", pa.string()),
        pa.field("source_table", pa.string()),
        pa.field("record_id", pa.string()),
        pa.field("text_chunk", pa.string()),
        pa.field("metadata", pa.string()),  # JSON string
        _vector_field(),
    ]),
    # b. Semantic documents (chunked context docs)
    "insurance_semantic_vectors": pa.schema([
        pa.field("id", pa.string()),
        pa.field("document_title", pa.string()),
        pa.field("document_type", pa.string()),
        pa.field("content_chunk", pa.string()),
        pa.field("chunk_index", pa.int32()),
        pa.field("source_table", pa.string()),
        pa.field("record_id", pa.string()),
        pa.field("text_chunk", pa.string()),
        pa.field("metadata", pa.string()),  # JSON string
        _vector_field(),
    ]),
    # c. Past Q&A pairs (semantic cache + few-shot retrieval)
    "insurance_query_history": pa.schema([
        pa.field("id", pa.string()),
        pa.field("question", pa.string()),
        pa.field("role", pa.string()),
        pa.field("answer_summary", pa.string()),
        pa.field("sql_used", pa.string()),
        pa.field("tables_used", pa.string()),
        pa.field("confidence_score", pa.float32()),
        pa.field("latency_ms", pa.int32()),
        pa.field("text_chunk", pa.string()),
        pa.field("metadata", pa.string()),  # JSON string
        _vector_field(),
    ]),
    # d. High-value entities (customers, agents, policies)
    "insurance_entity_vectors": pa.schema([
        pa.field("id", pa.string()),
        pa.field("entity_type", pa.string()),
        pa.field("entity_id", pa.string()),
        pa.field("entity_name", pa.string()),
        pa.field("description_text", pa.string()),
        pa.field("text_chunk", pa.string()),
        pa.field("metadata", pa.string()),  # JSON string
        _vector_field(),
    ]),
    # e. Schema catalog — semantic table/column discovery for the SQL agent
    #    e.g. "which table has lapse scores?" -> model_scores.score_value
    "insurance_schema_vectors": pa.schema([
        pa.field("id", pa.string()),
        pa.field("table_name", pa.string()),
        pa.field("column_name", pa.string()),
        pa.field("business_description", pa.string()),
        pa.field("data_type", pa.string()),
        pa.field("subject_area", pa.string()),
        pa.field("text_chunk", pa.string()),
        pa.field("metadata", pa.string()),  # JSON string
        _vector_field(),
    ]),
}


def main() -> int:
    db = lancedb.connect(LANCEDB_PATH)
    existing = set(db.list_tables().tables or [])
    created, skipped = [], []
    for name, schema in TABLE_SCHEMAS.items():
        if name in existing:
            skipped.append(name)
            continue
        db.create_table(name, schema=schema)
        created.append(name)

    print("LanceDB setup complete. Tables created:")
    for name in TABLE_SCHEMAS:
        suffix = " (already existed, skipped)" if name in skipped else ""
        print(f" - {name}{suffix}")
    print(f" Lance store path: {LANCEDB_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
