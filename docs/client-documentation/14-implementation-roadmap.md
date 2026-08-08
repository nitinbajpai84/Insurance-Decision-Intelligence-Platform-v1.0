# Implementation Roadmap

## Phase 1: Current MVP

| Scope | Expected Benefit | Technical Tasks | Business Value |
|---|---|---|---|
| Synthetic data, Supabase schema, dashboards, AI Intelligence, evidence snapshots | Demonstrate end-to-end decision intelligence | Stabilize demo data, refresh features, seed context, run smoke tests | Client proof of concept |

Status: Implemented / Partially implemented.

## Phase 2: Improve AI Intelligence Quality

| Scope | Expected Benefit | Technical Tasks | Business Value |
|---|---|---|---|
| Better prompt routing, regression testing, answer validation | More relevant answers and less hallucination | Expand question catalog, improve context selection, add answer-to-SQL consistency checks | More credible client demo and analyst trust |

Status: Planned / Recommended.

## Phase 3: Strengthen Context Layer And Embeddings

| Scope | Expected Benefit | Technical Tasks | Business Value |
|---|---|---|---|
| Enrich semantic documents, catalogs, join paths, missing data rules | Better SQL grounding | Populate `kpi_definitions`, `table_catalog`, `column_catalog`, `join_path_catalog`, `model_catalog`; embed all docs | Fewer wrong joins and better explanations |

Status: Partially implemented.

## Phase 4: Enhance ML Models

| Scope | Expected Benefit | Technical Tasks | Business Value |
|---|---|---|---|
| Move from demo scoring to validated models | Stronger decision recommendations | Add model training notebooks/pipelines, metrics, model cards, calibration, SHAP | Production-grade risk and opportunity scoring |

Status: Planned / Recommended.

## Phase 5: Improve Insight Evidence Hub

| Scope | Expected Benefit | Technical Tasks | Business Value |
|---|---|---|---|
| Full lineage across AI, recommendation, and model evidence | Better governance and explainability | Backfill `recommendation_evidence`, populate `model_explanations`, improve Evidence Hub UI | Client confidence and audit readiness |

Status: Partially implemented.

## Phase 6: Production Readiness

| Scope | Expected Benefit | Technical Tasks | Business Value |
|---|---|---|---|
| Security, integration, MLOps, observability, performance | Production deployment readiness | Add auth/RLS, source integrations, orchestration, monitoring, CI/CD, model governance | Deployable enterprise platform |

Status: Planned / Recommended.

## Suggested Next 30 Days

1. Finalize demo data refresh and feature table population.
2. Confirm semantic embeddings and context search quality.
3. Build a curated demo question set by role with verified outputs.
4. Backfill recommendation evidence for selected next best actions.
5. Add screenshots and demo script notes to the client presentation.
6. Add API auth and environment hardening before sharing externally.

