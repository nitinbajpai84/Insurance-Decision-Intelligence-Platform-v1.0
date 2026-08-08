from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import psycopg
from dotenv import load_dotenv
from psycopg.rows import dict_row

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from embedding_pipeline.config import load_settings
from embedding_pipeline.db import vector_literal
from embedding_pipeline.providers import build_provider


def connect(database_url: str):
    return psycopg.connect(database_url, row_factory=dict_row, connect_timeout=30)


def embed_verified_context(env_file: str, batch_size: int, limit: int | None) -> dict[str, int | str]:
    settings = load_settings(env_file)
    provider = build_provider(settings)
    embedded = 0
    with connect(settings.database_url) as conn:
        while True:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    select context_id, title, content
                    from public.cld_verified_sql_context_documents
                    where sql_usable = true
                      and embedding is null
                    order by updated_at desc
                    limit %s
                    """,
                    (min(batch_size, (limit - embedded) if limit else batch_size),),
                )
                rows = cur.fetchall()
            if not rows:
                break
            texts = [f"{row['title']}\n{row['content']}" for row in rows]
            result = provider.embed_batch(texts)
            if result.dimensions != settings.embedding_dimensions:
                raise RuntimeError(f"Embedding dimension mismatch: {result.dimensions} != {settings.embedding_dimensions}")
            with conn.cursor() as cur:
                for row, vector in zip(rows, result.vectors):
                    cur.execute(
                        """
                        update public.cld_verified_sql_context_documents
                        set embedding = %s::vector,
                            embedding_model = %s,
                            updated_at = now()
                        where context_id = %s
                        """,
                        (vector_literal(vector), result.model, row["context_id"]),
                    )
                    embedded += 1
            conn.commit()
            if limit and embedded >= limit:
                break
    return {"provider": settings.provider, "embedding_model": provider.model_name, "embedded": embedded}


def main() -> int:
    parser = argparse.ArgumentParser(description="Embed verified SQL context documents with configured embedding provider.")
    parser.add_argument("--env-file", default=".env")
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()
    load_dotenv(args.env_file, override=True)
    print(json.dumps(embed_verified_context(args.env_file, args.batch_size, args.limit), indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
