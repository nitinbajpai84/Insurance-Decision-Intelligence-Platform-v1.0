from __future__ import annotations

import csv
import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from uuid import uuid4

import psycopg
from psycopg.rows import dict_row

from table_governance_service import governance_registry_exists, has_table, load_table_registry_rows


REPO_ROOT = Path(__file__).resolve().parent
DOCS_DIR = REPO_ROOT / "docs"
GOVERNANCE_DIR = DOCS_DIR / "database-cleanup"
LLM_HARNESS_DIR = DOCS_DIR / "llm-harness"
CONTEXT_DIR = DOCS_DIR / "context"


CODE_FILE_EXTENSIONS = {
    ".py",
    ".sql",
    ".md",
    ".http",
    ".ts",
    ".tsx",
    ".js",
    ".jsx",
    ".json",
}

EXCLUDED_DIR_PARTS = {
    ".git",
    ".pytest_cache",
    ".uv-cache",
    ".venv",
    "node_modules",
    "dist",
    "build",
    "__pycache__",
    "demo_artifacts",
}


@dataclass
class TableSignal:
    used_by_frontend: bool = False
    used_by_backend: bool = False
    used_by_ai_sql: bool = False
    used_by_context: bool = False
    used_by_models: bool = False
    used_by_demo: bool = False
    used_by_sql_examples: bool = False
    used_by_semantic_docs: bool = False
    used_by_faq: bool = False
    match_count: int = 0
    sample_matches: list[str] = field(default_factory=list)


@dataclass
class TableAuditRow:
    schema_name: str
    table_name: str
    full_table_name: str
    table_type: str
    row_count: int
    total_size_bytes: int
    index_size_bytes: int
    column_count: int
    primary_key_columns: list[str]
    foreign_keys: list[dict[str, Any]]
    last_known_usage: str | None
    has_vector_columns: bool
    used_by_frontend: bool
    used_by_backend: bool
    used_by_ai_sql: bool
    used_by_context: bool
    used_by_models: bool
    used_by_demo: bool
    used_by_sql_examples: bool
    used_by_semantic_docs: bool
    used_by_faq: bool
    classification_label: str
    table_role: str
    recommended_action: str
    reason: str
    confidence_score: float
    risk_if_truncated: str
    manual_review_required: bool
    authoritative_for_kpis: list[str] = field(default_factory=list)
    used_by_tabs: list[str] = field(default_factory=list)
    used_by_models_list: list[str] = field(default_factory=list)
    ai_sql_allowed: bool = False
    context_allowed: bool = False
    truncate_candidate: bool = False
    truncate_risk_level: str = "LOW"
    status: str = "ACTUAL"
    missing_data_points: list[str] = field(default_factory=list)
    fallback_formula: list[str] = field(default_factory=list)


KPI_DEFINITIONS: list[dict[str, Any]] = [
    {
        "kpi_name": "Premium at Risk",
        "business_definition": "Annual premium exposed to lapse or churn signals.",
        "formula": "sum(annual_premium) for active or high-risk policies",
        "business_domain": "policy",
        "grain": "policy or agent month",
        "authoritative_tables": ["public.policies", "public.model_scores"],
        "required_columns": ["annual_premium", "policy_status", "score_value"],
        "allowed_join_paths": ["policies -> model_scores"],
        "used_by_tabs": ["Policy Lapse Risk", "Agent Performance Tracking"],
        "used_by_roles": ["Agency Manager", "Sales Director", "Executive Leadership"],
        "sql_generation_notes": "Use active policies only and join the latest lapse model score if available.",
        "demo_priority": "HIGH",
        "status": "ACTUAL",
        "missing_data_points": [],
        "fallback_formula": "",
    },
    {
        "kpi_name": "Lapse Rate",
        "business_definition": "Lapsed policies divided by total eligible policies.",
        "formula": "lapsed policies / total policies",
        "business_domain": "policy",
        "grain": "month",
        "authoritative_tables": ["public.policies"],
        "required_columns": ["policy_status", "policy_id"],
        "allowed_join_paths": ["policies"],
        "used_by_tabs": ["Policy Lapse Risk", "Home"],
        "used_by_roles": ["Agency Manager", "Executive Leadership"],
        "sql_generation_notes": "Use nullif for denominator protection.",
        "demo_priority": "HIGH",
        "status": "ACTUAL",
        "missing_data_points": [],
        "fallback_formula": "",
    },
    {
        "kpi_name": "Persistency Rate",
        "business_definition": "The percentage of policies still in force after the renewal window.",
        "formula": "1 - lapse rate",
        "business_domain": "policy",
        "grain": "month",
        "authoritative_tables": ["public.policies"],
        "required_columns": ["policy_status", "renewal_date"],
        "allowed_join_paths": ["policies"],
        "used_by_tabs": ["Policy Lapse Risk", "Agent Performance Tracking"],
        "used_by_roles": ["Agency Manager", "Sales Director"],
        "sql_generation_notes": "Use renewal or policy status tables only.",
        "demo_priority": "HIGH",
        "status": "ACTUAL",
        "missing_data_points": [],
        "fallback_formula": "",
    },
    {
        "kpi_name": "Campaign Conversion Rate",
        "business_definition": "Converted campaign responses divided by targeted or responded population.",
        "formula": "converted responses / targeted customers",
        "business_domain": "campaign",
        "grain": "campaign",
        "authoritative_tables": ["public.campaigns", "public.campaign_targets", "public.campaign_responses"],
        "required_columns": ["campaign_id", "conversion_flag"],
        "allowed_join_paths": ["campaigns -> campaign_targets -> campaign_responses"],
        "used_by_tabs": ["Campaign Effectiveness"],
        "used_by_roles": ["Campaign Manager", "Sales Director"],
        "sql_generation_notes": "Keep the denominator explicit and protect with nullif.",
        "demo_priority": "HIGH",
        "status": "ACTUAL",
        "missing_data_points": [],
        "fallback_formula": "",
    },
    {
        "kpi_name": "Lead Conversion Rate",
        "business_definition": "Converted leads divided by total leads created.",
        "formula": "converted leads / total leads",
        "business_domain": "sales",
        "grain": "month",
        "authoritative_tables": ["public.leads", "public.opportunities"],
        "required_columns": ["lead_id", "lead_status"],
        "allowed_join_paths": ["leads -> opportunities"],
        "used_by_tabs": ["Campaign Effectiveness", "Know Your Agent"],
        "used_by_roles": ["Campaign Manager", "Agency Manager"],
        "sql_generation_notes": "Use lead status or opportunity stage only.",
        "demo_priority": "HIGH",
        "status": "ACTUAL",
        "missing_data_points": [],
        "fallback_formula": "",
    },
    {
        "kpi_name": "Quote-to-Bind Rate",
        "business_definition": "Issued policies divided by issued quotes.",
        "formula": "policies issued / quotes created",
        "business_domain": "sales",
        "grain": "month",
        "authoritative_tables": ["public.quotes", "public.policies"],
        "required_columns": ["quote_id", "policy_id"],
        "allowed_join_paths": ["quotes -> policies"],
        "used_by_tabs": ["Campaign Effectiveness", "Model Insights"],
        "used_by_roles": ["Campaign Manager", "Sales Director"],
        "sql_generation_notes": "Only use if quote table exists; otherwise mark partial.",
        "demo_priority": "MEDIUM",
        "status": "PARTIAL",
        "missing_data_points": ["quote table or quote status column may be missing"],
        "fallback_formula": "policies issued / applications",
    },
    {
        "kpi_name": "Agent Conversion Rate",
        "business_definition": "Policies sold divided by applications or leads assigned to an agent.",
        "formula": "policies sold / applications",
        "business_domain": "agent",
        "grain": "agent month",
        "authoritative_tables": ["public.agents", "public.policies", "public.agent_mapa_metrics"],
        "required_columns": ["agent_id", "policy_id", "application_count"],
        "allowed_join_paths": ["agents -> policies", "agents -> agent_mapa_metrics"],
        "used_by_tabs": ["Agent Performance Tracking", "Know Your Agent"],
        "used_by_roles": ["Agency Manager", "Sales Director"],
        "sql_generation_notes": "Prefer the monthly MAPA grain.",
        "demo_priority": "HIGH",
        "status": "ACTUAL",
        "missing_data_points": [],
        "fallback_formula": "",
    },
    {
        "kpi_name": "MAPA Productivity",
        "business_definition": "Weighted productivity of meetings, activities, proposals, and applications.",
        "formula": "meetings + activities + proposals + applications",
        "business_domain": "agent",
        "grain": "agent month",
        "authoritative_tables": ["public.agent_mapa_metrics"],
        "required_columns": ["meetings_count", "activities_count", "proposals_count", "applications_count"],
        "allowed_join_paths": ["agent_mapa_metrics"],
        "used_by_tabs": ["Agent Performance Tracking", "Know Your Agent"],
        "used_by_roles": ["Agency Manager", "Sales Director"],
        "sql_generation_notes": "Use the monthly agent MAPA metrics table.",
        "demo_priority": "HIGH",
        "status": "ACTUAL",
        "missing_data_points": [],
        "fallback_formula": "",
    },
    {
        "kpi_name": "Claims Ratio",
        "business_definition": "Incurred claims divided by earned premium.",
        "formula": "sum(incurred_amount) / sum(earned_premium)",
        "business_domain": "claims",
        "grain": "product month",
        "authoritative_tables": ["public.claims", "public.premiums"],
        "required_columns": ["incurred_amount", "earned_premium"],
        "allowed_join_paths": ["claims -> policies -> products", "premiums -> policies"],
        "used_by_tabs": ["Claims 360", "Model Insights"],
        "used_by_roles": ["Claims Manager", "Executive Leadership"],
        "sql_generation_notes": "Use nullif on earned premium.",
        "demo_priority": "HIGH",
        "status": "ACTUAL",
        "missing_data_points": [],
        "fallback_formula": "",
    },
    {
        "kpi_name": "Loss Ratio",
        "business_definition": "Loss ratio derived from claims incurred relative to premium.",
        "formula": "incurred / premium",
        "business_domain": "claims",
        "grain": "product month",
        "authoritative_tables": ["public.claims", "public.premiums"],
        "required_columns": ["incurred_amount", "premium_amount"],
        "allowed_join_paths": ["claims -> premiums"],
        "used_by_tabs": ["Claims 360", "Model Insights"],
        "used_by_roles": ["Claims Manager", "Executive Leadership"],
        "sql_generation_notes": "Match the premium period to the claims analysis window.",
        "demo_priority": "MEDIUM",
        "status": "ACTUAL",
        "missing_data_points": [],
        "fallback_formula": "",
    },
    {
        "kpi_name": "Customer Lifetime Value",
        "business_definition": "Estimated future customer contribution from premium and retention behavior.",
        "formula": "sum(expected premium over retention horizon)",
        "business_domain": "customer",
        "grain": "customer",
        "authoritative_tables": ["public.customers", "public.policies", "public.model_scores"],
        "required_columns": ["customer_id", "annual_premium"],
        "allowed_join_paths": ["customers -> policies -> model_scores"],
        "used_by_tabs": ["Know Your Customer", "AI Intelligence"],
        "used_by_roles": ["Insurance Agent", "Agency Manager", "Executive Leadership"],
        "sql_generation_notes": "If the CLV model table is missing, use annual premium proxy.",
        "demo_priority": "HIGH",
        "status": "ACTUAL",
        "missing_data_points": [],
        "fallback_formula": "sum(annual_premium) * retention_factor",
    },
    {
        "kpi_name": "Propensity Score",
        "business_definition": "Model score indicating likelihood to purchase the next product.",
        "formula": "latest propensity model score",
        "business_domain": "customer",
        "grain": "customer snapshot",
        "authoritative_tables": ["public.model_scores"],
        "required_columns": ["entity_id", "model_name", "score_value"],
        "allowed_join_paths": ["model_scores -> customers"],
        "used_by_tabs": ["Know Your Customer", "AI Intelligence"],
        "used_by_roles": ["Insurance Agent", "Agency Manager"],
        "sql_generation_notes": "Use only the latest validated score.",
        "demo_priority": "HIGH",
        "status": "ACTUAL",
        "missing_data_points": [],
        "fallback_formula": "",
    },
    {
        "kpi_name": "Churn Risk",
        "business_definition": "Model score for likelihood of customer attrition or inactivity.",
        "formula": "latest churn model score",
        "business_domain": "customer",
        "grain": "customer snapshot",
        "authoritative_tables": ["public.model_scores"],
        "required_columns": ["entity_id", "model_name", "score_value"],
        "allowed_join_paths": ["model_scores -> customers"],
        "used_by_tabs": ["Know Your Customer", "AI Intelligence"],
        "used_by_roles": ["Agency Manager", "Executive Leadership"],
        "sql_generation_notes": "Use the newest score per entity.",
        "demo_priority": "HIGH",
        "status": "ACTUAL",
        "missing_data_points": [],
        "fallback_formula": "",
    },
    {
        "kpi_name": "Retention Success Rate",
        "business_definition": "Retained at-risk policies divided by total at-risk policies.",
        "formula": "retained / at-risk policies",
        "business_domain": "policy",
        "grain": "month",
        "authoritative_tables": ["public.policy_events", "public.policies"],
        "required_columns": ["policy_event_type", "policy_status"],
        "allowed_join_paths": ["policy_events -> policies"],
        "used_by_tabs": ["Policy Lapse Risk"],
        "used_by_roles": ["Agency Manager", "Sales Director"],
        "sql_generation_notes": "Use policy events if present, otherwise policy status proxy.",
        "demo_priority": "MEDIUM",
        "status": "PARTIAL",
        "missing_data_points": ["policy_events may not be fully loaded"],
        "fallback_formula": "renewed policies / at-risk policies",
    },
    {
        "kpi_name": "Revenue Opportunity",
        "business_definition": "Premium that can be unlocked through cross-sell, renewal, or retention actions.",
        "formula": "premium at risk + cross-sell premium",
        "business_domain": "revenue",
        "grain": "agent month",
        "authoritative_tables": ["public.next_best_actions", "public.model_scores", "public.policies"],
        "required_columns": ["recommended_action", "annual_premium"],
        "allowed_join_paths": ["next_best_actions -> policies"],
        "used_by_tabs": ["AI Intelligence", "Agent Performance Tracking"],
        "used_by_roles": ["Agency Manager", "Sales Director"],
        "sql_generation_notes": "Keep the business logic readable and demo-safe.",
        "demo_priority": "HIGH",
        "status": "ACTUAL",
        "missing_data_points": [],
        "fallback_formula": "",
    },
    {
        "kpi_name": "Product Sales Decline",
        "business_definition": "Negative change in new business sales by product over the review window.",
        "formula": "prior period sales - current period sales",
        "business_domain": "product",
        "grain": "product month",
        "authoritative_tables": ["public.products", "public.policies"],
        "required_columns": ["product_id", "effective_date"],
        "allowed_join_paths": ["products -> policies"],
        "used_by_tabs": ["AI Intelligence", "Model Insights"],
        "used_by_roles": ["Sales Director", "Executive Leadership"],
        "sql_generation_notes": "Compare equal-length time windows.",
        "demo_priority": "MEDIUM",
        "status": "ACTUAL",
        "missing_data_points": [],
        "fallback_formula": "",
    },
    {
        "kpi_name": "High-Risk Customer Count",
        "business_definition": "Customers with high churn, lapse, or complaint risk.",
        "formula": "count(customers with high risk model scores)",
        "business_domain": "customer",
        "grain": "snapshot",
        "authoritative_tables": ["public.model_scores", "public.customers"],
        "required_columns": ["entity_id", "score_band"],
        "allowed_join_paths": ["model_scores -> customers"],
        "used_by_tabs": ["Know Your Customer", "AI Intelligence"],
        "used_by_roles": ["Agency Manager", "Executive Leadership"],
        "sql_generation_notes": "Use only the latest score per customer.",
        "demo_priority": "HIGH",
        "status": "ACTUAL",
        "missing_data_points": [],
        "fallback_formula": "",
    },
    {
        "kpi_name": "High-Propensity Customer Count",
        "business_definition": "Customers with high propensity to buy or cross-sell likelihood.",
        "formula": "count(customers with high propensity model scores)",
        "business_domain": "customer",
        "grain": "snapshot",
        "authoritative_tables": ["public.model_scores", "public.customers"],
        "required_columns": ["entity_id", "score_band"],
        "allowed_join_paths": ["model_scores -> customers"],
        "used_by_tabs": ["Know Your Customer", "AI Intelligence"],
        "used_by_roles": ["Insurance Agent", "Agency Manager"],
        "sql_generation_notes": "Keep the score interpretation explicit.",
        "demo_priority": "HIGH",
        "status": "ACTUAL",
        "missing_data_points": [],
        "fallback_formula": "",
    },
    {
        "kpi_name": "Agent Coaching Need",
        "business_definition": "An indicator of agent support need based on productivity, conversion, persistency, and risk.",
        "formula": "low MAPA + low conversion + low persistency + attrition risk",
        "business_domain": "agent",
        "grain": "agent month",
        "authoritative_tables": ["public.agent_mapa_metrics", "public.model_scores"],
        "required_columns": ["agent_id", "meetings_count"],
        "allowed_join_paths": ["agent_mapa_metrics -> model_scores"],
        "used_by_tabs": ["Agent Performance Tracking", "AI Intelligence"],
        "used_by_roles": ["Agency Manager", "Sales Director"],
        "sql_generation_notes": "Present as a ranking signal, not a disciplinary metric.",
        "demo_priority": "HIGH",
        "status": "ACTUAL",
        "missing_data_points": [],
        "fallback_formula": "",
    },
    {
        "kpi_name": "Campaign ROI",
        "business_definition": "Incremental premium from the campaign relative to spend.",
        "formula": "(conversion premium - budget) / budget",
        "business_domain": "campaign",
        "grain": "campaign",
        "authoritative_tables": ["public.campaigns", "public.campaign_responses"],
        "required_columns": ["budget", "conversion_premium"],
        "allowed_join_paths": ["campaigns -> campaign_responses"],
        "used_by_tabs": ["Campaign Effectiveness"],
        "used_by_roles": ["Campaign Manager", "Sales Director"],
        "sql_generation_notes": "Use the campaign budget field or mark as partial.",
        "demo_priority": "HIGH",
        "status": "PARTIAL",
        "missing_data_points": ["campaign budget may be absent or null"],
        "fallback_formula": "conversion premium / delivered count",
    },
]


MODEL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "model_name": "policy_lapse_risk",
        "model_type": "classification",
        "entity_type": "policy",
        "business_purpose": "Predict lapse likelihood for retention action.",
        "score_table": "public.model_scores",
        "score_column": "score_value",
        "score_interpretation": "Higher values indicate higher lapse risk.",
        "required_source_tables": ["public.policies", "public.payments", "public.customer_engagement_events"],
        "feature_sources": ["policy lifecycle, premium, payment, and engagement history"],
        "used_by_tabs": ["Policy Lapse Risk", "AI Intelligence"],
        "used_by_roles": ["Insurance Agent", "Agency Manager"],
        "ai_sql_allowed": True,
        "demo_priority": "HIGH",
        "limitation_notes": "Use only the latest score per policy.",
        "registry_status": "ACTUAL",
        "missing_data_points": [],
    },
    {
        "model_name": "propensity_to_buy",
        "model_type": "classification",
        "entity_type": "customer",
        "business_purpose": "Predict next-product purchase likelihood.",
        "score_table": "public.model_scores",
        "score_column": "score_value",
        "score_interpretation": "Higher values indicate greater propensity to buy.",
        "required_source_tables": ["public.customers", "public.customer_engagement_events", "public.campaign_responses"],
        "feature_sources": ["digital engagement, campaign interaction, policy mix"],
        "used_by_tabs": ["Know Your Customer", "AI Intelligence"],
        "used_by_roles": ["Insurance Agent", "Agency Manager"],
        "ai_sql_allowed": True,
        "demo_priority": "HIGH",
        "limitation_notes": "Use only the latest score per customer.",
        "registry_status": "ACTUAL",
        "missing_data_points": [],
    },
    {
        "model_name": "next_best_product",
        "model_type": "ranking",
        "entity_type": "customer",
        "business_purpose": "Recommend the most relevant next product.",
        "score_table": "public.model_predictions",
        "score_column": "prediction_score",
        "score_interpretation": "Higher score means stronger product recommendation.",
        "required_source_tables": ["public.customers", "public.products", "public.model_scores"],
        "feature_sources": ["customer profile, existing holdings, scores"],
        "used_by_tabs": ["Know Your Customer", "AI Intelligence"],
        "used_by_roles": ["Insurance Agent", "Agency Manager"],
        "ai_sql_allowed": True,
        "demo_priority": "HIGH",
        "limitation_notes": "If model_predictions is absent, use a fallback ranking from model_scores.",
        "registry_status": "PARTIAL",
        "missing_data_points": ["prediction table or prediction score column may be missing"],
    },
    {
        "model_name": "customer_churn_risk",
        "model_type": "classification",
        "entity_type": "customer",
        "business_purpose": "Predict customer churn or inactivity risk.",
        "score_table": "public.model_scores",
        "score_column": "score_value",
        "score_interpretation": "Higher values indicate higher churn risk.",
        "required_source_tables": ["public.customers", "public.customer_complaints", "public.customer_engagement_events"],
        "feature_sources": ["complaints, service, engagement, premium, and tenure"],
        "used_by_tabs": ["Know Your Customer", "AI Intelligence"],
        "used_by_roles": ["Agency Manager", "Executive Leadership"],
        "ai_sql_allowed": True,
        "demo_priority": "HIGH",
        "limitation_notes": "Use the latest customer snapshot score.",
        "registry_status": "ACTUAL",
        "missing_data_points": [],
    },
    {
        "model_name": "customer_lifetime_value",
        "model_type": "regression",
        "entity_type": "customer",
        "business_purpose": "Estimate future premium contribution.",
        "score_table": "public.model_scores",
        "score_column": "score_value",
        "score_interpretation": "Higher values indicate higher expected lifetime value.",
        "required_source_tables": ["public.customers", "public.policies", "public.payments"],
        "feature_sources": ["premium, tenure, product holdings, retention"],
        "used_by_tabs": ["Know Your Customer", "AI Intelligence"],
        "used_by_roles": ["Insurance Agent", "Executive Leadership"],
        "ai_sql_allowed": True,
        "demo_priority": "HIGH",
        "limitation_notes": "Proxy with premium if dedicated CLV table is missing.",
        "registry_status": "ACTUAL",
        "missing_data_points": [],
    },
    {
        "model_name": "agent_performance",
        "model_type": "ranking",
        "entity_type": "agent",
        "business_purpose": "Rank agent productivity and growth.",
        "score_table": "public.model_scores",
        "score_column": "score_value",
        "score_interpretation": "Higher values indicate better performance.",
        "required_source_tables": ["public.agents", "public.agent_mapa_metrics", "public.policies"],
        "feature_sources": ["MAPA activity, premium, persistency, targets"],
        "used_by_tabs": ["Agent Performance Tracking", "Know Your Agent"],
        "used_by_roles": ["Agency Manager", "Sales Director"],
        "ai_sql_allowed": True,
        "demo_priority": "HIGH",
        "limitation_notes": "Use monthly grain and compare peers in cluster.",
        "registry_status": "ACTUAL",
        "missing_data_points": [],
    },
    {
        "model_name": "agent_attrition",
        "model_type": "classification",
        "entity_type": "agent",
        "business_purpose": "Predict agent attrition or disengagement risk.",
        "score_table": "public.model_scores",
        "score_column": "score_value",
        "score_interpretation": "Higher values indicate higher attrition risk.",
        "required_source_tables": ["public.agents", "public.agent_movements", "public.agent_commissions"],
        "feature_sources": ["movement history, commission trend, activity decline"],
        "used_by_tabs": ["Agent Performance Tracking", "AI Intelligence"],
        "used_by_roles": ["Agency Manager", "Executive Leadership"],
        "ai_sql_allowed": True,
        "demo_priority": "HIGH",
        "limitation_notes": "Use the latest agent snapshot score.",
        "registry_status": "PARTIAL",
        "missing_data_points": ["commission trend table may be partial or missing"],
    },
    {
        "model_name": "campaign_response",
        "model_type": "classification",
        "entity_type": "campaign_target",
        "business_purpose": "Predict likelihood of campaign response or conversion.",
        "score_table": "public.model_scores",
        "score_column": "score_value",
        "score_interpretation": "Higher values indicate greater response likelihood.",
        "required_source_tables": ["public.campaigns", "public.campaign_targets", "public.campaign_responses"],
        "feature_sources": ["target segment, channel, timing, agent assignment"],
        "used_by_tabs": ["Campaign Effectiveness", "AI Intelligence"],
        "used_by_roles": ["Campaign Manager", "Sales Director"],
        "ai_sql_allowed": True,
        "demo_priority": "HIGH",
        "limitation_notes": "Use target-level scores only.",
        "registry_status": "ACTUAL",
        "missing_data_points": [],
    },
    {
        "model_name": "lead_conversion",
        "model_type": "classification",
        "entity_type": "lead",
        "business_purpose": "Predict lead-to-opportunity conversion likelihood.",
        "score_table": "public.model_scores",
        "score_column": "score_value",
        "score_interpretation": "Higher values indicate higher conversion likelihood.",
        "required_source_tables": ["public.leads", "public.opportunities"],
        "feature_sources": ["lead source, age, agent assignment, segment"],
        "used_by_tabs": ["Campaign Effectiveness", "AI Intelligence"],
        "used_by_roles": ["Campaign Manager", "Agency Manager"],
        "ai_sql_allowed": True,
        "demo_priority": "HIGH",
        "limitation_notes": "Use the latest lead score per lead.",
        "registry_status": "ACTUAL",
        "missing_data_points": [],
    },
    {
        "model_name": "claims_risk",
        "model_type": "classification",
        "entity_type": "claim",
        "business_purpose": "Predict claims risk or severity.",
        "score_table": "public.model_scores",
        "score_column": "score_value",
        "score_interpretation": "Higher values indicate higher claim risk.",
        "required_source_tables": ["public.claims", "public.claim_parties", "public.claim_assessments"],
        "feature_sources": ["incident history, amount, parties, fraud indicators"],
        "used_by_tabs": ["Claims 360", "AI Intelligence"],
        "used_by_roles": ["Claims Manager", "Executive Leadership"],
        "ai_sql_allowed": True,
        "demo_priority": "MEDIUM",
        "limitation_notes": "Use only if claim feature tables exist.",
        "registry_status": "PARTIAL",
        "missing_data_points": ["claim feature tables may be incomplete"],
    },
    {
        "model_name": "fraud_risk",
        "model_type": "classification",
        "entity_type": "claim",
        "business_purpose": "Flag fraud indicators for investigation.",
        "score_table": "public.model_scores",
        "score_column": "score_value",
        "score_interpretation": "Higher values indicate higher fraud risk.",
        "required_source_tables": ["public.claims", "public.claim_fraud_indicators"],
        "feature_sources": ["fraud indicators, party relationships, claim timing"],
        "used_by_tabs": ["Claims 360", "AI Intelligence"],
        "used_by_roles": ["Claims Manager", "Executive Leadership"],
        "ai_sql_allowed": True,
        "demo_priority": "MEDIUM",
        "limitation_notes": "Only use validated fraud indicators.",
        "registry_status": "PARTIAL",
        "missing_data_points": ["fraud indicators table may be partial or empty"],
    },
    {
        "model_name": "next_best_action",
        "model_type": "ranking",
        "entity_type": "customer",
        "business_purpose": "Recommend the most appropriate action for a customer or policy.",
        "score_table": "public.next_best_actions",
        "score_column": "priority_score",
        "score_interpretation": "Higher values indicate higher action priority.",
        "required_source_tables": ["public.next_best_actions", "public.model_scores", "public.customers"],
        "feature_sources": ["score fusion, business rules, context retrieval"],
        "used_by_tabs": ["AI Intelligence", "Know Your Customer"],
        "used_by_roles": ["Insurance Agent", "Agency Manager", "Sales Director"],
        "ai_sql_allowed": True,
        "demo_priority": "HIGH",
        "limitation_notes": "Use as the action layer, not the raw score.",
        "registry_status": "ACTUAL",
        "missing_data_points": [],
    },
]


def connect(database_url: str):
    return psycopg.connect(database_url, row_factory=dict_row, autocommit=False)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_governance_tables(conn) -> None:
    ddl = """
    create extension if not exists pgcrypto;
    create extension if not exists vector;

    create table if not exists public.cld_table_registry (
      registry_id uuid primary key default gen_random_uuid(),
      schema_name text not null,
      table_name text not null,
      classification_label text not null,
      table_role text not null,
      business_domain text,
      authoritative_for_kpis jsonb not null default '[]'::jsonb,
      used_by_tabs jsonb not null default '[]'::jsonb,
      used_by_models jsonb not null default '[]'::jsonb,
      used_by_ai_sql boolean not null default false,
      used_by_context boolean not null default false,
      used_by_embeddings boolean not null default false,
      used_by_evidence_hub boolean not null default false,
      demo_required boolean not null default false,
      ai_sql_allowed boolean not null default false,
      context_allowed boolean not null default false,
      truncate_candidate boolean not null default false,
      truncate_risk_level text not null default 'LOW',
      recommendation text not null default 'REVIEW_REQUIRED',
      reason text not null default '',
      confidence_score numeric(5,4) not null default 0,
      row_count bigint,
      total_size_bytes bigint,
      index_size_bytes bigint,
      column_count integer,
      primary_key_columns jsonb not null default '[]'::jsonb,
      foreign_keys jsonb not null default '[]'::jsonb,
      has_vector_columns boolean not null default false,
      used_by_frontend boolean not null default false,
      used_by_backend boolean not null default false,
      used_by_demo boolean not null default false,
      used_by_ai_prompt boolean not null default false,
      risk_if_truncated text not null default 'UNKNOWN',
      manual_review_required boolean not null default true,
      status text,
      missing_data_points jsonb not null default '[]'::jsonb,
      fallback_formula jsonb not null default '[]'::jsonb,
      created_at timestamp with time zone not null default now(),
      updated_at timestamp with time zone not null default now(),
      unique(schema_name, table_name)
    );

    create table if not exists public.cld_kpi_registry (
      kpi_id uuid primary key default gen_random_uuid(),
      kpi_name text not null unique,
      business_definition text not null,
      formula text not null,
      business_domain text not null,
      grain text not null,
      authoritative_tables jsonb not null default '[]'::jsonb,
      required_columns jsonb not null default '[]'::jsonb,
      allowed_join_paths jsonb not null default '[]'::jsonb,
      used_by_tabs jsonb not null default '[]'::jsonb,
      used_by_roles jsonb not null default '[]'::jsonb,
      sql_generation_notes text not null default '',
      demo_priority text not null default 'MEDIUM',
      status text not null default 'ACTUAL',
      missing_data_points jsonb not null default '[]'::jsonb,
      fallback_formula text,
      created_at timestamp with time zone not null default now(),
      updated_at timestamp with time zone not null default now()
    );

    create table if not exists public.cld_model_registry (
      model_id uuid primary key default gen_random_uuid(),
      model_name text not null unique,
      model_type text not null,
      entity_type text not null,
      business_purpose text not null,
      score_table text not null,
      score_column text not null,
      score_interpretation text not null,
      required_source_tables jsonb not null default '[]'::jsonb,
      feature_sources jsonb not null default '[]'::jsonb,
      used_by_tabs jsonb not null default '[]'::jsonb,
      used_by_roles jsonb not null default '[]'::jsonb,
      ai_sql_allowed boolean not null default false,
      demo_priority text not null default 'MEDIUM',
      limitation_notes text not null default '',
      registry_status text not null default 'PLANNED',
      missing_data_points jsonb not null default '[]'::jsonb,
      created_at timestamp with time zone not null default now(),
      updated_at timestamp with time zone not null default now()
    );

    create table if not exists public.cld_context_registry (
      context_id uuid primary key default gen_random_uuid(),
      context_type text not null,
      title text not null,
      business_domain text not null,
      content text not null,
      related_tables jsonb not null default '[]'::jsonb,
      related_columns jsonb not null default '[]'::jsonb,
      related_kpis jsonb not null default '[]'::jsonb,
      related_models jsonb not null default '[]'::jsonb,
      sql_usable boolean not null default false,
      business_only boolean not null default true,
      demo_priority text not null default 'MEDIUM',
      embedding_status text not null default 'PENDING',
      embedding vector(768),
      embedding_model text,
      created_at timestamp with time zone not null default now(),
      updated_at timestamp with time zone not null default now()
    );

    create table if not exists public.cld_llm_skill_registry (
      skill_id uuid primary key default gen_random_uuid(),
      skill_name text not null unique,
      purpose text not null,
      instructions text not null,
      allowed_tables jsonb not null default '[]'::jsonb,
      allowed_kpis jsonb not null default '[]'::jsonb,
      allowed_models jsonb not null default '[]'::jsonb,
      created_at timestamp with time zone not null default now(),
      updated_at timestamp with time zone not null default now()
    );

    create table if not exists public.cld_sql_guardrail_rules (
      rule_id uuid primary key default gen_random_uuid(),
      rule_name text not null unique,
      severity text not null default 'HIGH',
      applies_to text not null default 'text_to_sql',
      rule_text text not null,
      enabled boolean not null default true,
      created_at timestamp with time zone not null default now(),
      updated_at timestamp with time zone not null default now()
    );

    create table if not exists public.cld_table_cleanup_report (
      report_id uuid primary key default gen_random_uuid(),
      generated_at timestamp with time zone not null default now(),
      total_tables integer not null default 0,
      active_tables integer not null default 0,
      truncate_candidates integer not null default 0,
      report_json jsonb not null default '{}'::jsonb,
      created_at timestamp with time zone not null default now()
    );
    """
    with conn.cursor() as cur:
        cur.execute(ddl)
    conn.commit()


def cursor_dict(conn):
    try:
        return conn.cursor(row_factory=dict_row)
    except TypeError:
        return conn.cursor()


def fetch_table_catalog(conn, allowed_schemas: set[str]) -> list[dict[str, Any]]:
    with cursor_dict(conn) as cur:
        cur.execute(
            """
            select
              n.nspname as schema_name,
              c.relname as table_name,
              c.relkind as relkind,
              c.reltuples::bigint as row_count_estimate,
              coalesce(pg_total_relation_size(c.oid), 0) as total_size_bytes,
              coalesce(pg_indexes_size(c.oid), 0) as index_size_bytes
            from pg_class c
            join pg_namespace n on n.oid = c.relnamespace
            where n.nspname = any(%s)
              and c.relkind in ('r', 'p', 'v', 'm')
            order by n.nspname, c.relname
            """,
            (list(allowed_schemas),),
        )
        return [dict(row) for row in cur.fetchall()]


def fetch_column_count(conn, allowed_schemas: set[str]) -> dict[str, int]:
    with cursor_dict(conn) as cur:
        cur.execute(
            """
            select table_schema, table_name, count(*) as column_count
            from information_schema.columns
            where table_schema = any(%s)
            group by table_schema, table_name
            """,
            (list(allowed_schemas),),
        )
        return {f"{row['table_schema']}.{row['table_name']}": int(row["column_count"]) for row in cur.fetchall()}


def fetch_primary_keys(conn, allowed_schemas: set[str]) -> dict[str, list[str]]:
    with cursor_dict(conn) as cur:
        cur.execute(
            """
            select
              tc.table_schema,
              tc.table_name,
              array_agg(kcu.column_name order by kcu.ordinal_position) as pk_columns
            from information_schema.table_constraints tc
            join information_schema.key_column_usage kcu
              on tc.constraint_name = kcu.constraint_name
             and tc.table_schema = kcu.table_schema
             and tc.table_name = kcu.table_name
            where tc.constraint_type = 'PRIMARY KEY'
              and tc.table_schema = any(%s)
            group by tc.table_schema, tc.table_name
            """,
            (list(allowed_schemas),),
        )
        return {f"{row['table_schema']}.{row['table_name']}": list(row["pk_columns"] or []) for row in cur.fetchall()}


def fetch_foreign_keys(conn, allowed_schemas: set[str]) -> dict[str, list[dict[str, Any]]]:
    with cursor_dict(conn) as cur:
        cur.execute(
            """
            select
              tc.table_schema,
              tc.table_name,
              kcu.column_name,
              ccu.table_schema as foreign_table_schema,
              ccu.table_name as foreign_table_name,
              ccu.column_name as foreign_column_name,
              tc.constraint_name
            from information_schema.table_constraints tc
            join information_schema.key_column_usage kcu
              on tc.constraint_name = kcu.constraint_name
             and tc.table_schema = kcu.table_schema
            join information_schema.constraint_column_usage ccu
              on ccu.constraint_name = tc.constraint_name
            where tc.constraint_type = 'FOREIGN KEY'
              and tc.table_schema = any(%s)
            order by tc.table_schema, tc.table_name, kcu.ordinal_position
            """,
            (list(allowed_schemas),),
        )
        buckets: dict[str, list[dict[str, Any]]] = {}
        for row in cur.fetchall():
            key = f"{row['table_schema']}.{row['table_name']}"
            buckets.setdefault(key, []).append(
                {
                    "column_name": row["column_name"],
                    "foreign_table_schema": row["foreign_table_schema"],
                    "foreign_table_name": row["foreign_table_name"],
                    "foreign_column_name": row["foreign_column_name"],
                    "constraint_name": row["constraint_name"],
                }
            )
        return buckets


def fetch_vector_columns(conn, allowed_schemas: set[str]) -> set[str]:
    with cursor_dict(conn) as cur:
        cur.execute(
            """
            select table_schema, table_name, column_name
            from information_schema.columns
            where table_schema = any(%s)
              and data_type = 'USER-DEFINED'
              and udt_name = 'vector'
            """,
            (list(allowed_schemas),),
        )
        return {f"{row['table_schema']}.{row['table_name']}" for row in cur.fetchall()}


def fetch_table_usage_stats(conn, allowed_schemas: set[str]) -> dict[str, str | None]:
    with cursor_dict(conn) as cur:
        cur.execute(
            """
            select
              schemaname,
              relname,
              greatest(
                coalesce(last_analyze, to_timestamp(0)),
                coalesce(last_autoanalyze, to_timestamp(0)),
                coalesce(last_vacuum, to_timestamp(0)),
                coalesce(last_autovacuum, to_timestamp(0))
              ) as last_known_usage
            from pg_stat_user_tables
            where schemaname = any(%s)
            """,
            (list(allowed_schemas),),
        )
        return {
            f"{row['schemaname']}.{row['relname']}": (row["last_known_usage"].isoformat() if row["last_known_usage"] else None)
            for row in cur.fetchall()
        }


def scan_repo_references(root: Path, table_names: Iterable[str]) -> dict[str, TableSignal]:
    signals = {table: TableSignal() for table in table_names}
    wanted = sorted(set(table_names), key=len, reverse=True)
    patterns = {table: re.compile(rf"(?<![A-Za-z0-9_])(?:public\.)?{re.escape(table)}(?![A-Za-z0-9_])", re.IGNORECASE) for table in wanted}
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in EXCLUDED_DIR_PARTS for part in path.parts):
            continue
        if path.suffix.lower() not in CODE_FILE_EXTENSIONS:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        normalized_path = str(path).replace("\\", "/").lower()
        for table, pattern in patterns.items():
            if not pattern.search(text):
                continue
            signal = signals[table]
            signal.match_count += 1
            if len(signal.sample_matches) < 5:
                signal.sample_matches.append(normalized_path)
            if "/frontend/" in normalized_path:
                signal.used_by_frontend = True
            else:
                signal.used_by_backend = True
            if normalized_path.endswith((".sql", ".http")):
                signal.used_by_ai_sql = True
                signal.used_by_sql_examples = True
            if "/docs/" in normalized_path or "semantic" in normalized_path or "context" in normalized_path:
                signal.used_by_context = True
                signal.used_by_semantic_docs = True
            if "model" in normalized_path or "ml_" in normalized_path or "scoring" in normalized_path or "nba" in normalized_path:
                signal.used_by_models = True
            if "demo" in normalized_path:
                signal.used_by_demo = True
                signal.used_by_faq = True
    return signals


def infer_business_domain(schema_name: str, table_name: str) -> str:
    lowered = table_name.lower()
    if lowered == "parties":
        return "customer"
    if lowered in {"customers", "customer_complaints", "customer_engagement_events", "customer_nps", "customer_service_requests", "customer_behavior_daily", "customer_digital_events"}:
        return "customer"
    if lowered in {"policies", "policy_coverages", "policy_events", "policy_renewals", "policy_lapse_events", "quotes", "proposals", "applications", "underwriting_decisions"}:
        return "policy"
    if lowered in {"agents", "agent_movements", "agent_mapa_metrics", "agent_calls", "agent_meetings", "agent_targets", "agent_commissions", "agent_training", "agent_attrition_events"}:
        return "agent"
    if lowered in {"campaigns", "campaign_targets", "campaign_responses", "leads", "opportunities"}:
        return "campaign"
    if lowered in {"claims", "claim_parties", "claim_assessments", "claim_fraud_indicators"}:
        return "claims"
    if lowered in {"premiums", "payments"}:
        return "finance"
    if lowered in {"semantic_documents", "business_glossary", "cld_context_registry", "cld_kpi_registry", "cld_model_registry", "cld_table_registry", "cld_llm_skill_registry", "cld_sql_guardrail_rules"}:
        return "governance"
    if lowered in {"model_scores", "model_predictions", "next_best_actions", "model_features", "insight_lineage", "recommendation_evidence", "model_explanations", "context_usage_log"}:
        return "ml"
    if lowered.startswith("cld_"):
        return "governance"
    return "general"


def infer_table_role(table_name: str) -> str:
    lowered = table_name.lower()
    if lowered == "parties":
        return "authoritative_source"
    if lowered in {"customers", "agents", "policies", "campaigns", "claims", "products", "premiums", "payments", "leads", "opportunities"}:
        return "authoritative_source"
    if lowered.startswith(("model_", "next_best_", "propensity_", "lapse_", "churn_", "fraud_", "claims_", "customer_lifetime_value")):
        return "model_output"
    if lowered in {"semantic_documents", "business_glossary", "cld_context_registry", "cld_kpi_registry", "cld_model_registry", "cld_llm_skill_registry"}:
        return "semantic_context"
    if lowered in {"model_scores", "model_predictions", "next_best_actions", "insight_lineage", "recommendation_evidence", "model_explanations", "context_usage_log"}:
        return "evidence_log"
    if lowered in {"agent_mapa_metrics", "customer_engagement_events", "customer_behavior_daily", "customer_digital_events", "policy_events", "policy_renewals", "policy_lapse_events", "campaign_targets", "campaign_responses", "claim_assessments", "claim_fraud_indicators"}:
        return "analytical_feature"
    if lowered.startswith("cld_"):
        return "system_required"
    return "technical_log"


def classify_table(full_table_name: str, signal: TableSignal, has_vector_columns: bool) -> tuple[str, str, str, bool, bool]:
    table_name = full_table_name.split(".", 1)[1]
    is_temp = any(term in table_name.lower() for term in ["tmp", "temp", "test", "old", "backup", "sample", "scratch", "draft", "staging", "debug"])
    if full_table_name in {
        "public.semantic_documents",
        "public.business_glossary",
        "public.model_scores",
        "public.model_predictions",
        "public.next_best_actions",
        "public.insight_lineage",
        "public.recommendation_evidence",
        "public.model_explanations",
        "public.context_usage_log",
        "public.cld_context_registry",
        "public.cld_kpi_registry",
        "public.cld_model_registry",
        "public.cld_table_registry",
        "public.cld_llm_skill_registry",
        "public.cld_sql_guardrail_rules",
    }:
        classification = "ACT_SYSTEM_REQUIRED"
        recommendation = "KEEP_ACTIVE"
        truncate_candidate = False
        ai_sql_allowed = True
        context_allowed = True
        manual_review_required = False
        return classification, recommendation, "Core governance or ML control table required for demo and/or runtime.", truncate_candidate, manual_review_required

    if signal.used_by_frontend or signal.used_by_backend or signal.used_by_ai_sql or signal.used_by_context or signal.used_by_models or signal.used_by_demo:
        classification = infer_classification_from_role(full_table_name, signal, has_vector_columns)
        return classification, "KEEP_ACTIVE", build_reason(signal, full_table_name, "Referenced by app, SQL, or demo artifacts."), False, False

    if is_temp:
        return "TRUN_TEMP_TEST", "TRUNCATE_CANDIDATE", "Strong temp/test signal and no app references found.", True, True

    if has_vector_columns or "context" in table_name.lower() or "semantic" in table_name.lower():
        return "ACT_UNUSED_CONTEXT", "REVIEW_REQUIRED", "Context-like table with no proven app usage yet.", False, True

    return "ACT_REVIEW_REQUIRED", "REVIEW_REQUIRED", "No strong evidence for safe truncation; keep until manually reviewed.", False, True


def infer_classification_from_role(full_table_name: str, signal: TableSignal, has_vector_columns: bool) -> str:
    table_name = full_table_name.split(".", 1)[1]
    role = infer_table_role(table_name)
    if role == "authoritative_source":
        return "ACT_AUTHORITATIVE_SOURCE"
    if role == "model_output":
        return "ACT_MODEL_OUTPUT"
    if role == "semantic_context":
        return "ACT_SEMANTIC_CONTEXT"
    if role == "evidence_log":
        return "ACT_EVIDENCE_LOG"
    if has_vector_columns or signal.used_by_context:
        return "ACT_EMBEDDING_CONTEXT"
    if signal.used_by_models:
        return "ACT_ANALYTICAL_FEATURE"
    if signal.used_by_frontend or signal.used_by_backend:
        return "ACT_DEMO_REQUIRED"
    return "ACT_SYSTEM_REQUIRED"


def build_reason(signal: TableSignal, full_table_name: str, fallback: str) -> str:
    reasons = []
    if signal.used_by_frontend:
        reasons.append("Referenced by frontend")
    if signal.used_by_backend:
        reasons.append("Referenced by backend")
    if signal.used_by_ai_sql:
        reasons.append("Referenced by SQL examples")
    if signal.used_by_context:
        reasons.append("Referenced by semantic/context docs")
    if signal.used_by_models:
        reasons.append("Referenced by model context")
    if signal.used_by_demo:
        reasons.append("Referenced by demo catalog")
    if not reasons:
        reasons.append(fallback)
    return "; ".join(reasons)


def build_table_audit_rows(
    conn,
    *,
    allowed_schemas: set[str],
    repo_root: Path | None = None,
) -> list[TableAuditRow]:
    repo_root = repo_root or REPO_ROOT
    catalog = fetch_table_catalog(conn, allowed_schemas)
    counts = fetch_column_count(conn, allowed_schemas)
    pks = fetch_primary_keys(conn, allowed_schemas)
    fks = fetch_foreign_keys(conn, allowed_schemas)
    vector_tables = fetch_vector_columns(conn, allowed_schemas)
    last_usage = fetch_table_usage_stats(conn, allowed_schemas)
    signals = scan_repo_references(repo_root, [f"{row['schema_name']}.{row['table_name']}" for row in catalog])
    registry_rows = load_table_registry_rows(conn, allowed_schemas) if governance_registry_exists(conn) else []
    registry_lookup = {f"{row['schema_name']}.{row['table_name']}": row for row in registry_rows}

    output: list[TableAuditRow] = []
    for row in catalog:
        full_table_name = f"{row['schema_name']}.{row['table_name']}"
        signal = signals.get(full_table_name, TableSignal())
        classification, recommendation, reason, truncate_candidate, manual_review_required = classify_table(
            full_table_name, signal, full_table_name in vector_tables
        )
        table_role = infer_table_role(row["table_name"])
        ai_sql_allowed = classification.startswith("ACT_") and table_role != "technical_log"
        context_allowed = classification.startswith("ACT_") and (table_role in {"semantic_context", "authoritative_source", "model_output"} or full_table_name in vector_tables)
        if full_table_name in registry_lookup:
            ai_sql_allowed = bool(registry_lookup[full_table_name].get("ai_sql_allowed", ai_sql_allowed))
            context_allowed = bool(registry_lookup[full_table_name].get("context_allowed", context_allowed))
        if row["table_name"].lower() == "parties":
            ai_sql_allowed = True
            context_allowed = True
        output.append(
            TableAuditRow(
                schema_name=row["schema_name"],
                table_name=row["table_name"],
                full_table_name=full_table_name,
                table_type=row["relkind"],
                row_count=int(row["row_count_estimate"] or 0),
                total_size_bytes=int(row["total_size_bytes"] or 0),
                index_size_bytes=int(row["index_size_bytes"] or 0),
                column_count=int(counts.get(full_table_name, 0)),
                primary_key_columns=pks.get(full_table_name, []),
                foreign_keys=fks.get(full_table_name, []),
                last_known_usage=last_usage.get(full_table_name),
                has_vector_columns=full_table_name in vector_tables,
                used_by_frontend=signal.used_by_frontend,
                used_by_backend=signal.used_by_backend,
                used_by_ai_sql=signal.used_by_ai_sql,
                used_by_context=signal.used_by_context,
                used_by_models=signal.used_by_models,
                used_by_demo=signal.used_by_demo,
                used_by_sql_examples=signal.used_by_sql_examples,
                used_by_semantic_docs=signal.used_by_semantic_docs,
                used_by_faq=signal.used_by_faq,
                classification_label=classification,
                table_role=table_role,
                recommended_action=recommendation,
                reason=reason,
                confidence_score=confidence_score(signal, classification, recommendation, full_table_name),
                risk_if_truncated=risk_if_truncated(signal, classification),
                manual_review_required=manual_review_required,
                authoritative_for_kpis=authoritative_kpis_for_table(full_table_name),
                used_by_tabs=used_by_tabs_for_table(full_table_name, signal),
                used_by_models_list=used_by_models_for_table(full_table_name),
                ai_sql_allowed=ai_sql_allowed,
                context_allowed=context_allowed,
                truncate_candidate=truncate_candidate,
                truncate_risk_level=truncate_risk_level(signal, classification),
                status=classification.split("_", 1)[0],
                missing_data_points=missing_data_points_for_table(full_table_name),
                fallback_formula=fallback_formula_for_table(full_table_name),
            )
        )
    return output


def authoritative_kpis_for_table(full_table_name: str) -> list[str]:
    lookups = {
        "public.policies": ["Premium at Risk", "Lapse Rate", "Persistency Rate", "Quote-to-Bind Rate", "Product Sales Decline"],
        "public.campaigns": ["Campaign Conversion Rate", "Campaign ROI"],
        "public.campaign_targets": ["Campaign Conversion Rate"],
        "public.campaign_responses": ["Campaign Conversion Rate", "Campaign ROI"],
        "public.leads": ["Lead Conversion Rate"],
        "public.opportunities": ["Lead Conversion Rate"],
        "public.agents": ["Agent Conversion Rate", "Agent Coaching Need"],
        "public.agent_mapa_metrics": ["MAPA Productivity", "Agent Conversion Rate", "Agent Coaching Need"],
        "public.claims": ["Claims Ratio", "Loss Ratio"],
        "public.premiums": ["Claims Ratio", "Loss Ratio"],
        "public.customers": ["Customer Lifetime Value", "Propensity Score", "Churn Risk"],
        "public.model_scores": ["Propensity Score", "Churn Risk", "Customer Lifetime Value", "Premium at Risk", "Agent Coaching Need"],
        "public.next_best_actions": ["Revenue Opportunity"],
        "public.semantic_documents": [],
        "public.business_glossary": [],
        "public.cld_kpi_registry": [],
        "public.cld_model_registry": [],
        "public.cld_context_registry": [],
    }
    return lookups.get(full_table_name, [])


def used_by_tabs_for_table(full_table_name: str, signal: TableSignal) -> list[str]:
    lookups = {
        "public.policies": ["Policy Lapse Risk", "Know Your Customer", "Agent Performance Tracking"],
        "public.customers": ["Know Your Customer", "AI Intelligence"],
        "public.agents": ["Know Your Agent", "Agent Performance Tracking"],
        "public.campaigns": ["Campaign Effectiveness"],
        "public.campaign_targets": ["Campaign Effectiveness"],
        "public.campaign_responses": ["Campaign Effectiveness"],
        "public.leads": ["Campaign Effectiveness", "Agent Performance Tracking"],
        "public.opportunities": ["Campaign Effectiveness", "AI Intelligence"],
        "public.claims": ["Claims 360"],
        "public.model_scores": ["AI Intelligence", "Know Your Customer", "Know Your Agent"],
        "public.model_predictions": ["AI Intelligence", "Know Your Customer"],
        "public.next_best_actions": ["AI Intelligence", "Know Your Customer", "Know Your Agent"],
        "public.semantic_documents": ["AI Intelligence"],
        "public.business_glossary": ["AI Intelligence"],
        "public.cld_table_registry": ["AI Intelligence"],
        "public.cld_kpi_registry": ["AI Intelligence"],
        "public.cld_model_registry": ["AI Intelligence"],
        "public.cld_context_registry": ["AI Intelligence"],
    }
    if signal.used_by_frontend:
        return lookups.get(full_table_name, []) + ["Frontend Demo"]
    return lookups.get(full_table_name, [])


def used_by_models_for_table(full_table_name: str) -> list[str]:
    lookups = {
        "public.policies": ["policy_lapse_risk", "customer_lifetime_value", "next_best_product"],
        "public.customers": ["propensity_to_buy", "customer_churn_risk", "customer_lifetime_value"],
        "public.agents": ["agent_performance", "agent_attrition"],
        "public.agent_mapa_metrics": ["agent_performance", "agent_attrition"],
        "public.campaigns": ["campaign_response"],
        "public.campaign_targets": ["campaign_response"],
        "public.campaign_responses": ["campaign_response"],
        "public.leads": ["lead_conversion"],
        "public.claims": ["claims_risk", "fraud_risk"],
        "public.model_scores": ["policy_lapse_risk", "propensity_to_buy", "customer_churn_risk", "customer_lifetime_value", "agent_performance", "campaign_response", "lead_conversion", "claims_risk", "fraud_risk", "next_best_action"],
        "public.model_predictions": ["next_best_product"],
        "public.next_best_actions": ["next_best_action"],
    }
    return lookups.get(full_table_name, [])


def missing_data_points_for_table(full_table_name: str) -> list[str]:
    return []


def fallback_formula_for_table(full_table_name: str) -> list[str]:
    return []


def build_kpi_registry_rows(existing_tables: set[str], active_tables: set[str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in KPI_DEFINITIONS:
        tables = list(dict.fromkeys([table for table in item["authoritative_tables"] if table in existing_tables and table in active_tables]))
        missing = [table for table in item["authoritative_tables"] if table not in existing_tables]
        status = item.get("status", "ACTUAL")
        if missing and not tables:
            status = "PARTIAL"
        elif len(tables) != len(item["authoritative_tables"]):
            status = "PARTIAL"
        rows.append(
            {
                "kpi_id": str(uuid4()),
                "kpi_name": item["kpi_name"],
                "business_definition": item["business_definition"],
                "formula": item["formula"],
                "business_domain": item["business_domain"],
                "grain": item["grain"],
                "authoritative_tables": tables,
                "required_columns": item["required_columns"],
                "allowed_join_paths": item["allowed_join_paths"],
                "used_by_tabs": item["used_by_tabs"],
                "used_by_roles": item["used_by_roles"],
                "sql_generation_notes": item["sql_generation_notes"],
                "demo_priority": item["demo_priority"],
                "status": status,
                "missing_data_points": missing if missing else item.get("missing_data_points", []),
                "fallback_formula": item.get("fallback_formula") or "",
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
            }
        )
    return rows


def build_model_registry_rows(existing_tables: set[str], active_tables: set[str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in MODEL_DEFINITIONS:
        required = [table for table in item["required_source_tables"] if table in existing_tables and table in active_tables]
        missing = [table for table in item["required_source_tables"] if table not in existing_tables]
        score_table_exists = item["score_table"] in existing_tables
        registry_status = item.get("registry_status", "PLANNED")
        required_all_available = len(required) == len(item["required_source_tables"])
        score_table_allowed = item["score_table"] in active_tables
        ai_sql_allowed = bool(item.get("ai_sql_allowed", False) and score_table_exists and score_table_allowed and required_all_available)
        if not score_table_exists:
            registry_status = "PLANNED"
        elif missing or not required_all_available or item["score_table"] not in active_tables:
            registry_status = "PARTIAL"
        else:
            registry_status = "ACTUAL"
        rows.append(
            {
                "model_id": str(uuid4()),
                "model_name": item["model_name"],
                "model_type": item["model_type"],
                "entity_type": item["entity_type"],
                "business_purpose": item["business_purpose"],
                "score_table": item["score_table"],
                "score_column": item["score_column"],
                "score_interpretation": item["score_interpretation"],
                "required_source_tables": required,
                "feature_sources": item["feature_sources"],
                "used_by_tabs": item["used_by_tabs"],
                "used_by_roles": item["used_by_roles"],
                "ai_sql_allowed": ai_sql_allowed,
                "demo_priority": item["demo_priority"],
                "limitation_notes": item["limitation_notes"],
                "registry_status": registry_status,
                "missing_data_points": missing if missing else item.get("missing_data_points", []),
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
            }
        )
    return rows


def build_guardrail_rows() -> list[dict[str, Any]]:
    return [
        {
            "rule_id": str(uuid4()),
            "rule_name": "allowlisted_select_only",
            "severity": "HIGH",
            "applies_to": "text_to_sql",
            "rule_text": "Generate only SELECT or WITH queries and restrict references to ACT tables with ai_sql_allowed=true.",
            "enabled": True,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        },
        {
            "rule_id": str(uuid4()),
            "rule_name": "no_planned_tables",
            "severity": "HIGH",
            "applies_to": "text_to_sql",
            "rule_text": "Do not use planned-only or TRUN tables in SQL generation.",
            "enabled": True,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        },
    ]


def confidence_score(signal: TableSignal, classification: str, recommendation: str, full_table_name: str) -> float:
    score = 0.55
    if signal.used_by_frontend:
        score += 0.15
    if signal.used_by_backend:
        score += 0.10
    if signal.used_by_ai_sql:
        score += 0.10
    if signal.used_by_context or signal.used_by_models:
        score += 0.05
    if classification.startswith("ACT_SYSTEM_REQUIRED"):
        score += 0.10
    if recommendation == "TRUNCATE_CANDIDATE":
        score = 0.90 if any(term in full_table_name.lower() for term in ["tmp", "temp", "test", "old"]) else 0.70
    return round(min(0.99, score), 4)


def risk_if_truncated(signal: TableSignal, classification: str) -> str:
    if signal.used_by_frontend or signal.used_by_backend or signal.used_by_ai_sql or signal.used_by_context or signal.used_by_models or signal.used_by_demo:
        return "HIGH"
    if classification.startswith("ACT_"):
        return "MEDIUM"
    return "LOW"


def truncate_risk_level(signal: TableSignal, classification: str) -> str:
    risk = risk_if_truncated(signal, classification)
    return risk


def load_kpi_rows(conn, allowed_schemas: set[str]) -> list[dict[str, Any]]:
    if not has_table(conn, "public", "cld_kpi_registry"):
        return []
    with cursor_dict(conn) as cur:
        cur.execute("select * from public.cld_kpi_registry order by kpi_name")
        return [dict(row) for row in cur.fetchall()]


def load_model_rows(conn, allowed_schemas: set[str]) -> list[dict[str, Any]]:
    if not has_table(conn, "public", "cld_model_registry"):
        return []
    with cursor_dict(conn) as cur:
        cur.execute("select * from public.cld_model_registry order by model_name")
        return [dict(row) for row in cur.fetchall()]


def load_context_rows(conn, allowed_schemas: set[str]) -> list[dict[str, Any]]:
    if not has_table(conn, "public", "cld_context_registry"):
        return []
    with cursor_dict(conn) as cur:
        cur.execute("select * from public.cld_context_registry order by context_type, title")
        return [dict(row) for row in cur.fetchall()]


def load_guardrail_rows(conn) -> list[dict[str, Any]]:
    if not has_table(conn, "public", "cld_sql_guardrail_rules"):
        return []
    with cursor_dict(conn) as cur:
        cur.execute("select * from public.cld_sql_guardrail_rules order by rule_name")
        return [dict(row) for row in cur.fetchall()]


def ensure_doc_dirs() -> None:
    GOVERNANCE_DIR.mkdir(parents=True, exist_ok=True)
    LLM_HARNESS_DIR.mkdir(parents=True, exist_ok=True)
    CONTEXT_DIR.mkdir(parents=True, exist_ok=True)


def json_dump(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")


def csv_dump(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key) for key in fieldnames})


def markdown_table(headers: list[str], rows: list[list[Any]]) -> str:
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |"]
    for row in rows:
        lines.append("| " + " | ".join(str(item).replace("|", "/") for item in row) + " |")
    return "\n".join(lines)
