from __future__ import annotations

from datetime import date
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


class CustomerDecisionInput(BaseModel):
    customer_id: UUID
    agent_id: UUID | None = None
    propensity_to_buy_score: float = 0.0
    lapse_risk_score: float = 0.0
    churn_risk_score: float = 0.0
    next_best_product_score: float = 0.0
    lead_conversion_score: float = 0.0
    customer_lifetime_value: float = 0.0
    campaign_response_score: float = 0.0
    agent_performance_score: float = 0.5
    customer_contact_preference: str | None = None
    marketing_opt_out: bool = False
    active_policy_count: int = 0
    has_health_policy: bool = False
    next_policy_renewal_date: date | None = None
    open_opportunity_count: int = 0
    unresolved_complaint_count: int = 0
    recent_service_issue_count: int = 0
    payment_delay_count: int = 0
    agent_capacity_status: str = "AVAILABLE"
    recommended_product_id: UUID | None = None
    next_best_product_prediction: str | None = None
    model_scores_used: list[dict[str, Any]] = Field(default_factory=list)


class NextBestActionDecision(BaseModel):
    customer_id: UUID
    agent_id: UUID | None = None
    recommended_action: str
    recommended_product_id: UUID | None = None
    priority_score: float = Field(ge=0.0, le=1.0)
    business_reason: str
    model_scores_used: list[dict[str, Any]] = Field(default_factory=list)
    context_used: list[dict[str, Any]] = Field(default_factory=list)
    suggested_message: str
    expiry_date: date
    confidence_score: float = Field(default=0.0, ge=0.0, le=1.0)
    decision_rule: str
    action_type: Literal[
        "call_customer",
        "send_campaign",
        "offer_product",
        "retention_outreach",
        "renewal_follow_up",
        "claim_review",
        "fraud_review",
        "agent_coaching",
        "assign_lead",
        "service_recovery",
    ]
    suppression_reason: str | None = None

    @property
    def reason(self) -> str:
        return self.business_reason
