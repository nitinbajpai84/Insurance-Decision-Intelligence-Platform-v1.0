# 3-Minute Client Demo Script

## Opening: 0:00-0:20

Narration:
This is the Insurance Intelligence Product. It connects customer, policy, campaign, claims, agent, model-score, semantic context, and SQL validation layers so business users can make growth and retention decisions with evidence.

Screen action:
Start on Home. Highlight the executive KPI strip, today's decision queue, and the buttons for AI Intelligence and Evidence Hub.

Key point:
This is not a static dashboard. It is a decision intelligence workflow that combines data, models, context, and governed AI.

## Campaign Effectiveness: 0:20-0:45

Narration:
The campaign view helps marketing teams understand which health protection campaigns are creating engagement, where conversion is weak, and which segment or channel should be retargeted.

Screen action:
Open Campaign Effectiveness. Highlight funnel metrics, policy conversion, segment performance, ROI, and recommendations.

Expected output:
Medical Upgrade or Health Protection campaigns should show strong engagement, lead creation, premium generated, and a recommended next action such as senior-agent follow-up or retargeting a low-conversion segment.

## Agent Performance Tracking: 0:45-1:10

Narration:
Agency managers can track premium, policies sold, conversion, persistency, MAPA activity, peer clusters, rising stars, and coaching needs in one view.

Screen action:
Open Agent Performance Tracking. Highlight the KPI strip, leaderboard, MAPA productivity, peer cluster view, MDRT-style producer segmentation, and coaching recommendations.

Expected output:
The screen should show agents needing coaching, high premium-at-risk agents, declining MAPA signals, and growth insight based on peer or cluster trends.

## Policy Lapse Risk: 1:10-1:35

Narration:
The lapse risk view focuses retention action. It surfaces high-risk policies, premium at risk, lapse drivers, customer segments at risk, responsible agents, and recommended retention actions.

Screen action:
Open Policy Lapse Risk. Highlight premium at risk, missed-payment or renewal-window drivers, high-risk policies, and retention recommendations.

Expected output:
The page should explain whether lapse scores come from model scores or from an internal proxy using missed payments, renewal timing, service issues, complaints, and engagement.

## Brief 360 Views: 1:35-1:50

Narration:
The same intelligence can be inspected at entity level. Know Your Customer shows policy portfolio, risks, opportunities, timeline, next-best-action, and evidence. Know Your Agent shows productivity, MAPA trend, customer portfolio, movement history, risk, and manager actions.

Screen action:
Briefly open Know Your Customer, then Know Your Agent.

Key point:
The platform supports both executive summary and operational drilldown.

## AI Intelligence: 1:50-2:25

Narration:
Now a business user can ask a natural language question. The platform retrieves verified context, generates SQL, validates it against the actual Supabase schema, executes only read-only SQL, validates the result, and then generates a business answer.

Screen action:
Open AI Intelligence. Select Agency Manager. Ask: "Which agents need coaching this month?"

Expected output:
The answer should be SQL-backed and show validation status, SQL execution status, row count, key data points, recommendations, result preview, and a button to view full evidence.

Backup if API fails:
Demo Mode should keep the business UI clean and show a controlled fallback answer. Technical notes should appear in the Evidence Hub, not as a raw business error.

## Insight Evidence Hub: 2:25-2:50

Narration:
The Evidence Hub makes the AI answer auditable. It shows the question, role, SQL, validation status, execution status, result preview, tables, columns, model layer, semantic context, and lineage.

Screen action:
Click View Full Evidence. Highlight SQL Evidence, Data Lineage, Semantic Context, Underlying Models, and Data, Models & Context Architecture.

Expected output:
The screen should prove grounding in real Supabase tables, generated SQL, model/context retrieval, and validation.

## Closing: 2:50-3:00

Narration:
This gives insurers one intelligence layer for campaign growth, agent productivity, lapse prevention, and evidence-backed AI decisions.

Screen action:
Return to Home or leave on Evidence Hub.

