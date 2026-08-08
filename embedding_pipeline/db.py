from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from dataclasses import dataclass

import psycopg
from psycopg import errors
from psycopg.rows import dict_row


@dataclass(frozen=True)
class SemanticDocument:
    semantic_document_id: str
    title: str
    document_type: str
    business_domain: str | None
    source_schema: str | None
    source_table: str | None
    source_column: str | None
    content: str
    related_tables: list[str]
    related_columns: list[str]
    related_models: list[str]
    related_metrics: list[str]
    example_questions: list[str]
    sql_examples: list[str]
    tags: list[str]


def connect(database_url: str):
    return psycopg.connect(database_url, row_factory=dict_row, autocommit=False)


def fetch_documents_without_embeddings(conn, *, limit: int) -> list[SemanticDocument]:
    limit_sql = "" if limit <= 0 else "limit %s"
    params: tuple[int, ...] = () if limit <= 0 else (limit,)
    query = f"""
        select
          semantic_document_id::text,
          title,
          document_type,
          business_domain,
          source_schema,
          source_table,
          source_column,
          content,
          coalesce(related_tables, '{{}}'::text[]) as related_tables,
          coalesce(related_columns, '{{}}'::text[]) as related_columns,
          coalesce(related_models, '{{}}'::text[]) as related_models,
          coalesce(related_metrics, '{{}}'::text[]) as related_metrics,
          coalesce(example_questions, '{{}}'::text[]) as example_questions,
          coalesce(sql_examples, '{{}}'::text[]) as sql_examples,
          coalesce(tags, '{{}}'::text[]) as tags
        from public.semantic_documents
        where active_flag = true
          and embedding is null
        order by created_at, semantic_document_id
        {limit_sql}
    """
    with conn.cursor() as cur:
        cur.execute(query, params)
        rows = cur.fetchall()
    return [SemanticDocument(**row) for row in rows]


def semantic_text(doc: SemanticDocument) -> str:
    payload = {
        "title": doc.title,
        "document_type": doc.document_type,
        "business_domain": doc.business_domain,
        "source": {
            "schema": doc.source_schema,
            "table": doc.source_table,
            "column": doc.source_column,
        },
        "content": doc.content,
        "related_tables": doc.related_tables,
        "related_columns": doc.related_columns,
        "related_models": doc.related_models,
        "related_metrics": doc.related_metrics,
        "example_questions": doc.example_questions,
        "sql_examples": doc.sql_examples,
        "tags": doc.tags,
    }
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def vector_literal(vector: list[float]) -> str:
    return "[" + ",".join(f"{float(value):.8f}" for value in vector) + "]"


def update_embeddings(
    conn,
    *,
    documents: list[SemanticDocument],
    vectors: list[list[float]],
    embedding_model: str,
) -> None:
    if len(documents) != len(vectors):
        raise ValueError(f"Document/vector count mismatch: {len(documents)} docs, {len(vectors)} vectors")

    rows = [
        (
            vector_literal(vector),
            embedding_model,
            content_hash(semantic_text(document)),
            document.semantic_document_id,
        )
        for document, vector in zip(documents, vectors, strict=True)
    ]
    with conn.cursor() as cur:
        for vector, model, hash_value, semantic_document_id in rows:
            try:
                cur.execute("savepoint semantic_document_embedding_update")
                cur.execute(
                    """
                    update public.semantic_documents
                    set embedding = %s::vector,
                        embedding_model = %s,
                        content_hash = %s,
                        updated_at = now()
                    where semantic_document_id = %s::uuid
                    """,
                    (vector, model, hash_value, semantic_document_id),
                )
                cur.execute("release savepoint semantic_document_embedding_update")
            except errors.UniqueViolation:
                cur.execute("rollback to savepoint semantic_document_embedding_update")
                cur.execute(
                    """
                    update public.semantic_documents
                    set active_flag = false,
                        embedding = null,
                        embedding_model = left(%s, 120),
                        content_hash = %s,
                        updated_at = now()
                    where semantic_document_id = %s::uuid
                    """,
                    (
                        f"duplicate-{model}-{semantic_document_id[:8]}",
                        hash_value,
                        semantic_document_id,
                    ),
                )
                cur.execute("release savepoint semantic_document_embedding_update")
    conn.commit()


def search_similar(
    conn,
    *,
    query_vector: list[float],
    match_count: int,
    threshold: float,
    business_domain: str | None,
    document_type: str | None,
) -> list[dict]:
    with conn.cursor() as cur:
        cur.execute(
            """
            select *
            from public.match_semantic_documents(
              %s::vector,
              %s,
              %s,
              %s,
              %s
            )
            """,
            (vector_literal(query_vector), match_count, threshold, business_domain, document_type),
        )
        return cur.fetchall()


def chunks(items: list[SemanticDocument], size: int) -> Iterable[list[SemanticDocument]]:
    for i in range(0, len(items), size):
        yield items[i : i + size]
