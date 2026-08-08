#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel, Field

from embedding_pipeline.config import load_settings
from embedding_pipeline.db import connect, vector_literal
from embedding_pipeline.providers import build_provider
from table_governance_service import has_table


@dataclass
class ContextDocument:
    semantic_document_id: str
    title: str
    document_type: str
    business_domain: str | None
    context_bucket: str
    content: str
    related_tables: list[str]
    related_columns: list[str]
    related_models: list[str]
    related_metrics: list[str]
    example_questions: list[str]
    sql_examples: list[str]
    vector_similarity: float
    keyword_score: float
    metadata_score: float
    hybrid_score: float


class RetrieveRequest(BaseModel):
    question: str = Field(min_length=1)
    match_count: int = Field(default=12, ge=1, le=50)
    threshold: float = Field(default=0.0, ge=-1.0, le=1.0)
    business_domain: str | None = None


class ContextRetriever:
    def __init__(self, env_file: str = ".env") -> None:
        self.settings = load_settings(env_file)
        self.provider = build_provider(self.settings)

    def retrieve(self, question: str, match_count: int = 12, threshold: float = 0.0, business_domain: str | None = None) -> dict[str, list[dict[str, Any]]]:
        embedding_result = self.provider.embed_batch([question])
        if embedding_result.dimensions != self.settings.embedding_dimensions:
            raise ValueError(
                f"Embedding dimension mismatch. Provider returned {embedding_result.dimensions}, "
                f"but EMBEDDING_DIMENSIONS is {self.settings.embedding_dimensions}."
            )

        with connect(self.settings.database_url) as conn:
            invalid_semantic_ids = self._invalid_semantic_document_ids(conn)
            semantic_rows = []
            governance_rows = self._governance_context_rows(
                conn,
                question=question,
                vector=embedding_result.vectors[0],
                match_count=match_count,
                threshold=threshold,
                business_domain=business_domain,
            )
            with conn.cursor() as cur:
                try:
                    cur.execute(
                        """
                        select *
                        from public.hybrid_match_semantic_documents(
                          %s,
                          %s::vector,
                          %s,
                          %s,
                          %s
                        )
                        """,
                        (
                            question,
                            vector_literal(embedding_result.vectors[0]),
                            match_count,
                            threshold,
                            business_domain,
                        ),
                    )
                    semantic_rows = cur.fetchall()
                except Exception:
                    conn.rollback()
            verified_rows = self._verified_context_rows(
                conn,
                question=question,
                vector=embedding_result.vectors[0],
                match_count=match_count,
                threshold=threshold,
                business_domain=business_domain,
            )

        rows = governance_rows + [
            row
            for row in semantic_rows
            if str(row.get("semantic_document_id")) not in invalid_semantic_ids
        ] + verified_rows
        docs = [
            ContextDocument(**{**row, "semantic_document_id": str(row["semantic_document_id"])})
            for row in rows
        ]
        docs.sort(key=lambda doc: doc.hybrid_score, reverse=True)
        return bundle_context(docs[:match_count])

    def _invalid_semantic_document_ids(self, conn) -> set[str]:
        with conn.cursor() as cur:
            try:
                cur.execute(
                    """
                    select context_id
                    from public.cld_context_validation_results
                    where context_source = 'semantic_documents'
                      and classification = 'invalid_schema_reference'
                    """
                )
                return {str(row["context_id"]) for row in cur.fetchall() if row.get("context_id")}
            except Exception:
                conn.rollback()
                return set()

    def _verified_context_rows(
        self,
        conn,
        *,
        question: str,
        vector: list[float],
        match_count: int,
        threshold: float,
        business_domain: str | None,
    ) -> list[dict[str, Any]]:
        with conn.cursor() as cur:
            try:
                cur.execute(
                    """
                    with scored as (
                      select
                        context_id::text as semantic_document_id,
                        title,
                        document_type,
                        business_domain,
                        case
                          when document_type in ('actual_table_description', 'actual_column_description', 'verified_join_path')
                            then 'schema_context'
                          when document_type in ('verified_kpi_definition', 'verified_sql_example')
                            then 'metric_context'
                          when document_type = 'model_score_usage'
                            then 'model_context'
                          else 'business_context'
                        end as context_bucket,
                        content,
                        related_tables,
                        related_columns,
                        related_models,
                        '[]'::jsonb as related_metrics,
                        example_questions,
                        sql_examples,
                        greatest(0.0, 1.0 - (embedding <=> %s::vector)) as vector_similarity,
                        case
                          when position(lower(%s) in lower(title || ' ' || content)) > 0 then 0.20
                          else 0.0
                        end as keyword_score,
                        case
                          when %s::text is not null and lower(coalesce(business_domain, '')) = lower(%s::text) then 0.10
                          else 0.0
                        end as metadata_score
                      from public.cld_verified_sql_context_documents
                      where sql_usable = true
                        and embedding is not null
                        and (%s::text is null or lower(coalesce(business_domain, '')) = lower(%s::text))
                    )
                    select *,
                      (0.75 * vector_similarity + keyword_score + metadata_score) as hybrid_score
                    from scored
                    where vector_similarity >= %s
                    order by hybrid_score desc, title
                    limit %s
                    """,
                    (
                        vector_literal(vector),
                        question,
                        business_domain,
                        business_domain,
                        business_domain,
                        business_domain,
                        threshold,
                        match_count,
                    ),
                )
                return [dict(row) for row in cur.fetchall()]
            except Exception:
                conn.rollback()
                return []

    def _governance_context_rows(
        self,
        conn,
        *,
        question: str,
        vector: list[float],
        match_count: int,
        threshold: float,
        business_domain: str | None,
    ) -> list[dict[str, Any]]:
        if not has_table(conn, "public", "cld_context_registry"):
            return []
        with conn.cursor() as cur:
            try:
                cur.execute(
                    """
                    with scored as (
                      select
                        context_id::text as semantic_document_id,
                        title,
                        context_type as document_type,
                        business_domain,
                        case
                          when context_type in ('table_context', 'column_context', 'join_path_context') then 'schema_context'
                          when context_type in ('kpi_context', 'demo_question_context') then 'metric_context'
                          when context_type = 'model_context' then 'model_context'
                          else 'business_context'
                        end as context_bucket,
                        content,
                        related_tables,
                        related_columns,
                        coalesce(related_models, '[]'::jsonb) as related_models,
                        coalesce(related_kpis, '[]'::jsonb) as related_metrics,
                        '[]'::jsonb as example_questions,
                        '[]'::jsonb as sql_examples,
                        greatest(0.0, 1.0 - (embedding <=> %s::vector)) as vector_similarity,
                        case
                          when position(lower(%s) in lower(title || ' ' || content)) > 0 then 0.20
                          else 0.0
                        end as keyword_score,
                        case
                          when %s::text is not null and lower(coalesce(business_domain, '')) = lower(%s::text) then 0.10
                          else 0.0
                        end as metadata_score
                      from public.cld_context_registry
                      where sql_usable = true
                        and embedding is not null
                        and (%s::text is null or lower(coalesce(business_domain, '')) = lower(%s::text))
                    )
                    select *,
                      (0.75 * vector_similarity + keyword_score + metadata_score) as hybrid_score
                    from scored
                    where vector_similarity >= %s
                    order by hybrid_score desc, title
                    limit %s
                    """,
                    (
                        vector_literal(vector),
                        question,
                        business_domain,
                        business_domain,
                        business_domain,
                        business_domain,
                        threshold,
                        match_count,
                    ),
                )
                return [dict(row) for row in cur.fetchall()]
            except Exception:
                conn.rollback()
                return []


def compact_document(doc: ContextDocument) -> dict[str, Any]:
    data = asdict(doc)
    return {
        "semantic_document_id": data["semantic_document_id"],
        "title": data["title"],
        "document_type": data["document_type"],
        "business_domain": data["business_domain"],
        "content": data["content"],
        "related_tables": data["related_tables"],
        "related_columns": data["related_columns"],
        "related_models": data["related_models"],
        "related_metrics": data["related_metrics"],
        "example_questions": data["example_questions"],
        "score": {
            "hybrid": round(float(data["hybrid_score"]), 6),
            "vector": round(float(data["vector_similarity"]), 6),
            "keyword": round(float(data["keyword_score"]), 6),
            "metadata": round(float(data["metadata_score"]), 6),
        },
    }


def bundle_context(docs: list[ContextDocument]) -> dict[str, list[dict[str, Any]]]:
    bundle: dict[str, list[dict[str, Any]]] = {
        "business_context": [],
        "schema_context": [],
        "metric_context": [],
        "model_context": [],
        "sql_examples": [],
    }

    for doc in docs:
        bucket = doc.context_bucket if doc.context_bucket in bundle else "business_context"
        bundle[bucket].append(compact_document(doc))
        for sql_example in doc.sql_examples:
            bundle["sql_examples"].append(
                {
                    "semantic_document_id": doc.semantic_document_id,
                    "title": doc.title,
                    "business_domain": doc.business_domain,
                    "sql": sql_example,
                    "score": {
                        "hybrid": round(float(doc.hybrid_score), 6),
                        "vector": round(float(doc.vector_similarity), 6),
                        "keyword": round(float(doc.keyword_score), 6),
                        "metadata": round(float(doc.metadata_score), 6),
                    },
                }
            )

    return bundle


app = FastAPI(title="Insurance Copilot Context Retriever", version="1.0.0")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/retrieve-context")
def retrieve_context(request: RetrieveRequest) -> dict[str, list[dict[str, Any]]]:
    retriever = ContextRetriever()
    return retriever.retrieve(
        question=request.question,
        match_count=request.match_count,
        threshold=request.threshold,
        business_domain=request.business_domain,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Retrieve GenAI Copilot context from Supabase pgvector.")
    parser.add_argument("question", nargs="?", help="Business question to retrieve context for.")
    parser.add_argument("--env-file", default=".env")
    parser.add_argument("--match-count", type=int, default=12)
    parser.add_argument("--threshold", type=float, default=0.0)
    parser.add_argument("--business-domain")
    parser.add_argument("--pretty", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.question:
        raise SystemExit("Provide a question, or run as an API with: uvicorn context_retriever_service:app --reload --port 8020")

    retriever = ContextRetriever(args.env_file)
    bundle = retriever.retrieve(
        question=args.question,
        match_count=args.match_count,
        threshold=args.threshold,
        business_domain=args.business_domain,
    )
    print(json.dumps(bundle, indent=2 if args.pretty else None, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
