from __future__ import annotations

from uuid import UUID

from explainability_service import build_recommendation_explanation


def test_build_recommendation_explanation_from_nba_payload():
    nba = {
        "next_best_action_id": UUID("11111111-1111-1111-1111-111111111111"),
        "recommended_action": "Contact customer C123",
        "business_reason": "Propensity is high and customer has no active health policy.",
        "suggested_message": "It may be worth reviewing health coverage options.",
        "priority_score": 0.91,
        "confidence_score": 0.86,
        "decision_rule": "health_cross_sell",
        "suppression_reason": None,
        "product_name": "PRUHealth",
        "expiry_date": "2026-06-07",
        "model_scores_used": [
            {
                "model_name": "propensity_to_buy",
                "model_version": "v1",
                "score_name": "propensity_to_buy",
                "score": 0.91,
                "score_band": "VERY_HIGH",
            }
        ],
        "context_used": [
            {
                "semantic_document_id": "22222222-2222-2222-2222-222222222222",
                "title": "Next Best Product",
                "document_type": "model_context",
                "business_domain": "next_best_product",
                "score": {"hybrid": 0.77},
            }
        ],
    }

    explanation = build_recommendation_explanation(nba)

    assert explanation.recommendation == "Contact customer C123"
    assert "propensity_to_buy" in explanation.ml_models_used
    assert "propensity_to_buy" in explanation.metrics_used
    assert "health_cross_sell" in explanation.business_rules_used
    assert "model_scores" in explanation.source_tables
    assert explanation.confidence_score == 0.86
    assert any("propensity_to_buy score 0.91" in fact for fact in explanation.supporting_facts)
    assert len(explanation.evidence) == 3

