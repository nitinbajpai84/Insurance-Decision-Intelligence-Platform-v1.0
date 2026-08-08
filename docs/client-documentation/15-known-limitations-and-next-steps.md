# Known Limitations And Next Steps

## Limitations

| Limitation | Status | Business Impact | Recommended Improvement |
|---|---:|---|---|
| Synthetic data only | Implemented by design | Demo patterns may not reflect real insurer distribution exactly | Integrate policy admin, CRM, claims, billing, marketing source systems. |
| No dedicated raw/staging layer found | Not found | Limited production ingestion lineage | Add raw/staging schemas and source-to-target controls. |
| No real policy administration integration | Not found | Cannot use with live policies | Build connectors and ingestion contracts. |
| No real CRM integration | Not found | Customer actions are not synchronized to CRM | Add CRM APIs or data export workflow. |
| No production MLOps pipeline found | Partially implemented scoring only | Model quality and drift not production-governed | Add training pipeline, registry, model cards, drift monitoring. |
| Gemini quota may affect testing | Known risk | AI responses may fallback or fail during demo | Pre-run demo questions; keep fallback answers ready. |
| Ollama not implemented as text-to-SQL provider in current SQL engine | Not found | Claims about Ollama text fallback should be limited | Either implement provider or remove from client messaging. |
| Some evidence tables may be empty | Expected until runtime/backfill | Evidence Hub may look sparse | Run AI questions and backfill recommendation lineage before demo. |
| Feature tables may be empty until refreshed | Expected | ML scoring and dashboards may lack data | Run `009_refresh_ml_feature_tables.sql` or Python refresh. |
| Authentication and RLS not found | Not found | Not safe for real customer data | Add identity, authorization, RLS, and secrets management. |
| Production observability not found | Not found | Hard to operate at scale | Add logging, metrics, traces, alerts, cost monitoring. |
| Frontend includes sample fallback data | Implemented | Demo can hide API/data issues | Clearly distinguish sample fallback from live data in production. |

## Missing Or Planned Objects From Requested Context

| Object | Status |
|---|---:|
| `households` | Not found in current codebase |
| Dedicated raw/staging tables | Not found |
| Real retention action outcome table | Not found |
| Production CRM integration | Not found |
| Production data catalog governance workflow | Planned / Recommended |
| Model explainability values such as persisted SHAP | Partially implemented conceptually; not fully populated |

## Recommended Client Presentation Position

Use this language:

"This is a working MVP and architecture demonstrator using synthetic insurance data. It shows the end-to-end pattern for decision intelligence: data, ML scores, semantic context, GenAI, SQL validation, business insight, recommendations, and evidence. The next phase would productionize the source integrations, security, MLOps, governance, and operational monitoring."

Avoid saying:

- The models are production-validated.
- The data is real client data.
- All evidence tables are always populated.
- Ollama is the active text-to-SQL provider unless implemented and verified.

## Next Steps Before Client Demo

1. Run feature table refreshes and validate row counts.
2. Generate or backfill selected `next_best_actions`.
3. Backfill `recommendation_evidence` for demo recommendations.
4. Run embedding pipeline and confirm `semantic_documents.embedding` is populated.
5. Run 5-10 curated AI questions and save evidence snapshots.
6. Prepare screenshots for each tab.
7. Test the demo without internet dependency where possible.

