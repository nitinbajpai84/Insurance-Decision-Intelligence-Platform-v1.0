# Demo Readiness Report

- Generated at: 2026-06-03T07:28:56.846490+00:00
- Frontend URL: `http://127.0.0.1:3000`
- API URL: `http://127.0.0.1:8071`
- Checks passed: 23/23

## Check Results

| Area | Name | Status | Details |
|---|---|---|---|
| frontend_route | Home | PASS | HTTP 200; route=/; brand_present=True |
| frontend_route | Know Your Customer | PASS | HTTP 200; route=/?view=customer; brand_present=True |
| frontend_route | Know Your Agent | PASS | HTTP 200; route=/?view=agent; brand_present=True |
| frontend_route | Campaign Effectiveness | PASS | HTTP 200; route=/?view=campaign; brand_present=True |
| frontend_route | Agent Performance Tracking | PASS | HTTP 200; route=/?view=agent-performance; brand_present=True |
| frontend_route | Policy Lapse Risk | PASS | HTTP 200; route=/?view=lapse-risk; brand_present=True |
| frontend_route | AI Intelligence | PASS | HTTP 200; route=/ai-intelligence; brand_present=True |
| frontend_route | Insight Evidence Hub | PASS | HTTP 200; route=/insight-evidence-hub; brand_present=True |
| backend_endpoint | backend health | PASS | {"status":"ok","service":"insurance-decision-intelligence-api"} |
| backend_endpoint | llm health | PASS | provider=gemini; gemini_available=True; quota_exhausted=False |
| backend_endpoint | sql context health | PASS | {"verified_context_count":289,"embedding_count":289,"missing_embedding_count":0,"invalid_context_count":21,"planned_only_context_count":0} |
| backend_endpoint | latest insight evidence | PASS | {"insight_id":"23e8d5f9-4894-4fad-80ca-bfa0121815c3","role":"Data Analyst","question":"Show campaign conversion rate by channel.","timestamp":"2026-06-03T07:26:26.100117+00:00","recent_insight_runs":[{"snapshot_id":"23e8d5f9-4894-4fad-80ca-bfa0121815c3","role":"Data Analyst","question":"Show campaig |
| sql_safety | blocks destructive SQL | PASS | HTTP 200; response={"valid":false,"sql":null,"referenced_tables":[],"safety_decision":"blocked_by_validator","error_message":"Only SELECT or WITH statements are allowed"} |
| ai_question | Agency Manager: Which agents have the highest premium at risk? | PASS | validation=VALIDATED; execution=executed; rows=25; answer=VALIDATED |
| ai_question | Agency Manager: Which agents need coaching this month? | PASS | validation=VALIDATED; execution=executed; rows=25; answer=VALIDATED |
| ai_question | Campaign Manager: Which campaign generated the highest policy conversion? | PASS | validation=VALIDATED; execution=executed; rows=25; answer=VALIDATED |
| ai_question | Campaign Manager: Which customer segment responded best to health campaigns? | PASS | validation=VALIDATED; execution=executed; rows=25; answer=VALIDATED |
| ai_question | Sales Director: Which products are declining in new sales? | PASS | validation=VALIDATED; execution=executed; rows=9; answer=VALIDATED |
| ai_question | Insurance Agent: Which policies are likely to lapse in the next 90 days? | PASS | validation=VALIDATED; execution=executed; rows=25; answer=VALIDATED |
| ai_question | Insurance Agent: Which customers should agents contact this week? | PASS | validation=VALIDATED; execution=executed; rows=25; answer=VALIDATED |
| ai_question | Executive Leadership: What are the top risks to revenue this month? | PASS | validation=VALIDATED; execution=executed; rows=5; answer=VALIDATED |
| ai_question | Executive Leadership: What are the top growth opportunities? | PASS | validation=VALIDATED; execution=executed; rows=7; answer=VALIDATED |
| ai_question | Data Analyst: Show campaign conversion rate by channel. | PASS | validation=VALIDATED; execution=executed; rows=8; answer=VALIDATED |

## Demo Question Catalog

| Role | Question | Demo Ready | Validation | Execution | Rows | Provider |
|---|---|---|---|---|---:|---|
| Agency Manager | Which agents have the highest premium at risk? | YES | VALIDATED | executed | 25 | gemini / validated_sql_template |
| Agency Manager | Which agents need coaching this month? | YES | VALIDATED | executed | 25 | gemini / validated_sql_template |
| Campaign Manager | Which campaign generated the highest policy conversion? | YES | VALIDATED | executed | 25 | gemini / validated_sql_template |
| Campaign Manager | Which customer segment responded best to health campaigns? | YES | VALIDATED | executed | 25 | gemini / validated_sql_template |
| Sales Director | Which products are declining in new sales? | YES | VALIDATED | executed | 9 | gemini / validated_sql_template |
| Insurance Agent | Which policies are likely to lapse in the next 90 days? | YES | VALIDATED | executed | 25 | gemini / validated_sql_template |
| Insurance Agent | Which customers should agents contact this week? | YES | VALIDATED | executed | 25 | gemini / validated_sql_template |
| Executive Leadership | What are the top risks to revenue this month? | YES | VALIDATED | executed | 5 | gemini / validated_sql_template |
| Executive Leadership | What are the top growth opportunities? | YES | VALIDATED | executed | 7 | gemini / gemini-2.5-flash-lite |
| Data Analyst | Show campaign conversion rate by channel. | YES | VALIDATED | executed | 8 | gemini / validated_sql_template |
