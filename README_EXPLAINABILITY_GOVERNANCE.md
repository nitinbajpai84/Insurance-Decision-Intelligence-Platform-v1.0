# Explainability Governance Framework

This framework makes every copilot recommendation explainable, auditable, and traceable to facts, tables, columns, metrics, business rules, ML models, and semantic context.

## SQL Setup

Run in Supabase SQL Editor:

```text
024_explainability_governance_framework.sql
```

Created objects:

- `insight_lineage`
- `recommendation_evidence`
- `model_explanations`
- `context_usage_log`
- `v_recommendation_explainability`
- `create_recommendation_lineage_from_nba(next_best_action_id, question, role_code)`

## API

Start locally:

```powershell
uvicorn explainability_service:app --reload --port 8040
```

Swagger:

```text
http://127.0.0.1:8040/docs
```

### Explain Recommendation

```http
POST /explain/recommendation
Content-Type: application/json

{
  "next_best_action_id": "uuid",
  "question": "Why should this customer be contacted?",
  "role_code": "insurance_agent",
  "persist": true
}
```

Returns:

```json
{
  "recommendation": "Contact customer C123",
  "supporting_facts": [
    "propensity_to_buy score 0.91 (VERY_HIGH)",
    "Business rule fired: health_cross_sell",
    "Recommended product: PRUHealth"
  ],
  "source_tables": [
    "next_best_actions",
    "model_scores",
    "policies",
    "campaign_responses",
    "semantic_documents"
  ],
  "source_columns": {
    "next_best_actions": ["recommended_action", "priority_score", "business_reason"],
    "model_scores": ["model_name", "model_version", "score_name", "score_value"]
  },
  "metrics_used": ["propensity_to_buy"],
  "business_rules_used": ["health_cross_sell"],
  "ml_models_used": ["propensity_to_buy"],
  "context_documents_used": [
    {
      "title": "Next Best Product",
      "business_domain": "next_best_product",
      "retrieval_score": 0.77
    }
  ],
  "confidence_score": 0.86,
  "timestamp": "2026-05-31T..."
}
```

### Fetch Persisted Explanation

```http
GET /explain/recommendation/{next_best_action_id}
```

This returns the latest record from `v_recommendation_explainability`.

### Create Generic Lineage

```http
POST /lineage
```

Use this for analytics, KPI, 360, or custom insight lineage that is not backed by `next_best_actions`.

## Governance Pattern

Every recommendation should include:

- Recommendation
- Supporting facts
- Source tables
- Source columns
- Metrics used
- Business rules used
- ML models used
- Context documents used
- Confidence score
- Timestamp

The API builds this from:

- `next_best_actions.recommended_action`
- `next_best_actions.business_reason`
- `next_best_actions.model_scores_used`
- `next_best_actions.context_used`
- `next_best_actions.decision_rule`
- `next_best_actions.suppression_reason`
- joined customer, agent, and product labels

## Example SQL Checks

```sql
select *
from public.v_recommendation_explainability
order by explanation_timestamp desc
limit 10;
```

```sql
select public.create_recommendation_lineage_from_nba(
  '00000000-0000-0000-0000-000000000000',
  'Why should this customer be contacted?',
  'insurance_agent'
);
```

## Test

```powershell
python -m pytest tests/test_explainability_service.py
```

