# Security, Guardrails And Validation

## SQL Safety

| Control | Status | Evidence |
|---|---:|---|
| SELECT/WITH only | Implemented | `copilot_sql_engine/safety.py`, `text_to_sql_agent/sql_safety.py` |
| Mutation keywords blocked | Implemented | Tests in `tests/test_copilot_sql_engine.py`, `tests/test_sql_safety.py` |
| Single read-only query wrapper | Implemented | `ensure_outer_limit` wraps SQL with row limit |
| Row limits | Implemented | `row_limit` fields in models/settings |
| Statement timeout | Implemented | `execute_select` sets `statement_timeout` |
| Allowed schemas | Implemented | `allowed_schemas` in SQL engine settings |
| SQL display to user | Implemented | AI Intelligence UI |

Blocked statements include:

- `INSERT`
- `UPDATE`
- `DELETE`
- `DROP`
- `ALTER`
- `TRUNCATE`
- other non-read-only statements

## LLM Safety

| Control | Status | Evidence |
|---|---:|---|
| Provider abstraction | Implemented | `copilot_sql_engine/llm_providers.py` |
| Gemini health check | Implemented | `/health/llm` |
| Fallback flagging | Implemented | `fallback_used`, provider metadata |
| API key not exposed in UI | Implemented by environment usage | `.env` values are server-side; do not commit secrets. |
| Technical warnings separated from business limitations | Implemented | `ai_insight_v11_service.py` response fields |

## Data Safety

| Control | Status | Notes |
|---|---:|---|
| Synthetic data | Implemented | Data is generated for MVP/demo. |
| Real customer PII exclusion | Intended | No real source integration found. |
| PII flags in catalog | Partially implemented / recommended | `column_catalog` exists; confirm sensitivity attributes before production. |
| Row-level security | Not found | Required for real client deployment. |
| Tenant isolation | Not found | Required for multi-client production. |

## Validation

| Validation | Status | Evidence |
|---|---:|---|
| SQL validation | Implemented | `copilot_sql_engine/safety.py` |
| SQL execution timeout | Implemented | `copilot_sql_engine/executor.py` |
| Result support validation | Partially implemented | `validate_result_support` in `ai_insight_v11_service.py` |
| Missing data handling | Implemented | `missing_data_rules` table and service logic |
| Feature data quality checks | Implemented | `008_ml_feature_quality_checks.sql`, `refresh_ml_feature_tables.py` |
| LLM answer regression tests | Implemented for selected flows | `scripts/test_evidence_hub_and_ai_cleanup.py`, `scripts/smoke_test_ai_insight_v11.py` |

## Observability

| Object | Status | Purpose |
|---|---:|---|
| `llm_request_log` | Implemented | Log LLM request metadata and failures. |
| `insight_test_snapshots` | Implemented | Store AI insight evidence payload. |
| `model_scoring_jobs` | Implemented | Track scoring jobs. |
| `query_audit_log` | Implemented in MVP schema | Earlier text-to-SQL audit log. |
| Frontend telemetry | Not found | Recommended for production. |

## Production Recommendations

1. Add authentication and authorization.
2. Add Supabase RLS policies for role-specific access.
3. Add prompt injection and data exfiltration tests.
4. Add LLM cost and rate-limit controls.
5. Add evidence retention policies.
6. Add production secret management.
7. Add model governance sign-off and model cards.

