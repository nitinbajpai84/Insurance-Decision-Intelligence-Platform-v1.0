from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any


ROLE_CONFIG: dict[str, dict[str, Any]] = {
    "insurance_agent": {
        "role_name": "Insurance Agent",
        "kpis": [
            {"label": "Priority customers", "value": "824", "trend": "+6.4%", "helper": "Customers to contact this week"},
            {"label": "Health cross-sell value", "value": "S$3.8M", "trend": "+11.2%", "helper": "High-propensity product gap"},
            {"label": "Lapse saves due", "value": "142", "trend": "-3.1%", "helper": "Policies needing retention call"},
            {"label": "Contact compliance", "value": "86%", "trend": "+4 pts", "helper": "Recommended actions touched"},
        ],
        "questions": [
            "Which customers should I call today?",
            "Which customers are likely to lapse?",
            "What should I cross-sell?",
            "Which customers need service recovery before sales?"
        ],
        "narrative": "Focus today on protecting high-value renewals, then convert engaged customers with clear health coverage gaps.",
        "owner": "Insurance Agent",
    },
    "agency_manager": {
        "role_name": "Agency Manager",
        "kpis": [
            {"label": "Agents needing coaching", "value": "38", "trend": "+5", "helper": "Declining MAPA or persistency"},
            {"label": "Premium at risk", "value": "S$5.2M", "trend": "-7.1%", "helper": "High-risk renewals"},
            {"label": "Branch conversion", "value": "18.4%", "trend": "+2.3 pts", "helper": "Quote-to-bind trend"},
            {"label": "Retention success", "value": "71%", "trend": "+6 pts", "helper": "Saved policies after action"},
        ],
        "questions": [
            "Which agents need coaching?",
            "Which regions are declining?",
            "Which agents have high-risk customers?",
            "Where should I reallocate leads?"
        ],
        "narrative": "The branch opportunity is to coach agents with declining activity while allocating high-intent leads to agents with better persistency.",
        "owner": "Agency Manager",
    },
    "campaign_manager": {
        "role_name": "Campaign Manager",
        "kpis": [
            {"label": "Campaign ROI", "value": "2.8x", "trend": "+0.4x", "helper": "Premium generated vs spend"},
            {"label": "Fatigue risk", "value": "18%", "trend": "+4 pts", "helper": "Repeated low engagement"},
            {"label": "Best segment lift", "value": "31%", "trend": "+9 pts", "helper": "Health-focused families"},
            {"label": "Follow-up backlog", "value": "1,284", "trend": "-8%", "helper": "Open high-intent responders"},
        ],
        "questions": [
            "Which campaign should receive more budget?",
            "Which segments are showing fatigue?",
            "Which leads should be routed to agents?",
            "Which campaign generated the most policy conversion?"
        ],
        "narrative": "Scale medical upgrade journeys in high-conversion segments and suppress fatigue-heavy cohorts before the next send.",
        "owner": "Campaign Manager",
    },
    "claims_manager": {
        "role_name": "Claims Manager",
        "kpis": [
            {"label": "Claims regions to review", "value": "7", "trend": "+2", "helper": "Higher frequency or severity"},
            {"label": "Fraud risk alerts", "value": "49", "trend": "+8", "helper": "Model and rule triggered"},
            {"label": "Service recovery cases", "value": "116", "trend": "-12", "helper": "Claims complaints open"},
            {"label": "Claims ratio", "value": "64%", "trend": "+3 pts", "helper": "Rolling 90 days"},
        ],
        "questions": [
            "Which regions have high claims ratios?",
            "Which claims need fraud review?",
            "Which customers need claims service recovery?",
            "Which products show rising claims severity?"
        ],
        "narrative": "Prioritize claims service recovery and investigate regions with rising frequency before lapse risk spreads to renewal cohorts.",
        "owner": "Claims Manager",
    },
    "sales_director": {
        "role_name": "Sales Director",
        "kpis": [
            {"label": "New business premium", "value": "S$42.8M", "trend": "+12.4%", "helper": "Rolling 90 days"},
            {"label": "Rising stars", "value": "57", "trend": "+14", "helper": "High-growth agents"},
            {"label": "MDRT pipeline", "value": "119", "trend": "+8", "helper": "Near-threshold producers"},
            {"label": "Productivity gap", "value": "S$6.1M", "trend": "-2.2%", "helper": "Peer cluster uplift"},
        ],
        "questions": [
            "Which agents are rising stars?",
            "Which agents can reach MDRT?",
            "Which product clusters are growing?",
            "Where is productivity falling?"
        ],
        "narrative": "The sales system is growing, but uneven agent productivity means coaching and lead reallocation can unlock meaningful premium.",
        "owner": "Sales Director",
    },
    "data_analyst": {
        "role_name": "Data Analyst",
        "kpis": [
            {"label": "Context coverage", "value": "92%", "trend": "+5 pts", "helper": "Questions mapped to semantic docs"},
            {"label": "SQL execution pass", "value": "98%", "trend": "+1 pt", "helper": "Read-only validated queries"},
            {"label": "Feature freshness", "value": "1 day", "trend": "stable", "helper": "Latest model snapshot"},
            {"label": "Lineage completeness", "value": "88%", "trend": "+6 pts", "helper": "Insight evidence captured"},
        ],
        "questions": [
            "Which models have the strongest signal?",
            "Which feature tables need refresh?",
            "Show lineage for latest recommendations.",
            "Which SQL templates are used most often?"
        ],
        "narrative": "Focus on feature freshness, semantic coverage, and lineage completeness so business answers remain trusted.",
        "owner": "Data Analyst",
    },
    "executive_leadership": {
        "role_name": "Executive Leadership",
        "kpis": [
            {"label": "Revenue at risk", "value": "S$5.2M", "trend": "-7.1%", "helper": "High-risk lapse exposure"},
            {"label": "Revenue opportunity", "value": "S$14.6M", "trend": "+10.4%", "helper": "Cross-sell and renewal upside"},
            {"label": "Customer growth", "value": "8.7%", "trend": "+1.2 pts", "helper": "Net growth momentum"},
            {"label": "Agent productivity", "value": "73%", "trend": "+4 pts", "helper": "MAPA-weighted productivity"},
        ],
        "questions": [
            "What trends should concern me?",
            "What opportunities should we prioritize?",
            "What revenue is at risk?",
            "Where should leadership intervene this week?"
        ],
        "narrative": "The strongest executive agenda is to reduce lapse exposure while scaling high-conversion health and wealth opportunities.",
        "owner": "Executive Leadership",
    },
}


def normalize_role(role_code: str | None) -> str:
    key = (role_code or "executive_leadership").strip().lower().replace(" ", "_")
    return key if key in ROLE_CONFIG else "executive_leadership"


def fetch_decision_intelligence(role_code: str | None = None) -> dict[str, Any]:
    key = normalize_role(role_code)
    role = ROLE_CONFIG[key]
    due = (datetime.now(timezone.utc) + timedelta(days=7)).date().isoformat()
    return {
        "role_code": key,
        "role_name": role["role_name"],
        "executive_briefing": {
            "narrative": role["narrative"],
            "top_risks": [
                "High-value policy lapse remains concentrated in health and wealth renewal cohorts.",
                "Agent activity is declining in selected branches despite healthy lead volume.",
                "Campaign fatigue is emerging in repeated medical upgrade journeys.",
            ],
            "top_opportunities": [
                "Health rider cross-sell among engaged families can unlock S$3.8M expected premium.",
                "MDRT-near agents can close the productivity gap with targeted lead allocation.",
                "Service recovery before renewal can protect high-CLV relationships.",
            ],
            "revenue_at_risk": "S$5.2M",
            "revenue_opportunity": "S$14.6M",
            "customer_growth": "8.7%",
            "lapse_trend": "-7.1%",
            "campaign_trend": "+3.4 pts",
            "agent_productivity_trend": "+4 pts",
        },
        "kpis": role["kpis"],
        "hidden_trends": [
            {
                "trend": "Health product lapse increasing",
                "reason": "Missed payments and premium increase events are clustered in health protection products.",
                "business_impact": "S$1.8M premium exposure",
                "confidence": 0.86,
                "recommended_action": "Trigger renewal rescue journeys and manager review.",
            },
            {
                "trend": "Agency productivity falling in selected branches",
                "reason": "Meetings and proposals are falling faster than lead volume.",
                "business_impact": "Potential 4.2 point conversion drag",
                "confidence": 0.82,
                "recommended_action": "Coach agents and reassign hot leads to high-conversion peers.",
            },
            {
                "trend": "High-value customer engagement dropping",
                "reason": "Digital visits and campaign opens are down for affluent wealth customers.",
                "business_impact": "S$2.6M retention exposure",
                "confidence": 0.79,
                "recommended_action": "Prioritize human relationship outreach over automated campaigns.",
            },
        ],
        "opportunities": [
            {
                "opportunity": "Customers likely to buy health rider",
                "potential_premium": "S$3.8M",
                "customer_count": 824,
                "confidence": 0.88,
                "recommended_action": "Create advisor call lists by product gap and engagement recency.",
            },
            {
                "opportunity": "Renewal-ready high-CLV customers",
                "potential_premium": "S$4.9M",
                "customer_count": 391,
                "confidence": 0.84,
                "recommended_action": "Assign senior agents for policy review conversations.",
            },
            {
                "opportunity": "Campaign segments with high conversion potential",
                "potential_premium": "S$2.4M",
                "customer_count": 1160,
                "confidence": 0.81,
                "recommended_action": "Increase budget for high-response segments and suppress low-response cohorts.",
            },
        ],
        "risks": [
            {
                "risk": "High lapse risk customers",
                "impact": "S$5.2M premium at risk",
                "root_cause": "Missed payments, renewal window, and reduced agent contact.",
                "confidence": 0.89,
                "recommended_action": "Launch retention call sequence within seven days.",
            },
            {
                "risk": "Underperforming agents",
                "impact": "S$6.1M productivity gap",
                "root_cause": "MAPA activity decline and lower proposal conversion.",
                "confidence": 0.83,
                "recommended_action": "Schedule coaching and route leads based on peer cluster fit.",
            },
            {
                "risk": "Campaign fatigue emerging",
                "impact": "18% response degradation",
                "root_cause": "Repeated touches to low-intent segments.",
                "confidence": 0.78,
                "recommended_action": "Suppress fatigued segments and refresh creative sequencing.",
            },
        ],
        "questions": role["questions"],
        "recommendations": [
            {
                "title": "Protect high-value renewal customers",
                "business_impact": "S$1.3M expected retained value",
                "reason": "High lapse probability, premium exposure, and renewal urgency are concentrated in 60-day windows.",
                "owner": role["owner"],
                "confidence": 0.91,
                "due_date": due,
                "expected_outcome": "Reduce near-term lapse and protect premium revenue.",
            },
            {
                "title": "Scale health cross-sell to engaged customers",
                "business_impact": "S$3.8M expected new premium",
                "reason": "Customers with strong engagement and no health product show high propensity.",
                "owner": role["owner"],
                "confidence": 0.87,
                "due_date": due,
                "expected_outcome": "Increase conversion while using existing customer intent.",
            },
            {
                "title": "Coach low-MAPA agents",
                "business_impact": "4.2 point conversion uplift opportunity",
                "reason": "Activity decline is visible before sales decline in peer clusters.",
                "owner": "Agency Manager",
                "confidence": 0.82,
                "due_date": due,
                "expected_outcome": "Improve proposal conversion and persistency.",
            },
        ],
        "evidence": {
            "source_tables": [
                "customers",
                "policies",
                "payments",
                "agent_mapa_metrics",
                "campaign_responses",
                "model_scores",
                "next_best_actions",
                "semantic_documents",
            ],
            "source_columns": [
                "customer_segment",
                "annual_premium",
                "payment_status",
                "metric_month",
                "response_type",
                "score",
                "recommended_action",
            ],
            "business_rules_used": [
                "Prioritize high CLV with human contact.",
                "Suppress sales action when unresolved complaint exists.",
                "Escalate renewal within 60 days when lapse risk is high.",
            ],
            "ml_models_used": [
                "policy_lapse",
                "propensity_to_buy",
                "campaign_response",
                "agent_performance",
                "customer_lifetime_value",
            ],
            "context_documents_used": [
                "Policy Lapse Risk Context",
                "Next Best Action Context",
                "Customer Segmentation Context",
                "MAPA Metrics Context",
            ],
            "confidence": 0.87,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
        "schema_additions": [
            "role_insight_templates",
            "role_action_templates",
            "proactive_insight_log",
            "trend_discovery_results",
            "opportunity_discovery_results",
            "risk_discovery_results",
        ],
        "services": [
            "trend_discovery_service",
            "opportunity_discovery_service",
            "risk_discovery_service",
            "executive_briefing_service",
            "role_personalization_service",
            "recommendation_generation_service",
        ],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
