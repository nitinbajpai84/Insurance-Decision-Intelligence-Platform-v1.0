from __future__ import annotations

from embedding_pipeline.db import search_similar
from embedding_pipeline.providers import EmbeddingProvider

from .models import SemanticContextItem


def retrieve_semantic_context(
    conn,
    *,
    provider: EmbeddingProvider,
    question: str,
    match_count: int,
    threshold: float,
    business_domain: str | None,
    expected_dimensions: int,
) -> list[SemanticContextItem]:
    embedding = provider.embed_batch([question])
    if embedding.dimensions != expected_dimensions:
        raise ValueError(
            f"Question embedding dimension {embedding.dimensions} does not match expected dimension {expected_dimensions}"
        )
    rows = search_similar(
        conn,
        query_vector=embedding.vectors[0],
        match_count=match_count,
        threshold=threshold,
        business_domain=business_domain,
        document_type=None,
    )
    return [
        SemanticContextItem(
            semantic_document_id=str(row["semantic_document_id"]),
            title=row["title"],
            document_type=row["document_type"],
            business_domain=row["business_domain"],
            content=row["content"],
            related_tables=row["related_tables"] or [],
            related_metrics=row["related_metrics"] or [],
            example_questions=row["example_questions"] or [],
            similarity=float(row["similarity"]) if row["similarity"] is not None else None,
        )
        for row in rows
    ]
