from __future__ import annotations

import os
import json
from typing import Iterable
from uuid import UUID

import psycopg
from dotenv import load_dotenv
from psycopg.rows import dict_row

from nba_engine.models import CustomerDecisionInput, NextBestActionDecision


def get_db_url(env_file: str = ".env") -> str:
    load_dotenv(env_file)
    db_url = os.getenv("SUPABASE_DB_URL")
    if not db_url:
        raise RuntimeError("Missing SUPABASE_DB_URL in environment or .env file.")
    return db_url


def connect(db_url: str | None = None) -> psycopg.Connection:
    return psycopg.connect(db_url or get_db_url(), row_factory=dict_row, connect_timeout=30)


def fetch_customer_context(conn: psycopg.Connection, customer_id: UUID) -> CustomerDecisionInput:
    with conn.cursor() as cur:
        cur.execute(
            """
            select
              customer_id,
              agent_id,
              propensity_to_buy_score,
              lapse_risk_score,
              churn_risk_score,
              next_best_product_score,
              lead_conversion_score,
              customer_lifetime_value,
              campaign_response_score,
              agent_performance_score,
              customer_contact_preference,
              marketing_opt_out,
              active_policy_count,
              has_health_policy,
              next_policy_renewal_date,
              open_opportunity_count,
              unresolved_complaint_count,
              recent_service_issue_count,
              payment_delay_count,
              agent_capacity_status,
              recommended_product_id,
              next_best_product_prediction,
              coalesce(model_scores_used, '[]'::jsonb) as model_scores_used
            from public.v_nba_customer_decision_context_v2
            where customer_id = %s
            """,
            (str(customer_id),),
        )
        row = cur.fetchone()
    if not row:
        raise ValueError(f"Customer not found in v_nba_customer_context: {customer_id}")
    return CustomerDecisionInput(**row)


def fetch_batch_context(conn: psycopg.Connection, limit: int) -> list[CustomerDecisionInput]:
    with conn.cursor() as cur:
        cur.execute(
            """
            select
              customer_id,
              agent_id,
              propensity_to_buy_score,
              lapse_risk_score,
              churn_risk_score,
              next_best_product_score,
              lead_conversion_score,
              customer_lifetime_value,
              campaign_response_score,
              agent_performance_score,
              customer_contact_preference,
              marketing_opt_out,
              active_policy_count,
              has_health_policy,
              next_policy_renewal_date,
              open_opportunity_count,
              unresolved_complaint_count,
              recent_service_issue_count,
              payment_delay_count,
              agent_capacity_status,
              recommended_product_id,
              next_best_product_prediction,
              coalesce(model_scores_used, '[]'::jsonb) as model_scores_used
            from public.v_nba_customer_decision_context_v2
            order by greatest(
              propensity_to_buy_score,
              lapse_risk_score,
              churn_risk_score,
              next_best_product_score,
              lead_conversion_score,
              campaign_response_score
            ) desc
            limit %s
            """,
            (limit,),
        )
        return [CustomerDecisionInput(**row) for row in cur.fetchall()]


def _json_default(value):
    if isinstance(value, UUID):
        return str(value)
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _decision_payload(decision: NextBestActionDecision) -> dict:
    if hasattr(decision, "model_dump"):
        return decision.model_dump(mode="json")
    return json.loads(decision.json())


def persist_decision(conn: psycopg.Connection, decision: NextBestActionDecision) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            insert into public.next_best_actions (
              customer_id,
              agent_id,
              product_id,
              action_type,
              action_rank,
              priority_score,
              due_date,
              action_status,
              action_reason,
              recommended_action,
              suggested_message,
              expiry_date,
              decision_rule,
              suppression_reason,
              business_reason,
              model_scores_used,
              context_used,
              confidence_score
            )
            values (
              %s, %s, %s, %s, 1,
              %s, %s, 'recommended', %s,
              %s, %s, %s, %s, %s,
              %s, %s::jsonb, %s::jsonb, %s
            )
            """,
            (
                str(decision.customer_id),
                str(decision.agent_id) if decision.agent_id else None,
                str(decision.recommended_product_id) if decision.recommended_product_id else None,
                decision.action_type,
                decision.priority_score,
                decision.expiry_date,
                decision.business_reason,
                decision.recommended_action,
                decision.suggested_message,
                decision.expiry_date,
                decision.decision_rule,
                decision.suppression_reason,
                decision.business_reason,
                json.dumps(decision.model_scores_used, default=_json_default),
                json.dumps(decision.context_used, default=_json_default),
                decision.confidence_score,
            ),
        )
    conn.commit()


def persist_decisions(conn: psycopg.Connection, decisions: Iterable[NextBestActionDecision]) -> int:
    count = 0
    for decision in decisions:
        if decision.recommended_action != "Monitor customer":
            persist_decision(conn, decision)
            count += 1
    return count


def audit_decision(
    conn: psycopg.Connection,
    decision: NextBestActionDecision,
    request_payload: dict | None = None,
    status: str = "completed",
    error_message: str | None = None,
) -> None:
    context_document_ids = [
        item.get("semantic_document_id")
        for item in decision.context_used
        if isinstance(item, dict) and item.get("semantic_document_id")
    ]
    with conn.cursor() as cur:
        cur.execute(
            """
            insert into public.nba_decision_audit (
              customer_id,
              agent_id,
              request_payload,
              decision_payload,
              context_document_ids,
              decision_status,
              error_message
            )
            values (%s, %s, %s::jsonb, %s::jsonb, %s::uuid[], %s, %s)
            """,
            (
                str(decision.customer_id),
                str(decision.agent_id) if decision.agent_id else None,
                json.dumps(request_payload or {}, default=_json_default),
                json.dumps(_decision_payload(decision), default=_json_default),
                context_document_ids,
                status,
                error_message,
            ),
        )
    conn.commit()
