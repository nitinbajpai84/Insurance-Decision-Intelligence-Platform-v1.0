# LLM-to-SQL Engine

This service implements the full Insurance Decision Intelligence Copilot query flow:

```text
Question
 -> Intent Classification
 -> Retrieve Context from pgvector
 -> Retrieve Role Context
 -> Generate SQL
 -> Validate SQL
 -> Execute SQL
 -> Generate Business Insight
 -> Generate Recommendations
 -> Generate Explainability Output
```

## Files

- `copilot_sql_engine/api.py`: FastAPI endpoint.
- `copilot_sql_engine/engine.py`: orchestration flow.
- `copilot_sql_engine/generator.py`: Gemini/Ollama SQL generation and deterministic mock provider.
- `copilot_sql_engine/llm_providers.py`: provider abstraction, fallback, timeout handling, and metadata-only LLM logging.
- `copilot_sql_engine/safety.py`: strict SQL validator.
- `copilot_sql_engine/prompts.py`: SQL and insight prompt templates.
- `copilot_sql_engine/executor.py`: read-only Supabase execution.
- `tests/test_copilot_sql_engine.py`: safety and provider tests.
- `llm_sql_engine_examples.http`: runnable API examples.

## Safety Rules

Allowed:

- `SELECT`
- `WITH ... SELECT`

Blocked:

- `INSERT`
- `UPDATE`
- `DELETE`
- `DROP`
- `ALTER`
- `TRUNCATE`
- plus other unsafe commands such as `CREATE`, `MERGE`, `COPY`, `CALL`, `DO`, `GRANT`, `REVOKE`, `SET`, `RESET`, and `VACUUM`.

The service also wraps every query in an outer `LIMIT`.

## Run

Start locally:

```powershell
uvicorn copilot_sql_engine.api:app --reload --port 8050
```

Open Swagger:

```text
http://127.0.0.1:8050/docs
```

## Endpoint

```http
POST /copilot/query
Content-Type: application/json

{
  "question": "Which campaigns performed best?",
  "role_code": "campaign_manager",
  "include_context": true,
  "execute_sql": true,
  "row_limit": 100,
  "include_debug": true
}
```

## Output

The response includes:

- intent classification
- generated SQL
- validation decision
- result table
- business insight
- generated recommendations
- explainability output with:
  - supporting facts
  - source tables
  - source columns
  - metrics used
  - business rules used
  - ML models used
  - context documents used
  - confidence score
  - timestamp

## Gemini, Ollama, or Mock Mode

For faster MVP responses, use Gemini for all LLM calls:

```env
LLM_PROVIDER=gemini
GEMINI_API_KEY=your_google_api_key_here
GEMINI_MODEL_SQL=gemini-2.5-flash-lite
GEMINI_MODEL_FAST=gemini-2.5-flash-lite
LLM_TIMEOUT_SECONDS=120
TARGET_RESPONSE_TIME_SECONDS=5
```

Get a Gemini API key from Google AI Studio:

```text
https://aistudio.google.com/app/apikey
```

Keep the key only in local `.env`; never commit it.

For deterministic testing without LLM generation:

```env
TEXT2SQL_PROVIDER=mock
```

## LLM Health and Benchmark

Start the gateway:

```powershell
python -m uvicorn copilot_api_gateway.api:app --host 127.0.0.1 --port 8060 --reload
```

Check provider availability:

```powershell
Invoke-WebRequest http://127.0.0.1:8060/health/llm -UseBasicParsing
```

Test one LLM call:

```powershell
Invoke-WebRequest http://127.0.0.1:8060/copilot/test-llm `
  -Method POST `
  -ContentType "application/json" `
  -Body '{"question":"Which customers should Agent A contact this week?"}' `
  -UseBasicParsing
```

Run the benchmark:

```powershell
python scripts/benchmark_llm.py
```

Outputs:

- `benchmark_results.json`
- `benchmark_results.csv`

Troubleshooting:

- If Gemini returns authentication errors, check `GEMINI_API_KEY` and Gemini API access.
- If a Gemini model is unavailable, change `GEMINI_MODEL_SQL` or `GEMINI_MODEL_FAST` in `.env`.
- If responses are slow, reduce context size and then tune `LLM_TIMEOUT_SECONDS`.
- Ollama is not used by the current Gemini-only MVP configuration.

## Test

```powershell
python -m pytest tests/test_copilot_sql_engine.py
```
