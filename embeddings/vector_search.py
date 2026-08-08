#!/usr/bin/env python3
"""
Insurance PoC V2.0 — async vector search over LanceDB.

Each search function embeds the incoming query with gemini-embedding-001 and
runs a cosine-similarity search against one LanceDB table. `search_all` fans
out all four searches concurrently with asyncio.gather — never sequentially.

Returned `score` is cosine similarity in [0, 1] (1 = identical direction),
derived from LanceDB's `_distance` (cosine distance): score = 1 - distance.
"""
from __future__ import annotations

import asyncio
import os
import sys
from functools import lru_cache
from pathlib import Path
from typing import Any

import google.generativeai as genai
import lancedb
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL", "models/gemini-embedding-001")
LANCEDB_PATH = os.environ.get("LANCEDB_PATH", str(PROJECT_ROOT / "lance_store"))
VECTOR_DIMS = 3072
CACHE_SIMILARITY_THRESHOLD = float(os.environ.get("CACHE_SIMILARITY_THRESHOLD", "0.92"))

_api_key = os.environ.get("GEMINI_API_KEY", "").strip()
if _api_key:
    genai.configure(api_key=_api_key)


@lru_cache(maxsize=1)
def _db() -> lancedb.DBConnection:
    return lancedb.connect(LANCEDB_PATH)


# ---------------------------------------------------------------------------
# Sync embedding helper (used internally by every search function)
# ---------------------------------------------------------------------------
def embed_text(text: str) -> list[float]:
    """Embed `text` with gemini-embedding-001 -> 3072-dim vector."""
    result = genai.embed_content(
        model=EMBEDDING_MODEL,
        content=text[:9000],
        output_dimensionality=VECTOR_DIMS,
    )
    return list(result["embedding"])


async def _embed_async(text: str) -> list[float]:
    return await asyncio.to_thread(embed_text, text)


async def _search(
    table_name: str,
    vector: list[float],
    top_k: int,
    where: str | None = None,
) -> list[dict[str, Any]]:
    def _run() -> list[dict[str, Any]]:
        table = _db().open_table(table_name)
        query = table.search(vector).distance_type("cosine").limit(top_k)
        if where:
            query = query.where(where)
        rows = query.to_list()
        for row in rows:
            row["score"] = round(1.0 - float(row.get("_distance", 1.0)), 6)
        return rows

    return await asyncio.to_thread(_run)


def _escape(value: str) -> str:
    return value.replace("'", "''")


# ---------------------------------------------------------------------------
# Public async search API
# ---------------------------------------------------------------------------
async def search_glossary(query: str, top_k: int = 5, role: str | None = None) -> list[dict]:
    """Business-glossary lookup. `role` is accepted for API symmetry; glossary
    terms are role-agnostic today, so it does not filter."""
    vector = await _embed_async(query)
    rows = await _search("insurance_glossary_vectors", vector, top_k)
    return [
        {
            "term": r.get("term"),
            "definition": r.get("definition"),
            "subject_area": r.get("subject_area"),
            "score": r["score"],
        }
        for r in rows
    ]


async def search_semantic_docs(query: str, top_k: int = 5, doc_type: str | None = None) -> list[dict]:
    vector = await _embed_async(query)
    where = f"document_type = '{_escape(doc_type)}'" if doc_type else None
    rows = await _search("insurance_semantic_vectors", vector, top_k, where=where)
    return [
        {
            "document_title": r.get("document_title"),
            "content_chunk": r.get("content_chunk"),
            "chunk_index": r.get("chunk_index"),
            "score": r["score"],
        }
        for r in rows
    ]


async def search_schema(query: str, top_k: int = 10) -> list[dict]:
    """Semantic table/column discovery for the SQL agent —
    'which table has lapse scores?' -> model_scores.score_value etc."""
    vector = await _embed_async(query)
    rows = await _search("insurance_schema_vectors", vector, top_k)
    return [
        {
            "table_name": r.get("table_name"),
            "column_name": r.get("column_name"),
            "business_description": r.get("business_description"),
            "score": r["score"],
        }
        for r in rows
    ]


async def search_query_history(
    query: str,
    role: str,
    top_k: int = 3,
    similarity_threshold: float = CACHE_SIMILARITY_THRESHOLD,
) -> list[dict]:
    """Past Q&A retrieval. Any result with score >= similarity_threshold is a
    semantic-cache hit (each dict carries `cache_hit` for convenience)."""
    vector = await _embed_async(query)
    where = f"role = '{_escape(role)}'" if role else None
    rows = await _search("insurance_query_history", vector, top_k, where=where)
    if not rows and where:
        # fall back to cross-role history when this role has none
        rows = await _search("insurance_query_history", vector, top_k)
    return [
        {
            "question": r.get("question"),
            "answer_summary": r.get("answer_summary"),
            "sql_used": r.get("sql_used"),
            "confidence_score": r.get("confidence_score"),
            "score": r["score"],
            "cache_hit": r["score"] >= similarity_threshold,
        }
        for r in rows
    ]


async def search_all(query: str, role: str, top_k: int = 5) -> dict:
    """Run all four searches simultaneously (asyncio.gather) — one query
    embedding round-trip per search, all in parallel, never sequential."""
    glossary, docs, schema, history = await asyncio.gather(
        search_glossary(query, top_k=top_k, role=role),
        search_semantic_docs(query, top_k=top_k),
        search_schema(query, top_k=max(top_k, 10)),
        search_query_history(query, role, top_k=min(top_k, 3)),
        return_exceptions=True,
    )

    def _safe(result: Any, label: str) -> list:
        if isinstance(result, Exception):
            print(f"[search_all] {label} failed: {type(result).__name__}: {result}", file=sys.stderr)
            return []
        return result

    return {
        "glossary": _safe(glossary, "glossary"),
        "docs": _safe(docs, "docs"),
        "schema": _safe(schema, "schema"),
        "history": _safe(history, "history"),
    }


if __name__ == "__main__":
    async def _demo() -> None:
        question = sys.argv[1] if len(sys.argv) > 1 else "which table has lapse scores?"
        results = await search_all(question, role="Executive Leadership")
        for bucket, rows in results.items():
            print(f"\n== {bucket} ==")
            for row in rows[:3]:
                print(row)

    asyncio.run(_demo())
