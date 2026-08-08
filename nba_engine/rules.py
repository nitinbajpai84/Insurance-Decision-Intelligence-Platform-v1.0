from __future__ import annotations

from datetime import date, timedelta

from nba_engine.models import CustomerDecisionInput, NextBestActionDecision


HIGH = 0.60
PROPENSITY_HIGH = 0.70
HIGH_CLV = 10000.0
LOW_AGENT_PERFORMANCE = 0.35


def _max_priority(customer: CustomerDecisionInput, *extra_scores: float) -> float:
    agent_penalty = 0.08 if _agent_is_constrained(customer) else 0.0
    return round(
        min(
            1.0,
            max(
                0.0,
                max(
                    customer.propensity_to_buy_score,
                    customer.lapse_risk_score,
                    customer.churn_risk_score,
                    customer.next_best_product_score,
                    customer.lead_conversion_score,
                    customer.campaign_response_score,
                    0.85 if customer.customer_lifetime_value >= HIGH_CLV else 0.0,
                    0.75 if customer.payment_delay_count > 0 else 0.0,
                    *extra_scores,
                )
                - agent_penalty,
            ),
        ),
        6,
    )


def _agent_is_constrained(customer: CustomerDecisionInput) -> bool:
    return customer.agent_capacity_status == "LOW_CAPACITY" or customer.agent_performance_score < LOW_AGENT_PERFORMANCE


def _assigned_agent(customer: CustomerDecisionInput):
    return None if _agent_is_constrained(customer) else customer.agent_id


def _confidence(customer: CustomerDecisionInput, rule_strength: float) -> float:
    score_support = max(
        customer.propensity_to_buy_score,
        customer.lapse_risk_score,
        customer.churn_risk_score,
        customer.next_best_product_score,
        customer.lead_conversion_score,
        customer.campaign_response_score,
    )
    value = (
        0.55
        + (0.15 if customer.model_scores_used else 0.0)
        + (0.15 if score_support >= 0.75 else 0.0)
        + rule_strength
        - (0.05 if customer.marketing_opt_out else 0.0)
        - (0.10 if _agent_is_constrained(customer) else 0.0)
    )
    return round(min(1.0, max(0.0, value)), 6)


def _human_contact_note(customer: CustomerDecisionInput) -> str:
    if customer.customer_lifetime_value >= HIGH_CLV:
        return " Because customer lifetime value is high, prioritize a human agent contact."
    return ""


def _agent_capacity_note(customer: CustomerDecisionInput) -> str:
    if customer.agent_capacity_status == "LOW_CAPACITY":
        return " The assigned agent appears capacity constrained, so route to an available agent or queue."
    if customer.agent_performance_score < LOW_AGENT_PERFORMANCE:
        return " The assigned agent performance score is low, so avoid overloading this agent."
    return ""


def decide_next_best_action(customer: CustomerDecisionInput, today: date | None = None) -> NextBestActionDecision:
    today = today or date.today()

    if customer.unresolved_complaint_count > 0:
        return NextBestActionDecision(
            customer_id=customer.customer_id,
            agent_id=_assigned_agent(customer),
            recommended_action="Service recovery" if customer.churn_risk_score >= HIGH else "Resolve complaint before sales outreach",
            recommended_product_id=None,
            priority_score=_max_priority(customer, 0.95),
            business_reason=(
                "High churn risk with unresolved complaint: service recovery takes precedence over sales."
                if customer.churn_risk_score >= HIGH
                else "Unresolved complaint suppresses sales action and requires service recovery."
            )
            + _agent_capacity_note(customer),
            model_scores_used=customer.model_scores_used,
            suggested_message="I wanted to personally follow up on your recent concern and help get it resolved.",
            expiry_date=today + timedelta(days=3),
            confidence_score=_confidence(customer, 0.10),
            decision_rule="churn_complaint_service_recovery" if customer.churn_risk_score >= HIGH else "complaint_suppression",
            action_type="service_recovery",
            suppression_reason="unresolved_complaint",
        )

    if customer.recent_service_issue_count > 0:
        return NextBestActionDecision(
            customer_id=customer.customer_id,
            agent_id=_assigned_agent(customer),
            recommended_action="Service recovery follow-up",
            recommended_product_id=None,
            priority_score=_max_priority(customer, 0.88),
            business_reason="Recent service issue should be resolved before promotional outreach." + _agent_capacity_note(customer),
            model_scores_used=customer.model_scores_used,
            suggested_message="I wanted to check that your recent service request has been handled properly.",
            expiry_date=today + timedelta(days=3),
            confidence_score=_confidence(customer, 0.10),
            decision_rule="service_recovery",
            action_type="service_recovery",
        )

    if customer.next_policy_renewal_date and today <= customer.next_policy_renewal_date <= today + timedelta(days=60):
        return NextBestActionDecision(
            customer_id=customer.customer_id,
            agent_id=_assigned_agent(customer),
            recommended_action="Renewal conversation",
            recommended_product_id=None,
            priority_score=_max_priority(customer, 0.90),
            business_reason="Policy renewal is within 60 days." + _human_contact_note(customer) + _agent_capacity_note(customer),
            model_scores_used=customer.model_scores_used,
            suggested_message="Your policy renewal is coming up soon. Let us review your coverage and payment options.",
            expiry_date=min(customer.next_policy_renewal_date, today + timedelta(days=14)),
            confidence_score=_confidence(customer, 0.10),
            decision_rule="renewal_60d",
            action_type="renewal_follow_up",
        )

    if customer.lapse_risk_score >= HIGH:
        return NextBestActionDecision(
            customer_id=customer.customer_id,
            agent_id=_assigned_agent(customer),
            recommended_action="Retention call",
            recommended_product_id=None,
            priority_score=_max_priority(customer),
            business_reason="Policy lapse risk is high." + _human_contact_note(customer) + _agent_capacity_note(customer),
            model_scores_used=customer.model_scores_used,
            suggested_message="I would like to review your policy and make sure it still fits your needs.",
            expiry_date=today + timedelta(days=14),
            confidence_score=_confidence(customer, 0.05),
            decision_rule="lapse_high",
            action_type="retention_outreach",
        )

    if customer.churn_risk_score >= HIGH:
        return NextBestActionDecision(
            customer_id=customer.customer_id,
            agent_id=_assigned_agent(customer),
            recommended_action="Retention call",
            recommended_product_id=None,
            priority_score=_max_priority(customer),
            business_reason="Customer churn risk is high." + _human_contact_note(customer) + _agent_capacity_note(customer),
            model_scores_used=customer.model_scores_used,
            suggested_message="I would like to review your policy and make sure it still fits your needs.",
            expiry_date=today + timedelta(days=14),
            confidence_score=_confidence(customer, 0.05),
            decision_rule="churn_high",
            action_type="retention_outreach",
        )

    if customer.propensity_to_buy_score >= PROPENSITY_HIGH and not customer.has_health_policy:
        return NextBestActionDecision(
            customer_id=customer.customer_id,
            agent_id=_assigned_agent(customer),
            recommended_action="Health cross-sell",
            recommended_product_id=customer.recommended_product_id,
            priority_score=_max_priority(customer, 0.85 if customer.customer_lifetime_value >= HIGH_CLV else 0.0),
            business_reason="Propensity is high and customer has no active health policy." + _human_contact_note(customer) + _agent_capacity_note(customer),
            model_scores_used=customer.model_scores_used,
            suggested_message="Based on your current protection needs, it may be worth reviewing health coverage options.",
            expiry_date=today + timedelta(days=30),
            confidence_score=_confidence(customer, 0.05),
            decision_rule="health_cross_sell",
            action_type="offer_product",
        )

    if customer.campaign_response_score >= HIGH:
        if customer.marketing_opt_out:
            return NextBestActionDecision(
                customer_id=customer.customer_id,
                agent_id=_assigned_agent(customer),
                recommended_action="Monitor customer",
                recommended_product_id=None,
                priority_score=_max_priority(customer),
                business_reason="Marketing opt-out suppresses campaign action." + _agent_capacity_note(customer),
                model_scores_used=customer.model_scores_used,
                suggested_message="We will continue monitoring for relevant service or coverage needs.",
                expiry_date=today + timedelta(days=30),
                confidence_score=_confidence(customer, 0.05),
                decision_rule="marketing_opt_out_suppression",
                action_type="call_customer",
                suppression_reason="marketing_opt_out",
            )
        return NextBestActionDecision(
            customer_id=customer.customer_id,
            agent_id=_assigned_agent(customer),
            recommended_action="Campaign follow-up",
            recommended_product_id=None,
            priority_score=_max_priority(customer),
            business_reason="Campaign response score is high; follow up within 7 days." + _human_contact_note(customer) + _agent_capacity_note(customer),
            model_scores_used=customer.model_scores_used,
            suggested_message="Thanks for your interest. I can help answer questions and explain the next step.",
            expiry_date=today + timedelta(days=7),
            confidence_score=_confidence(customer, 0.05),
            decision_rule="campaign_response_high",
            action_type="send_campaign",
        )

    if customer.lead_conversion_score >= HIGH:
        return NextBestActionDecision(
            customer_id=customer.customer_id,
            agent_id=_assigned_agent(customer),
            recommended_action="Lead follow-up",
            recommended_product_id=None,
            priority_score=_max_priority(customer),
            business_reason="Lead conversion score is high." + _human_contact_note(customer) + _agent_capacity_note(customer),
            model_scores_used=customer.model_scores_used,
            suggested_message="I can help complete your quote or application when convenient.",
            expiry_date=today + timedelta(days=14),
            confidence_score=_confidence(customer, 0.05),
            decision_rule="lead_conversion_high",
            action_type="assign_lead",
        )

    if customer.next_best_product_score >= HIGH:
        return NextBestActionDecision(
            customer_id=customer.customer_id,
            agent_id=_assigned_agent(customer),
            recommended_action="Product recommendation follow-up",
            recommended_product_id=customer.recommended_product_id,
            priority_score=_max_priority(customer),
            business_reason="Next-best-product signal is high." + _human_contact_note(customer) + _agent_capacity_note(customer),
            model_scores_used=customer.model_scores_used,
            suggested_message="There may be a product option that complements your current coverage.",
            expiry_date=today + timedelta(days=30),
            confidence_score=_confidence(customer, 0.05),
            decision_rule="nbp_high",
            action_type="offer_product",
        )

    return NextBestActionDecision(
        customer_id=customer.customer_id,
        agent_id=_assigned_agent(customer),
        recommended_action="Monitor customer",
        recommended_product_id=None,
        priority_score=_max_priority(customer),
        business_reason="No urgent rule fired; continue monitoring." + _agent_capacity_note(customer),
        model_scores_used=customer.model_scores_used,
        suggested_message="We will continue monitoring for relevant service or coverage needs.",
        expiry_date=today + timedelta(days=30),
        confidence_score=_confidence(customer, 0.0),
        decision_rule="monitor",
        action_type="call_customer",
    )
