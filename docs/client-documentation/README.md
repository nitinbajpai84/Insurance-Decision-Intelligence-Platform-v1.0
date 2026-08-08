# Insurance Decision Intelligence Platform Documentation Pack

This folder is a client-facing and technical documentation pack for the Insurance Decision Intelligence Platform MVP.

The pack is grounded in the current codebase and database scripts. Where a capability exists, the documentation references the module, SQL script, table, view, or API where it is implemented. Where a capability is not implemented or is only partially implemented, it is explicitly marked.

## How To Read This Pack

1. Start with `00-executive-summary.md` and `01-solution-overview.md` for senior stakeholder context.
2. Use `02-data-architecture.md` through `07-kpi-definitions-and-formulas.md` for architecture and data walkthroughs.
3. Use `08-ai-intelligence-architecture.md` and `09-insight-evidence-hub.md` for GenAI and explainability review.
4. Use `10-ui-tab-feature-guide.md` for client demo preparation.
5. Use `11-api-and-service-architecture.md` and `12-security-guardrails-and-validation.md` for technical review.
6. Use `13-client-demo-storyline.md` for a 10-15 minute walkthrough script.
7. Use `14-implementation-roadmap.md` and `15-known-limitations-and-next-steps.md` for next-phase planning.

## Status Legend

| Status | Meaning |
|---|---|
| Implemented | Found in the current codebase or SQL migration scripts. |
| Partially implemented | Some code, data model, or UI exists, but production maturity or full integration is incomplete. |
| Planned / Recommended | Reasonable next step, but not fully implemented in the current codebase. |
| Not found in current codebase | Requested or expected capability was not found during inspection. |

## Core Code References

| Area | Main References |
|---|---|
| Frontend tabs | `frontend/app/page.tsx` |
| API gateway | `copilot_api_gateway/api.py` |
| Entity 360 and dashboards | `copilot_api_gateway/entity360.py` |
| SQL engine | `copilot_sql_engine/` |
| AI insight service | `ai_insight_v11_service.py` |
| Evidence snapshot service | `insight_snapshot_service.py` |
| Context retrieval | `context_retriever_service.py`, `embedding_pipeline/` |
| Synthetic data generator | `generate_synthetic_insurance_data.py` |
| ML feature views and tables | `006_ml_feature_engineering_views.sql`, `007_ml_feature_tables.sql` |
| Scoring pipeline | `ml_scoring_pipeline.py`, `014_ml_scoring_serving_schema.sql` |
| Next best action | `016_next_best_action_engine.sql`, `020_genai_next_best_action_decisioning.sql`, `nba_engine/` |
| Role layer | `023_role_based_intelligence_layer.sql`, `role_intelligence_service.py` |
| Explainability governance | `024_explainability_governance_framework.sql` |

## Diagram Files

The `diagrams/` folder contains standalone Mermaid diagrams that can be pasted into Markdown, Confluence, Lucid, Mermaid Live, or architecture decks.

