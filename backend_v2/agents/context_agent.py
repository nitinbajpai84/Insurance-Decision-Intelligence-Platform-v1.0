"""
Context agent — parallel retrieval + token-budgeted assembly.

All four vector searches run SIMULTANEOUSLY via asyncio.gather (the query is
embedded once per search, each in its own thread — never sequential).
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from time import perf_counter
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend_v2.config import CACHE_SIMILARITY_THRESHOLD, CONTEXT_PRIORITY, MAX_CONTEXT_TOKENS
from backend_v2.agents.models import ContextResult
from embeddings.vector_search import (
    search_glossary,
    search_query_history,
    search_schema,
    search_semantic_docs,
)


def estimate_tokens(text: str) -> int:
    """Cheap estimator: ~4 chars per token."""
    return max(1, len(text) // 4) if text else 0


def _bucket_tokens(items: list[dict[str, Any]]) -> int:
    return sum(estimate_tokens(" ".join(str(v) for v in item.values())) for item in items)


async def get_context(question: str, role: str) -> ContextResult:
    started = perf_counter()
    result = ContextResult()

    glossary, docs, schema, history = await asyncio.gather(
        search_glossary(question, top_k=5, role=role),
        search_semantic_docs(question, top_k=5),
        search_schema(question, top_k=12),
        search_query_history(question, role, top_k=3),
        return_exceptions=True,
    )

    def safe(value: Any, label: str) -> list:
        if isinstance(value, Exception):
            result.errors.append(f"{label}: {type(value).__name__}: {value}")
            return []
        return value

    glossary = safe(glossary, "glossary")
    docs = safe(docs, "semantic_docs")
    schema = safe(schema, "schema")
    history = safe(history, "query_history")

    # Semantic cache check — best past answer above threshold wins
    for item in history:
        if item.get("cache_hit") and item.get("score", 0.0) >= CACHE_SIMILARITY_THRESHOLD:
            if item.get("score", 0.0) > result.cache_similarity:
                result.cache_hit = True
                result.cache_similarity = float(item["score"])
                result.cached_answer = item.get("answer_summary") or None

    result.glossary_terms = [
        {"term": g.get("term"), "definition": g.get("definition")} for g in glossary
    ]
    result.semantic_docs = [
        {"title": d.get("document_title"), "chunk": d.get("content_chunk"), "score": d.get("score")}
        for d in docs
    ]
    result.schema_context = [
        {"table": s.get("table_name"), "column": s.get("column_name"),
         "description": s.get("business_description"), "score": s.get("score")}
        for s in schema
    ]
    result.similar_past_queries = [
        {"question": h.get("question"), "answer": h.get("answer_summary"),
         "sql": h.get("sql_used"), "score": h.get("score")}
        for h in history
    ]

    _enforce_budget(result)
    result.assembly_time_ms = int((perf_counter() - started) * 1000)
    return result


def _enforce_budget(result: ContextResult) -> None:
    """Trim lowest-priority buckets first until under MAX_CONTEXT_TOKENS.

    Priority (kept first): schema_context > glossary_terms > semantic_docs > past_queries.
    """
    buckets: dict[str, list[dict[str, Any]]] = {
        "schema_context": result.schema_context,
        "glossary_terms": result.glossary_terms,
        "semantic_docs": result.semantic_docs,
        "past_queries": result.similar_past_queries,
    }

    def total() -> int:
        return sum(_bucket_tokens(items) for items in buckets.values())

    # Drop items one at a time from the lowest-priority non-empty bucket
    for bucket_name in reversed(CONTEXT_PRIORITY):
        while total() > MAX_CONTEXT_TOKENS and buckets[bucket_name]:
            buckets[bucket_name].pop()
        if total() <= MAX_CONTEXT_TOKENS:
            break

    result.schema_context = buckets["schema_context"]
    result.glossary_terms = buckets["glossary_terms"]
    result.semantic_docs = buckets["semantic_docs"]
    result.similar_past_queries = buckets["past_queries"]
    result.total_tokens_estimate = total()
