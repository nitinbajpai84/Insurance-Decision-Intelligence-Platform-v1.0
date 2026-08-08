# Validation-First Text-to-SQL Runbook

This MVP now uses the live Supabase schema as the source of truth before SQL is shown or executed.

## Rebuild Actual Schema Context

Run from the project root:

```powershell
.\.venv\Scripts\Activate.ps1
python scripts\build_actual_schema_catalog.py
python scripts\enrich_actual_schema_with_llm.py
python scripts\audit_semantic_context_against_actual_schema.py
python scripts\build_verified_sql_context_documents.py
python scripts\embed_verified_sql_context.py --batch-size 32
```

## Smoke Test

```powershell
python scripts\smoke_test_demo_questions.py --limit 3
python -m pytest tests\test_copilot_sql_engine.py tests\test_copilot_api_gateway.py -q
```

Useful API checks:

```powershell
Invoke-WebRequest http://127.0.0.1:8071/debug/actual-schema-catalog -UseBasicParsing
Invoke-WebRequest http://127.0.0.1:8071/debug/sql-context-health -UseBasicParsing
```

The validator should block missing tables:

```json
{
  "sql": "select * from public.customer_segments limit 10"
}
```

POST this to `http://127.0.0.1:8071/debug/validate-sql`; it should return `is_valid=false` and report `public.customer_segments` as missing.

## Demo Recording

```powershell
node scripts\record_demo_video.mjs
```

Outputs are written to:

- `demo_artifacts/videos`
- `demo_artifacts/screenshots`
- `demo_artifacts/demo_manifest.json`

## What Was Added

- `cld_actual_*` live schema catalog tables.
- `cld_verified_sql_context_documents` with pgvector embeddings.
- Strict SQL validation with table/column checks and Supabase `EXPLAIN`.
- One-pass SQL repair service.
- Result relevance validation before publishing insight.
- Evidence snapshot logging in `insight_test_snapshots` and `cld_ai_insight_run_log`.
- AI Intelligence UI states for validated, partial, not-supported, repair, and evidence tracing.
