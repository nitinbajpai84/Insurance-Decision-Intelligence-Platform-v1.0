# Insurance Analytics Text-to-SQL Agent

FastAPI backend for business-question analytics over the Supabase insurance MVP schema.

## Flow

1. User submits a business question to `POST /query`.
2. The service embeds the question with the configured embedding provider.
3. It retrieves semantic context from `public.match_semantic_documents`.
4. It reads schema metadata from `information_schema`.
5. The LLM generates a single PostgreSQL `SELECT`.
6. SQL safety validation blocks non-read-only statements and disallowed schemas.
7. The query runs in a read-only transaction with statement timeout and row limit.
8. The service returns rows, generated SQL, semantic context, and business explanation.
9. The service logs question, semantic document ids, generated SQL, status, row count, and duration into `public.query_audit_log`.

## Files

- `text_to_sql_agent/app.py` - FastAPI application.
- `text_to_sql_agent/llm.py` - OpenAI/OpenAI-compatible/mock SQL generation and explanation.
- `text_to_sql_agent/sql_safety.py` - SQL parser and safety validator.
- `text_to_sql_agent/retrieval.py` - pgvector semantic retrieval.
- `text_to_sql_agent/schema.py` - schema metadata retrieval.
- `text_to_sql_agent/executor.py` - read-only query execution with timeout.
- `text_to_sql_agent/audit.py` - query audit logging.
- `text_to_sql_examples.http` - request examples.
- `tests/test_sql_safety.py` - validator test examples.

## Setup

Install dependencies:

```powershell
& 'C:\Users\Nitin\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pip install -r requirements.txt
```

Apply migrations:

```sql
\i 001_insurance_analytics_mvp_schema.sql
\i 002_semantic_layer_enrichment.sql
\i 004_product_riders_and_nbp_views.sql
\i 003_semantic_vector_search.sql
```

Load semantic documents, then run the embedding pipeline so `semantic_documents.embedding` is populated.

Copy `.env.example` to `.env` and set:

```text
SUPABASE_DB_URL=postgresql://...
EMBEDDING_PROVIDER=openai
OPENAI_API_KEY=...
OPENAI_EMBEDDING_MODEL=text-embedding-3-small

TEXT2SQL_PROVIDER=openai
TEXT2SQL_MODEL=gpt-4.1-mini
TEXT2SQL_API_KEY=...
TEXT2SQL_ROW_LIMIT=500
TEXT2SQL_STATEMENT_TIMEOUT_MS=5000
TEXT2SQL_ALLOWED_SCHEMAS=public
```

For OpenAI-compatible gateways:

```text
TEXT2SQL_PROVIDER=compatible
TEXT2SQL_BASE_URL=https://your-gateway.example/v1
TEXT2SQL_API_KEY=...
TEXT2SQL_MODEL=your-chat-model
```

For local smoke tests without an LLM key:

```text
TEXT2SQL_PROVIDER=mock
```

The mock provider returns deterministic SQL for policy, campaign, and loss-ratio examples. It still uses the real embedding provider unless you adapt retrieval for tests.

## Run

```powershell
& 'C:\Users\Nitin\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m uvicorn text_to_sql_agent.app:app --host 127.0.0.1 --port 8000 --reload
```

Health check:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

Example query:

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8000/query `
  -ContentType 'application/json' `
  -Body '{"question":"Show loss ratio by line of business.","business_domain":"claims","row_limit":100,"include_debug":true}'
```

## Safety Controls

The service blocks:

- `DELETE`
- `UPDATE`
- `INSERT`
- `DROP`
- `ALTER`
- `TRUNCATE`
- `CREATE`
- `MERGE`
- `COPY`
- `CALL`
- `DO`
- `SET`
- multi-statement SQL
- schemas outside `TEXT2SQL_ALLOWED_SCHEMAS`

Execution controls:

- generated SQL is wrapped as `select * from (...) limit N`
- transaction is set to read-only
- `statement_timeout` is set per query
- query results are JSON-safe converted
- every request is logged to `query_audit_log`

## Test Examples

Run validator tests:

```powershell
& 'C:\Users\Nitin\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest tests
```

Manual HTTP examples are in:

```text
text_to_sql_examples.http
```

## Response Shape

`POST /query` returns:

```json
{
  "question": "Show loss ratio by line of business.",
  "sql": "select * from (...) as text_to_sql_limited_result limit 100",
  "columns": ["line_of_business", "loss_ratio"],
  "rows": [],
  "row_count": 0,
  "execution_status": "executed",
  "business_insight": "Concise explanation of the result.",
  "semantic_context": [],
  "audit_id": "..."
}
```
