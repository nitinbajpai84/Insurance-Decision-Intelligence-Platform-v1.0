from __future__ import annotations

from typing import Any

from context_retriever_service import ContextRetriever

from nba_engine.models import NextBestActionDecision


def build_context_question(decision: NextBestActionDecision) -> str:
    bits = [
        "next best action",
        decision.recommended_action,
        decision.decision_rule,
        decision.business_reason,
    ]
    if decision.recommended_product_id:
        bits.append("next best product cross sell")
    if decision.suppression_reason:
        bits.append(decision.suppression_reason)
    return " ".join(str(bit) for bit in bits if bit)


def flatten_context_bundle(bundle: dict[str, list[dict[str, Any]]], limit: int = 8) -> list[dict[str, Any]]:
    flattened: list[dict[str, Any]] = []
    for bucket, docs in bundle.items():
        if bucket == "sql_examples":
            continue
        for doc in docs:
            flattened.append(
                {
                    "semantic_document_id": doc.get("semantic_document_id"),
                    "title": doc.get("title"),
                    "document_type": doc.get("document_type"),
                    "business_domain": doc.get("business_domain"),
                    "related_tables": doc.get("related_tables", []),
                    "related_models": doc.get("related_models", []),
                    "related_metrics": doc.get("related_metrics", []),
                    "score": doc.get("score", {}),
                    "snippet": str(doc.get("content", ""))[:500],
                }
            )
    flattened.sort(key=lambda item: item.get("score", {}).get("hybrid", 0), reverse=True)
    return flattened[:limit]


class NBAContextProvider:
    def __init__(self, env_file: str = ".env") -> None:
        self.retriever = ContextRetriever(env_file)

    def retrieve_for_decision(self, decision: NextBestActionDecision, match_count: int = 8) -> list[dict[str, Any]]:
        bundle = self.retriever.retrieve(
            question=build_context_question(decision),
            match_count=match_count,
            threshold=0.0,
            business_domain=None,
        )
        return flatten_context_bundle(bundle, limit=match_count)

