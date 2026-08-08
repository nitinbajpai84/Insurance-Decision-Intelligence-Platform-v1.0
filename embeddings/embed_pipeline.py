#!/usr/bin/env python3
"""
Insurance PoC V2.0 — embedding pipeline (DuckDB -> Gemini -> LanceDB).

Priority order:
  1. business_glossary       -> insurance_glossary_vectors
  2. semantic_documents      -> insurance_semantic_vectors   (chunked ~500 tokens, 50 overlap)
  3. schema catalog          -> insurance_schema_vectors     (from db_connection.get_all_tables())
  4. query_audit_log         -> insurance_query_history
  5. top-500 customers/agents/policies by value -> insurance_entity_vectors

Idempotent: a record already present in DuckDB vector_index_log (same
lance_table + record_id) is skipped, so re-running only embeds new rows.

Rate limiting: EMBEDDING_DELAY_SECONDS sleep (default 0.1s) between Gemini
calls — the free tier allows ~1500 requests/day, so a full first run is sized
to stay comfortably below that.

Run:  venv\\Scripts\\python.exe embeddings\\embed_pipeline.py
"""
from __future__ import annotations

import json
import os
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path

import google.generativeai as genai
import lancedb
from dotenv import load_dotenv
from tqdm import tqdm

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
load_dotenv(PROJECT_ROOT / ".env")

from database.db_connection import execute_query, get_all_tables, get_duckdb_path  # noqa: E402

import duckdb  # noqa: E402

EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL", "models/gemini-embedding-001")
LANCEDB_PATH = os.environ.get("LANCEDB_PATH", str(PROJECT_ROOT / "lance_store"))
DELAY_SECONDS = float(os.environ.get("EMBEDDING_DELAY_SECONDS", "0.1"))
VECTOR_DIMS = 3072

API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()
if not API_KEY:
    print("ERROR: GEMINI_API_KEY is not set. Add it to the project-root .env (see .env.example).")
    sys.exit(1)
genai.configure(api_key=API_KEY)

stats = {"embedded": 0, "skipped": 0, "failed": 0}


# ---------------------------------------------------------------------------
# Embedding with retry
# ---------------------------------------------------------------------------
def embed_text(text: str) -> list[float] | None:
    """Embed one text with gemini-embedding-001; one retry after 5s on failure."""
    for attempt in (1, 2):
        try:
            result = genai.embed_content(
                model=EMBEDDING_MODEL,
                content=text[:9000],
                output_dimensionality=VECTOR_DIMS,
            )
            time.sleep(DELAY_SECONDS)
            return list(result["embedding"])
        except Exception as exc:
            print(f"  [embed] attempt {attempt} failed: {type(exc).__name__}: {exc}")
            if attempt == 1:
                time.sleep(5)
    return None


# ---------------------------------------------------------------------------
# Idempotency via DuckDB vector_index_log
# ---------------------------------------------------------------------------
def already_embedded(lance_table: str) -> set[str]:
    rows, _ = execute_query(
        "SELECT record_id FROM vector_index_log WHERE lance_table = ? AND model_used = ?",
        [lance_table, EMBEDDING_MODEL],
    )
    return {r[0] for r in rows}


def flush_index_log(rows: list[list]) -> None:
    """Batch-insert vector_index_log rows via a short-lived write connection.

    DuckDB rejects mixed read-only/read-write connections open simultaneously
    in one process, so writes happen in their own open->insert->close window.
    """
    if not rows:
        return
    conn = duckdb.connect(get_duckdb_path(), read_only=False)
    try:
        conn.executemany(
            "INSERT INTO vector_index_log (table_name, record_id, chunk_text, embedded_at, model_used, vector_dims, lance_table) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            rows,
        )
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Chunking (~500 tokens with ~50-token overlap; 1 token ~ 0.75 words)
# ---------------------------------------------------------------------------
CHUNK_WORDS = 375     # ~500 tokens
OVERLAP_WORDS = 38    # ~50 tokens


def chunk_text(text: str) -> list[str]:
    words = (text or "").split()
    if len(words) <= CHUNK_WORDS:
        return [text.strip()] if text and text.strip() else []
    chunks, start = [], 0
    while start < len(words):
        chunks.append(" ".join(words[start:start + CHUNK_WORDS]))
        start += CHUNK_WORDS - OVERLAP_WORDS
    return chunks


# ---------------------------------------------------------------------------
# Per-table embedding jobs
# ---------------------------------------------------------------------------
def run_job(lance_db, *, lance_table: str, source_table: str, items: list[dict]) -> None:
    """items: [{record_id, text, row(dict of lance columns minus vector/text_chunk)}]"""
    done = already_embedded(lance_table)
    pending = [item for item in items if item["record_id"] not in done]
    stats["skipped"] += len(items) - len(pending)
    print(f"\n[{lance_table}] source={source_table} total={len(items)} "
          f"already_done={len(items) - len(pending)} to_embed={len(pending)}")
    if not pending:
        return
    table = lance_db.open_table(lance_table)
    batch: list[dict] = []
    log_rows: list[list] = []
    for item in tqdm(pending, desc=lance_table, unit="rec"):
        vector = embed_text(item["text"])
        if vector is None:
            stats["failed"] += 1
            print(f"  [skip] embedding failed for record_id={item['record_id']}")
            continue
        row = dict(item["row"])
        row["text_chunk"] = item["text"]
        row["vector"] = vector
        batch.append(row)
        log_rows.append([source_table, item["record_id"], item["text"][:400],
                         datetime.now(), EMBEDDING_MODEL, VECTOR_DIMS, lance_table])
        stats["embedded"] += 1
        if len(batch) >= 50:
            table.add(batch)
            flush_index_log(log_rows)
            batch, log_rows = [], []
    if batch:
        table.add(batch)
        flush_index_log(log_rows)


def job_glossary() -> list[dict]:
    rows, _ = execute_query(
        "SELECT glossary_id, term, definition, coalesce(domain,''), coalesce(synonyms,'') FROM business_glossary "
        "WHERE active_flag = true"
    )
    items = []
    for glossary_id, term, definition, domain, synonyms in rows:
        context = f"domain={domain}; synonyms={synonyms}"
        text = f"{term} | {definition or ''} | {context}"
        items.append({
            "record_id": str(glossary_id),
            "text": text,
            "row": {
                "id": str(uuid.uuid4()),
                "term": term or "",
                "definition": definition or "",
                "business_context": context,
                "subject_area": domain or "",
                "source_table": "business_glossary",
                "record_id": str(glossary_id),
                "metadata": json.dumps({"synonyms": synonyms}),
            },
        })
    return items


def job_semantic_documents() -> list[dict]:
    rows, _ = execute_query(
        "SELECT semantic_document_id, coalesce(title,''), coalesce(document_type,''), coalesce(content,''), "
        "coalesce(source_table,'') FROM semantic_documents WHERE active_flag = true"
    )
    items = []
    for doc_id, title, doc_type, content, src in rows:
        for idx, chunk in enumerate(chunk_text(f"{title}\n{content}")):
            items.append({
                "record_id": f"{doc_id}:{idx}",
                "text": chunk,
                "row": {
                    "id": str(uuid.uuid4()),
                    "document_title": title,
                    "document_type": doc_type,
                    "content_chunk": chunk,
                    "chunk_index": idx,
                    "source_table": "semantic_documents",
                    "record_id": f"{doc_id}:{idx}",
                    "metadata": json.dumps({"v1_source_table": src}),
                },
            })
    return items


SUBJECT_AREA_HINTS = {
    "customer": "Customer", "household": "Customer", "address": "Customer", "part": "Customer",
    "policy": "Policy", "premium": "Policy", "payment": "Payment",
    "agent": "Agent", "lead": "Sales", "opportunit": "Sales", "quote": "Sales",
    "proposal": "Sales", "application": "Sales", "underwriting": "Sales",
    "campaign": "Campaign", "next_best": "Campaign",
    "claim": "Claims", "product": "Product",
    "model": "ML", "semantic": "AI", "glossary": "AI", "query_audit": "AI",
    "vector": "AI", "agent_reasoning": "AI", "cache": "AI",
}


def subject_area_for(table: str) -> str:
    for prefix, area in SUBJECT_AREA_HINTS.items():
        if prefix in table:
            return area
    return "Other"


def job_schema_catalog() -> list[dict]:
    catalog = get_all_tables()
    items = []
    for table_name, columns in catalog.items():
        for col in columns:
            description = (
                f"Column {col['column_name']} ({col['data_type']}) in table {table_name} "
                f"({subject_area_for(table_name)} subject area) of the Singapore insurance analytics database."
            )
            text = f"{table_name}.{col['column_name']}: {description}"
            items.append({
                "record_id": f"{table_name}.{col['column_name']}",
                "text": text,
                "row": {
                    "id": str(uuid.uuid4()),
                    "table_name": table_name,
                    "column_name": col["column_name"],
                    "business_description": description,
                    "data_type": col["data_type"],
                    "subject_area": subject_area_for(table_name),
                    "metadata": json.dumps({"nullable": col["nullable"]}),
                },
            })
    return items


def job_query_history() -> list[dict]:
    rows, _ = execute_query(
        "SELECT query_audit_log_id, coalesce(question,''), coalesce(generated_sql,''), "
        "coalesce(execution_status,''), coalesce(row_count,0), coalesce(duration_ms,0) FROM query_audit_log"
    )
    items = []
    for log_id, question, sql, status, row_count, duration_ms in rows:
        if not question:
            continue
        answer = f"SQL executed ({status}), {row_count} rows."
        items.append({
            "record_id": str(log_id),
            "text": f"{question} | {answer}",
            "row": {
                "id": str(uuid.uuid4()),
                "question": question,
                "role": "unknown",
                "answer_summary": answer,
                "sql_used": sql,
                "tables_used": "",
                "confidence_score": 0.5,
                "latency_ms": int(duration_ms or 0),
                "metadata": json.dumps({"source": "query_audit_log"}),
            },
        })
    return items


def job_entities() -> list[dict]:
    items = []
    customers, _ = execute_query(
        "SELECT c.customer_id, coalesce(p.display_name, c.customer_number), coalesce(c.customer_segment,''), "
        "coalesce(c.risk_tier,''), count(pol.policy_id), coalesce(sum(pol.annual_premium),0) "
        "FROM customers c LEFT JOIN parties p ON p.party_id = c.party_id "
        "LEFT JOIN policies pol ON pol.customer_id = c.customer_id "
        "GROUP BY 1,2,3,4 ORDER BY 6 DESC LIMIT 500")
    for cid, name, segment, risk, n_pol, premium in customers:
        desc = (f"{segment} customer, risk tier {risk}, {n_pol} policies, "
                f"total annual premium SGD {premium:,.0f}.")
        items.append(_entity_item("customer", cid, name, desc))

    agents, _ = execute_query(
        "SELECT a.agent_id, coalesce(p.display_name, a.agent_number), coalesce(a.territory_code,''), "
        "coalesce(a.channel,''), count(pol.policy_id), coalesce(sum(pol.annual_premium),0) "
        "FROM agents a LEFT JOIN parties p ON p.party_id = a.party_id "
        "LEFT JOIN policies pol ON pol.agent_id = a.agent_id "
        "GROUP BY 1,2,3,4 ORDER BY 6 DESC LIMIT 500")
    for aid, name, territory, channel, n_pol, premium in agents:
        desc = (f"{channel} channel agent in {territory}, {n_pol} policies in force, "
                f"book annual premium SGD {premium:,.0f}.")
        items.append(_entity_item("agent", aid, name, desc))

    policies, _ = execute_query(
        "SELECT pol.policy_id, pol.policy_number, coalesce(pr.product_name,''), coalesce(pol.policy_status,''), "
        "coalesce(pol.annual_premium,0) FROM policies pol LEFT JOIN products pr ON pr.product_id = pol.product_id "
        "ORDER BY pol.annual_premium DESC NULLS LAST LIMIT 500")
    for pid, number, product, status, premium in policies:
        desc = f"{product} policy, status {status}, annual premium SGD {premium:,.0f}."
        items.append(_entity_item("policy", pid, number, desc))
    return items


def _entity_item(entity_type: str, entity_id: str, name: str, desc: str) -> dict:
    return {
        "record_id": f"{entity_type}:{entity_id}",
        "text": f"{entity_type} {name}: {desc}",
        "row": {
            "id": str(uuid.uuid4()),
            "entity_type": entity_type,
            "entity_id": str(entity_id),
            "entity_name": str(name or ""),
            "description_text": desc,
            "metadata": json.dumps({}),
        },
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
JOB_KEYS = {
    "glossary": ("insurance_glossary_vectors", "business_glossary", job_glossary),
    "semantic": ("insurance_semantic_vectors", "semantic_documents", job_semantic_documents),
    "schema": ("insurance_schema_vectors", "schema_catalog", job_schema_catalog),
    "history": ("insurance_query_history", "query_audit_log", job_query_history),
    "entities": ("insurance_entity_vectors", "entities_top500", job_entities),
}


def main() -> int:
    # Optional job filter: python embed_pipeline.py --jobs glossary,schema
    selected = list(JOB_KEYS)
    if "--jobs" in sys.argv:
        raw = sys.argv[sys.argv.index("--jobs") + 1]
        selected = [j.strip() for j in raw.split(",") if j.strip() in JOB_KEYS]
    print(f"Embedding model: {EMBEDDING_MODEL} (dims={VECTOR_DIMS})")
    print(f"LanceDB:         {LANCEDB_PATH}")
    print(f"Jobs:            {', '.join(selected)}")
    lance_db = lancedb.connect(LANCEDB_PATH)
    jobs = [JOB_KEYS[key] for key in selected]
    for lance_table, source_table, builder in jobs:
        try:
            items = builder()
            run_job(lance_db, lance_table=lance_table, source_table=source_table, items=items)
        except Exception as exc:
            print(f"[{lance_table}] JOB FAILED: {type(exc).__name__}: {exc}")
            stats["failed"] += 1
    print(f"\nEmbedded {stats['embedded']} records, skipped {stats['skipped']}, failed {stats['failed']}")
    return 0 if stats["failed"] == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
