# AI Intelligence Platform

This page is the role-aware, SQL-backed intelligence workspace for the Insurance Decision Intelligence Platform.

## What Changed

- The ask experience is the core of the `AI Intelligence` page.
- Detailed evidence, context, lineage, parsed SQL columns, and technical diagnostics are now handled by `Insight Evidence Hub`.
- Answers expose generated SQL, SQL validation status, row count, execution time, provider/model, result preview, compact evidence, and a `View Full Evidence` link.
- Backend endpoints return proactive briefing and diagnostic proof that role, context, SQL, execution, and insights are wired.
- Smoke tests can run 35 role-specific questions and save proof snapshots into Supabase.

## Backend Endpoints

- `GET /intelligence/briefing?role=campaign_manager`
- `POST /intelligence/ask`
- `POST /copilot/ask` retained as a compatibility alias
- `POST /ai-insight-v11/ask`
- `GET /debug/latest-insight-evidence`
- `GET /health/llm`
- `GET /debug/insight-pipeline?role=executive_leadership&question=What%20revenue%20is%20at%20risk%3F`

## Snapshot Table

Run `027_insight_test_snapshots.sql` in Supabase SQL Editor, or let the smoke script create the table automatically.

The table `public.insight_test_snapshots` stores:

- role and question
- retrieved context
- generated SQL
- validation and execution status
- result preview
- models, tables, and columns used
- business insight and recommendations
- confidence and latency

## Smoke Test

Start the API first:

```powershell
python -m uvicorn copilot_api_gateway.api:app --host 127.0.0.1 --port 8071
```

Then run:

```powershell
python scripts\smoke_test_ai_copilot.py --base-url http://127.0.0.1:8071 --output-dir .
```

Outputs:

- `smoke_test_results.json`
- `smoke_test_results.csv`
- `smoke_test_report.md`

## Cleanup Regression Test

```powershell
python scripts\test_evidence_hub_and_ai_cleanup.py --backend-url http://127.0.0.1:8071 --frontend-url http://127.0.0.1:3000 --timeout 120
```

## Demo Acceptance Checks

- AI Intelligence is question-focused and no duplicate AI page labels appear.
- Insight Evidence Hub shows full evidence for the latest or selected insight.
- Role changes update suggested questions.
- Generated SQL is shown after each answer.
- SQL validation status and confidence are visible.
- Gemini quota or fallback issues appear only as technical warnings.
- Business limitations do not contain provider or quota failures.
- Real related columns and models used are captured in the evidence payload.
- Smoke tests save snapshots for auditability.
