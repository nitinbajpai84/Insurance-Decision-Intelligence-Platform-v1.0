#!/usr/bin/env python3
"""
Generate synthetic Singapore/Hong Kong insurance analytics data for the MVP schema.

The product and campaign catalogue is inspired by public Prudential Singapore and
Prudential Hong Kong product/campaign themes, but every customer, policy, agent,
lead, response, claim, and transaction produced by this script is fictional.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import random
import uuid
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

from faker import Faker


SINGAPORE_DISTRICTS = [
    ("Central", "01", "Singapore", "SG", "018956"),
    ("Orchard", "09", "Singapore", "SG", "238879"),
    ("Novena", "11", "Singapore", "SG", "307591"),
    ("Toa Payoh", "12", "Singapore", "SG", "319191"),
    ("Queenstown", "03", "Singapore", "SG", "149053"),
    ("Tampines", "18", "Singapore", "SG", "529538"),
    ("Bedok", "16", "Singapore", "SG", "469659"),
    ("Jurong East", "22", "Singapore", "SG", "609601"),
    ("Woodlands", "25", "Singapore", "SG", "738099"),
    ("Punggol", "19", "Singapore", "SG", "828761"),
]

HONG_KONG_DISTRICTS = [
    ("Central and Western", "HK-CW", "Hong Kong", "HK", "000000"),
    ("Wan Chai", "HK-WC", "Hong Kong", "HK", "000000"),
    ("Eastern", "HK-EA", "Hong Kong", "HK", "000000"),
    ("Yau Tsim Mong", "HK-YT", "Kowloon", "HK", "000000"),
    ("Kowloon City", "HK-KC", "Kowloon", "HK", "000000"),
    ("Sha Tin", "HK-ST", "New Territories", "HK", "000000"),
    ("Tsuen Wan", "HK-TW", "New Territories", "HK", "000000"),
    ("Tuen Mun", "HK-TM", "New Territories", "HK", "000000"),
    ("Sai Kung", "HK-SK", "New Territories", "HK", "000000"),
    ("Islands", "HK-IS", "New Territories", "HK", "000000"),
]

CUSTOMER_SEGMENTS = [
    ("young_professional", 0.20),
    ("family_protection", 0.25),
    ("affluent_wealth", 0.15),
    ("retirement_planner", 0.15),
    ("health_focused", 0.15),
    ("sme_owner", 0.10),
]

PRODUCTS = [
    {
        "code": "SG-PRUSHIELD-PREMIER",
        "name": "PRUShield Premier (SG synthetic)",
        "lob": "health",
        "family": "integrated_shield",
        "market": "SG",
        "premium_mu": 2400,
        "premium_sigma": 0.35,
        "claim_rate": 0.095,
        "coverage": "Hospital and surgical protection",
    },
    {
        "code": "SG-PRUACTIVE-LIFE-V",
        "name": "PRUActive Life V (SG synthetic)",
        "lob": "life",
        "family": "whole_life",
        "market": "SG",
        "premium_mu": 5200,
        "premium_sigma": 0.42,
        "claim_rate": 0.012,
        "coverage": "Whole life and critical illness protection",
    },
    {
        "code": "SG-PRUACTIVE-CASH",
        "name": "PRUActive Cash (SG synthetic)",
        "lob": "savings",
        "family": "participating_savings",
        "market": "SG",
        "premium_mu": 4100,
        "premium_sigma": 0.38,
        "claim_rate": 0.006,
        "coverage": "Savings plan with yearly cash benefit",
    },
    {
        "code": "SG-PRULINK-INVESTGROWTH",
        "name": "PRULink InvestGrowth (SG synthetic)",
        "lob": "investment_linked",
        "family": "investment_linked",
        "market": "SG",
        "premium_mu": 6200,
        "premium_sigma": 0.50,
        "claim_rate": 0.010,
        "coverage": "Investment-linked life protection",
    },
    {
        "code": "HK-PRUCANCER-360",
        "name": "PRUCancer 360 (HK synthetic)",
        "lob": "critical_illness",
        "family": "cancer_protection",
        "market": "HK",
        "premium_mu": 14500,
        "premium_sigma": 0.40,
        "claim_rate": 0.030,
        "coverage": "Cancer lump-sum and early-stage cancer benefit",
    },
    {
        "code": "HK-PRUHEALTH-VHIS-VIP",
        "name": "PRUHealth VHIS VIP Plan (HK synthetic)",
        "lob": "health",
        "family": "vhis_medical",
        "market": "HK",
        "premium_mu": 18000,
        "premium_sigma": 0.45,
        "claim_rate": 0.105,
        "coverage": "VHIS certified medical protection",
    },
    {
        "code": "HK-PRUHEALTH-GUARDIAN-CI",
        "name": "PRUHealth Guardian Critical Illness Plan (HK synthetic)",
        "lob": "critical_illness",
        "family": "critical_illness",
        "market": "HK",
        "premium_mu": 21000,
        "premium_sigma": 0.48,
        "claim_rate": 0.024,
        "coverage": "Critical illness protection",
    },
    {
        "code": "HK-PRULIFE-PROTECTOR-II",
        "name": "PRULife Protector II (HK synthetic)",
        "lob": "life",
        "family": "life_protection",
        "market": "HK",
        "premium_mu": 26000,
        "premium_sigma": 0.48,
        "claim_rate": 0.014,
        "coverage": "Life protection with optional riders",
    },
    {
        "code": "HK-EVERGREEN-WEALTH-MC",
        "name": "Evergreen Wealth Multi-Currency Plan (HK synthetic)",
        "lob": "wealth",
        "family": "multi_currency_savings",
        "market": "HK",
        "premium_mu": 42000,
        "premium_sigma": 0.55,
        "claim_rate": 0.004,
        "coverage": "Multi-currency wealth and legacy planning",
    },
]

RIDERS_BY_BASE_PRODUCT = {
    "SG-PRUSHIELD-PREMIER": [
        ("SG-PRUEXTRA-PLUS-RIDER", "PRUExtra Plus Rider (SG synthetic)", "medical_rider", "hospital_cash", 0.24, 0.58),
        ("SG-PRUSHIELD-DAILY-CASH", "Daily Hospital Cash Rider (SG synthetic)", "medical_rider", "hospital_cash", 0.08, 0.25),
        ("SG-PRUSHIELD-OUTPATIENT", "Outpatient Specialist Rider (SG synthetic)", "medical_rider", "outpatient", 0.12, 0.32),
    ],
    "SG-PRUACTIVE-LIFE-V": [
        ("SG-PRUCI-EARLYCARE", "Early Critical Illness Rider (SG synthetic)", "critical_illness_rider", "early_ci", 0.22, 0.52),
        ("SG-PRUPAY-WAIVER", "Premium Waiver Rider (SG synthetic)", "waiver_rider", "premium_waiver", 0.07, 0.34),
        ("SG-PRUTERM-BOOSTER", "Term Protection Booster Rider (SG synthetic)", "term_rider", "term_booster", 0.16, 0.30),
    ],
    "SG-PRUACTIVE-CASH": [
        ("SG-SAVER-WAIVER", "Savings Premium Waiver Rider (SG synthetic)", "waiver_rider", "premium_waiver", 0.05, 0.24),
        ("SG-ACCIDENT-INCOME", "Accident Income Rider (SG synthetic)", "accident_rider", "accident_income", 0.10, 0.22),
    ],
    "SG-PRULINK-INVESTGROWTH": [
        ("SG-ILP-TERM-RIDER", "Investment Term Protection Rider (SG synthetic)", "term_rider", "term_booster", 0.12, 0.28),
        ("SG-ILP-CRISIS-COVER", "Crisis Cover Rider (SG synthetic)", "critical_illness_rider", "critical_illness", 0.18, 0.35),
    ],
    "HK-PRUCANCER-360": [
        ("HK-CANCER-RECOVERY-RIDER", "Cancer Recovery Income Rider (HK synthetic)", "cancer_rider", "cancer_recovery", 0.20, 0.50),
        ("HK-CANCER-CAREPLUS-RIDER", "Cancer CarePlus Rider (HK synthetic)", "cancer_rider", "cancer_care", 0.15, 0.42),
    ],
    "HK-PRUHEALTH-VHIS-VIP": [
        ("HK-VHIS-DEDUCTIBLE-SAVER", "VHIS Deductible Saver Rider (HK synthetic)", "medical_rider", "deductible_saver", 0.10, 0.36),
        ("HK-VHIS-OUTPATIENT-PLUS", "VHIS Outpatient Plus Rider (HK synthetic)", "medical_rider", "outpatient", 0.18, 0.44),
        ("HK-VHIS-HOSPITAL-CASH", "VHIS Hospital Cash Rider (HK synthetic)", "medical_rider", "hospital_cash", 0.08, 0.28),
    ],
    "HK-PRUHEALTH-GUARDIAN-CI": [
        ("HK-CI-MULTIPAY-RIDER", "MultiPay Critical Illness Rider (HK synthetic)", "critical_illness_rider", "multipay_ci", 0.26, 0.48),
        ("HK-CI-WAIVER-RIDER", "Critical Illness Premium Waiver Rider (HK synthetic)", "waiver_rider", "premium_waiver", 0.06, 0.30),
    ],
    "HK-PRULIFE-PROTECTOR-II": [
        ("HK-LIFE-ACCIDENT-RIDER", "Accident Protection Rider (HK synthetic)", "accident_rider", "accident", 0.12, 0.34),
        ("HK-LIFE-TERM-PLUS", "Term Plus Rider (HK synthetic)", "term_rider", "term_booster", 0.17, 0.35),
        ("HK-LIFE-WAIVER-RIDER", "Life Premium Waiver Rider (HK synthetic)", "waiver_rider", "premium_waiver", 0.06, 0.28),
    ],
    "HK-EVERGREEN-WEALTH-MC": [
        ("HK-WEALTH-LTC-RIDER", "Long Term Care Rider (HK synthetic)", "care_rider", "long_term_care", 0.09, 0.20),
        ("HK-WEALTH-LEGACY-RIDER", "Legacy Continuity Rider (HK synthetic)", "legacy_rider", "legacy", 0.07, 0.18),
    ],
}

CAMPAIGN_ARCHETYPES = [
    ("Every Body Club wellness journey", "wellness", "health", "SG", ["web", "app", "social", "email"], 1.25),
    ("Health gap years protection", "health_protection", "life", "SG", ["email", "agent_call", "sms"], 1.20),
    ("PRUShield annual review", "medical_review", "health", "SG", ["email", "app", "agent_call"], 1.10),
    ("PRUActive Cash savings reset", "savings", "savings", "SG", ["email", "direct_mail", "agent_call"], 0.95),
    ("PRULink wealth confidence", "wealth", "investment_linked", "SG", ["agent_call", "web", "email"], 0.90),
    ("PruNextGen family future", "family", "life", "HK", ["email", "web", "social", "partner"], 1.15),
    ("PruLivingHK newcomer privileges", "newcomer", "health", "HK", ["web", "social", "partner", "email"], 1.05),
    ("PRUCancer 360 awareness", "cancer_awareness", "critical_illness", "HK", ["email", "sms", "agent_call"], 1.30),
    ("VHIS medical upgrade", "medical_review", "health", "HK", ["email", "agent_call", "app"], 1.18),
    ("Paid-up maturity appreciation", "maturity_appreciation", "wealth", "HK", ["direct_mail", "agent_call", "email"], 1.00),
]


@dataclass
class CsvWriter:
    path: Path
    fieldnames: list[str]

    def __post_init__(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.file = self.path.open("w", newline="", encoding="utf-8")
        self.writer = csv.DictWriter(self.file, fieldnames=self.fieldnames, extrasaction="ignore")
        self.writer.writeheader()
        self.count = 0

    def write(self, row: dict) -> None:
        self.writer.writerow({key: csv_value(row.get(key)) for key in self.fieldnames})
        self.count += 1

    def close(self) -> None:
        self.file.close()


def csv_value(value):
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, list):
        escaped = [str(item).replace('"', '\\"') for item in value]
        return "{" + ",".join(f'"{item}"' for item in escaped) + "}"
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return value


def new_id() -> str:
    return str(uuid.uuid4())


def now_ts() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def dt(day: date, hour: int | None = None) -> datetime:
    selected_hour = random.randint(8, 20) if hour is None else hour
    return datetime.combine(day, time(selected_hour, random.randint(0, 59), random.randint(0, 59)), timezone.utc)


def weighted_choice(weighted_items):
    total = sum(weight for _, weight in weighted_items)
    pick = random.random() * total
    upto = 0
    for item, weight in weighted_items:
        upto += weight
        if upto >= pick:
            return item
    return weighted_items[-1][0]


def random_day(start: date, end: date, seasonal: bool = False) -> date:
    days = (end - start).days
    if days <= 0:
        return start
    if not seasonal:
        return start + timedelta(days=random.randint(0, days))

    # Insurance demand is slightly heavier around Jan/Apr/Jun/Sep/Nov campaign cycles.
    month_weights = {
        1: 1.25,
        2: 0.85,
        3: 0.95,
        4: 1.15,
        5: 0.95,
        6: 1.20,
        7: 1.00,
        8: 0.95,
        9: 1.25,
        10: 1.05,
        11: 1.30,
        12: 1.10,
    }
    for _ in range(100):
        candidate = start + timedelta(days=random.randint(0, days))
        if random.random() < month_weights[candidate.month] / 1.30:
            return candidate
    return start + timedelta(days=random.randint(0, days))


def add_days(base: date, min_days: int, max_days: int) -> date:
    return base + timedelta(days=random.randint(min_days, max_days))


def money(amount: float) -> str:
    return f"{max(amount, 0):.2f}"


def signed_money(amount: float) -> str:
    return f"{amount:.2f}"


def lognormal_around(mean: float, sigma: float) -> float:
    return random.lognormvariate(math.log(mean), sigma)


def fake_embedding(dim: int = 1536) -> str:
    # Compact deterministic-looking vector literal. Values are tiny because they are placeholders.
    values = [f"{random.uniform(-0.05, 0.05):.6f}" for _ in range(dim)]
    return "[" + ",".join(values) + "]"


def make_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def create_writers(output_dir: Path) -> dict[str, CsvWriter]:
    specs = {
        "parties": ["party_id", "party_type", "display_name", "first_name", "middle_name", "last_name", "organization_name", "date_of_birth", "tax_id_last4", "email", "phone", "preferred_contact_method", "created_at", "updated_at"],
        "customers": ["customer_id", "party_id", "customer_number", "customer_segment", "lifecycle_stage", "acquisition_date", "risk_tier", "engagement_score", "household_party_id", "created_at", "updated_at"],
        "addresses": ["address_id", "party_id", "address_type", "line1", "line2", "city", "state_code", "postal_code", "country_code", "latitude", "longitude", "is_current", "effective_date", "expiration_date", "created_at", "updated_at"],
        "agents": ["agent_id", "party_id", "agent_number", "agency_party_id", "license_state", "license_number", "channel", "territory_code", "appointment_date", "termination_date", "status", "created_at", "updated_at"],
        "agent_movements": ["agent_movement_id", "agent_id", "movement_type", "from_agency_party_id", "to_agency_party_id", "from_territory_code", "to_territory_code", "effective_date", "end_date", "reason", "created_at", "updated_at"],
        "agent_mapa_metrics": ["agent_mapa_metric_id", "agent_id", "metric_month", "leads_count", "contacts_count", "quotes_count", "applications_count", "policies_bound_count", "new_business_premium", "renewal_premium", "retained_policy_count", "lapsed_policy_count", "claims_count", "loss_ratio", "created_at", "updated_at"],
        "products": ["product_id", "parent_product_id", "product_code", "product_name", "line_of_business", "product_family", "product_component_type", "rider_category", "product_version", "effective_date", "expiration_date", "active_flag", "created_at", "updated_at"],
        "campaigns": ["campaign_id", "campaign_code", "campaign_name", "campaign_type", "channel", "objective", "target_line_of_business", "start_date", "end_date", "budget_amount", "status", "created_at", "updated_at"],
        "leads": ["lead_id", "lead_number", "party_id", "customer_id", "campaign_id", "assigned_agent_id", "product_id", "lead_source", "lead_status", "received_at", "qualified_at", "score", "created_at", "updated_at"],
        "opportunities": ["opportunity_id", "opportunity_number", "lead_id", "customer_id", "agent_id", "campaign_id", "product_id", "opportunity_stage", "opened_date", "close_date", "estimated_premium", "quoted_premium", "lost_reason", "created_at", "updated_at"],
        "policies": ["policy_id", "policy_number", "customer_id", "agent_id", "product_id", "opportunity_id", "prior_policy_id", "policy_status", "effective_date", "expiration_date", "issue_date", "cancellation_date", "source_channel", "payment_plan", "annual_premium", "written_premium", "created_at", "updated_at"],
        "policy_coverages": ["policy_coverage_id", "policy_id", "product_id", "coverage_code", "coverage_name", "coverage_status", "is_rider", "rider_tag", "limit_amount", "deductible_amount", "exposure_basis", "exposure_value", "effective_date", "expiration_date", "created_at", "updated_at"],
        "premiums": ["premium_id", "policy_id", "policy_coverage_id", "premium_period_start", "premium_period_end", "transaction_date", "transaction_type", "written_premium_amount", "earned_premium_amount", "tax_fee_amount", "created_at", "updated_at"],
        "payments": ["payment_id", "policy_id", "customer_id", "payment_date", "due_date", "payment_status", "payment_method", "billed_amount", "paid_amount", "created_at", "updated_at"],
        "claims": ["claim_id", "claim_number", "policy_id", "customer_id", "policy_coverage_id", "assigned_agent_id", "loss_date", "report_date", "close_date", "claim_status", "loss_cause", "loss_description", "paid_amount", "reserve_amount", "litigation_flag", "catastrophe_flag", "created_at", "updated_at"],
        "campaign_targets": ["campaign_target_id", "campaign_id", "customer_id", "lead_id", "agent_id", "target_status", "selected_at", "suppression_reason", "created_at", "updated_at"],
        "campaign_responses": ["campaign_response_id", "campaign_id", "campaign_target_id", "customer_id", "lead_id", "opportunity_id", "policy_id", "response_ts", "response_type", "conversion_flag", "conversion_premium", "created_at", "updated_at"],
        "customer_engagement_events": ["customer_engagement_event_id", "customer_id", "policy_id", "claim_id", "campaign_id", "agent_id", "event_ts", "event_type", "channel", "sentiment_score", "duration_seconds", "metadata", "created_at", "updated_at"],
        "business_glossary": ["glossary_id", "term", "domain", "definition", "calculation_sql", "synonyms", "owner", "active_flag", "created_at", "updated_at"],
        "semantic_documents": ["semantic_document_id", "glossary_id", "document_type", "source_schema", "source_table", "source_column", "title", "content", "tags", "content_hash", "embedding_model", "embedding", "active_flag", "created_at", "updated_at"],
        "query_audit_log": ["query_audit_log_id", "user_id", "session_id", "question", "retrieved_semantic_document_ids", "generated_sql", "execution_status", "safety_decision", "error_message", "row_count", "duration_ms", "feedback_rating", "created_at", "updated_at"],
        "customer_behavior_daily": ["customer_behavior_daily_id", "customer_id", "behavior_date", "active_policy_count", "open_claim_count", "payment_missed_count_90d", "digital_event_count", "service_request_count", "complaint_count", "campaign_touch_count", "quote_count_90d", "engagement_score", "churn_signal_score", "feature_snapshot", "created_at", "updated_at"],
        "customer_digital_events": ["customer_digital_event_id", "customer_id", "party_id", "policy_id", "campaign_id", "event_ts", "session_id", "device_type", "channel", "event_name", "event_category", "page_name", "product_id", "dwell_seconds", "metadata", "created_at", "updated_at"],
        "customer_complaints": ["customer_complaint_id", "customer_id", "policy_id", "claim_id", "agent_id", "complaint_date", "complaint_channel", "complaint_category", "severity", "status", "resolution_date", "resolution_days", "sentiment_score", "complaint_text", "created_at", "updated_at"],
        "customer_satisfaction_surveys": ["customer_satisfaction_survey_id", "customer_id", "policy_id", "claim_id", "agent_id", "survey_date", "survey_type", "channel", "satisfaction_score", "effort_score", "response_text", "created_at", "updated_at"],
        "customer_nps": ["customer_nps_id", "customer_id", "survey_date", "touchpoint", "nps_score", "comment_text", "created_at", "updated_at"],
        "customer_service_requests": ["customer_service_request_id", "customer_id", "policy_id", "claim_id", "assigned_agent_id", "request_ts", "request_type", "channel", "priority", "status", "first_response_ts", "resolved_ts", "sla_breached", "service_summary", "created_at", "updated_at"],
        "policy_events": ["policy_event_id", "policy_id", "customer_id", "agent_id", "event_ts", "event_type", "event_reason", "source_system", "old_status", "new_status", "premium_delta", "event_payload", "created_at", "updated_at"],
        "policy_renewals": ["policy_renewal_id", "policy_id", "prior_policy_id", "renewal_policy_id", "customer_id", "agent_id", "renewal_cycle_date", "renewal_offer_date", "renewal_due_date", "renewal_status", "offered_premium", "expiring_premium", "premium_change_pct", "retention_reason", "created_at", "updated_at"],
        "policy_lapse_events": ["policy_lapse_event_id", "policy_id", "customer_id", "agent_id", "lapse_event_date", "lapse_stage", "missed_payment_count", "days_past_due", "reinstatement_date", "lapse_reason", "intervention_type", "created_at", "updated_at"],
        "quotes": ["quote_id", "quote_number", "lead_id", "opportunity_id", "customer_id", "agent_id", "product_id", "campaign_id", "quote_date", "quote_status", "quoted_premium", "sum_assured", "quote_channel", "decline_reason", "quote_features", "created_at", "updated_at"],
        "proposals": ["proposal_id", "proposal_number", "quote_id", "opportunity_id", "customer_id", "agent_id", "product_id", "proposal_date", "proposal_status", "proposed_premium", "proposed_sum_assured", "proposal_payload", "created_at", "updated_at"],
        "applications": ["application_id", "application_number", "proposal_id", "quote_id", "opportunity_id", "customer_id", "agent_id", "product_id", "application_date", "application_status", "requested_premium", "requested_sum_assured", "medical_required", "application_payload", "created_at", "updated_at"],
        "underwriting_decisions": ["underwriting_decision_id", "application_id", "customer_id", "product_id", "decision_date", "decision_status", "risk_class", "rating_factor", "exclusion_applied", "underwriting_reason", "decision_payload", "created_at", "updated_at"],
        "agent_calls": ["agent_call_id", "agent_id", "customer_id", "lead_id", "opportunity_id", "campaign_id", "call_ts", "call_direction", "call_outcome", "duration_seconds", "sentiment_score", "next_step_date", "call_notes", "created_at", "updated_at"],
        "agent_meetings": ["agent_meeting_id", "agent_id", "customer_id", "lead_id", "opportunity_id", "meeting_ts", "meeting_type", "meeting_channel", "meeting_outcome", "duration_minutes", "product_id", "meeting_notes", "created_at", "updated_at"],
        "agent_targets": ["agent_target_id", "agent_id", "target_period_start", "target_period_end", "target_type", "product_id", "target_value", "actual_value", "attainment_pct", "created_at", "updated_at"],
        "agent_commissions": ["agent_commission_id", "agent_id", "policy_id", "product_id", "commission_period", "commission_type", "premium_basis_amount", "commission_rate", "commission_amount", "paid_date", "chargeback_flag", "created_at", "updated_at"],
        "agent_training": ["agent_training_id", "agent_id", "training_code", "training_name", "training_category", "assigned_date", "completed_date", "completion_status", "assessment_score", "certification_flag", "created_at", "updated_at"],
        "agent_attrition_events": ["agent_attrition_event_id", "agent_id", "event_date", "attrition_stage", "attrition_reason", "voluntary_flag", "manager_intervention_flag", "intervention_notes", "created_at", "updated_at"],
        "claim_parties": ["claim_party_id", "claim_id", "party_id", "customer_id", "role_type", "relationship_to_insured", "provider_specialty", "involvement_notes", "created_at", "updated_at"],
        "claim_assessments": ["claim_assessment_id", "claim_id", "assessed_by_agent_id", "assessment_date", "assessment_type", "severity_score", "liability_pct", "estimated_loss_amount", "recommended_reserve_amount", "assessment_outcome", "assessment_notes", "created_at", "updated_at"],
        "claim_fraud_indicators": ["claim_fraud_indicator_id", "claim_id", "customer_id", "indicator_date", "indicator_type", "indicator_source", "indicator_score", "severity", "resolved_flag", "resolution_outcome", "indicator_payload", "created_at", "updated_at"],
        "model_features": ["model_feature_id", "feature_set_name", "feature_set_version", "entity_type", "entity_id", "customer_id", "policy_id", "agent_id", "lead_id", "opportunity_id", "claim_id", "campaign_id", "product_id", "feature_date", "prediction_horizon_days", "features", "label_name", "label_value", "data_split", "feature_hash", "created_at", "updated_at"],
        "model_scores": ["model_score_id", "model_name", "model_version", "model_feature_id", "entity_type", "entity_id", "score_ts", "score_name", "score_value", "probability", "score_band", "rank_within_segment", "explanation", "created_at", "updated_at"],
        "model_predictions": ["model_prediction_id", "model_score_id", "model_name", "model_version", "prediction_type", "entity_type", "entity_id", "prediction_ts", "prediction_horizon_days", "predicted_label", "predicted_value", "probability", "confidence_score", "recommended_product_id", "prediction_payload", "created_at", "updated_at"],
        "next_best_actions": ["next_best_action_id", "model_prediction_id", "customer_id", "agent_id", "policy_id", "lead_id", "campaign_id", "product_id", "action_type", "action_rank", "priority_score", "expected_value", "due_date", "action_status", "outcome", "outcome_value", "action_reason", "created_at", "updated_at"],
        "ml_training_labels": ["label_snapshot_id", "entity_type", "entity_id", "customer_id", "agent_id", "policy_id", "lead_id", "claim_id", "campaign_id", "as_of_date", "propensity_to_buy_label", "next_best_product_label", "churn_label", "lapse_label", "lead_conversion_label", "agent_attrition_label", "claim_occurrence_label", "fraud_label", "campaign_response_label", "feature_summary", "created_at"],
    }
    return {name: CsvWriter(output_dir / f"{name}.csv", fields) for name, fields in specs.items()}


def generate(args) -> dict[str, int]:
    random.seed(args.seed)
    # Faker does not currently provide dedicated Singapore/Hong Kong English
    # locales in all builds, so use stable English providers and localize
    # geography, products, phone/email patterns, and campaign logic ourselves.
    fake_sg = Faker("en_GB")
    fake_hk = Faker("en_GB")
    Faker.seed(args.seed)

    start = date(args.start_year, 1, 1)
    end = date(args.start_year + 2, 12, 31)
    created = now_ts()
    output_dir = Path(args.output_dir)
    writers = create_writers(output_dir)

    customer_refs = []
    agent_refs = []
    agency_party_ids = []
    product_refs = []
    product_lookup = {}
    rider_refs_by_base_code = defaultdict(list)
    campaign_refs = []
    lead_refs = []
    opportunity_refs = []
    policy_refs = []
    coverage_refs_by_policy = defaultdict(list)
    claim_refs = []
    target_refs = []
    response_refs = []
    glossary_refs = []
    quote_refs = []
    proposal_refs = []
    application_refs = []
    model_score_refs = []

    customer_signal_stats = defaultdict(lambda: {
        "missed_payments": 0,
        "complaints": 0,
        "service_requests": 0,
        "digital_events": 0,
        "campaign_touches": 0,
        "campaign_positive": 0,
        "quotes": 0,
        "claims": 0,
        "fraud_indicators": 0,
        "premium_increase_pct": 0.0,
    })
    agent_signal_stats = defaultdict(lambda: {
        "calls": 0,
        "meetings": 0,
        "commissions": 0.0,
        "commission_h1": 0.0,
        "commission_h2": 0.0,
        "chargebacks": 0,
    })

    agent_month_stats = defaultdict(lambda: {
        "leads": 0,
        "contacts": 0,
        "quotes": 0,
        "applications": 0,
        "bound": 0,
        "new_premium": 0.0,
        "renewal_premium": 0.0,
        "retained": 0,
        "lapsed": 0,
        "claims": 0,
        "claim_incurred": 0.0,
        "earned": 0.0,
    })

    # Agency parties.
    agency_count = max(80, args.agents // 45)
    for i in range(agency_count):
        market = "SG" if random.random() < 0.55 else "HK"
        faker = fake_sg if market == "SG" else fake_hk
        agency_id = new_id()
        name = f"{random.choice(['Prudential Advisory', 'PFA', 'Premier Wealth', 'HealthFirst', 'Legacy'])} {faker.city()} {i + 1}"
        writers["parties"].write({
            "party_id": agency_id,
            "party_type": "organization",
            "display_name": name,
            "organization_name": name,
            "email": f"agency{i + 1}@synthetic-pru.example",
            "phone": faker.phone_number(),
            "preferred_contact_method": "email",
            "created_at": created,
            "updated_at": created,
        })
        agency_party_ids.append((agency_id, market))
        district = random.choice(SINGAPORE_DISTRICTS if market == "SG" else HONG_KONG_DISTRICTS)
        writers["addresses"].write(make_address(agency_id, district, faker, created, "business"))

    # Products and rider components. Base products are used as policy headers;
    # rider products are linked through policy_coverages and premium rows.
    for i, product in enumerate(PRODUCTS, 1):
        product_id = new_id()
        writers["products"].write({
            "product_id": product_id,
            "parent_product_id": None,
            "product_code": product["code"],
            "product_name": product["name"],
            "line_of_business": product["lob"],
            "product_family": product["family"],
            "product_component_type": "base",
            "rider_category": None,
            "product_version": "2026 synthetic MVP",
            "effective_date": date(2023, 1, 1),
            "expiration_date": None,
            "active_flag": True,
            "created_at": created,
            "updated_at": created,
        })
        base_ref = {"product_id": product_id, "component_type": "base", **product}
        product_refs.append(base_ref)
        product_lookup[product["code"]] = base_ref

    for base_product in product_refs:
        for rider_code, rider_name, rider_family, rider_category, premium_factor, attach_rate in RIDERS_BY_BASE_PRODUCT.get(base_product["code"], []):
            rider_id = new_id()
            writers["products"].write({
                "product_id": rider_id,
                "parent_product_id": base_product["product_id"],
                "product_code": rider_code,
                "product_name": rider_name,
                "line_of_business": base_product["lob"],
                "product_family": rider_family,
                "product_component_type": "rider",
                "rider_category": rider_category,
                "product_version": "2026 synthetic rider MVP",
                "effective_date": date(2023, 1, 1),
                "expiration_date": None,
                "active_flag": True,
                "created_at": created,
                "updated_at": created,
            })
            rider_ref = {
                "product_id": rider_id,
                "parent_product_id": base_product["product_id"],
                "code": rider_code,
                "name": rider_name,
                "lob": base_product["lob"],
                "family": rider_family,
                "market": base_product["market"],
                "component_type": "rider",
                "rider_category": rider_category,
                "premium_factor": premium_factor,
                "attach_rate": attach_rate,
                "coverage": rider_name,
            }
            rider_refs_by_base_code[base_product["code"]].append(rider_ref)
            product_lookup[rider_code] = rider_ref

    # Customers and their parties/addresses.
    household_ids = []
    for i in range(args.customers):
        market = "SG" if random.random() < 0.52 else "HK"
        faker = fake_sg if market == "SG" else fake_hk
        district = random.choice(SINGAPORE_DISTRICTS if market == "SG" else HONG_KONG_DISTRICTS)
        segment = weighted_choice(CUSTOMER_SEGMENTS)
        party_id = new_id()
        customer_id = new_id()
        gender = random.choice(["M", "F"])
        first = faker.first_name_male() if gender == "M" else faker.first_name_female()
        last = faker.last_name()
        display = f"{first} {last}"
        age = age_for_segment(segment)
        dob = date(end.year - age, random.randint(1, 12), random.randint(1, 28))
        email = None if random.random() < 0.025 else f"{first}.{last}.{i}@example-insurance.test".lower().replace(" ", "")
        phone = None if random.random() < 0.018 else faker.phone_number()
        writers["parties"].write({
            "party_id": party_id,
            "party_type": "person",
            "display_name": display,
            "first_name": first,
            "last_name": last,
            "date_of_birth": dob,
            "tax_id_last4": f"{random.randint(0, 9999):04d}" if random.random() > 0.06 else None,
            "email": email,
            "phone": phone,
            "preferred_contact_method": weighted_choice([("email", 0.45), ("sms", 0.25), ("phone", 0.18), ("app", 0.10), ("mail", 0.02)]),
            "created_at": created,
            "updated_at": created,
        })
        if i % random.randint(3, 6) == 0:
            household_id = new_id()
            household_name = f"{last} Household"
            writers["parties"].write({
                "party_id": household_id,
                "party_type": "household",
                "display_name": household_name,
                "organization_name": household_name,
                "preferred_contact_method": "email",
                "created_at": created,
                "updated_at": created,
            })
            household_ids.append(household_id)
        household_id = random.choice(household_ids) if household_ids and random.random() < 0.62 else None
        risk = weighted_choice([("low", 0.35), ("medium", 0.45), ("high", 0.17), ("very_high", 0.03)])
        engagement = min(100, max(0, random.gauss(58, 18) + (8 if segment == "health_focused" else 0)))
        income_score = income_score_for_segment(segment)
        income_band = income_band_from_score(income_score)
        acquisition = random_day(start - timedelta(days=720), end, seasonal=True)
        lifecycle = weighted_choice([("active", 0.72), ("prospect", 0.07), ("inactive", 0.08), ("lapsed", 0.10), ("former", 0.03)])
        writers["customers"].write({
            "customer_id": customer_id,
            "party_id": party_id,
            "customer_number": f"CUST-{i + 1:06d}",
            "customer_segment": segment,
            "lifecycle_stage": lifecycle,
            "acquisition_date": acquisition,
            "risk_tier": risk,
            "engagement_score": f"{engagement:.2f}",
            "household_party_id": household_id,
            "created_at": created,
            "updated_at": created,
        })
        writers["addresses"].write(make_address(party_id, district, faker, created, "primary"))
        if random.random() < 0.04:
            old_address = make_address(party_id, district, faker, created, "mailing")
            old_address["is_current"] = random.random() < 0.35  # benign DQ issue: stale secondary address still current.
            old_address["effective_date"] = random_day(start - timedelta(days=1200), start - timedelta(days=30))
            old_address["expiration_date"] = random_day(start, end)
            writers["addresses"].write(old_address)
        customer_refs.append({
            "customer_id": customer_id,
            "party_id": party_id,
            "market": market,
            "segment": segment,
            "risk": risk,
            "engagement": engagement,
            "income_score": income_score,
            "income_band": income_band,
            "acquisition": acquisition,
            "age": age,
            "lifecycle": lifecycle,
        })

    # Agents and movements.
    for i in range(args.agents):
        market = "SG" if random.random() < 0.58 else "HK"
        faker = fake_sg if market == "SG" else fake_hk
        district = random.choice(SINGAPORE_DISTRICTS if market == "SG" else HONG_KONG_DISTRICTS)
        possible_agencies = [item for item in agency_party_ids if item[1] == market] or agency_party_ids
        agency_id, _ = random.choice(possible_agencies)
        party_id = new_id()
        agent_id = new_id()
        first = faker.first_name()
        last = faker.last_name()
        appointment = random_day(start - timedelta(days=1800), end - timedelta(days=30), seasonal=True)
        status = weighted_choice([("active", 0.88), ("inactive", 0.05), ("terminated", 0.06), ("suspended", 0.01)])
        termination = random_day(start, end) if status == "terminated" else None
        channel = weighted_choice([("exclusive", 0.45), ("independent", 0.18), ("broker", 0.12), ("direct", 0.08), ("partner", 0.17)])
        performance = max(0.25, random.lognormvariate(0, 0.55))
        writers["parties"].write({
            "party_id": party_id,
            "party_type": "person",
            "display_name": f"{first} {last}",
            "first_name": first,
            "last_name": last,
            "email": f"{first}.{last}.{i}@synthetic-adviser.example".lower().replace(" ", ""),
            "phone": faker.phone_number(),
            "preferred_contact_method": "email",
            "created_at": created,
            "updated_at": created,
        })
        writers["agents"].write({
            "agent_id": agent_id,
            "party_id": party_id,
            "agent_number": f"AGT-{market}-{i + 1:05d}",
            "agency_party_id": agency_id,
            "license_state": market,
            "license_number": f"{market}{random.randint(100000, 999999)}",
            "channel": channel,
            "territory_code": district[1],
            "appointment_date": appointment,
            "termination_date": termination,
            "status": status,
            "created_at": created,
            "updated_at": created,
        })
        writers["addresses"].write(make_address(party_id, district, faker, created, "business"))
        writers["agent_movements"].write({
            "agent_movement_id": new_id(),
            "agent_id": agent_id,
            "movement_type": "appointment",
            "to_agency_party_id": agency_id,
            "to_territory_code": district[1],
            "effective_date": appointment,
            "reason": "Initial appointment",
            "created_at": created,
            "updated_at": created,
        })
        if random.random() < 0.22:
            movement_date = random_day(max(appointment + timedelta(days=90), start), end)
            new_district = random.choice(SINGAPORE_DISTRICTS if market == "SG" else HONG_KONG_DISTRICTS)
            new_agency_id, _ = random.choice(possible_agencies)
            movement_type = "agency_change" if random.random() < 0.45 else "territory_change"
            writers["agent_movements"].write({
                "agent_movement_id": new_id(),
                "agent_id": agent_id,
                "movement_type": movement_type,
                "from_agency_party_id": agency_id,
                "to_agency_party_id": new_agency_id,
                "from_territory_code": district[1],
                "to_territory_code": new_district[1],
                "effective_date": movement_date,
                "reason": random.choice(["Book realignment", "Growth market coverage", "Manager reassignment", "Customer proximity"]),
                "created_at": created,
                "updated_at": created,
            })
        if status == "terminated":
            writers["agent_movements"].write({
                "agent_movement_id": new_id(),
                "agent_id": agent_id,
                "movement_type": "termination",
                "from_agency_party_id": agency_id,
                "from_territory_code": district[1],
                "effective_date": termination,
                "reason": random.choice(["Voluntary exit", "Production threshold not met", "Career move"]),
                "created_at": created,
                "updated_at": created,
            })
        agent_refs.append({
            "agent_id": agent_id,
            "market": market,
            "agency_party_id": agency_id,
            "territory": district[1],
            "channel": channel,
            "performance": performance,
            "status": status,
        })

    # Campaigns.
    for i in range(args.campaigns):
        archetype = random.choice(CAMPAIGN_ARCHETYPES)
        title, campaign_type, lob, market, channels, lift = archetype
        start_day = random_day(start, end - timedelta(days=30), seasonal=True)
        duration = random.choice([14, 21, 30, 45, 60, 90])
        channel = random.choice(channels)
        status = "completed" if start_day + timedelta(days=duration) < end else weighted_choice([("active", 0.7), ("planned", 0.2), ("cancelled", 0.1)])
        campaign_id = new_id()
        writers["campaigns"].write({
            "campaign_id": campaign_id,
            "campaign_code": f"CMP-{market}-{i + 1:04d}",
            "campaign_name": f"{title} {start_day.year} Wave {random.randint(1, 8)}",
            "campaign_type": campaign_type,
            "channel": channel,
            "objective": campaign_objective(campaign_type, market),
            "target_line_of_business": lob,
            "start_date": start_day,
            "end_date": start_day + timedelta(days=duration),
            "budget_amount": money(random.uniform(12000, 260000) * (1.25 if channel in {"agent_call", "partner"} else 1)),
            "status": status,
            "created_at": created,
            "updated_at": created,
        })
        campaign_refs.append({
            "campaign_id": campaign_id,
            "market": market,
            "lob": lob,
            "channel": channel,
            "start": start_day,
            "end": start_day + timedelta(days=duration),
            "lift": lift,
            "type": campaign_type,
        })

    # Leads.
    lead_count = max(args.policies, int(args.customers * 1.8))
    for i in range(lead_count):
        campaign = random.choice(campaign_refs) if random.random() < 0.68 else None
        market = campaign["market"] if campaign else random.choice(["SG", "HK"])
        customer_pool = [c for c in customer_refs if c["market"] == market]
        customer = random.choice(customer_pool) if customer_pool and random.random() < 0.78 else None
        product_pool = [p for p in product_refs if p["market"] == market and (not campaign or p["lob"] == campaign["lob"] or random.random() < 0.25)]
        product = random.choice(product_pool or product_refs)
        agent_pool = [a for a in agent_refs if a["market"] == market and a["status"] == "active"]
        agent = weighted_agent(agent_pool)
        received_day = random_day(start, end, seasonal=True) if not campaign else random_day(campaign["start"], campaign["end"], seasonal=True)
        score = min(100, max(0, random.gauss(55, 20) + (customer["engagement"] - 50) * 0.25 if customer else random.gauss(45, 22)))
        lead_status = weighted_choice([("new", 0.07), ("contacted", 0.20), ("qualified", 0.24), ("disqualified", 0.18), ("converted", 0.17), ("closed", 0.14)])
        if score > 78 and random.random() < 0.45:
            lead_status = "converted"
        lead_id = new_id()
        lead_source = campaign["channel"] if campaign else weighted_choice([("referral", 0.22), ("web", 0.25), ("agent", 0.30), ("partner", 0.15), ("walk_in", 0.08)])
        writers["leads"].write({
            "lead_id": lead_id,
            "lead_number": f"LEAD-{i + 1:07d}",
            "party_id": customer["party_id"] if customer else None,
            "customer_id": customer["customer_id"] if customer else None,
            "campaign_id": campaign["campaign_id"] if campaign else None,
            "assigned_agent_id": agent["agent_id"] if agent else None,
            "product_id": product["product_id"],
            "lead_source": lead_source,
            "lead_status": lead_status,
            "received_at": dt(received_day),
            "qualified_at": dt(add_days(received_day, 1, 21)) if lead_status in {"qualified", "converted"} else None,
            "score": f"{score:.2f}",
            "created_at": created,
            "updated_at": created,
        })
        lead_refs.append({
            "lead_id": lead_id,
            "customer_id": customer["customer_id"] if customer else None,
            "party_id": customer["party_id"] if customer else None,
            "campaign_id": campaign["campaign_id"] if campaign else None,
            "agent_id": agent["agent_id"] if agent else None,
            "product_id": product["product_id"],
            "market": market,
            "status": lead_status,
            "score": score,
            "received": received_day,
            "lead_source": lead_source,
        })
        if agent:
            month_key = (agent["agent_id"], received_day.replace(day=1))
            agent_month_stats[month_key]["leads"] += 1
            if lead_status != "new":
                agent_month_stats[month_key]["contacts"] += 1

    # Opportunities from a large subset of qualified/converted leads.
    opp_candidates = [lead for lead in lead_refs if lead["status"] in {"qualified", "converted", "contacted"}]
    random.shuffle(opp_candidates)
    for i, lead in enumerate(opp_candidates[: int(args.policies * 0.85)]):
        opened = add_days(lead["received"], 1, 35)
        score = lead["score"]
        if lead["status"] == "converted" or score > 82:
            stage = weighted_choice([("bound", 0.58), ("underwriting", 0.11), ("quoted", 0.11), ("application", 0.10), ("lost", 0.08), ("withdrawn", 0.02)])
        else:
            stage = weighted_choice([("opened", 0.10), ("quoted", 0.25), ("application", 0.18), ("underwriting", 0.13), ("bound", 0.17), ("lost", 0.13), ("withdrawn", 0.04)])
        product = next(p for p in product_refs if p["product_id"] == lead["product_id"])
        estimate = lognormal_around(product["premium_mu"], product["premium_sigma"])
        close_day = add_days(opened, 7, 80) if stage in {"bound", "lost", "withdrawn"} else None
        opp_id = new_id()
        writers["opportunities"].write({
            "opportunity_id": opp_id,
            "opportunity_number": f"OPP-{i + 1:07d}",
            "lead_id": lead["lead_id"],
            "customer_id": lead["customer_id"],
            "agent_id": lead["agent_id"],
            "campaign_id": lead["campaign_id"],
            "product_id": lead["product_id"],
            "opportunity_stage": stage,
            "opened_date": opened,
            "close_date": close_day,
            "estimated_premium": money(estimate),
            "quoted_premium": money(estimate * random.uniform(0.92, 1.12)) if stage != "opened" else None,
            "lost_reason": random.choice(["Price objection", "Medical underwriting", "Deferred decision", "Competitor offer", "Unable to contact"]) if stage in {"lost", "withdrawn"} else None,
            "created_at": created,
            "updated_at": created,
        })
        opportunity_refs.append({**lead, "opportunity_id": opp_id, "stage": stage, "opened": opened, "quoted_premium": estimate})
        if lead["agent_id"]:
            month_key = (lead["agent_id"], opened.replace(day=1))
            if stage in {"quoted", "application", "underwriting", "bound", "lost"}:
                agent_month_stats[month_key]["quotes"] += 1
            if stage in {"application", "underwriting", "bound"}:
                agent_month_stats[month_key]["applications"] += 1

    # Policies.
    bound_opps = [opp for opp in opportunity_refs if opp["stage"] == "bound" and opp["customer_id"]]
    for i in range(args.policies):
        use_opp = i < len(bound_opps) and random.random() < 0.78
        opp = bound_opps[i] if use_opp else None
        market = opp["market"] if opp else random.choice(["SG", "HK"])
        customer = next((c for c in customer_refs if c["customer_id"] == opp["customer_id"]), None) if opp else random.choice([c for c in customer_refs if c["market"] == market])
        product = next((p for p in product_refs if p["product_id"] == opp["product_id"]), None) if opp else random.choice([p for p in product_refs if p["market"] == market])
        agent = next((a for a in agent_refs if a["agent_id"] == opp["agent_id"]), None) if opp and opp["agent_id"] else weighted_agent([a for a in agent_refs if a["market"] == market and a["status"] == "active"])
        effective = add_days(opp["opened"], 1, 45) if opp else random_day(start, end, seasonal=True)
        if effective > end:
            effective = end - timedelta(days=random.randint(0, 20))
        term_months = random.choice([12, 12, 12, 24, 36])
        expiration = effective + timedelta(days=365 * term_months // 12)
        base_annual = lognormal_around(product["premium_mu"], product["premium_sigma"])
        if customer["segment"] == "affluent_wealth":
            base_annual *= random.uniform(1.25, 2.1)
        if customer["risk"] in {"high", "very_high"} and product["lob"] in {"health", "critical_illness"}:
            base_annual *= random.uniform(1.08, 1.35)
        attached_riders = []
        for rider in select_riders_for_policy(product, customer, rider_refs_by_base_code):
            rider_with_premium = dict(rider)
            rider_with_premium["annual_premium"] = base_annual * rider["premium_factor"] * random.uniform(0.75, 1.25)
            attached_riders.append(rider_with_premium)
        rider_annual = sum(rider["annual_premium"] for rider in attached_riders)
        annual = base_annual + rider_annual
        status = policy_status_for_dates(effective, expiration, end)
        cancellation = None
        if status in {"cancelled", "lapsed"}:
            cancellation = add_days(effective, 45, min(330, max(50, (expiration - effective).days - 5)))
        issue = effective - timedelta(days=random.randint(0, 18))
        policy_id = new_id()
        writers["policies"].write({
            "policy_id": policy_id,
            "policy_number": f"POL-{market}-{i + 1:08d}",
            "customer_id": customer["customer_id"],
            "agent_id": agent["agent_id"] if agent else None,
            "product_id": product["product_id"],
            "opportunity_id": opp["opportunity_id"] if opp else None,
            "prior_policy_id": random.choice(policy_refs)["policy_id"] if policy_refs and random.random() < 0.08 else None,
            "policy_status": status,
            "effective_date": effective,
            "expiration_date": expiration,
            "issue_date": issue,
            "cancellation_date": cancellation,
            "source_channel": "campaign" if opp and opp.get("campaign_id") else weighted_choice([("agent", 0.45), ("web", 0.18), ("partner", 0.18), ("referral", 0.12), ("direct", 0.07)]),
            "payment_plan": weighted_choice([("annual", 0.35), ("monthly", 0.45), ("quarterly", 0.15), ("single", 0.05)]),
            "annual_premium": money(annual),
            "written_premium": signed_money(-annual * random.uniform(0.25, 0.9) if status == "cancelled" and random.random() < 0.35 else annual),
            "created_at": created,
            "updated_at": created,
        })
        policy = {
            "policy_id": policy_id,
            "customer_id": customer["customer_id"],
            "agent_id": agent["agent_id"] if agent else None,
            "product_id": product["product_id"],
            "product": product,
            "market": market,
            "status": status,
            "effective": effective,
            "expiration": expiration,
            "annual": annual,
            "base_annual": base_annual,
            "rider_annual": rider_annual,
            "attached_riders": attached_riders,
            "campaign_id": opp["campaign_id"] if opp else None,
            "opportunity_id": opp["opportunity_id"] if opp else None,
        }
        policy_refs.append(policy)
        coverage_allocations = write_coverages(writers, policy, product, created)
        coverage_refs_by_policy[policy_id].extend([item["coverage_id"] for item in coverage_allocations])
        write_premiums_and_payments(writers, policy, coverage_allocations, customer, created, agent_month_stats, customer_signal_stats)
        if agent:
            month_key = (agent["agent_id"], effective.replace(day=1))
            agent_month_stats[month_key]["bound"] += 1
            if status == "renewed":
                agent_month_stats[month_key]["renewal_premium"] += annual
                agent_month_stats[month_key]["retained"] += 1
            else:
                agent_month_stats[month_key]["new_premium"] += annual
            if status == "lapsed":
                agent_month_stats[month_key]["lapsed"] += 1

    # Claims.
    claim_number = 1
    for policy in policy_refs:
        product = policy["product"]
        risk_multiplier = 1.0
        if random.random() < product["claim_rate"] * risk_multiplier:
            claim_count = 1 + (1 if random.random() < 0.10 else 0)
            for _ in range(claim_count):
                loss_end = min(policy["expiration"], end)
                if loss_end <= policy["effective"]:
                    continue
                loss_date = random_day(policy["effective"], loss_end)
                report_date = add_days(loss_date, 0, 21)
                paid = claim_amount(product)
                reserve = paid * random.uniform(0.05, 0.85) if random.random() < 0.35 else 0
                status = weighted_choice([("closed", 0.68), ("open", 0.20), ("reopened", 0.03), ("denied", 0.07), ("subrogation", 0.02)])
                close_date = add_days(report_date, 14, 220) if status == "closed" else None
                claim_id = new_id()
                coverage_id = random.choice(coverage_refs_by_policy[policy["policy_id"]])
                writers["claims"].write({
                    "claim_id": claim_id,
                    "claim_number": f"CLM-{policy['market']}-{claim_number:08d}",
                    "policy_id": policy["policy_id"],
                    "customer_id": policy["customer_id"],
                    "policy_coverage_id": coverage_id,
                    "assigned_agent_id": policy["agent_id"],
                    "loss_date": loss_date,
                    "report_date": report_date,
                    "close_date": close_date,
                    "claim_status": status,
                    "loss_cause": loss_cause(product["lob"]),
                    "loss_description": claim_description(product["lob"]),
                    "paid_amount": money(paid if status != "denied" else 0),
                    "reserve_amount": money(reserve if status in {"open", "reopened", "subrogation"} else 0),
                    "litigation_flag": random.random() < 0.025,
                    "catastrophe_flag": random.random() < 0.012,
                    "created_at": created,
                    "updated_at": created,
                })
                claim_refs.append({"claim_id": claim_id, **policy, "loss_date": loss_date, "paid": paid, "reserve": reserve})
                customer_signal_stats[policy["customer_id"]]["claims"] += 1
                if policy["agent_id"]:
                    month_key = (policy["agent_id"], loss_date.replace(day=1))
                    agent_month_stats[month_key]["claims"] += 1
                    agent_month_stats[month_key]["claim_incurred"] += paid + reserve
                claim_number += 1

    # Campaign targets and responses.
    for campaign in campaign_refs:
        target_size = random.randint(args.min_targets_per_campaign, args.max_targets_per_campaign)
        customer_pool = [c for c in customer_refs if c["market"] == campaign["market"]]
        lead_pool = [l for l in lead_refs if l["campaign_id"] == campaign["campaign_id"]]
        selected_customers = random.sample(customer_pool, min(len(customer_pool), int(target_size * 0.75)))
        selected_leads = random.sample(lead_pool, min(len(lead_pool), target_size - len(selected_customers)))
        selected = [("customer", item) for item in selected_customers] + [("lead", item) for item in selected_leads]
        for kind, entity in selected:
            agent = weighted_agent([a for a in agent_refs if a["market"] == campaign["market"] and a["status"] == "active"])
            status = weighted_choice([("sent", 0.82), ("selected", 0.09), ("suppressed", 0.06), ("excluded", 0.03)])
            target_id = new_id()
            writers["campaign_targets"].write({
                "campaign_target_id": target_id,
                "campaign_id": campaign["campaign_id"],
                "customer_id": entity["customer_id"] if kind == "customer" else entity.get("customer_id"),
                "lead_id": entity["lead_id"] if kind == "lead" else None,
                "agent_id": agent["agent_id"] if agent else None,
                "target_status": status,
                "selected_at": dt(campaign["start"] - timedelta(days=random.randint(0, 7))),
                "suppression_reason": random.choice(["No marketing consent", "Recent complaint", "Duplicate contact", "Invalid email"]) if status in {"suppressed", "excluded"} else None,
                "created_at": created,
                "updated_at": created,
            })
            target_refs.append({"target_id": target_id, "campaign": campaign, "kind": kind, "entity": entity, "agent_id": agent["agent_id"] if agent else None, "status": status})
            if status in {"sent", "selected"}:
                write_campaign_response(writers, target_id, campaign, kind, entity, agent, policy_refs, opportunity_refs, created, response_refs, customer_signal_stats)

    # Engagement events.
    policies_by_customer = defaultdict(list)
    for policy in policy_refs:
        policies_by_customer[policy["customer_id"]].append(policy)
    claims_by_customer = defaultdict(list)
    for claim in claim_refs:
        claims_by_customer[claim["customer_id"]].append(claim)

    engagement_count = args.engagement_events
    for i in range(engagement_count):
        customer = random.choice(customer_refs)
        related_policies = policies_by_customer[customer["customer_id"]]
        policy = random.choice(related_policies) if related_policies and random.random() < 0.55 else None
        related_claims = claims_by_customer[customer["customer_id"]]
        claim = random.choice(related_claims) if related_claims and random.random() < 0.12 else None
        campaign = random.choice(campaign_refs) if random.random() < 0.22 else None
        event_day = random_day(start, end, seasonal=True)
        event_type = weighted_choice([
            ("policy_view", 0.18),
            ("premium_payment", 0.15),
            ("claim_status_check", 0.08),
            ("agent_call", 0.14),
            ("campaign_click", 0.13),
            ("quote_request", 0.10),
            ("wellness_content_view", 0.12),
            ("service_request", 0.10),
        ])
        channel = channel_for_event(event_type)
        writers["customer_engagement_events"].write({
            "customer_engagement_event_id": new_id(),
            "customer_id": customer["customer_id"],
            "policy_id": policy["policy_id"] if policy else None,
            "claim_id": claim["claim_id"] if claim else None,
            "campaign_id": campaign["campaign_id"] if campaign else None,
            "agent_id": policy["agent_id"] if policy and random.random() < 0.7 else None,
            "event_ts": dt(event_day),
            "event_type": event_type,
            "channel": channel,
            "sentiment_score": f"{max(-1, min(1, random.gauss(0.25, 0.38))):.2f}" if channel in {"call_center", "agent", "chat"} else None,
            "duration_seconds": random.randint(20, 2400) if channel in {"call_center", "agent", "chat"} else random.randint(3, 420),
            "metadata": {
                "market": customer["market"],
                "segment": customer["segment"],
                "synthetic_dq_note": random.choice(["missing_cookie_id", "late_arriving_event", "duplicate_click_candidate"]) if random.random() < 0.018 else None,
            },
            "created_at": created,
            "updated_at": created,
        })
        customer_signal_stats[customer["customer_id"]]["digital_events"] += 1

    generate_ml_ready_data(
        writers=writers,
        customer_refs=customer_refs,
        agent_refs=agent_refs,
        product_refs=product_refs,
        campaign_refs=campaign_refs,
        lead_refs=lead_refs,
        opportunity_refs=opportunity_refs,
        policy_refs=policy_refs,
        claim_refs=claim_refs,
        response_refs=response_refs,
        customer_signal_stats=customer_signal_stats,
        agent_signal_stats=agent_signal_stats,
        agent_month_stats=agent_month_stats,
        start=start,
        end=end,
        created=created,
        args=args,
    )

    # MAPA monthly metrics for every agent/month.
    month = date(start.year, start.month, 1)
    months = []
    while month <= end:
        months.append(month)
        month = (month.replace(day=28) + timedelta(days=4)).replace(day=1)
    for agent in agent_refs:
        for month in months:
            stats = agent_month_stats[(agent["agent_id"], month)]
            base = agent["performance"]
            leads = stats["leads"] + random.randint(0, max(2, int(5 * base)))
            contacts = stats["contacts"] + int(leads * random.uniform(0.45, 0.85))
            quotes = stats["quotes"] + int(contacts * random.uniform(0.18, 0.45))
            apps = stats["applications"] + int(quotes * random.uniform(0.35, 0.72))
            bound = stats["bound"] + int(apps * random.uniform(0.22, 0.55))
            earned = stats["earned"] or (stats["new_premium"] + stats["renewal_premium"]) * random.uniform(0.45, 0.95)
            loss_ratio = (stats["claim_incurred"] / earned) if earned > 0 else None
            writers["agent_mapa_metrics"].write({
                "agent_mapa_metric_id": new_id(),
                "agent_id": agent["agent_id"],
                "metric_month": month,
                "leads_count": leads,
                "contacts_count": contacts,
                "quotes_count": quotes,
                "applications_count": apps,
                "policies_bound_count": bound,
                "new_business_premium": money(stats["new_premium"]),
                "renewal_premium": money(stats["renewal_premium"]),
                "retained_policy_count": stats["retained"],
                "lapsed_policy_count": stats["lapsed"],
                "claims_count": stats["claims"],
                "loss_ratio": f"{min(loss_ratio, 9.9999):.4f}" if loss_ratio is not None else None,
                "created_at": created,
                "updated_at": created,
            })

    write_glossary_and_semantics(writers, glossary_refs, created, args.include_fake_embeddings)
    write_query_audit(writers, created)

    counts = {}
    for name, writer in writers.items():
        writer.close()
        counts[name] = writer.count
    write_manifest(output_dir, counts, args)
    return counts


def make_address(party_id: str, district, faker: Faker, created: datetime, address_type: str) -> dict:
    district_name, state_code, city, country_code, postal_code = district
    return {
        "address_id": new_id(),
        "party_id": party_id,
        "address_type": address_type,
        "line1": faker.street_address().replace("\n", " "),
        "line2": district_name if random.random() < 0.35 else None,
        "city": city,
        "state_code": state_code,
        "postal_code": postal_code if country_code == "HK" else f"{random.randint(100000, 829999)}",
        "country_code": country_code,
        "latitude": f"{random.uniform(1.25, 1.47):.6f}" if country_code == "SG" else f"{random.uniform(22.20, 22.55):.6f}",
        "longitude": f"{random.uniform(103.62, 104.05):.6f}" if country_code == "SG" else f"{random.uniform(113.85, 114.35):.6f}",
        "is_current": True,
        "effective_date": date(2020, 1, 1) + timedelta(days=random.randint(0, 1200)),
        "expiration_date": None,
        "created_at": created,
        "updated_at": created,
    }


def age_for_segment(segment: str) -> int:
    ranges = {
        "young_professional": (24, 38),
        "family_protection": (32, 52),
        "affluent_wealth": (38, 68),
        "retirement_planner": (50, 78),
        "health_focused": (28, 66),
        "sme_owner": (34, 62),
    }
    lo, hi = ranges[segment]
    return random.randint(lo, hi)


def income_score_for_segment(segment: str) -> float:
    means = {
        "young_professional": 58,
        "family_protection": 66,
        "affluent_wealth": 88,
        "retirement_planner": 72,
        "health_focused": 64,
        "sme_owner": 78,
    }
    return min(100, max(10, random.gauss(means.get(segment, 60), 12)))


def income_band_from_score(score: float) -> str:
    if score >= 85:
        return "very_high"
    if score >= 70:
        return "high"
    if score >= 45:
        return "medium"
    return "mass"


def sigmoid(x: float) -> float:
    return 1 / (1 + math.exp(-x))


def bool_label(probability: float) -> int:
    return 1 if random.random() < max(0.0, min(1.0, probability)) else 0


def weighted_agent(agent_pool):
    if not agent_pool:
        return None
    sample = random.sample(agent_pool, min(len(agent_pool), 8))
    return max(sample, key=lambda agent: random.random() * agent["performance"])


def campaign_objective(campaign_type: str, market: str) -> str:
    objectives = {
        "wellness": "Drive wellness registration and health protection conversations",
        "health_protection": "Position protection for families facing health gap years",
        "medical_review": "Review medical coverage adequacy and upgrade riders",
        "savings": "Promote disciplined savings and annual cash benefit planning",
        "wealth": "Support wealth accumulation and legacy planning",
        "family": "Engage parents with next-generation education and resilience benefits",
        "newcomer": "Welcome mobile families and newcomers with protection and lifestyle privileges",
        "cancer_awareness": "Raise cancer protection awareness and convert health-conscious customers",
        "maturity_appreciation": "Retain mature policyholders with appreciation offers and new plans",
    }
    return f"{objectives.get(campaign_type, 'Generate qualified insurance demand')} in {market}"


def policy_status_for_dates(effective: date, expiration: date, data_end: date) -> str:
    if random.random() < 0.045:
        return "cancelled"
    if random.random() < 0.055:
        return "lapsed"
    if expiration <= data_end and random.random() < 0.62:
        return "renewed"
    if expiration <= data_end:
        return "expired"
    if random.random() < 0.025:
        return "issued"
    return "active"


def select_riders_for_policy(product, customer, rider_refs_by_base_code) -> list[dict]:
    selected = []
    segment_boost = {
        "health_focused": {"medical_rider", "cancer_rider", "critical_illness_rider"},
        "family_protection": {"waiver_rider", "term_rider", "critical_illness_rider", "accident_rider"},
        "affluent_wealth": {"legacy_rider", "care_rider", "critical_illness_rider"},
        "retirement_planner": {"care_rider", "legacy_rider", "medical_rider"},
        "young_professional": {"accident_rider", "medical_rider"},
        "sme_owner": {"waiver_rider", "term_rider", "accident_rider"},
    }
    for rider in rider_refs_by_base_code.get(product["code"], []):
        attach_rate = rider["attach_rate"]
        if rider["family"] in segment_boost.get(customer["segment"], set()):
            attach_rate += 0.12
        if customer["risk"] in {"high", "very_high"} and rider["rider_category"] in {"early_ci", "multipay_ci", "cancer_recovery", "outpatient"}:
            attach_rate += 0.08
        if random.random() < min(0.82, attach_rate):
            selected.append(rider)
    return selected[: random.choice([1, 1, 2, 2, 3])]


def write_coverages(writers, policy, product, created) -> list[dict]:
    primary_coverage_id = new_id()
    limit_base = {
        "health": random.uniform(250000, 2500000),
        "critical_illness": random.uniform(100000, 1200000),
        "life": random.uniform(250000, 3000000),
        "savings": random.uniform(50000, 400000),
        "investment_linked": random.uniform(100000, 1600000),
        "wealth": random.uniform(300000, 5000000),
    }.get(product["lob"], random.uniform(100000, 1000000))
    writers["policy_coverages"].write({
        "policy_coverage_id": primary_coverage_id,
        "policy_id": policy["policy_id"],
        "product_id": product["product_id"],
        "coverage_code": f"{product['family'].upper()[:12]}-BASE",
        "coverage_name": product["coverage"],
        "coverage_status": "cancelled" if policy["status"] == "cancelled" else "active",
        "is_rider": False,
        "rider_tag": "base_policy",
        "limit_amount": money(limit_base),
        "deductible_amount": money(random.choice([0, 500, 1000, 2500, 5000])),
        "exposure_basis": "sum_assured" if product["lob"] != "health" else "medical_limit",
        "exposure_value": money(limit_base),
        "effective_date": policy["effective"],
        "expiration_date": policy["expiration"],
        "created_at": created,
        "updated_at": created,
    })
    allocations = [{"coverage_id": primary_coverage_id, "annual": policy["base_annual"], "is_rider": False, "rider_tag": "base_policy"}]
    for rider in policy["attached_riders"]:
        rider_coverage_id = new_id()
        rider_annual = rider["annual_premium"]
        rider_limit = limit_base * random.uniform(0.04, 0.35)
        writers["policy_coverages"].write({
            "policy_coverage_id": rider_coverage_id,
            "policy_id": policy["policy_id"],
            "product_id": rider["product_id"],
            "coverage_code": rider["code"],
            "coverage_name": rider["name"],
            "coverage_status": "cancelled" if policy["status"] == "cancelled" else "active",
            "is_rider": True,
            "rider_tag": rider["rider_category"],
            "limit_amount": money(rider_limit),
            "deductible_amount": money(random.choice([0, 250, 500])),
            "exposure_basis": "rider_limit",
            "exposure_value": money(rider_limit),
            "effective_date": policy["effective"],
            "expiration_date": policy["expiration"],
            "created_at": created,
            "updated_at": created,
        })
        allocations.append({"coverage_id": rider_coverage_id, "annual": rider_annual, "is_rider": True, "rider_tag": rider["rider_category"]})
    return allocations


def write_premiums_and_payments(writers, policy, coverage_allocations, customer, created, agent_month_stats, customer_signal_stats):
    annual = policy["annual"]
    months = 12 if policy["status"] in {"active", "renewed", "expired"} else random.randint(3, 10)
    monthly = annual / 12
    current = policy["effective"]
    for idx in range(months):
        period_start = current + timedelta(days=30 * idx)
        period_end = min(period_start + timedelta(days=29), policy["expiration"])
        if period_start > policy["expiration"]:
            break
        txn_type = "renewal" if policy["status"] == "renewed" and idx == 0 else ("new_business" if idx == 0 else "endorsement" if random.random() < 0.025 else "audit")
        for allocation in coverage_allocations:
            coverage_annual = allocation["annual"]
            coverage_monthly = coverage_annual / 12
            written = coverage_annual if idx == 0 else (coverage_monthly * random.uniform(-0.08, 0.10) if txn_type == "endorsement" else 0)
            earned = coverage_monthly
            writers["premiums"].write({
                "premium_id": new_id(),
                "policy_id": policy["policy_id"],
                "policy_coverage_id": allocation["coverage_id"],
                "premium_period_start": period_start,
                "premium_period_end": period_end,
                "transaction_date": period_start,
                "transaction_type": txn_type,
                "written_premium_amount": signed_money(written),
                "earned_premium_amount": money(earned),
                "tax_fee_amount": money(earned * random.uniform(0.0, 0.09)),
                "created_at": created,
                "updated_at": created,
            })
        if policy["agent_id"]:
            agent_month_stats[(policy["agent_id"], period_start.replace(day=1))]["earned"] += monthly
        due = period_start
        paid_status = weighted_choice([("paid", 0.88), ("scheduled", 0.03), ("failed", 0.025), ("reversed", 0.01), ("refunded", 0.01), ("past_due", 0.045)])
        if customer["risk"] in {"high", "very_high"} and random.random() < 0.08:
            paid_status = weighted_choice([("past_due", 0.55), ("failed", 0.35), ("paid", 0.10)])
        billed = monthly
        paid = billed if paid_status == "paid" else (0 if paid_status in {"failed", "past_due", "scheduled"} else billed * random.uniform(0.2, 0.9))
        if paid_status in {"failed", "past_due"}:
            customer_signal_stats[customer["customer_id"]]["missed_payments"] += 1
        writers["payments"].write({
            "payment_id": new_id(),
            "policy_id": policy["policy_id"],
            "customer_id": customer["customer_id"],
            "payment_date": add_days(due, -2, 12),
            "due_date": due,
            "payment_status": paid_status,
            "payment_method": weighted_choice([("card", 0.38), ("ach", 0.22), ("check", 0.04), ("cash", 0.02), ("wire", 0.04), ("payroll", 0.08), ("other", 0.22)]),
            "billed_amount": money(billed),
            "paid_amount": money(paid),
            "created_at": created,
            "updated_at": created,
        })


def claim_amount(product) -> float:
    if product["lob"] == "health":
        return lognormal_around(8500 if product["market"] == "SG" else 55000, 0.8)
    if product["lob"] == "critical_illness":
        return lognormal_around(150000 if product["market"] == "HK" else 35000, 0.65)
    if product["lob"] == "life":
        return lognormal_around(180000, 0.85)
    return lognormal_around(12000, 0.65)


def loss_cause(lob: str) -> str:
    causes = {
        "health": ["hospitalisation", "surgery", "specialist_consultation", "diagnostic_scan", "outpatient_cancer_treatment"],
        "critical_illness": ["cancer", "heart_attack", "stroke", "early_stage_cancer", "major_organ_condition"],
        "life": ["death", "terminal_illness", "total_permanent_disability"],
        "savings": ["maturity_claim", "surrender", "cash_benefit_request"],
        "investment_linked": ["partial_withdrawal", "death", "surrender"],
        "wealth": ["maturity_claim", "legacy_transfer", "surrender"],
    }
    return random.choice(causes.get(lob, ["other"]))


def claim_description(lob: str) -> str:
    descriptions = {
        "health": "Customer submitted medical invoices after private specialist or hospital treatment.",
        "critical_illness": "Customer filed a protection claim following diagnosis and supporting medical review.",
        "life": "Beneficiary or policyholder submitted life protection claim documentation.",
        "savings": "Policyholder requested benefit payment under savings or maturity feature.",
        "investment_linked": "Policyholder requested benefit or withdrawal under investment-linked policy.",
        "wealth": "Customer submitted wealth plan benefit transaction request.",
    }
    return descriptions.get(lob, "Customer submitted insurance claim documentation.")


def write_campaign_response(writers, target_id, campaign, kind, entity, agent, policy_refs, opportunity_refs, created, response_refs, customer_signal_stats):
    base = {
        "email": [("delivered", 0.45), ("opened", 0.28), ("clicked", 0.12), ("quoted", 0.05), ("converted", 0.025), ("unsubscribed", 0.015), ("bounced", 0.025), ("no_response", 0.04)],
        "sms": [("delivered", 0.50), ("clicked", 0.14), ("called", 0.08), ("quoted", 0.06), ("converted", 0.035), ("no_response", 0.17), ("unsubscribed", 0.015)],
        "agent_call": [("called", 0.42), ("quoted", 0.20), ("converted", 0.09), ("no_response", 0.25), ("unsubscribed", 0.04)],
        "web": [("clicked", 0.42), ("quoted", 0.12), ("converted", 0.04), ("no_response", 0.42)],
        "app": [("delivered", 0.42), ("opened", 0.25), ("clicked", 0.15), ("quoted", 0.06), ("converted", 0.035), ("no_response", 0.085)],
        "social": [("clicked", 0.34), ("quoted", 0.06), ("converted", 0.02), ("no_response", 0.58)],
        "partner": [("delivered", 0.35), ("clicked", 0.20), ("quoted", 0.10), ("converted", 0.045), ("no_response", 0.305)],
        "direct_mail": [("delivered", 0.45), ("called", 0.10), ("quoted", 0.04), ("converted", 0.015), ("no_response", 0.395)],
    }
    response_type = weighted_choice(base.get(campaign["channel"], base["email"]))
    response_day = random_day(campaign["start"], campaign["end"], seasonal=False)
    customer_id = entity["customer_id"] if kind == "customer" else entity.get("customer_id")
    lead_id = entity["lead_id"] if kind == "lead" else None
    matching_policy = None
    matching_opp = None
    if response_type == "converted" and customer_id:
        candidates = [p for p in policy_refs if p["customer_id"] == customer_id and p["campaign_id"] == campaign["campaign_id"]]
        if not candidates:
            candidates = [p for p in policy_refs if p["customer_id"] == customer_id and p["effective"] >= campaign["start"]]
        matching_policy = random.choice(candidates) if candidates else None
        if matching_policy:
            opp_candidates = [o for o in opportunity_refs if o["opportunity_id"] == matching_policy["opportunity_id"]]
            matching_opp = opp_candidates[0] if opp_candidates else None
    response_id = new_id()
    writers["campaign_responses"].write({
        "campaign_response_id": response_id,
        "campaign_id": campaign["campaign_id"],
        "campaign_target_id": target_id,
        "customer_id": customer_id,
        "lead_id": lead_id,
        "opportunity_id": matching_opp["opportunity_id"] if matching_opp else None,
        "policy_id": matching_policy["policy_id"] if matching_policy else None,
        "response_ts": dt(response_day),
        "response_type": response_type,
        "conversion_flag": response_type == "converted",
        "conversion_premium": money(matching_policy["annual"]) if matching_policy and response_type == "converted" else None,
        "created_at": created,
        "updated_at": created,
    })
    if customer_id:
        customer_signal_stats[customer_id]["campaign_touches"] += 1
        if response_type in {"opened", "clicked", "called", "quoted", "converted"}:
            customer_signal_stats[customer_id]["campaign_positive"] += 1
    response_refs.append({
        "response_id": response_id,
        "campaign_id": campaign["campaign_id"],
        "customer_id": customer_id,
        "lead_id": lead_id,
        "response_type": response_type,
        "conversion_flag": response_type == "converted",
        "response_date": response_day,
    })


def channel_for_event(event_type: str) -> str:
    mapping = {
        "policy_view": [("web", 0.45), ("mobile_app", 0.45), ("call_center", 0.10)],
        "premium_payment": [("mobile_app", 0.35), ("web", 0.30), ("email", 0.10), ("agent", 0.15), ("call_center", 0.10)],
        "claim_status_check": [("mobile_app", 0.35), ("web", 0.25), ("call_center", 0.25), ("agent", 0.15)],
        "agent_call": [("agent", 0.80), ("call_center", 0.20)],
        "campaign_click": [("email", 0.35), ("sms", 0.15), ("web", 0.25), ("social", 0.15), ("mobile_app", 0.10)],
        "quote_request": [("web", 0.35), ("agent", 0.35), ("mobile_app", 0.15), ("call_center", 0.15)],
        "wellness_content_view": [("mobile_app", 0.40), ("web", 0.35), ("social", 0.25)],
        "service_request": [("chat", 0.20), ("call_center", 0.35), ("web", 0.25), ("mobile_app", 0.20)],
    }
    return weighted_choice(mapping[event_type])


def month_starts(start: date, end: date) -> list[date]:
    month = date(start.year, start.month, 1)
    months = []
    while month <= end:
        months.append(month)
        month = (month.replace(day=28) + timedelta(days=4)).replace(day=1)
    return months


def generate_ml_ready_data(
    *,
    writers,
    customer_refs,
    agent_refs,
    product_refs,
    campaign_refs,
    lead_refs,
    opportunity_refs,
    policy_refs,
    claim_refs,
    response_refs,
    customer_signal_stats,
    agent_signal_stats,
    agent_month_stats,
    start,
    end,
    created,
    args,
):
    customer_by_id = {c["customer_id"]: c for c in customer_refs}
    agent_by_id = {a["agent_id"]: a for a in agent_refs}
    base_products = [p for p in product_refs if p.get("component_type") == "base"]
    policies_by_customer = defaultdict(list)
    policies_by_agent = defaultdict(list)
    claims_by_customer = defaultdict(list)
    claims_by_policy = defaultdict(list)
    leads_by_customer = defaultdict(list)
    responses_by_customer = defaultdict(list)
    quote_refs = []
    proposal_refs = []
    application_refs = []
    model_score_refs = []

    for policy in policy_refs:
        policies_by_customer[policy["customer_id"]].append(policy)
        if policy["agent_id"]:
            policies_by_agent[policy["agent_id"]].append(policy)
    for claim in claim_refs:
        claims_by_customer[claim["customer_id"]].append(claim)
        claims_by_policy[claim["policy_id"]].append(claim)
    for lead in lead_refs:
        if lead["customer_id"]:
            leads_by_customer[lead["customer_id"]].append(lead)
    for response in response_refs:
        if response["customer_id"]:
            responses_by_customer[response["customer_id"]].append(response)

    # Digital behavior and daily feature snapshots, generated from latent customer signals.
    for customer in customer_refs:
        stats = customer_signal_stats[customer["customer_id"]]
        customer_policies = policies_by_customer[customer["customer_id"]]
        customer_claims = claims_by_customer[customer["customer_id"]]
        tenure_days = max(0, (end - customer["acquisition"]).days)
        high_income = customer["income_score"] >= 72
        complaint_risk = sigmoid(-3.1 + stats["missed_payments"] * 0.18 + len(customer_claims) * 0.25 - customer["engagement"] / 90)
        lapse_risk = sigmoid(-3.2 + stats["missed_payments"] * 0.28 + stats["complaints"] * 0.5 - tenure_days / 1600 + stats["premium_increase_pct"] * 3)
        churn_risk = sigmoid(-2.8 + stats["missed_payments"] * 0.16 + stats["complaints"] * 0.75 - customer["engagement"] / 65 - tenure_days / 1800)
        propensity = sigmoid(-2.1 + customer["engagement"] / 28 + customer["income_score"] / 45 + stats["campaign_positive"] * 0.12 - stats["complaints"] * 0.35)
        campaign_response_prob = sigmoid(-2.4 + customer["engagement"] / 35 + stats["campaign_positive"] * 0.22 + (0.35 if high_income else 0))

        digital_count = max(1, int(random.gauss(4 + customer["engagement"] / 8 + stats["campaign_positive"] * 0.4, 4)))
        for _ in range(min(digital_count, 45)):
            event_day = random_day(start, end, seasonal=True)
            event_name = weighted_choice([
                ("app_login", 0.24 + customer["engagement"] / 300),
                ("web_visit", 0.24),
                ("product_view", 0.18),
                ("quote_request", 0.08 + propensity / 8),
                ("payment_portal_view", 0.10 + stats["missed_payments"] / 80),
                ("claim_status_view", 0.06 + len(customer_claims) / 30),
                ("campaign_landing_view", 0.10),
            ])
            product = random.choice(base_products)
            policy = random.choice(customer_policies) if customer_policies and random.random() < 0.35 else None
            campaign = random.choice(campaign_refs) if random.random() < 0.18 else None
            writers["customer_digital_events"].write({
                "customer_digital_event_id": new_id(),
                "customer_id": customer["customer_id"],
                "party_id": customer["party_id"],
                "policy_id": policy["policy_id"] if policy else None,
                "campaign_id": campaign["campaign_id"] if campaign else None,
                "event_ts": dt(event_day),
                "session_id": f"sess_{customer['customer_id'][:8]}_{random.randint(1000, 999999)}",
                "device_type": weighted_choice([("mobile", 0.58), ("desktop", 0.28), ("tablet", 0.10), ("unknown", 0.04)]),
                "channel": "mobile_app" if event_name == "app_login" else weighted_choice([("web", 0.52), ("mobile_app", 0.28), ("email", 0.08), ("sms", 0.04), ("chat", 0.04), ("social", 0.03), ("partner", 0.01)]),
                "event_name": event_name,
                "event_category": event_name.split("_")[0],
                "page_name": random.choice(["home", "product_detail", "quote_start", "payment", "claims", "campaign_landing", "profile"]),
                "product_id": product["product_id"] if event_name in {"product_view", "quote_request"} else None,
                "dwell_seconds": random.randint(6, 900),
                "metadata": {"income_band": customer["income_band"], "propensity_signal": round(propensity, 4), "market": customer["market"]},
                "created_at": created,
                "updated_at": created,
            })
            stats["digital_events"] += 1
            if event_name == "quote_request":
                stats["quotes"] += 1

        complaint_count = 1 + (1 if random.random() < 0.18 else 0) if random.random() < complaint_risk else 0
        for _ in range(complaint_count):
            complaint_day = random_day(start, end, seasonal=True)
            policy = random.choice(customer_policies) if customer_policies and random.random() < 0.6 else None
            claim = random.choice(customer_claims) if customer_claims and random.random() < 0.3 else None
            severity = weighted_choice([("low", 0.42), ("medium", 0.35), ("high", 0.18), ("critical", 0.05)])
            resolution_days = random.randint(1, 45) + (15 if severity in {"high", "critical"} else 0)
            writers["customer_complaints"].write({
                "customer_complaint_id": new_id(),
                "customer_id": customer["customer_id"],
                "policy_id": policy["policy_id"] if policy else None,
                "claim_id": claim["claim_id"] if claim else None,
                "agent_id": policy["agent_id"] if policy else None,
                "complaint_date": complaint_day,
                "complaint_channel": weighted_choice([("call_center", 0.35), ("email", 0.22), ("web", 0.15), ("mobile_app", 0.12), ("agent", 0.10), ("regulator", 0.03), ("social", 0.03)]),
                "complaint_category": random.choice(["premium_increase", "claim_delay", "service_delay", "coverage_confusion", "payment_issue", "agent_follow_up"]),
                "severity": severity,
                "status": weighted_choice([("resolved", 0.72), ("open", 0.08), ("in_review", 0.08), ("rejected", 0.05), ("escalated", 0.07)]),
                "resolution_date": complaint_day + timedelta(days=resolution_days),
                "resolution_days": resolution_days,
                "sentiment_score": f"{random.uniform(-0.95, -0.05):.2f}",
                "complaint_text": "Synthetic complaint describing service, premium, claim, or coverage dissatisfaction.",
                "created_at": created,
                "updated_at": created,
            })
            stats["complaints"] += 1

        service_count = max(0, int(random.gauss(0.6 + len(customer_policies) * 0.25 + len(customer_claims) * 0.55 + stats["complaints"] * 0.6, 0.9)))
        for _ in range(min(service_count, 8)):
            request_day = random_day(start, end, seasonal=True)
            policy = random.choice(customer_policies) if customer_policies and random.random() < 0.7 else None
            claim = random.choice(customer_claims) if customer_claims and random.random() < 0.25 else None
            priority = weighted_choice([("low", 0.18), ("normal", 0.58), ("high", 0.20), ("urgent", 0.04 + stats["complaints"] * 0.01)])
            resolved = random.random() < 0.82
            writers["customer_service_requests"].write({
                "customer_service_request_id": new_id(),
                "customer_id": customer["customer_id"],
                "policy_id": policy["policy_id"] if policy else None,
                "claim_id": claim["claim_id"] if claim else None,
                "assigned_agent_id": policy["agent_id"] if policy else None,
                "request_ts": dt(request_day),
                "request_type": random.choice(["beneficiary_change", "payment_change", "policy_document", "claim_question", "coverage_review", "address_update"]),
                "channel": weighted_choice([("call_center", 0.30), ("email", 0.16), ("web", 0.18), ("mobile_app", 0.18), ("agent", 0.12), ("chat", 0.05), ("branch", 0.01)]),
                "priority": priority,
                "status": "resolved" if resolved else weighted_choice([("open", 0.35), ("pending_customer", 0.20), ("in_progress", 0.35), ("cancelled", 0.10)]),
                "first_response_ts": dt(request_day + timedelta(days=random.randint(0, 2))),
                "resolved_ts": dt(request_day + timedelta(days=random.randint(1, 18))) if resolved else None,
                "sla_breached": priority in {"high", "urgent"} and random.random() < 0.22,
                "service_summary": "Synthetic service request for customer support feature engineering.",
                "created_at": created,
                "updated_at": created,
            })
            stats["service_requests"] += 1

        if random.random() < 0.35:
            nps_base = 8.2 + customer["engagement"] / 45 - stats["complaints"] * 1.6 - stats["missed_payments"] * 0.12
            nps_score = int(max(0, min(10, round(random.gauss(nps_base, 1.8)))))
            writers["customer_nps"].write({
                "customer_nps_id": new_id(),
                "customer_id": customer["customer_id"],
                "survey_date": random_day(start, end, seasonal=True),
                "touchpoint": random.choice(["onboarding", "claim", "renewal", "service", "campaign", "annual_review"]),
                "nps_score": nps_score,
                "comment_text": "Synthetic NPS comment influenced by engagement, complaint, and payment behavior.",
                "created_at": created,
                "updated_at": created,
            })
        if random.random() < 0.28:
            sat = int(max(1, min(5, round(random.gauss(4.2 - stats["complaints"] * 0.7 - stats["missed_payments"] * 0.03, 0.9)))))
            survey_day = random_day(start, end, seasonal=True)
            policy = random.choice(customer_policies) if customer_policies else None
            claim = random.choice(customer_claims) if customer_claims and random.random() < 0.25 else None
            writers["customer_satisfaction_surveys"].write({
                "customer_satisfaction_survey_id": new_id(),
                "customer_id": customer["customer_id"],
                "policy_id": policy["policy_id"] if policy else None,
                "claim_id": claim["claim_id"] if claim else None,
                "agent_id": policy["agent_id"] if policy else None,
                "survey_date": survey_day,
                "survey_type": random.choice(["onboarding", "claim", "renewal", "service", "annual_review"]),
                "channel": weighted_choice([("email", 0.42), ("sms", 0.22), ("web", 0.18), ("mobile_app", 0.14), ("phone", 0.04)]),
                "satisfaction_score": sat,
                "effort_score": int(max(1, min(7, round(random.gauss(3.0 + stats["complaints"] * 0.8, 1.2))))),
                "response_text": "Synthetic satisfaction survey response.",
                "created_at": created,
                "updated_at": created,
            })

        for snapshot_month in month_starts(start, end):
            if random.random() > 0.45:
                continue
            active_count = sum(1 for p in customer_policies if p["effective"] <= snapshot_month <= p["expiration"] and p["status"] in {"active", "renewed", "issued"})
            writers["customer_behavior_daily"].write({
                "customer_behavior_daily_id": new_id(),
                "customer_id": customer["customer_id"],
                "behavior_date": snapshot_month,
                "active_policy_count": active_count,
                "open_claim_count": sum(1 for c in customer_claims if c["loss_date"] <= snapshot_month),
                "payment_missed_count_90d": min(stats["missed_payments"], random.randint(0, max(0, stats["missed_payments"]))),
                "digital_event_count": min(stats["digital_events"], random.randint(0, max(1, stats["digital_events"]))),
                "service_request_count": stats["service_requests"],
                "complaint_count": stats["complaints"],
                "campaign_touch_count": stats["campaign_touches"],
                "quote_count_90d": stats["quotes"],
                "engagement_score": f"{customer['engagement']:.2f}",
                "churn_signal_score": f"{churn_risk:.4f}",
                "feature_snapshot": {
                    "income_band": customer["income_band"],
                    "tenure_days": tenure_days,
                    "propensity_signal": round(propensity, 4),
                    "lapse_signal": round(lapse_risk, 4),
                    "campaign_response_signal": round(campaign_response_prob, 4),
                },
                "created_at": created,
                "updated_at": created,
            })

    # Sales funnel tables: quote -> proposal -> application -> underwriting.
    opp_by_id = {o["opportunity_id"]: o for o in opportunity_refs}
    for i, lead in enumerate(lead_refs):
        if random.random() > min(0.92, 0.22 + lead["score"] / 120 + (0.18 if lead["campaign_id"] else 0)):
            continue
        opp = next((o for o in opportunity_refs if o["lead_id"] == lead["lead_id"]), None)
        quote_date = add_days(lead["received"], 1, 25)
        quoted = max(250, lead["score"] * random.uniform(40, 420))
        quote_status = "accepted" if lead["status"] == "converted" or (opp and opp["stage"] in {"bound", "application", "underwriting"}) else weighted_choice([("presented", 0.25), ("declined", 0.25), ("expired", 0.18), ("draft", 0.12), ("accepted", 0.16), ("withdrawn", 0.04)])
        quote_id = new_id()
        writers["quotes"].write({
            "quote_id": quote_id,
            "quote_number": f"QT-{i + 1:08d}",
            "lead_id": lead["lead_id"],
            "opportunity_id": opp["opportunity_id"] if opp else None,
            "customer_id": lead["customer_id"],
            "agent_id": lead["agent_id"],
            "product_id": lead["product_id"],
            "campaign_id": lead["campaign_id"],
            "quote_date": quote_date,
            "quote_status": quote_status,
            "quoted_premium": money(quoted),
            "sum_assured": money(quoted * random.uniform(30, 140)),
            "quote_channel": lead["lead_source"],
            "decline_reason": random.choice(["price", "coverage_mismatch", "deferred_decision", "competitor", "no_response"]) if quote_status in {"declined", "expired", "withdrawn"} else None,
            "quote_features": {"lead_score": round(lead["score"], 2), "campaign_attributed": bool(lead["campaign_id"])},
            "created_at": created,
            "updated_at": created,
        })
        quote_refs.append({"quote_id": quote_id, **lead, "quote_status": quote_status, "quote_date": quote_date, "quoted": quoted, "opportunity_id": opp["opportunity_id"] if opp else None})
        if lead["customer_id"]:
            customer_signal_stats[lead["customer_id"]]["quotes"] += 1

        if quote_status in {"accepted", "presented"} and random.random() < (0.72 if quote_status == "accepted" else 0.26):
            proposal_id = new_id()
            proposal_status = "converted" if quote_status == "accepted" and random.random() < 0.62 else weighted_choice([("presented", 0.35), ("accepted", 0.28), ("declined", 0.20), ("expired", 0.10), ("created", 0.07)])
            proposal_date = add_days(quote_date, 1, 20)
            writers["proposals"].write({
                "proposal_id": proposal_id,
                "proposal_number": f"PROP-{len(proposal_refs) + 1:08d}",
                "quote_id": quote_id,
                "opportunity_id": opp["opportunity_id"] if opp else None,
                "customer_id": lead["customer_id"],
                "agent_id": lead["agent_id"],
                "product_id": lead["product_id"],
                "proposal_date": proposal_date,
                "proposal_status": proposal_status,
                "proposed_premium": money(quoted * random.uniform(0.92, 1.12)),
                "proposed_sum_assured": money(quoted * random.uniform(35, 150)),
                "proposal_payload": {"needs_analysis_completed": random.random() < 0.82},
                "created_at": created,
                "updated_at": created,
            })
            proposal_refs.append({"proposal_id": proposal_id, **lead, "quote_id": quote_id, "proposal_status": proposal_status, "proposal_date": proposal_date, "opportunity_id": opp["opportunity_id"] if opp else None, "quoted": quoted})

            if proposal_status in {"accepted", "converted"} and lead["customer_id"] and random.random() < 0.76:
                application_id = new_id()
                customer = customer_by_id.get(lead["customer_id"])
                risk = customer["risk"] if customer else "medium"
                app_status = weighted_choice([("issued", 0.44), ("approved", 0.22), ("in_underwriting", 0.12), ("declined", 0.10), ("withdrawn", 0.08), ("submitted", 0.04)])
                application_date = add_days(proposal_date, 1, 16)
                writers["applications"].write({
                    "application_id": application_id,
                    "application_number": f"APP-{len(application_refs) + 1:08d}",
                    "proposal_id": proposal_id,
                    "quote_id": quote_id,
                    "opportunity_id": opp["opportunity_id"] if opp else None,
                    "customer_id": lead["customer_id"],
                    "agent_id": lead["agent_id"],
                    "product_id": lead["product_id"],
                    "application_date": application_date,
                    "application_status": app_status,
                    "requested_premium": money(quoted),
                    "requested_sum_assured": money(quoted * random.uniform(35, 150)),
                    "medical_required": risk in {"high", "very_high"} or random.random() < 0.22,
                    "application_payload": {"risk_tier": risk, "income_band": customer["income_band"] if customer else None},
                    "created_at": created,
                    "updated_at": created,
                })
                application_refs.append({"application_id": application_id, **lead, "application_status": app_status, "application_date": application_date})
                decision_status = "approved_standard"
                if app_status == "declined":
                    decision_status = "declined"
                elif risk == "very_high":
                    decision_status = weighted_choice([("approved_rated", 0.45), ("approved_exclusion", 0.18), ("postponed", 0.17), ("declined", 0.20)])
                elif risk == "high":
                    decision_status = weighted_choice([("approved_standard", 0.45), ("approved_rated", 0.30), ("approved_exclusion", 0.15), ("postponed", 0.06), ("declined", 0.04)])
                writers["underwriting_decisions"].write({
                    "underwriting_decision_id": new_id(),
                    "application_id": application_id,
                    "customer_id": lead["customer_id"],
                    "product_id": lead["product_id"],
                    "decision_date": add_days(application_date, 2, 30),
                    "decision_status": decision_status,
                    "risk_class": risk,
                    "rating_factor": f"{random.uniform(1.0, 1.8):.4f}" if decision_status == "approved_rated" else None,
                    "exclusion_applied": decision_status == "approved_exclusion",
                    "underwriting_reason": random.choice(["standard_risk", "medical_history", "financial_underwriting", "occupation", "deferred_evidence"]),
                    "decision_payload": {"model_risk_band": risk},
                    "created_at": created,
                    "updated_at": created,
                })

    # Policy lifecycle, renewals, lapse and premium increase signals.
    for policy in policy_refs:
        customer = customer_by_id[policy["customer_id"]]
        stats = customer_signal_stats[policy["customer_id"]]
        premium_increase_pct = max(0, random.gauss(0.035 + stats["missed_payments"] * 0.002 + len(claims_by_policy[policy["policy_id"]]) * 0.018, 0.045))
        stats["premium_increase_pct"] = max(stats["premium_increase_pct"], premium_increase_pct)
        writers["policy_events"].write({
            "policy_event_id": new_id(),
            "policy_id": policy["policy_id"],
            "customer_id": policy["customer_id"],
            "agent_id": policy["agent_id"],
            "event_ts": dt(policy["effective"]),
            "event_type": "issue",
            "event_reason": "policy_issued",
            "source_system": "synthetic_policy_admin",
            "old_status": None,
            "new_status": policy["status"],
            "premium_delta": money(policy["annual"]),
            "event_payload": {"base_annual": round(policy["base_annual"], 2), "rider_annual": round(policy["rider_annual"], 2)},
            "created_at": created,
            "updated_at": created,
        })
        renewal_due = policy["expiration"] - timedelta(days=30)
        renewal_status = "renewed" if policy["status"] == "renewed" else ("lapsed" if policy["status"] == "lapsed" else weighted_choice([("pending", 0.35), ("offered", 0.24), ("accepted", 0.18), ("declined", 0.08), ("cancelled", 0.04), ("renewed", 0.11)]))
        writers["policy_renewals"].write({
            "policy_renewal_id": new_id(),
            "policy_id": policy["policy_id"],
            "prior_policy_id": None,
            "renewal_policy_id": None,
            "customer_id": policy["customer_id"],
            "agent_id": policy["agent_id"],
            "renewal_cycle_date": policy["expiration"],
            "renewal_offer_date": policy["expiration"] - timedelta(days=60),
            "renewal_due_date": renewal_due,
            "renewal_status": renewal_status,
            "offered_premium": money(policy["annual"] * (1 + premium_increase_pct)),
            "expiring_premium": money(policy["annual"]),
            "premium_change_pct": f"{premium_increase_pct:.4f}",
            "retention_reason": random.choice(["accepted_value", "price_increase", "claim_experience", "payment_behavior", "agent_follow_up"]),
            "created_at": created,
            "updated_at": created,
        })
        writers["policy_events"].write({
            "policy_event_id": new_id(),
            "policy_id": policy["policy_id"],
            "customer_id": policy["customer_id"],
            "agent_id": policy["agent_id"],
            "event_ts": dt(policy["expiration"] - timedelta(days=60)),
            "event_type": "renewal_notice",
            "event_reason": "renewal_offer",
            "source_system": "synthetic_policy_admin",
            "old_status": policy["status"],
            "new_status": renewal_status,
            "premium_delta": money(policy["annual"] * premium_increase_pct),
            "event_payload": {"premium_increase_pct": round(premium_increase_pct, 4), "previous_claims": len(claims_by_policy[policy["policy_id"]])},
            "created_at": created,
            "updated_at": created,
        })
        lapse_prob = sigmoid(-3.0 + stats["missed_payments"] * 0.30 + stats["complaints"] * 0.65 + premium_increase_pct * 6 - max(0, (end - customer["acquisition"]).days) / 1700)
        if policy["status"] == "lapsed" or random.random() < lapse_prob:
            lapse_day = min(policy["expiration"], random_day(policy["effective"], min(policy["expiration"], end)))
            stage = "lapsed" if random.random() < 0.72 else "grace_period"
            reinstated = random.random() < (0.28 if customer["engagement"] > 65 else 0.12)
            writers["policy_lapse_events"].write({
                "policy_lapse_event_id": new_id(),
                "policy_id": policy["policy_id"],
                "customer_id": policy["customer_id"],
                "agent_id": policy["agent_id"],
                "lapse_event_date": lapse_day,
                "lapse_stage": "reinstated" if reinstated else stage,
                "missed_payment_count": max(1, stats["missed_payments"]),
                "days_past_due": random.randint(15, 120),
                "reinstatement_date": lapse_day + timedelta(days=random.randint(7, 65)) if reinstated else None,
                "lapse_reason": random.choice(["missed_payment", "premium_increase", "coverage_no_longer_needed", "service_issue", "replacement_policy"]),
                "intervention_type": random.choice(["agent_call", "sms_reminder", "payment_plan_offer", "retention_offer", "none"]),
                "created_at": created,
                "updated_at": created,
            })

    # Agent activity, targets, commission and attrition signals.
    active_agents = [a for a in agent_refs if a["status"] == "active"]
    for i, lead in enumerate(random.sample(lead_refs, min(len(lead_refs), int(len(lead_refs) * 0.62)))):
        if not lead["agent_id"]:
            continue
        customer = customer_by_id.get(lead["customer_id"]) if lead["customer_id"] else None
        call_day = random_day(lead["received"], min(end, lead["received"] + timedelta(days=45)), seasonal=False)
        outcome = weighted_choice([("contacted", 0.32), ("no_answer", 0.24), ("appointment_set", 0.16), ("quote_requested", 0.14), ("declined", 0.10), ("do_not_call", 0.04)])
        writers["agent_calls"].write({
            "agent_call_id": new_id(),
            "agent_id": lead["agent_id"],
            "customer_id": lead["customer_id"],
            "lead_id": lead["lead_id"],
            "opportunity_id": None,
            "campaign_id": lead["campaign_id"],
            "call_ts": dt(call_day),
            "call_direction": "outbound",
            "call_outcome": outcome,
            "duration_seconds": random.randint(15, 1800),
            "sentiment_score": f"{random.uniform(-0.4, 0.9):.2f}",
            "next_step_date": add_days(call_day, 2, 21) if outcome in {"contacted", "appointment_set", "quote_requested"} else None,
            "call_notes": "Synthetic agent call generated from lead and campaign activity.",
            "created_at": created,
            "updated_at": created,
        })
        agent_signal_stats[lead["agent_id"]]["calls"] += 1
        if outcome in {"appointment_set", "quote_requested"} and random.random() < 0.65:
            writers["agent_meetings"].write({
                "agent_meeting_id": new_id(),
                "agent_id": lead["agent_id"],
                "customer_id": lead["customer_id"],
                "lead_id": lead["lead_id"],
                "opportunity_id": None,
                "meeting_ts": dt(add_days(call_day, 2, 28)),
                "meeting_type": weighted_choice([("initial_consultation", 0.35), ("needs_analysis", 0.25), ("proposal_review", 0.18), ("application", 0.12), ("servicing", 0.04), ("renewal", 0.04), ("claim_support", 0.02)]),
                "meeting_channel": weighted_choice([("in_person", 0.38), ("video", 0.25), ("phone", 0.20), ("branch", 0.10), ("webinar", 0.07)]),
                "meeting_outcome": random.choice(["needs_identified", "quote_requested", "proposal_presented", "not_ready", "application_started"]),
                "duration_minutes": random.randint(20, 120),
                "product_id": lead["product_id"],
                "meeting_notes": "Synthetic meeting note for sales activity modelling.",
                "created_at": created,
                "updated_at": created,
            })
            agent_signal_stats[lead["agent_id"]]["meetings"] += 1

    for agent in agent_refs:
        agent_policies = policies_by_agent[agent["agent_id"]]
        for quarter_start in [m for m in month_starts(start, end) if m.month in {1, 4, 7, 10}]:
            quarter_end = (quarter_start.replace(day=28) + timedelta(days=95)).replace(day=1) - timedelta(days=1)
            target_value = max(5000, agent["performance"] * random.uniform(35000, 160000))
            actual = target_value * random.uniform(0.55, 1.45) * agent["performance"]
            writers["agent_targets"].write({
                "agent_target_id": new_id(),
                "agent_id": agent["agent_id"],
                "target_period_start": quarter_start,
                "target_period_end": min(quarter_end, end),
                "target_type": "premium",
                "product_id": None,
                "target_value": money(target_value),
                "actual_value": money(actual),
                "attainment_pct": f"{actual / target_value:.4f}",
                "created_at": created,
                "updated_at": created,
            })
        for policy in agent_policies[:80]:
            commission_period = policy["effective"].replace(day=1)
            commission_rate = random.uniform(0.025, 0.12)
            commission_amount = policy["annual"] * commission_rate
            writers["agent_commissions"].write({
                "agent_commission_id": new_id(),
                "agent_id": agent["agent_id"],
                "policy_id": policy["policy_id"],
                "product_id": policy["product_id"],
                "commission_period": commission_period,
                "commission_type": "new_business" if policy["status"] != "renewed" else "renewal",
                "premium_basis_amount": money(policy["annual"]),
                "commission_rate": f"{commission_rate:.4f}",
                "commission_amount": money(commission_amount),
                "paid_date": commission_period + timedelta(days=random.randint(20, 60)),
                "chargeback_flag": policy["status"] in {"lapsed", "cancelled"} and random.random() < 0.35,
                "created_at": created,
                "updated_at": created,
            })
            stats = agent_signal_stats[agent["agent_id"]]
            stats["commissions"] += commission_amount
            if commission_period < date(start.year + 1, 7, 1):
                stats["commission_h1"] += commission_amount
            else:
                stats["commission_h2"] += commission_amount
            if policy["status"] in {"lapsed", "cancelled"}:
                stats["chargebacks"] += 1
        for t in range(random.randint(1, 4)):
            assigned = random_day(start, end - timedelta(days=30), seasonal=True)
            completed = random.random() < (0.82 if agent["performance"] > 0.8 else 0.62)
            writers["agent_training"].write({
                "agent_training_id": new_id(),
                "agent_id": agent["agent_id"],
                "training_code": f"TRN-{random.choice(['PROD', 'COMP', 'SALES', 'LEAD'])}-{random.randint(100, 999)}",
                "training_name": random.choice(["Product Mastery", "Responsible Advice", "Digital Leads", "Claims Support", "Retirement Planning"]),
                "training_category": random.choice(["product", "compliance", "sales", "leadership"]),
                "assigned_date": assigned,
                "completed_date": add_days(assigned, 3, 60) if completed else None,
                "completion_status": "completed" if completed else weighted_choice([("assigned", 0.35), ("in_progress", 0.45), ("expired", 0.15), ("waived", 0.05)]),
                "assessment_score": f"{max(40, min(100, random.gauss(78 + agent['performance'] * 8, 12))):.2f}" if completed else None,
                "certification_flag": completed and random.random() < 0.4,
                "created_at": created,
                "updated_at": created,
            })
        stats = agent_signal_stats[agent["agent_id"]]
        decline = stats["commission_h2"] < stats["commission_h1"] * 0.72
        attrition_prob = sigmoid(-3.4 + (1.2 if decline else 0) - agent["performance"] + stats["chargebacks"] * 0.08 + (1.0 if agent["status"] == "terminated" else 0))
        if agent["status"] == "terminated" or random.random() < attrition_prob:
            writers["agent_attrition_events"].write({
                "agent_attrition_event_id": new_id(),
                "agent_id": agent["agent_id"],
                "event_date": random_day(start, end, seasonal=True),
                "attrition_stage": "terminated" if agent["status"] == "terminated" else weighted_choice([("risk_signal", 0.45), ("notice", 0.18), ("inactive", 0.16), ("retained", 0.14), ("reactivated", 0.07)]),
                "attrition_reason": random.choice(["declining_commissions", "low_activity", "career_change", "compliance_issue", "territory_change"]),
                "voluntary_flag": random.random() < 0.72,
                "manager_intervention_flag": random.random() < 0.45,
                "intervention_notes": "Synthetic manager coaching or retention intervention.",
                "created_at": created,
                "updated_at": created,
            })

    # Claims enrichment and fraud indicators.
    for claim in claim_refs:
        customer = customer_by_id[claim["customer_id"]]
        claim_party_id = new_id()
        writers["claim_parties"].write({
            "claim_party_id": claim_party_id,
            "claim_id": claim["claim_id"],
            "party_id": customer["party_id"],
            "customer_id": customer["customer_id"],
            "role_type": "insured",
            "relationship_to_insured": "self",
            "provider_specialty": None,
            "involvement_notes": "Synthetic insured party on claim.",
            "created_at": created,
            "updated_at": created,
        })
        if random.random() < 0.55:
            writers["claim_parties"].write({
                "claim_party_id": new_id(),
                "claim_id": claim["claim_id"],
                "party_id": None,
                "customer_id": None,
                "role_type": weighted_choice([("provider", 0.72), ("witness", 0.08), ("third_party", 0.12), ("adjuster", 0.08)]),
                "relationship_to_insured": None,
                "provider_specialty": random.choice(["hospital", "clinic", "oncology", "surgery", "rehabilitation"]),
                "involvement_notes": "Synthetic external claim party.",
                "created_at": created,
                "updated_at": created,
            })
        severity = min(1, (claim["paid"] + claim["reserve"]) / 250000)
        writers["claim_assessments"].write({
            "claim_assessment_id": new_id(),
            "claim_id": claim["claim_id"],
            "assessed_by_agent_id": claim["agent_id"],
            "assessment_date": claim["loss_date"] + timedelta(days=random.randint(1, 35)),
            "assessment_type": weighted_choice([("initial", 0.42), ("medical", 0.24), ("damage", 0.10), ("liability", 0.08), ("fraud_review", 0.06), ("settlement", 0.08), ("reopen_review", 0.02)]),
            "severity_score": f"{severity:.4f}",
            "liability_pct": f"{random.uniform(0.35, 1.0):.4f}",
            "estimated_loss_amount": money((claim["paid"] + claim["reserve"]) * random.uniform(0.9, 1.35)),
            "recommended_reserve_amount": money(claim["reserve"] * random.uniform(0.9, 1.4)),
            "assessment_outcome": random.choice(["pay", "review", "request_documents", "settle", "refer_fraud"]),
            "assessment_notes": "Synthetic claim assessment note.",
            "created_at": created,
            "updated_at": created,
        })
        fraud_prob = sigmoid(-4.0 + severity * 2.0 + customer_signal_stats[customer["customer_id"]]["claims"] * 0.35 + (1.0 if customer["risk"] == "very_high" else 0))
        if random.random() < fraud_prob:
            customer_signal_stats[customer["customer_id"]]["fraud_indicators"] += 1
            writers["claim_fraud_indicators"].write({
                "claim_fraud_indicator_id": new_id(),
                "claim_id": claim["claim_id"],
                "customer_id": customer["customer_id"],
                "indicator_date": claim["loss_date"] + timedelta(days=random.randint(2, 60)),
                "indicator_type": random.choice(["unusual_provider_pattern", "late_reporting", "duplicate_document", "high_severity_outlier", "network_link"]),
                "indicator_source": weighted_choice([("rules", 0.38), ("model", 0.28), ("adjuster", 0.18), ("provider_network", 0.08), ("external", 0.04), ("manual_review", 0.04)]),
                "indicator_score": f"{min(0.99, max(0.05, fraud_prob + random.uniform(-0.08, 0.18))):.4f}",
                "severity": weighted_choice([("low", 0.25), ("medium", 0.38), ("high", 0.27), ("critical", 0.10)]),
                "resolved_flag": random.random() < 0.66,
                "resolution_outcome": random.choice(["cleared", "confirmed", "inconclusive", "referred"]),
                "indicator_payload": {"severity_signal": round(severity, 4), "prior_claim_count": customer_signal_stats[customer["customer_id"]]["claims"]},
                "created_at": created,
                "updated_at": created,
            })

    # ML labels, feature store rows, scores, predictions and next-best-action history.
    product_by_lob = defaultdict(list)
    for product in base_products:
        product_by_lob[product["lob"]].append(product)

    for customer in customer_refs:
        stats = customer_signal_stats[customer["customer_id"]]
        customer_policies = policies_by_customer[customer["customer_id"]]
        tenure_days = max(0, (end - customer["acquisition"]).days)
        propensity_prob = sigmoid(-2.1 + customer["engagement"] / 28 + customer["income_score"] / 45 + stats["campaign_positive"] * 0.12 - stats["complaints"] * 0.35)
        churn_prob = sigmoid(-2.8 + stats["missed_payments"] * 0.16 + stats["complaints"] * 0.75 - customer["engagement"] / 65 - tenure_days / 1800)
        claim_prob = sigmoid(-3.2 + stats["claims"] * 0.65 + (0.9 if customer["risk"] in {"high", "very_high"} else 0) + len(customer_policies) * 0.14)
        campaign_prob = sigmoid(-2.4 + customer["engagement"] / 35 + stats["campaign_positive"] * 0.22 + (0.35 if customer["income_score"] > 72 else 0))
        owned_lobs = {p["product"]["lob"] for p in customer_policies}
        candidate_lobs = [lob for lob in ["health", "life", "critical_illness", "savings", "wealth", "investment_linked"] if lob not in owned_lobs and product_by_lob.get(lob)]
        if not candidate_lobs:
            candidate_lobs = list(product_by_lob)
        if customer["income_score"] > 78 and "wealth" in product_by_lob:
            nbp = random.choice(product_by_lob["wealth"])
        elif customer["segment"] == "family_protection" and "life" in product_by_lob:
            nbp = random.choice(product_by_lob["life"])
        elif customer["segment"] == "health_focused" and "critical_illness" in product_by_lob:
            nbp = random.choice(product_by_lob["critical_illness"])
        else:
            nbp = random.choice(product_by_lob[random.choice(candidate_lobs)])

        labels = {
            "propensity_to_buy_label": bool_label(propensity_prob),
            "next_best_product_label": nbp["code"],
            "churn_label": bool_label(churn_prob),
            "lapse_label": None,
            "lead_conversion_label": None,
            "agent_attrition_label": None,
            "claim_occurrence_label": bool_label(claim_prob),
            "fraud_label": None,
            "campaign_response_label": bool_label(campaign_prob),
        }
        write_ml_label(writers, "customer", customer["customer_id"], customer, None, None, None, None, None, end, labels, created)
        feature_id = write_model_feature(writers, "customer_360", "v1", "customer", customer["customer_id"], customer, None, None, None, None, None, None, nbp["product_id"], end, 180, {
            "engagement_score": round(customer["engagement"], 2),
            "income_score": round(customer["income_score"], 2),
            "income_band": customer["income_band"],
            "tenure_days": tenure_days,
            "missed_payments": stats["missed_payments"],
            "complaints": stats["complaints"],
            "claims": stats["claims"],
            "campaign_positive": stats["campaign_positive"],
        }, "propensity_to_buy_label", labels["propensity_to_buy_label"], created)
        score_id = write_model_score(writers, "propensity_to_buy", "v1", feature_id, "customer", customer["customer_id"], "propensity_to_buy", propensity_prob, created, len(model_score_refs) + 1)
        model_score_refs.append(score_id)
        prediction_id = write_model_prediction(writers, score_id, "propensity_to_buy", "v1", "propensity_to_buy", "customer", customer["customer_id"], 180, "buy" if labels["propensity_to_buy_label"] else "not_buy", None, propensity_prob, nbp["product_id"], {"next_best_product_code": nbp["code"]}, created)
        if labels["propensity_to_buy_label"] or random.random() < 0.18:
            agent = weighted_agent([a for a in active_agents if a["market"] == customer["market"]]) or random.choice(agent_refs)
            writers["next_best_actions"].write({
                "next_best_action_id": new_id(),
                "model_prediction_id": prediction_id,
                "customer_id": customer["customer_id"],
                "agent_id": agent["agent_id"],
                "policy_id": random.choice(customer_policies)["policy_id"] if customer_policies else None,
                "lead_id": random.choice(leads_by_customer[customer["customer_id"]])["lead_id"] if leads_by_customer[customer["customer_id"]] else None,
                "campaign_id": random.choice(campaign_refs)["campaign_id"] if random.random() < 0.45 else None,
                "product_id": nbp["product_id"],
                "action_type": weighted_choice([("offer_product", 0.34), ("call_customer", 0.24), ("send_campaign", 0.16), ("retention_outreach", 0.14), ("renewal_follow_up", 0.06), ("service_recovery", 0.06)]),
                "action_rank": random.randint(1, 5),
                "priority_score": f"{propensity_prob:.6f}",
                "expected_value": money(propensity_prob * customer["income_score"] * random.uniform(80, 650)),
                "due_date": add_days(end, 1, 45),
                "action_status": weighted_choice([("recommended", 0.45), ("accepted", 0.16), ("assigned", 0.18), ("completed", 0.12), ("dismissed", 0.05), ("expired", 0.04)]),
                "outcome": random.choice(["pending", "contacted", "quoted", "converted", "no_response"]),
                "outcome_value": money(propensity_prob * random.uniform(0, 5000)),
                "action_reason": "High propensity, product gap, campaign response, or retention signal.",
                "created_at": created,
                "updated_at": created,
            })

    for policy in policy_refs:
        customer = customer_by_id[policy["customer_id"]]
        stats = customer_signal_stats[policy["customer_id"]]
        lapse_prob = sigmoid(-3.0 + stats["missed_payments"] * 0.30 + stats["complaints"] * 0.65 + stats["premium_increase_pct"] * 6 - max(0, (end - customer["acquisition"]).days) / 1700)
        labels = {"lapse_label": 1 if policy["status"] == "lapsed" else bool_label(lapse_prob)}
        write_ml_label(writers, "policy", policy["policy_id"], customer, policy, None, None, None, None, end, labels, created)
        feature_id = write_model_feature(writers, "policy_lapse", "v1", "policy", policy["policy_id"], customer, policy, None, None, None, None, None, policy["product_id"], end, 90, {
            "missed_payments": stats["missed_payments"],
            "complaints": stats["complaints"],
            "premium_increase_pct": round(stats["premium_increase_pct"], 4),
            "policy_status": policy["status"],
            "prior_claims": len(claims_by_policy[policy["policy_id"]]),
        }, "lapse_label", labels["lapse_label"], created)
        score_id = write_model_score(writers, "policy_lapse", "v1", feature_id, "policy", policy["policy_id"], "lapse_risk", lapse_prob, created, None)
        write_model_prediction(writers, score_id, "policy_lapse", "v1", "policy_lapse", "policy", policy["policy_id"], 90, "lapse" if labels["lapse_label"] else "retain", None, lapse_prob, None, {}, created)

    for lead in lead_refs:
        conversion_prob = sigmoid(-2.6 + lead["score"] / 25 + (0.45 if lead["campaign_id"] else 0) + (agent_by_id.get(lead["agent_id"], {}).get("performance", 0.8) if lead["agent_id"] else 0) / 2)
        labels = {"lead_conversion_label": 1 if lead["status"] == "converted" else bool_label(conversion_prob)}
        customer = customer_by_id.get(lead["customer_id"]) if lead["customer_id"] else None
        write_ml_label(writers, "lead", lead["lead_id"], customer, None, agent_by_id.get(lead["agent_id"]) if lead["agent_id"] else None, lead, None, None, end, labels, created)

    for agent in agent_refs:
        stats = agent_signal_stats[agent["agent_id"]]
        decline = stats["commission_h2"] < stats["commission_h1"] * 0.72
        attrition_prob = sigmoid(-3.4 + (1.2 if decline else 0) - agent["performance"] + stats["chargebacks"] * 0.08 + (1.0 if agent["status"] == "terminated" else 0))
        labels = {"agent_attrition_label": 1 if agent["status"] == "terminated" else bool_label(attrition_prob)}
        write_ml_label(writers, "agent", agent["agent_id"], None, None, agent, None, None, None, end, labels, created)

    for claim in claim_refs:
        customer = customer_by_id[claim["customer_id"]]
        fraud_prob = sigmoid(-4.0 + min(1, (claim["paid"] + claim["reserve"]) / 250000) * 2.0 + customer_signal_stats[customer["customer_id"]]["claims"] * 0.35 + (1.0 if customer["risk"] == "very_high" else 0))
        labels = {"fraud_label": bool_label(fraud_prob)}
        write_ml_label(writers, "claim", claim["claim_id"], customer, None, agent_by_id.get(claim["agent_id"]) if claim["agent_id"] else None, None, claim, None, end, labels, created)

    for response in response_refs[: min(len(response_refs), 60000)]:
        customer = customer_by_id.get(response["customer_id"]) if response["customer_id"] else None
        labels = {"campaign_response_label": 1 if response["response_type"] in {"clicked", "called", "quoted", "converted"} else 0}
        write_ml_label(writers, "campaign_response", response["response_id"], customer, None, None, None, None, response["campaign_id"], response["response_date"], labels, created)


def write_ml_label(writers, entity_type, entity_id, customer, policy, agent, lead, claim, campaign_id, as_of_date, labels, created):
    writers["ml_training_labels"].write({
        "label_snapshot_id": new_id(),
        "entity_type": entity_type,
        "entity_id": entity_id,
        "customer_id": customer["customer_id"] if customer else (policy["customer_id"] if policy else None),
        "agent_id": agent["agent_id"] if agent else (policy["agent_id"] if policy else None),
        "policy_id": policy["policy_id"] if policy and "policy_id" in policy else None,
        "lead_id": lead["lead_id"] if lead else None,
        "claim_id": claim["claim_id"] if claim else None,
        "campaign_id": campaign_id,
        "as_of_date": as_of_date,
        "propensity_to_buy_label": labels.get("propensity_to_buy_label"),
        "next_best_product_label": labels.get("next_best_product_label"),
        "churn_label": labels.get("churn_label"),
        "lapse_label": labels.get("lapse_label"),
        "lead_conversion_label": labels.get("lead_conversion_label"),
        "agent_attrition_label": labels.get("agent_attrition_label"),
        "claim_occurrence_label": labels.get("claim_occurrence_label"),
        "fraud_label": labels.get("fraud_label"),
        "campaign_response_label": labels.get("campaign_response_label"),
        "feature_summary": {k: v for k, v in labels.items() if v is not None},
        "created_at": created,
    })


def write_model_feature(writers, feature_set_name, feature_set_version, entity_type, entity_id, customer, policy, agent, lead, opportunity, claim, campaign_id, product_id, feature_date, horizon, features, label_name, label_value, created) -> str:
    feature_id = new_id()
    feature_text = json.dumps(features, sort_keys=True)
    writers["model_features"].write({
        "model_feature_id": feature_id,
        "feature_set_name": feature_set_name,
        "feature_set_version": feature_set_version,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "customer_id": customer["customer_id"] if customer else (policy["customer_id"] if policy else None),
        "policy_id": policy["policy_id"] if policy else None,
        "agent_id": agent["agent_id"] if agent else (policy["agent_id"] if policy else None),
        "lead_id": lead["lead_id"] if lead else None,
        "opportunity_id": opportunity["opportunity_id"] if opportunity else None,
        "claim_id": claim["claim_id"] if claim else None,
        "campaign_id": campaign_id,
        "product_id": product_id,
        "feature_date": feature_date,
        "prediction_horizon_days": horizon,
        "features": features,
        "label_name": label_name,
        "label_value": {label_name: label_value},
        "data_split": weighted_choice([("train", 0.70), ("validation", 0.15), ("test", 0.10), ("score", 0.05)]),
        "feature_hash": make_hash(feature_text),
        "created_at": created,
        "updated_at": created,
    })
    return feature_id


def write_model_score(writers, model_name, model_version, feature_id, entity_type, entity_id, score_name, probability, created, rank) -> str:
    score_id = new_id()
    writers["model_scores"].write({
        "model_score_id": score_id,
        "model_name": model_name,
        "model_version": model_version,
        "model_feature_id": feature_id,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "score_ts": created,
        "score_name": score_name,
        "score_value": f"{probability:.6f}",
        "probability": f"{probability:.6f}",
        "score_band": "very_high" if probability >= 0.8 else "high" if probability >= 0.6 else "medium" if probability >= 0.35 else "low",
        "rank_within_segment": rank,
        "explanation": {"top_drivers": ["engagement", "payment_behavior", "complaints", "income", "claims"]},
        "created_at": created,
        "updated_at": created,
    })
    return score_id


def write_model_prediction(writers, score_id, model_name, model_version, prediction_type, entity_type, entity_id, horizon, label, value, probability, recommended_product_id, payload, created) -> str:
    prediction_id = new_id()
    writers["model_predictions"].write({
        "model_prediction_id": prediction_id,
        "model_score_id": score_id,
        "model_name": model_name,
        "model_version": model_version,
        "prediction_type": prediction_type,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "prediction_ts": created,
        "prediction_horizon_days": horizon,
        "predicted_label": label,
        "predicted_value": value,
        "probability": f"{probability:.6f}" if probability is not None else None,
        "confidence_score": f"{min(0.99, max(0.45, 0.55 + (probability or 0) * 0.4)):.6f}" if probability is not None else None,
        "recommended_product_id": recommended_product_id,
        "prediction_payload": payload,
        "created_at": created,
        "updated_at": created,
    })
    return prediction_id


def write_glossary_and_semantics(writers, glossary_refs, created, include_embeddings: bool):
    terms = [
        ("Written Premium", "premium", "Premium amount recorded when a policy or endorsement is issued.", "sum(written_premium_amount)", ["WP", "sales premium"]),
        ("Earned Premium", "premium", "Portion of premium recognized for coverage already provided.", "sum(earned_premium_amount)", ["EP"]),
        ("Loss Ratio", "claims", "Claims incurred divided by earned premium for a period.", "sum(paid_amount + reserve_amount) / nullif(sum(earned_premium_amount), 0)", ["claims ratio"]),
        ("Conversion Rate", "campaign", "Converted campaign responses divided by sent or selected targets.", "count(converted) / nullif(count(targets), 0)", ["campaign conversion"]),
        ("MAPA", "agent", "Monthly marketing, activity, production, and agent performance measures.", None, ["agent metrics", "monthly activity"]),
        ("Persistency", "policy", "Share of policies retained or renewed over a period.", "retained_policy_count / nullif(retained_policy_count + lapsed_policy_count, 0)", ["retention"]),
        ("Quote to Bind", "sales", "Policies bound divided by quotes generated.", "policies_bound_count / nullif(quotes_count, 0)", ["bind rate"]),
    ]
    for term, domain, definition, sql, synonyms in terms:
        glossary_id = new_id()
        writers["business_glossary"].write({
            "glossary_id": glossary_id,
            "term": term,
            "domain": domain,
            "definition": definition,
            "calculation_sql": sql,
            "synonyms": synonyms,
            "owner": "Insurance Analytics CoE",
            "active_flag": True,
            "created_at": created,
            "updated_at": created,
        })
        glossary_refs.append((glossary_id, term, domain, definition, synonyms))

    docs = []
    for glossary_id, term, domain, definition, synonyms in glossary_refs:
        docs.append((glossary_id, "glossary", None, None, None, term, f"{term}: {definition}. Synonyms: {', '.join(synonyms)}.", [domain, "metric"]))
    docs.extend([
        (None, "table", "public", "policies", None, "Policies table", "Policy contract headers linked to customers, agents, products, opportunities, dates, statuses, and premium summaries.", ["policy", "contract"]),
        (None, "table", "public", "claims", None, "Claims table", "Claim records contain loss dates, report dates, status, cause, paid amount, reserve amount, and catastrophe or litigation indicators.", ["claim", "loss"]),
        (None, "table", "public", "campaign_responses", None, "Campaign responses table", "Marketing responses attribute delivered, opened, clicked, quoted, and converted outcomes back to campaigns, leads, opportunities, and policies.", ["campaign", "attribution"]),
        (None, "example_question", None, None, None, "Loss ratio by product", "Question: Show loss ratio by line of business and market for the last 12 months. Use claims, policies, products, and premiums joined by policy_id.", ["example", "claims"]),
        (None, "example_question", None, None, None, "Agent conversion performance", "Question: Which agents had the highest quote-to-bind rate last quarter? Use agent_mapa_metrics grouped by agent_id and metric_month.", ["example", "agent"]),
    ])
    for glossary_id, doc_type, schema, table, column, title, content, tags in docs:
        writers["semantic_documents"].write({
            "semantic_document_id": new_id(),
            "glossary_id": glossary_id,
            "document_type": doc_type,
            "source_schema": schema,
            "source_table": table,
            "source_column": column,
            "title": title,
            "content": content,
            "tags": tags,
            "content_hash": make_hash(content),
            "embedding_model": "synthetic-placeholder-1536",
            "embedding": fake_embedding() if include_embeddings else None,
            "active_flag": True,
            "created_at": created,
            "updated_at": created,
        })


def write_query_audit(writers, created):
    examples = [
        ("What was written premium by market last quarter?", "executed", 20),
        ("Which campaigns converted the most PRUCancer 360 premium?", "executed", 15),
        ("Show loss ratio by line of business for Singapore health products.", "executed", 12),
        ("Delete failed payments for old customers", "blocked", None),
        ("Which transferred agents had declining persistency?", "executed", 50),
    ]
    for question, status, rows in examples:
        writers["query_audit_log"].write({
            "query_audit_log_id": new_id(),
            "user_id": None,
            "session_id": new_id(),
            "question": question,
            "retrieved_semantic_document_ids": [],
            "generated_sql": "select ... from analytics approved views limit 1000" if status != "blocked" else None,
            "execution_status": status,
            "safety_decision": "allowed_select" if status != "blocked" else "blocked_non_select",
            "error_message": None if status != "blocked" else "Only SELECT analytics queries are allowed.",
            "row_count": rows,
            "duration_ms": random.randint(80, 1800),
            "feedback_rating": random.choice([4, 5, None]),
            "created_at": created,
            "updated_at": created,
        })


def write_manifest(output_dir: Path, counts: dict[str, int], args) -> None:
    manifest = {
        "generated_at": now_ts().isoformat(),
        "seed": args.seed,
        "start_year": args.start_year,
        "counts": counts,
        "note": "Synthetic fictional data inspired by public Singapore/Hong Kong Prudential product and campaign themes.",
    }
    (output_dir / "_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    load_order = [
        "parties.csv",
        "products.csv",
        "customers.csv",
        "addresses.csv",
        "agents.csv",
        "agent_movements.csv",
        "campaigns.csv",
        "leads.csv",
        "opportunities.csv",
        "policies.csv",
        "policy_coverages.csv",
        "premiums.csv",
        "payments.csv",
        "claims.csv",
        "campaign_targets.csv",
        "campaign_responses.csv",
        "customer_engagement_events.csv",
        "agent_mapa_metrics.csv",
        "business_glossary.csv",
        "semantic_documents.csv",
        "query_audit_log.csv",
        "customer_behavior_daily.csv",
        "customer_digital_events.csv",
        "customer_complaints.csv",
        "customer_satisfaction_surveys.csv",
        "customer_nps.csv",
        "customer_service_requests.csv",
        "policy_events.csv",
        "policy_renewals.csv",
        "policy_lapse_events.csv",
        "quotes.csv",
        "proposals.csv",
        "applications.csv",
        "underwriting_decisions.csv",
        "agent_calls.csv",
        "agent_meetings.csv",
        "agent_targets.csv",
        "agent_commissions.csv",
        "agent_training.csv",
        "agent_attrition_events.csv",
        "claim_parties.csv",
        "claim_assessments.csv",
        "claim_fraud_indicators.csv",
        "model_features.csv",
        "model_scores.csv",
        "model_predictions.csv",
        "next_best_actions.csv",
        "ml_training_labels.csv",
    ]
    (output_dir / "load_order.txt").write_text("\n".join(load_order) + "\n", encoding="utf-8")
    validation = {
        "required_core_counts": {
            "customers": args.customers,
            "policies": args.policies,
            "agents": args.agents,
            "campaigns": args.campaigns,
        },
        "actual_counts": counts,
        "relationship_checks": {
            "policy_headers_use_base_products_only": "validated by generator product selection",
            "policy_coverages_reference_products": "base coverage and rider coverage rows carry product_id",
            "premiums_reference_policy_coverages": "premium rows are allocated to base and rider coverage rows",
            "model_scores_after_model_features": "load_order places model_features before model_scores",
            "model_predictions_after_model_scores": "load_order places model_scores before model_predictions",
            "next_best_actions_after_predictions": "load_order places model_predictions before next_best_actions",
        },
        "hidden_patterns": [
            "missed payments increase lapse probability",
            "high engagement and high income increase propensity to buy",
            "complaints increase churn and service risk",
            "high MAPA/activity agents have stronger sales conversion",
            "declining commissions increase agent attrition risk",
            "prior claims change renewal and fraud/claim likelihood",
            "campaign responders have higher conversion probability",
            "long-tenure customers have higher retention probability",
            "premium increases increase lapse risk",
        ],
    }
    (output_dir / "validation_checks.json").write_text(json.dumps(validation, indent=2), encoding="utf-8")


def parse_args():
    parser = argparse.ArgumentParser(description="Generate synthetic insurance analytics CSVs for Supabase.")
    parser.add_argument("--output-dir", default="data", help="Directory for generated CSV files.")
    parser.add_argument("--seed", type=int, default=20260529)
    parser.add_argument("--start-year", type=int, default=2023)
    parser.add_argument("--customers", type=int, default=10_000)
    parser.add_argument("--policies", type=int, default=20_000)
    parser.add_argument("--agents", type=int, default=6_000)
    parser.add_argument("--campaigns", type=int, default=800)
    parser.add_argument("--engagement-events", type=int, default=120_000)
    parser.add_argument("--min-targets-per-campaign", type=int, default=65)
    parser.add_argument("--max-targets-per-campaign", type=int, default=150)
    parser.add_argument("--include-fake-embeddings", action="store_true", help="Write placeholder 1536-dimension vectors. Omit for smaller CSVs and embed later.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    counts = generate(args)
    print("Generated synthetic insurance CSV files:")
    for table, count in counts.items():
        print(f"  {table}: {count:,}")


if __name__ == "__main__":
    main()
