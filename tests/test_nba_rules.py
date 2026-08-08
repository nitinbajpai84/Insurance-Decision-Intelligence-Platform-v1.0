from __future__ import annotations

from datetime import date, timedelta
from uuid import UUID

from nba_engine.models import CustomerDecisionInput
from nba_engine.rules import decide_next_best_action


CUSTOMER_ID = UUID("11111111-1111-1111-1111-111111111111")
AGENT_ID = UUID("22222222-2222-2222-2222-222222222222")
PRODUCT_ID = UUID("33333333-3333-3333-3333-333333333333")
TODAY = date(2026, 5, 31)


def customer(**overrides):
    base = {
        "customer_id": CUSTOMER_ID,
        "agent_id": AGENT_ID,
    }
    base.update(overrides)
    return CustomerDecisionInput(**base)


def test_unresolved_complaint_suppresses_sales_action():
    decision = decide_next_best_action(
        customer(
            unresolved_complaint_count=1,
            propensity_to_buy_score=0.95,
            has_health_policy=False,
            recommended_product_id=PRODUCT_ID,
        ),
        today=TODAY,
    )

    assert decision.recommended_action == "Resolve complaint before sales outreach"
    assert decision.recommended_product_id is None
    assert decision.action_type == "service_recovery"
    assert decision.suppression_reason == "unresolved_complaint"
    assert decision.business_reason
    assert decision.confidence_score > 0


def test_high_lapse_risk_recommends_retention_call():
    decision = decide_next_best_action(customer(lapse_risk_score=0.72), today=TODAY)

    assert decision.recommended_action == "Retention call"
    assert decision.action_type == "retention_outreach"
    assert decision.decision_rule == "lapse_high"


def test_health_cross_sell_when_propensity_high_and_no_health_policy():
    decision = decide_next_best_action(
        customer(
            propensity_to_buy_score=0.81,
            has_health_policy=False,
            recommended_product_id=PRODUCT_ID,
        ),
        today=TODAY,
    )

    assert decision.recommended_action == "Health cross-sell"
    assert decision.recommended_product_id == PRODUCT_ID
    assert decision.action_type == "offer_product"


def test_marketing_opt_out_suppresses_campaign_action():
    decision = decide_next_best_action(
        customer(campaign_response_score=0.88, marketing_opt_out=True),
        today=TODAY,
    )

    assert decision.recommended_action == "Monitor customer"
    assert decision.suppression_reason == "marketing_opt_out"
    assert decision.decision_rule == "marketing_opt_out_suppression"


def test_campaign_response_follow_up_expires_within_7_days():
    decision = decide_next_best_action(customer(campaign_response_score=0.73), today=TODAY)

    assert decision.recommended_action == "Campaign follow-up"
    assert decision.expiry_date == TODAY + timedelta(days=7)


def test_renewal_within_60_days_takes_priority():
    decision = decide_next_best_action(
        customer(
            next_policy_renewal_date=TODAY + timedelta(days=45),
            propensity_to_buy_score=0.91,
            has_health_policy=False,
            recommended_product_id=PRODUCT_ID,
        ),
        today=TODAY,
    )

    assert decision.recommended_action == "Renewal conversation"
    assert decision.decision_rule == "renewal_60d"
    assert decision.recommended_product_id is None


def test_churn_with_unresolved_complaint_recommends_service_recovery():
    decision = decide_next_best_action(
        customer(churn_risk_score=0.84, unresolved_complaint_count=1),
        today=TODAY,
    )

    assert decision.recommended_action == "Service recovery"
    assert decision.decision_rule == "churn_complaint_service_recovery"
    assert decision.action_type == "service_recovery"


def test_low_capacity_agent_is_not_assigned():
    decision = decide_next_best_action(
        customer(lapse_risk_score=0.78, agent_capacity_status="LOW_CAPACITY"),
        today=TODAY,
    )

    assert decision.recommended_action == "Retention call"
    assert decision.agent_id is None
    assert "capacity constrained" in decision.business_reason
