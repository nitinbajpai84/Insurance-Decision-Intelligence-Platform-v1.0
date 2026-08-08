#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

import psycopg
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from psycopg.rows import dict_row
from pydantic import BaseModel, Field


class EvidenceItem(BaseModel):
    evidence_type: str
    evidence_label: str
    evidence_value: dict[str, Any] = Field(default_factory=dict)
    source_table: str | None = None
    source_column: str | None = None
    metric_name: str | None = None
    model_name: str | None = None
    business_rule: str | None = None
    evidence_weight: float | None = None


class RecommendationExplanation(BaseModel):
    insight_lineage_id: UUID | None = None
    next_best_action_id: UUID | None = None
    recommendation: str
    supporting_facts: list[str]
    source_tables: list[str]
    source_columns: dict[str, list[str]]
    metrics_used: list[str]
    business_rules_used: list[str]
    ml_models_used: list[str]
    context_documents_used: list[dict[str, Any]]
    confidence_score: float | None = None
    timestamp: datetime
    evidence: list[EvidenceItem]
    business_reason: str | None = None
    suggested_message: str | None = None


class ExplainRecommendationRequest(BaseModel):
    next_best_action_id: UUID
    question: str | None = None
    role_code: str | None = None
    persist: bool = True


class LineagePayloadRequest(BaseModel):
    insight_type: str = "recommendation"
    role_code: str | None = None
    question: str | None = None
    recommendation: str
    business_reason: str | None = None
    confidence_score: float | None = Field(default=None, ge=0.0, le=1.0)
    source_tables: list[str] = Field(default_factory=list)
    source_columns: dict[str, list[str]] = Field(default_factory=dict)
    metrics_used: list[str] = Field(default_factory=list)
    business_rules_used: list[str] = Field(default_factory=list)
    ml_models_used: list[str] = Field(default_factory=list)
    context_document_ids: list[UUID] = Field(default_factory=list)
    explanation_payload: dict[str, Any] = Field(default_factory=dict)


def get_db_url(env_file: str = ".env") -> str:
    load_dotenv(env_file)
    db_url = os.getenv("SUPABASE_DB_URL")
    if not db_url:
        raise RuntimeError("Missing SUPABASE_DB_URL in .env.")
    return db_url


def connect(db_url: str | None = None):
    return psycopg.connect(db_url or get_db_url(), row_factory=dict_row, connect_timeout=30)


def json_ready(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: json_ready(item) for key, item in value.items()}
    if isinstance(value, list):
        return [json_ready(item) for item in value]
    if isinstance(value, UUID):
        return str(value)
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


def _array(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def fetch_next_best_action(conn, next_best_action_id: UUID) -> dict[str, Any]:
    with conn.cursor() as cur:
        cur.execute(
            """
            select
              nba.*,
              c.customer_number,
              a.agent_number,
              p.product_name
            from public.next_best_actions nba
            left join public.customers c on c.customer_id = nba.customer_id
            left join public.agents a on a.agent_id = nba.agent_id
            left join public.products p on p.product_id = nba.product_id
            where nba.next_best_action_id = %s
            """,
            (str(next_best_action_id),),
        )
        row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail=f"next_best_action_id not found: {next_best_action_id}")
    return dict(row)


def build_supporting_facts(nba: dict[str, Any]) -> list[str]:
    facts: list[str] = []
    for score in _array(nba.get("model_scores_used")):
        if not isinstance(score, dict):
            continue
        model_name = score.get("model_name") or score.get("score_name")
        score_value = score.get("score") or score.get("score_value") or score.get("probability")
        score_band = score.get("score_band")
        if model_name and score_value is not None:
            band_text = f" ({score_band})" if score_band else ""
            facts.append(f"{model_name} score {score_value}{band_text}")
    if nba.get("decision_rule"):
        facts.append(f"Business rule fired: {nba['decision_rule']}")
    if nba.get("suppression_reason"):
        facts.append(f"Suppression applied: {nba['suppression_reason']}")
    if nba.get("product_name"):
        facts.append(f"Recommended product: {nba['product_name']}")
    if nba.get("expiry_date"):
        facts.append(f"Recommendation expires on {nba['expiry_date']}")
    return facts


def build_evidence(nba: dict[str, Any]) -> list[EvidenceItem]:
    evidence: list[EvidenceItem] = []
    if nba.get("decision_rule"):
        evidence.append(
            EvidenceItem(
                evidence_type="business_rule",
                evidence_label=str(nba["decision_rule"]),
                evidence_value={"decision_rule": nba.get("decision_rule"), "suppression_reason": nba.get("suppression_reason")},
                source_table="next_best_actions",
                business_rule=nba.get("decision_rule"),
                evidence_weight=0.8,
            )
        )
    for score in _array(nba.get("model_scores_used")):
        if not isinstance(score, dict):
            continue
        evidence.append(
            EvidenceItem(
                evidence_type="model_score",
                evidence_label=str(score.get("score_name") or score.get("model_name") or "model_score"),
                evidence_value=score,
                source_table="model_scores",
                metric_name=score.get("score_name"),
                model_name=score.get("model_name"),
                evidence_weight=_safe_float(score.get("score") or score.get("score_value") or score.get("probability")),
            )
        )
    for context in _array(nba.get("context_used")):
        if not isinstance(context, dict):
            continue
        evidence.append(
            EvidenceItem(
                evidence_type="context_document",
                evidence_label=str(context.get("title") or "semantic context"),
                evidence_value=context,
                source_table="semantic_documents",
                evidence_weight=_safe_float((context.get("score") or {}).get("hybrid") if isinstance(context.get("score"), dict) else None),
            )
        )
    return evidence


def _safe_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def build_recommendation_explanation(nba: dict[str, Any], insight_lineage_id: UUID | None = None) -> RecommendationExplanation:
    model_scores = [item for item in _array(nba.get("model_scores_used")) if isinstance(item, dict)]
    context_used = [item for item in _array(nba.get("context_used")) if isinstance(item, dict)]
    ml_models = sorted({str(item["model_name"]) for item in model_scores if item.get("model_name")})
    metrics = sorted({str(item["score_name"]) for item in model_scores if item.get("score_name")})
    context_docs = [
        {
            "semantic_document_id": item.get("semantic_document_id"),
            "title": item.get("title"),
            "document_type": item.get("document_type"),
            "business_domain": item.get("business_domain"),
            "retrieval_score": (item.get("score") or {}).get("hybrid") if isinstance(item.get("score"), dict) else None,
        }
        for item in context_used
    ]
    return RecommendationExplanation(
        insight_lineage_id=insight_lineage_id,
        next_best_action_id=nba.get("next_best_action_id"),
        recommendation=nba.get("recommended_action") or nba.get("action_type") or "Recommendation",
        supporting_facts=build_supporting_facts(nba),
        source_tables=[
            "next_best_actions",
            "model_scores",
            "model_predictions",
            "customers",
            "policies",
            "products",
            "campaign_responses",
            "customer_complaints",
            "payments",
            "semantic_documents",
        ],
        source_columns={
            "next_best_actions": ["recommended_action", "priority_score", "business_reason", "confidence_score", "decision_rule", "model_scores_used", "context_used"],
            "model_scores": ["model_name", "model_version", "score_name", "score_value", "score_band", "top_reason_1", "top_reason_2", "top_reason_3"],
            "semantic_documents": ["title", "document_type", "business_domain", "content", "related_tables", "related_metrics"],
        },
        metrics_used=metrics or ["priority_score", "confidence_score"],
        business_rules_used=[item for item in [nba.get("decision_rule"), nba.get("suppression_reason")] if item],
        ml_models_used=ml_models,
        context_documents_used=context_docs,
        confidence_score=_safe_float(nba.get("confidence_score") or nba.get("priority_score")),
        timestamp=datetime.now(timezone.utc),
        evidence=build_evidence(nba),
        business_reason=nba.get("business_reason") or nba.get("action_reason"),
        suggested_message=nba.get("suggested_message"),
    )


def create_lineage_from_payload(conn, payload: LineagePayloadRequest) -> UUID:
    with conn.cursor() as cur:
        cur.execute(
            """
            insert into public.insight_lineage (
              insight_type,
              role_code,
              question,
              recommendation,
              business_reason,
              confidence_score,
              source_tables,
              source_columns,
              metrics_used,
              business_rules_used,
              ml_models_used,
              context_document_ids,
              explanation_payload,
              status
            )
            values (%s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s, %s::uuid[], %s::jsonb, 'created')
            returning insight_lineage_id
            """,
            (
                payload.insight_type,
                payload.role_code,
                payload.question,
                payload.recommendation,
                payload.business_reason,
                payload.confidence_score,
                payload.source_tables,
                json.dumps(payload.source_columns),
                payload.metrics_used,
                payload.business_rules_used,
                payload.ml_models_used,
                [str(item) for item in payload.context_document_ids],
                json.dumps(payload.explanation_payload, default=str),
            ),
        )
        lineage_id = cur.fetchone()["insight_lineage_id"]
    conn.commit()
    return lineage_id


def create_lineage_for_nba(conn, next_best_action_id: UUID, question: str | None, role_code: str | None) -> UUID:
    with conn.cursor() as cur:
        cur.execute(
            "select public.create_recommendation_lineage_from_nba(%s, %s, %s) as insight_lineage_id",
            (str(next_best_action_id), question, role_code),
        )
        lineage_id = cur.fetchone()["insight_lineage_id"]
    conn.commit()
    return lineage_id


def fetch_recommendation_explainability(conn, next_best_action_id: UUID) -> dict[str, Any] | None:
    with conn.cursor() as cur:
        cur.execute(
            """
            select *
            from public.v_recommendation_explainability
            where next_best_action_id = %s
            order by explanation_timestamp desc
            limit 1
            """,
            (str(next_best_action_id),),
        )
        row = cur.fetchone()
    return json_ready(dict(row)) if row else None


app = FastAPI(title="Insurance Explainability Governance Service", version="1.0.0")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "insurance-explainability-governance"}


@app.post("/explain/recommendation", response_model=RecommendationExplanation)
def explain_recommendation(request: ExplainRecommendationRequest) -> RecommendationExplanation:
    with connect() as conn:
        nba = fetch_next_best_action(conn, request.next_best_action_id)
        lineage_id = None
        if request.persist:
            lineage_id = create_lineage_for_nba(conn, request.next_best_action_id, request.question, request.role_code)
        return build_recommendation_explanation(nba, lineage_id)


@app.get("/explain/recommendation/{next_best_action_id}")
def get_recommendation_explainability(next_best_action_id: UUID) -> dict[str, Any]:
    with connect() as conn:
        existing = fetch_recommendation_explainability(conn, next_best_action_id)
        if existing:
            return existing
        nba = fetch_next_best_action(conn, next_best_action_id)
        return json_ready(build_recommendation_explanation(nba).model_dump())


@app.post("/lineage")
def create_lineage(payload: LineagePayloadRequest) -> dict[str, str]:
    with connect() as conn:
        lineage_id = create_lineage_from_payload(conn, payload)
    return {"insight_lineage_id": str(lineage_id)}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Explainability governance helper.")
    parser.add_argument("--next-best-action-id")
    parser.add_argument("--question")
    parser.add_argument("--role-code")
    parser.add_argument("--no-persist", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.next_best_action_id:
        raise SystemExit("Provide --next-best-action-id or run API with uvicorn explainability_service:app --reload --port 8040")
    with connect() as conn:
        nba = fetch_next_best_action(conn, UUID(args.next_best_action_id))
        lineage_id = None
        if not args.no_persist:
            lineage_id = create_lineage_for_nba(conn, UUID(args.next_best_action_id), args.question, args.role_code)
        explanation = build_recommendation_explanation(nba, lineage_id)
    print(json.dumps(json_ready(explanation.model_dump()), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

