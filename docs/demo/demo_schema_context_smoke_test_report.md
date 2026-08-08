# Demo Schema/Context Smoke Test Report

- Generated at: 2026-06-04T01:17:54.683195+00:00
- Table registry status: present
- KPI registry status: present
- Model registry status: present
- Context registry status: present
- ACT allowlisted tables: 65
- TRUN tables: 0

## Registry Checks

| Check | Status | Details |
|---|---|---|
| table_registry_exists | PASS | cld_table_registry is available |
| kpi_registry_exists | PASS | cld_kpi_registry is available |
| model_registry_exists | PASS | cld_model_registry is available |
| context_registry_exists | PASS | cld_context_registry is available |
| prompt_guardrails_present | PASS | SQL_SYSTEM_PROMPT contains allowlist guardrails |
| fake_table_validation | PASS | Missing table(s) in actual Supabase schema: public.this_table_does_not_exist |
| no_trun_tables_in_context | PASS | No SQL-usable context rows include TRUN tables |
| kpis_use_act_tables | PASS | All KPI rows reference ACT tables |
| models_use_act_tables | PASS | All model rows reference ACT tables |
| allowlist_loaded | PASS | 65 AI SQL allowlisted tables loaded |

## Demo Questions

| Role | Question | Passed | Validation | Answer Status |
|---|---|---|---|---|
| Agency Manager | Which agents have the highest premium at risk? | YES | VALIDATED | NOT_SUPPORTED |
| Campaign Manager | Which campaigns generated the highest policy conversion? | YES | VALIDATED | NOT_SUPPORTED |
| Insurance Agent | Which customers are likely to lapse in the next 90 days? | YES | VALIDATED | NOT_SUPPORTED |
| Sales Director | Which products are declining in new sales? | YES | VALIDATED | NOT_SUPPORTED |
| Insurance Agent | Which customers should agents contact this week? | YES | VALIDATED | NOT_SUPPORTED |
| Executive Leadership | What are the top risks to revenue this month? | YES | VALIDATED | NOT_SUPPORTED |
| Campaign Manager | Show campaign conversion rate by channel. | YES | VALIDATED | NOT_SUPPORTED |
| Insurance Agent | Show SQL for lapse risk by product. | YES | VALIDATED | NOT_SUPPORTED |
