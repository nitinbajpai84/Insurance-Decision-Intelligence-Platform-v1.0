# Insurance Next-Best-Action Engine

This engine turns model scores plus CRM context into prioritized customer actions.

## Files

- `016_next_best_action_engine.sql`: SQL decisioning views and `generate_next_best_actions()` function.
- `nba_engine/rules.py`: pure Python rule engine.
- `nba_engine/db.py`: Supabase Postgres read/write helpers.
- `nba_engine/api.py`: FastAPI endpoint.
- `nba_examples.http`: API examples.
- `tests/test_nba_rules.py`: unit tests for rule precedence.

## SQL Setup

Run:

```sql
-- 016_next_best_action_engine.sql
```

Preview recommendations:

```sql
select
  customer_id,
  agent_id,
  recommended_action,
  recommended_product_id,
  priority_score,
  reason,
  suggested_message,
  expiry_date
from public.v_next_best_action_recommendations
order by priority_score desc
limit 100;
```

Persist recommendations to `next_best_actions`:

```sql
select *
from public.generate_next_best_actions(1000);
```

## Rule Precedence

The engine evaluates rules in this order:

1. Unresolved complaint: suppress sales and recommend service recovery.
2. Recent service issue: recommend service recovery.
3. Policy renewal within 60 days: recommend renewal conversation.
4. High lapse risk: recommend retention call.
5. High churn risk: recommend retention call.
6. High propensity with no health policy: recommend health cross-sell.
7. High campaign response and not opted out: follow up within 7 days.
8. High lead conversion: lead follow-up.
9. High next-best-product score: product recommendation.
10. Otherwise monitor.

High CLV increases priority and keeps human agent contact preferred.

## API

Start the API:

```bash
uvicorn nba_engine.api:app --reload --port 8010
```

Payload decision:

```bash
curl -X POST http://localhost:8010/decide ^
  -H "Content-Type: application/json" ^
  -d "{\"customer_id\":\"11111111-1111-1111-1111-111111111111\",\"propensity_to_buy_score\":0.82,\"has_health_policy\":false}"
```

Customer decision from Supabase:

```bash
curl "http://localhost:8010/customers/<customer_id>/next-best-action?persist=false"
```

Batch decisioning:

```bash
curl -X POST "http://localhost:8010/batch/next-best-actions?limit=100&persist=true"
```

## Tests

```bash
pytest tests/test_nba_rules.py
```

## Notes

- Contact preference comes from `parties.preferred_contact_method`.
- Marketing opt-out is inferred from `campaign_responses.response_type = 'unsubscribed'`.
- Agent relationship is inferred from the most recent active policy agent, falling back to open opportunity agent.
- Health cross-sell uses the first active base product whose line, family, or name contains `health`.
- The SQL view is intentionally transparent so business users can inspect why a recommendation fired.
