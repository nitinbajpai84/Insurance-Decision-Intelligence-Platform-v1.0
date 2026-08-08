# UI Tab Feature Guide

## Tab Overview

The frontend is implemented in `frontend/app/page.tsx`. The main navigation is defined in `navItems`, and the main tabs are:

1. Home
2. Know Your Customer
3. Know Your Agent
4. Campaign Effectiveness
5. Agent Performance Tracking
6. Policy Lapse Risk
7. AI Intelligence
8. Insight Evidence Hub

## 1. Home

| Topic | Detail |
|---|---|
| Purpose | Executive command center for insurance performance and decision priorities. |
| Audience | Executive leadership, sales directors, managers. |
| Data sources | Mix of sample and API-driven briefing via `/intelligence/briefing`. |
| APIs | `GET /intelligence/briefing` |
| Key KPIs | Revenue at risk, revenue opportunity, customer growth, agent productivity. |
| Models | Policy lapse, propensity, campaign response, agent performance, CLV where surfaced through briefing. |
| Demo script | "Start here to show the business agenda: risk, growth, productivity, and decision queue." |
| Value proposition | Executive-level narrative before drilling into data products. |

## 2. Know Your Customer

| Topic | Detail |
|---|---|
| Purpose | Customer 360 view with profile, policies, risks, opportunities, engagement, recommendations, and evidence. |
| Audience | Insurance agents, agency managers, customer service. |
| APIs | `GET /customers/search`, `GET /customers/{id}/360` |
| Tables | `customers`, `parties`, `addresses`, `policies`, `products`, `claims`, `model_scores`, `next_best_actions` |
| Models | Propensity, churn, lapse, CLV, next best product as available in scores/actions. |
| UI components | Search, profile cards, policy portfolio, risk scores, engagement timeline, recommendations, evidence panel. |
| Demo script | "Search for a customer and show how the platform explains risk, holdings, relationship context, and recommended next action." |

## 3. Know Your Agent

| Topic | Detail |
|---|---|
| Purpose | Agent 360 view for profile, productivity, customer book, risk, movement, and manager actions. |
| Audience | Agency managers, sales directors. |
| APIs | `GET /agents/search`, `GET /agents/{id}/360` |
| Tables | `agents`, `parties`, `agent_mapa_metrics`, `agent_movements`, `agent_targets`, `agent_commissions`, `policies`, `model_scores` |
| Models | Agent performance, agent attrition, next best customer. |
| Demo script | "Show the agent as the owner of customer relationships and explain productivity, movement history, and coaching needs." |

## 4. Campaign Effectiveness

| Topic | Detail |
|---|---|
| Purpose | Evaluate campaign performance, funnel quality, conversion, ROI, and follow-up actions. |
| Audience | Campaign managers, sales leaders. |
| APIs | `GET /campaigns/search`, `GET /campaigns/{id}/360` |
| Tables | `campaigns`, `campaign_targets`, `campaign_responses`, `leads`, `opportunities`, `policies`, `products`, `model_scores` |
| Models | Campaign response, lead conversion, propensity. |
| Key visualizations | Funnel metrics, conversion analytics, segment performance, recommendations, lineage. |
| Demo script | "Filter by campaign, channel, or date; show where conversion is strongest and which follow-up actions matter." |

## 5. Agent Performance Tracking

| Topic | Detail |
|---|---|
| Purpose | Track agent productivity, target achievement, conversion, persistency, peer clusters, MDRT agents, rising stars, and coaching needs. |
| Audience | Agency managers, sales directors. |
| APIs | `GET /agents/performance-dashboard` |
| Tables | `agents`, `parties`, `agent_mapa_metrics`, `agent_targets`, `policies`, `customers`, `products`, `v_latest_model_scores` |
| Models | Agent performance, agent attrition, next best customer where available. |
| UI components | Region filter, cluster filter, KPI strip, leaderboard, MAPA productivity, trends, peer clusters, risk alerts, coaching recommendations. |
| Demo script | "Show SG and HK region filters, identify rising stars and MDRT-style producers, then move to coaching recommendations." |

## 6. Policy Lapse Risk

| Topic | Detail |
|---|---|
| Purpose | Identify premium at risk, high-risk policies, root causes, vulnerable products, agents, and retention actions. |
| Audience | Retention teams, agency managers, executives. |
| APIs | `GET /policies/lapse-dashboard` |
| Tables | `policies`, `payments`, `policy_events`, `policy_renewals`, `customer_complaints`, `customer_service_requests`, `customers`, `agents`, `products`, `model_scores`, `next_best_actions` |
| Models | Policy lapse, propensity, next best product, retention action logic. |
| Key features | Premium at risk, root causes, top customers, associated agents, product hotspots, action center, scenario simulator. |
| Demo script | "Start with premium at risk, then drill into root causes and recommended retention actions." |

## 7. AI Intelligence

| Topic | Detail |
|---|---|
| Purpose | Ask natural language questions and receive SQL-backed, context-aware, model-aware insights. |
| Audience | All roles; especially executives, analysts, managers. |
| APIs | `POST /intelligence/ask` (legacy alias `POST /ai-insight-v11/ask`), `GET /health/llm` |
| Tables | Varies by question; semantic and evidence tables are also used. |
| Models | Varies by question; returned in `models_used`. |
| UI components | Question input, role selector, answer summary, SQL viewer, result preview, data points, context, models, limitations. |
| Demo script | "Ask a role-specific question, show the generated SQL, then explain that the answer is grounded in data and context." |

## 8. Insight Evidence Hub

| Topic | Detail |
|---|---|
| Purpose | Trace AI answers to SQL, tables, columns, context documents, models, limitations, and diagnostics. |
| Audience | Data analysts, risk/governance teams, architects, business owners. |
| APIs | `GET /debug/latest-insight-evidence` |
| Tables | `insight_test_snapshots`, `llm_request_log`, `semantic_documents`, `model_scores`, `insight_lineage`, `recommendation_evidence` |
| UI components | Recent runs, related tables, related columns, semantic context, data lineage, underlying models, SQL evidence, technical diagnostics. |
| Demo script | "After asking AI Intelligence a question, open the Evidence Hub to show traceability and governance." |
