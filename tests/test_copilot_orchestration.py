from __future__ import annotations

from copilot_orchestration.classifier import classify_intent
from copilot_orchestration.models import CopilotIntent, OrchestrationRequest, RouteTarget
from copilot_orchestration.router import build_orchestration_plan


def test_campaign_analytics_classifies_as_campaign_360():
    result = classify_intent("Which campaigns performed best?")

    assert result.intent == CopilotIntent.CAMPAIGN_360


def test_recommendation_classification():
    result = classify_intent("Which customers should I call this week?")

    assert result.intent == CopilotIntent.RECOMMENDATION


def test_explanation_classification():
    result = classify_intent("Why is this customer at high lapse risk?")

    assert result.intent == CopilotIntent.EXPLANATION


def test_exploration_defaults_to_analytics():
    result = classify_intent("Show me policies sold in Singapore.")

    assert result.intent == CopilotIntent.ANALYTICS


def test_kpi_lookup_classification():
    result = classify_intent("What is our current lapse rate?")

    assert result.intent == CopilotIntent.KPI_LOOKUP


def test_orchestration_plan_without_context_does_not_require_database():
    plan = build_orchestration_plan(
        OrchestrationRequest(
            question="Which customers should I call this week?",
            role_code="insurance_agent",
            include_context=False,
        )
    )

    assert plan.classification.intent == CopilotIntent.RECOMMENDATION
    assert plan.intent_definition.default_route == RouteTarget.NEXT_BEST_ACTION
    assert plan.retrieval_plan.include_next_best_actions is True
    assert "model_scores" in plan.intent_definition.context_sources
    assert plan.retrieved_context is None

