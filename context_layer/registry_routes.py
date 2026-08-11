"""
Context-layer API — agent gallery, profiles, and conversational ask.

Spec: docs/context-layer/DESIGN.md §7. Registered in backend_v2/api/main.py
behind try/except like the graph routers. All DuckDB access goes through
graph.db_util.robust_connect so every connection shares DUCKDB_CONFIG.
"""
from __future__ import annotations

import json
import sys
import uuid
from pathlib import Path
from typing import Any, AsyncGenerator

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend_v2.agents.orchestrator import stream_pipeline
from backend_v2.config import DUCKDB_PATH
from graph.db_util import robust_connect

router = APIRouter(prefix="/api/v2", tags=["context-layer"])

_JSON_COLS = {"skills", "knowledge_scopes", "policies", "source_systems", "core_tables",
              "master_data", "events", "external_data", "document_data",
              "model_families", "kpi_impact"}


def _row_dict(cols: list[str], row: tuple) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for col, val in zip(cols, row):
        if col in _JSON_COLS and isinstance(val, str):
            try:
                val = json.loads(val)
            except (ValueError, TypeError):
                pass
        if hasattr(val, "isoformat"):
            val = val.isoformat()
        out[col] = val
    return out


def _query(sql: str, params: list | None = None, *, write: bool = False) -> list[dict[str, Any]]:
    con = robust_connect(DUCKDB_PATH, read_only=not write)
    try:
        cur = con.execute(sql, params or [])
        cols = [d[0] for d in (cur.description or [])]
        return [_row_dict(cols, r) for r in cur.fetchall()]
    finally:
        con.close()


def _execute(sql: str, params: list | None = None) -> None:
    con = robust_connect(DUCKDB_PATH, read_only=False)
    try:
        con.execute(sql, params or [])
    finally:
        con.close()


# ---------------------------------------------------------------------------
# Gallery + profiles
# ---------------------------------------------------------------------------
@router.get("/ai-agents")
def list_agents() -> dict[str, Any]:
    platform = _query(
        "select agent_id, name, description, role_scope, skills, jurisdiction, status "
        "from agent_registry where initiative_id is null order by name"
    )
    initiatives = _query(
        "select a.agent_id, i.initiative_id, i.domain, i.name, i.strategic_goal, "
        "i.ai_capability, i.primary_users, i.phase, i.value_score, i.complexity_score, "
        "i.industry_maturity, i.model_families, a.skills, a.role_scope, a.status "
        "from initiative_registry i "
        "left join agent_registry a on a.initiative_id = i.initiative_id "
        "where i.status != 'retired' "
        "order by case i.domain when 'Health' then 0 when 'Operations' then 1 else 2 end, i.initiative_id"
    )
    return {"platform_agents": platform, "initiatives": initiatives,
            "counts": {"total": len(initiatives),
                       "functional": sum(1 for a in platform + initiatives
                                         if a.get("status") in ("functional", "live"))}}


@router.get("/ai-agents/{agent_id}")
def get_agent(agent_id: str) -> dict[str, Any]:
    rows = _query("select * from agent_registry where agent_id = ?", [agent_id])
    if not rows:
        raise HTTPException(status_code=404, detail=f"agent not found: {agent_id}")
    agent = rows[0]
    if agent.get("initiative_id"):
        ini = _query("select * from initiative_registry where initiative_id = ?",
                     [agent["initiative_id"]])
        agent["initiative"] = ini[0] if ini else None
    return agent


# ---------------------------------------------------------------------------
# Conversational ask (SSE) with memory
# ---------------------------------------------------------------------------
class AgentAskRequest(BaseModel):
    question: str = Field(min_length=3, max_length=2000)
    conversation_id: str | None = None
    user_role: str | None = None


def _sse(payload: dict[str, Any]) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False, default=str)}\n\n"


def _conversation_context(conversation_id: str, limit_turns: int = 4) -> str:
    rows = _query(
        "select role, content from conversation_messages where conversation_id = ? "
        "order by turn_index desc limit ?", [conversation_id, limit_turns])
    if not rows:
        return ""
    lines = [f"{r['role']}: {str(r['content'])[:300]}" for r in reversed(rows)]
    return " | ".join(lines)


@router.post("/ai-agents/{agent_id}/ask")
async def agent_ask(agent_id: str, request: AgentAskRequest) -> StreamingResponse:
    rows = _query("select * from agent_registry where agent_id = ?", [agent_id])
    if not rows:
        raise HTTPException(status_code=404, detail=f"agent not found: {agent_id}")
    agent = rows[0]
    if agent.get("status") not in ("functional", "live"):
        raise HTTPException(
            status_code=409,
            detail=f"agent {agent_id} is '{agent.get('status')}' — browse its charter in the "
                   f"gallery; it is not yet wired to the pipeline.")

    conversation_id = request.conversation_id
    if conversation_id:
        if not _query("select 1 from conversations where conversation_id = ?", [conversation_id]):
            raise HTTPException(status_code=404, detail=f"conversation not found: {conversation_id}")
    else:
        conversation_id = str(uuid.uuid4())
        _execute(
            "insert into conversations (conversation_id, agent_id, user_role, title) values (?, ?, ?, ?)",
            [conversation_id, agent_id, request.user_role, request.question[:120]])

    turn_rows = _query(
        "select coalesce(max(turn_index), -1) + 1 as next from conversation_messages "
        "where conversation_id = ?", [conversation_id])
    next_turn = int(turn_rows[0]["next"])
    _execute(
        "insert into conversation_messages (conversation_id, turn_index, role, content) values (?, ?, 'user', ?)",
        [conversation_id, next_turn, request.question])

    history = _conversation_context(conversation_id) if next_turn > 0 else ""
    question = (f"[conversation so far: {history}] {request.question}" if history
                else request.question)
    role = agent.get("role_scope") or "Executive Leadership"
    query_id = str(uuid.uuid4())

    async def event_stream() -> AsyncGenerator[str, None]:
        answer_parts: list[str] = []
        yield _sse({"step": "conversation", "conversation_id": conversation_id,
                    "agent_id": agent_id, "turn_index": next_turn})
        try:
            async for event in stream_pipeline(question, role, query_id):
                if event.get("step") == "insight_token":
                    answer_parts.append(event.get("token") or "")
                yield _sse(event)
        except Exception as exc:
            yield _sse({"step": "error", "status": "failed",
                        "error": f"{type(exc).__name__}: {exc}", "query_id": query_id})
        finally:
            answer = "".join(answer_parts).strip()
            if answer:
                try:
                    _execute(
                        "insert into conversation_messages (conversation_id, turn_index, role, content, query_id) "
                        "values (?, ?, 'agent', ?, ?)",
                        [conversation_id, next_turn + 1, answer, query_id])
                    _execute("update conversations set last_active_at = now() where conversation_id = ?",
                             [conversation_id])
                except Exception as exc:  # persistence must never kill the stream
                    print(f"[context-layer] WARN failed to persist agent turn: {exc}", file=sys.stderr)

    return StreamingResponse(
        event_stream(), media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no",
                 "X-Query-Id": query_id, "X-Conversation-Id": conversation_id})


# ---------------------------------------------------------------------------
# Conversation history
# ---------------------------------------------------------------------------
@router.get("/ai-agents/{agent_id}/conversations")
def list_conversations(agent_id: str, limit: int = 20) -> list[dict[str, Any]]:
    return _query(
        "select conversation_id, title, user_role, created_at, last_active_at, "
        "(select count(*) from conversation_messages m where m.conversation_id = c.conversation_id) as message_count "
        "from conversations c where agent_id = ? order by last_active_at desc limit ?",
        [agent_id, min(max(limit, 1), 100)])


@router.get("/conversations/{conversation_id}")
def get_conversation(conversation_id: str) -> dict[str, Any]:
    convo = _query("select * from conversations where conversation_id = ?", [conversation_id])
    if not convo:
        raise HTTPException(status_code=404, detail=f"conversation not found: {conversation_id}")
    messages = _query(
        "select turn_index, role, content, query_id, created_at from conversation_messages "
        "where conversation_id = ? order by turn_index", [conversation_id])
    return {**convo[0], "messages": messages}
