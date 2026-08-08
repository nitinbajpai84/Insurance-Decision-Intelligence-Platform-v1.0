# GenAI Next-Best-Action Engine

This layer combines CRM context, model scores, model predictions, transparent business rules, and pgvector semantic context to produce agent-ready next-best-actions.

## Files

- `020_genai_next_best_action_decisioning.sql` creates the GenAI-aware SQL views, candidate action logic, audit table, and batch insert function.
- `nba_engine/rules.py` contains the Python rule engine.
- `nba_engine/context.py` retrieves LLM-readable context from `semantic_documents` through pgvector hybrid search.
- `nba_engine/explainer.py` builds deterministic explanations by default and can call an Ollama/OpenAI-compatible chat endpoint when `use_llm=true`.
- `nba_engine/api.py` exposes FastAPI endpoints.
- `tests/test_nba_rules.py` covers core rule precedence and suppression behavior.

## Supabase Setup

Run these scripts in Supabase SQL Editor in order:

```text
014_ml_scoring_serving_schema.sql
017_genai_context_layer_pgvector.sql
018_seed_insurance_copilot_context_documents.sql
019_use_ollama_embeddings_768.sql
020_genai_next_best_action_decisioning.sql
```

Then embed semantic documents locally:

```powershell
python embed_semantic_documents.py embed-missing --batch-size 16
```

## API

Start the service locally:

```powershell
uvicorn nba_engine.api:app --reload --port 8010
```

Get one customer recommendation:

```http
GET http://127.0.0.1:8010/customers/{customer_id}/next-best-action?retrieve_context=true&use_llm=false&audit=true
```

Batch recommendations:

```http
POST http://127.0.0.1:8010/batch/next-best-actions?limit=100&persist=true&retrieve_context=false&audit=true
```

Use `use_llm=true` only after Ollama is running and `.env` has:

```env
TEXT2SQL_BASE_URL=http://localhost:11434/v1
TEXT2SQL_API_KEY=ollama
TEXT2SQL_MODEL=qwen2.5-coder:7b
```

## Output Shape

Each API decision returns:

```json
{
  "customer_id": "",
  "agent_id": "",
  "recommended_action": "",
  "recommended_product_id": "",
  "priority_score": 0.0,
  "business_reason": "",
  "model_scores_used": [],
  "context_used": [],
  "suggested_message": "",
  "expiry_date": "",
  "confidence_score": 0.0
}
```

The response also includes operational fields such as `decision_rule`, `action_type`, and `suppression_reason`.

## Rule Precedence

1. Unresolved complaint with high churn risk becomes service recovery.
2. Any unresolved complaint suppresses sales.
3. Recent service issue suppresses promotional outreach.
4. Renewal within 60 days is prioritized.
5. High lapse risk or churn risk triggers retention.
6. High propensity with missing health cover triggers cross-sell unless suppressed.
7. Marketing opt-out suppresses campaign action.
8. Low-capacity or low-performing agents are not assigned.

## Verification

Run unit tests:

```powershell
python -m pytest tests/test_nba_rules.py
```

Check SQL objects after running `020`:

```sql
select count(*) from public.v_nba_customer_decision_context_v2;
select * from public.v_nba_candidate_actions_v2 limit 10;
select * from public.generate_next_best_actions_v2(10);
```

