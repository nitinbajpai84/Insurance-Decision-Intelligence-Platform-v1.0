# Insurance AI Copilot pgvector Context Layer

This layer gives an LLM the right insurance business, schema, metric, ML, and SQL context before generating SQL or business insights.

## Files

- `017_genai_context_layer_pgvector.sql`: semantic document enhancements, pgvector indexes, similarity search, and hybrid retrieval SQL functions.
- `018_seed_insurance_copilot_context_documents.sql`: sample context documents for customer, policy, agent, campaign, claims, ML, and NBA domains.
- `embed_semantic_documents.py`: embedding CLI, updated to include related columns, models, and SQL examples in embedding text.
- `context_retriever_service.py`: Python retriever and FastAPI service returning structured LLM context.

## Apply SQL

Run in Supabase:

```sql
-- 017_genai_context_layer_pgvector.sql
-- 018_seed_insurance_copilot_context_documents.sql
```

Then embed the newly inserted documents.

## Configure Embeddings

Gemini-only MVP `.env`:

```env
SUPABASE_DB_URL=postgresql://postgres.[project-ref]:[password]@aws-0-ap-southeast-1.pooler.supabase.com:6543/postgres

EMBEDDING_PROVIDER=gemini
GEMINI_API_KEY=your_google_api_key_here
GEMINI_EMBEDDING_MODEL=gemini-embedding-001
EMBEDDING_DIMENSIONS=768
```

Before embedding with Gemini, confirm the semantic embedding column is `vector(768)`. If you previously embedded with Ollama, run this in Supabase first:

```sql
-- 026_reset_semantic_embeddings_for_gemini.sql
```

Then run locally:

```bash
python embed_semantic_documents.py embed-missing --batch-size 16
```

Local sentence-transformers option:

```env
EMBEDDING_PROVIDER=local
LOCAL_EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
EMBEDDING_DIMENSIONS=384
```

Important: vector dimensions must match the embedding model. This MVP uses Gemini `gemini-embedding-001` with `output_dimensionality=768`, matching `semantic_documents.embedding vector(768)`.

## Generate Embeddings

Dry run:

```bash
python embed_semantic_documents.py embed-missing --dry-run
```

Embed missing documents:

```bash
python embed_semantic_documents.py embed-missing --batch-size 32
```

Test similarity:

```bash
python embed_semantic_documents.py search "Which high CLV customers have high churn risk?"
```

## Hybrid Retrieval

The SQL function:

```sql
select *
from public.hybrid_match_semantic_documents(
  'Which campaigns generated the highest policy conversion?',
  '[...]'::vector,
  12,
  0.0,
  null
);
```

Hybrid score combines:

- pgvector cosine similarity
- full-text keyword score
- related table, column, model, and metric name matches
- business domain match

## Python Retriever

CLI:

```bash
python context_retriever_service.py "Which agents have declining MAPA productivity?" --pretty
```

API:

```bash
uvicorn context_retriever_service:app --reload --port 8020
```

Request:

```bash
curl -X POST http://localhost:8020/retrieve-context ^
  -H "Content-Type: application/json" ^
  -d "{\"question\":\"Which customers have high lapse risk and open complaints?\",\"match_count\":12}"
```

Response shape:

```json
{
  "business_context": [],
  "schema_context": [],
  "metric_context": [],
  "model_context": [],
  "sql_examples": []
}
```

## Included Sample Context Documents

- Customer 360
- Policy lapse
- Propensity to buy
- Next best product
- Agent performance
- Campaign conversion
- Claims ratio
- Fraud indicators
- Customer lifetime value
- Next best action
- MAPA metrics
- Churn risk
- Lead conversion

## Recommended LLM Use

Before text-to-SQL:

1. Call `/retrieve-context`.
2. Provide `business_context` for definitions and constraints.
3. Provide `schema_context` for tables, columns, and joins.
4. Provide `metric_context` for calculations.
5. Provide `model_context` for ML score meaning and usage.
6. Provide `sql_examples` as style and safety templates.

This reduces hallucinated joins, wrong metric formulas, and misuse of future labels or feature tables.
