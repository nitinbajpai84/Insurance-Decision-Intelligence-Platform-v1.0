from __future__ import annotations

from uuid import UUID

from fastapi import FastAPI, Query
from pydantic import BaseModel

from nba_engine.context import NBAContextProvider
from nba_engine.db import audit_decision, connect, fetch_batch_context, fetch_customer_context, persist_decisions
from nba_engine.explainer import LLMExplanationLayer
from nba_engine.models import CustomerDecisionInput, NextBestActionDecision
from nba_engine.rules import decide_next_best_action


app = FastAPI(title="Insurance Next-Best-Action Engine", version="1.0.0")


class BatchDecisionResponse(BaseModel):
    decisions: list[NextBestActionDecision]
    persisted_count: int = 0
    audited_count: int = 0


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/decide", response_model=NextBestActionDecision)
def decide_from_payload(
    payload: CustomerDecisionInput,
    retrieve_context: bool = Query(default=False),
    use_llm: bool = Query(default=False),
) -> NextBestActionDecision:
    decision = decide_next_best_action(payload)
    return enrich_decision(decision, retrieve_context=retrieve_context, use_llm=use_llm)


@app.get("/customers/{customer_id}/next-best-action", response_model=NextBestActionDecision)
def decide_customer(
    customer_id: UUID,
    persist: bool = Query(default=False),
    retrieve_context: bool = Query(default=True),
    use_llm: bool = Query(default=False),
    audit: bool = Query(default=True),
) -> NextBestActionDecision:
    with connect() as conn:
        context = fetch_customer_context(conn, customer_id)
        decision = enrich_decision(decide_next_best_action(context), retrieve_context=retrieve_context, use_llm=use_llm)
        if persist and decision.recommended_action != "Monitor customer":
            persist_decisions(conn, [decision])
        if audit:
            audit_decision(
                conn,
                decision,
                request_payload={
                    "customer_id": str(customer_id),
                    "persist": persist,
                    "retrieve_context": retrieve_context,
                    "use_llm": use_llm,
                },
                status="persisted" if persist else "completed",
            )
        return decision


@app.post("/batch/next-best-actions", response_model=BatchDecisionResponse)
def decide_batch(
    limit: int = Query(default=100, ge=1, le=5000),
    persist: bool = Query(default=False),
    retrieve_context: bool = Query(default=False),
    use_llm: bool = Query(default=False),
    audit: bool = Query(default=False),
) -> BatchDecisionResponse:
    with connect() as conn:
        contexts = fetch_batch_context(conn, limit)
        decisions = [
            enrich_decision(decide_next_best_action(context), retrieve_context=retrieve_context, use_llm=use_llm)
            for context in contexts
        ]
        persisted_count = persist_decisions(conn, decisions) if persist else 0
        audited_count = 0
        if audit:
            for decision in decisions:
                audit_decision(
                    conn,
                    decision,
                    request_payload={
                        "batch": True,
                        "limit": limit,
                        "persist": persist,
                        "retrieve_context": retrieve_context,
                        "use_llm": use_llm,
                    },
                    status="persisted" if persist else "completed",
                )
                audited_count += 1
    return BatchDecisionResponse(decisions=decisions, persisted_count=persisted_count, audited_count=audited_count)


def enrich_decision(
    decision: NextBestActionDecision,
    retrieve_context: bool = True,
    use_llm: bool = False,
) -> NextBestActionDecision:
    context_used = []
    if retrieve_context:
        try:
            context_used = NBAContextProvider().retrieve_for_decision(decision)
        except Exception as exc:
            context_used = [{"title": "context_retrieval_failed", "snippet": str(exc)}]
    return LLMExplanationLayer(enable_llm=use_llm).explain(decision, context_used)
