"""
V2 API routes — SSE ask pipeline, roles, governed glossary, evidence hub, health.
"""
from __future__ import annotations

import json
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, AsyncGenerator

import duckdb
import lancedb
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend_v2.agents.orchestrator import stream_pipeline
from backend_v2.config import (
    DUCKDB_CONFIG,
    DUCKDB_PATH,
    GEMINI_API_KEY,
    GEMINI_MODEL,
    LANCEDB_PATH,
    ROLES,
)
from backend_v2.observability import tracer
from database.db_connection import health_check as duckdb_health

router = APIRouter(prefix="/api/v2", tags=["v2"])


# ---------------------------------------------------------------------------
# POST /api/v2/ask — Server-Sent Events stream
# ---------------------------------------------------------------------------
class AskRequest(BaseModel):
    question: str = Field(min_length=3, max_length=2000)
    role: str = Field(default="Executive Leadership")
    # optional "Ask why" context hints — sharpen graph retrieval
    process_id: str | None = None
    metric_id: str | None = None
    page: str | None = None
    stage: str | None = None


def _sse(payload: dict[str, Any]) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False, default=str)}\n\n"


def _augment(req: AskRequest) -> str:
    """Prepend lightweight context tags so binding/graph retrieval is sharper."""
    hints = []
    if req.process_id:
        hints.append(f"process={req.process_id}")
    if req.metric_id:
        hints.append(f"metric={req.metric_id}")
    if req.stage:
        hints.append(f"stage={req.stage}")
    if req.page:
        hints.append(f"page={req.page}")
    return f"[context: {' '.join(hints)}] {req.question}" if hints else req.question


@router.post("/ask")
async def ask(request: AskRequest) -> StreamingResponse:
    query_id = str(uuid.uuid4())
    question = _augment(request)

    async def event_stream() -> AsyncGenerator[str, None]:
        try:
            async for event in stream_pipeline(question, request.role, query_id):
                yield _sse(event)
        except Exception as exc:
            yield _sse({"step": "error", "status": "failed",
                        "error": f"{type(exc).__name__}: {exc}", "query_id": query_id})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no",
                 "X-Query-Id": query_id},
    )


# ---------------------------------------------------------------------------
# GET /api/v2/roles
# ---------------------------------------------------------------------------
@router.get("/roles")
def get_roles() -> list[dict[str, str]]:
    return ROLES


# ---------------------------------------------------------------------------
# Glossary — read + governed update
# ---------------------------------------------------------------------------
@router.get("/glossary")
def get_glossary() -> list[dict[str, Any]]:
    conn = duckdb.connect(DUCKDB_PATH, read_only=True, config=DUCKDB_CONFIG)
    try:
        rows = conn.execute(
            "SELECT glossary_id, term, domain, definition, synonyms, owner, active_flag, updated_at "
            "FROM business_glossary ORDER BY term"
        ).fetchall()
    finally:
        conn.close()
    return [
        {"glossary_id": r[0], "term": r[1], "domain": r[2], "definition": r[3],
         "synonyms": r[4], "owner": r[5], "active_flag": r[6],
         "updated_at": r[7].isoformat() if hasattr(r[7], "isoformat") else r[7]}
        for r in rows
    ]


class GlossaryUpdateRequest(BaseModel):
    term_id: str
    new_definition: str = Field(min_length=3)
    updated_by: str
    reason: str = Field(min_length=3)


@router.post("/glossary/update")
def update_glossary(request: GlossaryUpdateRequest) -> dict[str, Any]:
    """Governed update: DuckDB write + LanceDB re-embed + audit trail."""
    conn = duckdb.connect(DUCKDB_PATH, read_only=False, config=DUCKDB_CONFIG)
    try:
        row = conn.execute(
            "SELECT term, definition, coalesce(domain,''), coalesce(synonyms,'') "
            "FROM business_glossary WHERE glossary_id = ?", [request.term_id]
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail=f"Glossary term not found: {request.term_id}")
        term, old_definition, domain, synonyms = row
        conn.execute(
            "UPDATE business_glossary SET definition = ?, updated_at = ? WHERE glossary_id = ?",
            [request.new_definition, datetime.now(), request.term_id],
        )
    finally:
        conn.close()

    # Re-embed into LanceDB (delete old vector rows for this record, add fresh)
    reembedded = False
    embed_error = None
    try:
        from embeddings.vector_search import embed_text

        text = f"{term} | {request.new_definition} | domain={domain}; synonyms={synonyms}"
        vector = embed_text(text)
        db = lancedb.connect(LANCEDB_PATH)
        table = db.open_table("insurance_glossary_vectors")
        table.delete(f"record_id = '{str(request.term_id).replace(chr(39), chr(39) * 2)}'")
        table.add([{
            "id": str(uuid.uuid4()), "term": term, "definition": request.new_definition,
            "business_context": f"domain={domain}; synonyms={synonyms}", "subject_area": domain,
            "source_table": "business_glossary", "record_id": str(request.term_id),
            "text_chunk": text,
            "metadata": json.dumps({"updated_by": request.updated_by, "reason": request.reason}),
            "vector": vector,
        }])
        reembedded = True
    except Exception as exc:
        embed_error = f"{type(exc).__name__}: {exc}"

    # Audit trail
    tracer.log_step(
        query_id=f"glossary-update-{request.term_id}",
        agent_name="glossary_governance",
        input_summary=f"term={term} updated_by={request.updated_by} reason={request.reason}",
        output_summary=f"old={str(old_definition)[:200]} new={request.new_definition[:200]} reembedded={reembedded}",
        duration_ms=0,
    )
    return {
        "status": "updated",
        "term_id": request.term_id,
        "term": term,
        "reembedded": reembedded,
        "embed_error": embed_error,
        "audited": True,
    }


# ---------------------------------------------------------------------------
# Evidence Hub  (note: /evidence/recent MUST be registered before /{query_id})
# ---------------------------------------------------------------------------
@router.get("/evidence/recent")
def evidence_recent(limit: int = 20) -> list[dict[str, Any]]:
    return tracer.get_recent_traces(min(max(limit, 1), 100))


@router.get("/evidence/{query_id}")
def evidence(query_id: str) -> dict[str, Any]:
    steps = tracer.get_trace(query_id)
    if not steps:
        raise HTTPException(status_code=404, detail=f"No trace found for query_id: {query_id}")
    return {
        "query_id": query_id,
        "steps": steps,
        "agents_involved": sorted({s["agent_name"] for s in steps}),
        "total_duration_ms": sum(int(s.get("duration_ms") or 0) for s in steps),
        "total_tokens": sum(int(s.get("tokens_used") or 0) for s in steps),
        "cache_hit": any(bool(s.get("cache_hit")) for s in steps),
    }


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------
@router.get("/health")
def health() -> dict[str, Any]:
    duck = duckdb_health()

    lance_status: dict[str, Any] = {"status": "ok", "path": LANCEDB_PATH, "tables": {}}
    try:
        db = lancedb.connect(LANCEDB_PATH)
        names = db.list_tables().tables or []
        for name in names:
            try:
                lance_status["tables"][name] = db.open_table(name).count_rows()
            except Exception:
                lance_status["tables"][name] = None
    except Exception as exc:
        lance_status = {"status": "error", "error": f"{type(exc).__name__}: {exc}"}

    return {
        "service": "insurance-v2-agentic-api",
        "duckdb": duck,
        "lancedb": lance_status,
        "gemini": {
            "api_key_present": bool(GEMINI_API_KEY),
            "generation_model": GEMINI_MODEL,
            "embedding_model": "gemini-embedding-001",
        },
        "vector_index_stats": lance_status.get("tables", {}),
        "cache_hit_rate_24h": tracer.cache_hit_rate_24h(),
    }
