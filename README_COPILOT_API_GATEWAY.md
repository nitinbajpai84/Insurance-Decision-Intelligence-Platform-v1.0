# Copilot API Gateway

This FastAPI gateway exposes the main Insurance Decision Intelligence Copilot APIs from one local service.

## Run

```powershell
uvicorn copilot_api_gateway.api:app --reload --port 8060
```

Swagger:

```text
http://127.0.0.1:8060/docs
```

OpenAPI JSON:

```text
http://127.0.0.1:8060/openapi.json
```

Export OpenAPI to a file:

```powershell
python export_openapi.py
```

This writes:

```text
openapi_copilot_api.json
```

## Endpoints

```text
POST /copilot/ask
POST /intent/classify
POST /context/search
POST /sql/validate
POST /sql/execute
GET  /customers/{id}/360
GET  /agents/{id}/360
GET  /campaigns/{id}/360
GET  /claims/{id}/360
GET  /roles
GET  /roles/{role}/dashboard
GET  /recommendations/{entity_id}
GET  /lineage/{insight_id}
```

## Quick PowerShell Tests

```powershell
Invoke-RestMethod http://127.0.0.1:8060/health
Invoke-RestMethod http://127.0.0.1:8060/roles
```

```powershell
$body = @{
  question = "Which customers should I call this week?"
} | ConvertTo-Json

Invoke-RestMethod `
  -Uri http://127.0.0.1:8060/intent/classify `
  -Method Post `
  -ContentType "application/json" `
  -Body $body
```

```powershell
$body = @{
  sql = "select campaign_name, channel from public.campaigns"
  row_limit = 10
} | ConvertTo-Json

Invoke-RestMethod `
  -Uri http://127.0.0.1:8060/sql/validate `
  -Method Post `
  -ContentType "application/json" `
  -Body $body
```

## Notes

- `/copilot/ask` uses the integrated LLM-to-SQL engine.
- `/sql/validate` and `/sql/execute` only allow `SELECT` or `WITH`.
- `/context/search` uses pgvector via `semantic_documents`.
- `/roles/{role}/dashboard` uses `v_role_intelligence_profile`.
- `/lineage/{insight_id}` requires `024_explainability_governance_framework.sql`.

