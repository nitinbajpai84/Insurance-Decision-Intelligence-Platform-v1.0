# Executive Summary

## Client-Friendly Positioning

The Insurance Decision Intelligence Platform is an insurance analytics and AI platform that combines structured insurance data, ML scores, semantic context, and GenAI to produce explainable business insights and recommendations.

It is designed for an insurance client demo using synthetic ACORD-inspired data. It is not a production policy administration system. It demonstrates how insurers can move beyond static dashboards into decision support: what is happening, why it matters, what action to take, and what evidence supports the recommendation.

## What The Platform Does

| Capability | Status | Evidence |
|---|---:|---|
| Customer 360 | Implemented | `frontend/app/page.tsx`, `GET /customers/{id}/360` in `copilot_api_gateway/api.py` |
| Agent 360 | Implemented | `frontend/app/page.tsx`, `GET /agents/{id}/360` |
| Campaign analytics | Implemented | `CampaignView` in `frontend/app/page.tsx`, `GET /campaigns/{id}/360` |
| Agent performance tracking | Implemented | `AgentPerformanceView`, `GET /agents/performance-dashboard` |
| Policy lapse risk analytics | Implemented | `LapseRiskView`, `GET /policies/lapse-dashboard` |
| AI Intelligence | Partially implemented | `POST /ai-insight-v11/ask`, `ai_insight_v11_service.py` |
| Insight Evidence Hub | Implemented for AI snapshots | `GET /debug/latest-insight-evidence`, `insight_snapshot_service.py` |
| pgvector semantic context | Implemented | `017_genai_context_layer_pgvector.sql`, `embedding_pipeline/` |
| Gemini provider | Implemented | `copilot_sql_engine/llm_providers.py` |
| Ollama fallback | Partially implemented | Embedding provider exists in `embedding_pipeline/providers.py`; current SQL engine constrains `LLM_PROVIDER` to Gemini or fallback templates. |

## Why It Matters For An Insurer

The platform demonstrates decision intelligence across the insurance value chain:

| Decision Area | Business Value |
|---|---|
| Retention | Identify lapse risk, premium at risk, root causes, and retention actions. |
| Growth | Prioritize cross-sell and next-best-product opportunities. |
| Distribution | Track agent productivity, coaching needs, MDRT-style producers, and rising stars. |
| Campaigns | Measure targeting, response, conversion, ROI, and lead follow-up. |
| Claims | Provide claim context and fraud indicator architecture for future expansion. |
| Governance | Explain why an AI answer or recommendation was produced. |

## How AI, ML, Data, And Context Work Together

The platform combines four layers:

1. Structured data: customers, policies, agents, campaigns, claims, payments, and engagement.
2. ML outputs: feature tables, model scores, model predictions, and next best actions.
3. Semantic context: business glossary, KPI definitions, table and column catalog, join paths, and semantic documents stored with pgvector embeddings.
4. GenAI workflow: role-aware question handling, SQL generation, SQL validation, result interpretation, recommendations, and evidence capture.

## How This Differs From A Normal Dashboard

A normal dashboard shows fixed metrics. This platform also supports:

| Normal Dashboard | Decision Intelligence Platform |
|---|---|
| Static charts | Natural language question answering |
| Metric-only output | SQL-backed business explanation |
| Limited context | Semantic context retrieval from pgvector |
| Little traceability | Evidence Hub with source tables, SQL, context, and model traces |
| Descriptive analytics | Recommendations and next best actions |

## Client Value Demonstrated

The MVP demonstrates how an insurer can:

- Improve retention by identifying lapse risk before policy exit.
- Improve cross-sell by targeting customers with product gaps and high propensity.
- Improve campaign ROI through segment and channel performance insights.
- Improve agent productivity by comparing agents against peer clusters.
- Improve trust in AI by showing SQL, model, context, and data evidence.

## Important Maturity Statement

This is a synthetic-data MVP. It is suitable for client demonstration, architecture walkthrough, and roadmap planning. Production deployment would require real source integration, data governance, identity and access controls, MLOps, monitoring, testing, security review, and model validation.

