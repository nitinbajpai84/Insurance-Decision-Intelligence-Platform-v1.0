#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from typing import NoReturn

from embedding_pipeline.config import load_settings
from embedding_pipeline.db import (
    chunks,
    connect,
    fetch_documents_without_embeddings,
    search_similar,
    semantic_text,
    update_embeddings,
)
from embedding_pipeline.providers import build_provider


def fail(message: str) -> NoReturn:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(1)


def embed_missing(args) -> None:
    settings = load_settings(args.env_file)
    batch_size = args.batch_size or settings.batch_size
    max_rows = settings.max_rows if args.max_rows is None else args.max_rows

    provider = build_provider(settings)
    print(f"Using provider={settings.provider} model={provider.model_name}")

    try:
        with connect(settings.database_url) as conn:
            documents = fetch_documents_without_embeddings(conn, limit=max_rows)
            print(f"Found {len(documents)} semantic_documents rows without embeddings.")
            if not documents:
                return
            if settings.dry_run or args.dry_run:
                print("Dry run enabled. First document text:")
                print(semantic_text(documents[0])[:2000])
                return

            total = len(documents)
            done = 0
            expected_dimensions: int | None = None
            for batch in chunks(documents, batch_size):
                texts = [semantic_text(document) for document in batch]
                result = provider.embed_batch(texts)
                if expected_dimensions is None:
                    expected_dimensions = result.dimensions
                    print(f"Embedding dimensions: {expected_dimensions}")
                    if expected_dimensions != settings.embedding_dimensions:
                        print(
                            f"WARNING: expected embedding dimension is {settings.embedding_dimensions}. "
                            f"Current model returned {expected_dimensions} dimensions. "
                            "Change the column/function dimensions or choose a matching model before updating."
                        )
                if result.dimensions != settings.embedding_dimensions:
                    fail(
                        "Embedding dimension mismatch. "
                        f"Expected {settings.embedding_dimensions}; provider returned {result.dimensions}."
                    )
                update_model = result.model or provider.model_name
                update_embeddings(conn, documents=batch, vectors=result.vectors, embedding_model=update_model)
                done += len(batch)
                print(f"Embedded {done}/{total}")
    except Exception as exc:
        fail(str(exc))


def search(args) -> None:
    settings = load_settings(args.env_file)
    provider = build_provider(settings)
    try:
        result = provider.embed_batch([args.query])
        if result.dimensions != settings.embedding_dimensions:
            fail(f"Search embedding dimension {result.dimensions} does not match expected dimension {settings.embedding_dimensions}.")
        with connect(settings.database_url) as conn:
            rows = search_similar(
                conn,
                query_vector=result.vectors[0],
                match_count=args.match_count,
                threshold=args.threshold,
                business_domain=args.business_domain,
                document_type=args.document_type,
            )
        for i, row in enumerate(rows, 1):
            print(f"{i}. {row['title']} [{row['document_type']} / {row['business_domain']}] similarity={row['similarity']:.4f}")
            print(f"   tables={row['related_tables']} metrics={row['related_metrics']}")
            print(f"   {row['content'][:500]}")
    except Exception as exc:
        fail(str(exc))


def parse_args():
    parser = argparse.ArgumentParser(description="Embed semantic_documents into Supabase pgvector.")
    parser.add_argument("--env-file", default=".env")
    sub = parser.add_subparsers(dest="command", required=True)

    embed_cmd = sub.add_parser("embed-missing", help="Embed active semantic_documents rows where embedding is null.")
    embed_cmd.add_argument("--batch-size", type=int)
    embed_cmd.add_argument("--max-rows", type=int)
    embed_cmd.add_argument("--dry-run", action="store_true")
    embed_cmd.set_defaults(func=embed_missing)

    search_cmd = sub.add_parser("search", help="Embed a query and call match_semantic_documents.")
    search_cmd.add_argument("query")
    search_cmd.add_argument("--match-count", type=int, default=8)
    search_cmd.add_argument("--threshold", type=float, default=0.0)
    search_cmd.add_argument("--business-domain")
    search_cmd.add_argument("--document-type")
    search_cmd.set_defaults(func=search)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
