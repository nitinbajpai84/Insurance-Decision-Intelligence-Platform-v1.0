# AI Intelligence and Insight Evidence Hub

This is the focused AI question-answering and evidence experience for the Insurance Decision Intelligence Platform.

## What Is Included

- Frontend route: `/ai-intelligence`
- Frontend route: `/insight-evidence-hub`
- Backend endpoint: `POST /ai-insight-v11/ask`
- Backend diagnostic endpoint: `GET /health/llm`
- Backend evidence endpoint: `GET /debug/latest-insight-evidence`
- Role-aware suggested questions for insurance agents, agency managers, campaign managers, claims managers, sales directors, executive leadership, and data analysts
- SQL-backed answer summary, key data points, recommendations, generated SQL, validation status, result preview, confidence score, and compact evidence summary
- Detailed evidence hub with recent insight runs, related tables, parsed SQL columns, semantic context, models used, SQL evidence, lineage, related facts, and technical diagnostics

## Important Design Rule

AI Intelligence stays clean and business-facing. It shows only the answer, key facts, recommendations, SQL, result preview, confidence, and a compact evidence summary.

Insight Evidence Hub is the detailed traceability page. It holds full context, lineage, model details, parsed SQL columns, and technical diagnostics.

Gemini quota or provider failures are stored in `technical_warnings`. They are not business/data limitations.

## API

```http
POST http://127.0.0.1:8071/ai-insight-v11/ask
Content-Type: application/json
```

```json
{
  "role": "Agency Manager",
  "question": "Which agents need coaching this month?"
}
```

The response includes:

- `insight_id`
- `answer_summary`
- `key_data_points`
- `recommendations`
- `generated_sql`
- `related_tables`
- `related_columns`
- `related_context`
- `models_used`
- `business_data_limitations`
- `context_limitations`
- `model_limitations`
- `technical_warnings`
- `provider_used`
- `model_used`
- `fallback_used`
- `gemini_available`
- `gemini_quota_exhausted`

Open full evidence:

```http
GET http://127.0.0.1:8071/debug/latest-insight-evidence?insight_id=<insight_id>
```

## Run Locally

Start the backend:

```powershell
python -m uvicorn copilot_api_gateway.api:app --host 127.0.0.1 --port 8071
```

Start the frontend:

```powershell
cd frontend
npm.cmd run dev
```

Open:

```text
http://127.0.0.1:3000/ai-intelligence
```

## Regression Test

With backend and frontend running:

```powershell
python scripts\test_evidence_hub_and_ai_cleanup.py --backend-url http://127.0.0.1:8071 --frontend-url http://127.0.0.1:3000 --timeout 120
```

Outputs:

- `evidence_hub_cleanup_results.json`
- `evidence_hub_cleanup_report.md`

The script checks route health, old label removal, insight ID generation, Gemini warning separation, real related-column structures, model detection, and Evidence Hub payload completeness.
