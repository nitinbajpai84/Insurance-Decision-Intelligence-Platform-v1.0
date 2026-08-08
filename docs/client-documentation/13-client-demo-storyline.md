# Client Demo Storyline

## 10-15 Minute Demo Flow

### 1. Start With Home

Talk track:

"This is the executive view of the Insurance Decision Intelligence Platform. It brings together customer intelligence, agent productivity, campaign effectiveness, lapse risk monitoring, model governance, and decision insights."

Show:

- Executive command center.
- Revenue risk and opportunity narrative.
- Decision queue.
- Role selector.

### 2. Show Policy Lapse Risk

Talk track:

"Retention is one of the highest-value use cases. The platform identifies premium at risk, root causes, vulnerable products, customers, agents, and recommended retention actions."

Show:

- Premium at risk.
- High-risk policies/customers.
- Product and segment hotspots.
- Root causes such as missed payments or complaints.

### 3. Drill Into Know Your Customer

Talk track:

"From portfolio-level risk, we can drill into a customer view and understand the customer profile, policy portfolio, risk scores, engagement, recommendations, and data evidence."

Show:

- Search by customer.
- Customer profile and policies.
- Risk and opportunity scores.
- Recommended action and evidence.

### 4. Show Know Your Agent

Talk track:

"Insurance distribution depends on agent relationships. Here we can see the agent profile, MAPA activity, movement history, customer portfolio, and risk indicators."

Show:

- Agent search.
- Agent KPIs.
- Movement and productivity context.
- Manager actions.

### 5. Show Campaign Effectiveness

Talk track:

"The campaign view connects marketing activity to leads, quotes, policies, premium, ROI, and next follow-up actions."

Show:

- Campaign/channel/date filter.
- Funnel metrics.
- Segment and channel performance.
- Recommendations.

### 6. Show Agent Performance Tracking

Talk track:

"Managers can compare agents by region, peer cluster, customer mix, product focus, rising-star status, MDRT-style performance, and coaching needs."

Show:

- SG and HK region filters.
- Leaderboard.
- MAPA productivity.
- Peer clusters.
- Coaching recommendations.

### 7. Show AI Intelligence

Talk track:

"Instead of only using dashboards, users can ask natural language questions. The answer is SQL-backed, model-aware, and context-aware."

Suggested question:

"What are the top risks to revenue this month?"

Show:

- Answer summary.
- Generated SQL.
- Result rows.
- Key data points.
- Context and limitations.

### 8. Show The Generated SQL

Talk track:

"This is not a black-box answer. The platform shows the SQL used to produce the answer, and the SQL is validated as read-only before execution."

### 9. Show Insight Evidence Hub

Talk track:

"The Evidence Hub explains what data, context, models, SQL, and diagnostics supported the answer."

Show:

- Recent insight run.
- Related tables and columns.
- Context documents.
- SQL evidence.
- Model evidence.
- Technical diagnostics.

### 10. Close With Business Value

Talk track:

"The platform demonstrates how insurers can improve retention, cross-sell, campaign ROI, agent productivity, and trust in AI-generated recommendations."

## Demo Questions By Role

| Role | Questions |
|---|---|
| Executive Leadership | What are the top risks to revenue this month? What are the top growth opportunities? |
| Agency Manager | Which agents need coaching this month? Which branch has the highest lapse exposure? |
| Insurance Agent | Which customers should I contact first this week? Which product should I cross-sell? |
| Campaign Manager | Which campaign generated the highest conversion? Which leads should be prioritized? |
| Data Analyst | Show SQL for lapse risk by product. Which tables support campaign conversion? |

## Demo Preparation Checklist

1. Start backend on `http://127.0.0.1:8071`.
2. Start frontend on `http://127.0.0.1:3000`.
3. Confirm `/health` and `/health/llm`.
4. Confirm feature tables and semantic embeddings have rows.
5. Ask one AI Intelligence question and open Evidence Hub.
6. Keep a fallback story ready if Gemini quota is exhausted.

