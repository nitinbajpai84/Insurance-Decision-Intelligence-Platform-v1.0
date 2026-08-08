#!/usr/bin/env python3
"""
Insurance PoC V2.0 — DuckDB seeder.

Strategy:
  1. Reuse the V1 synthetic data (..\\data\\*.csv) wherever a table has a CSV.
     Loading is column-name-intersection based, so the DuckDB schema and the
     CSVs do not need to match exactly.
  2. Generate new rows ONLY for tables that are new in V2 (households,
     household_members, customer_type, policy_type_config, agent_performance
     derived fields, agent_service_events, agent_assessments, model_versions,
     vector_index_log, agent_reasoning_log, semantic_cache) and to top up
     minimum row counts (500 customers, 200 agents, 1000 policies,
     50 campaigns, 200 claims, 30 semantic documents, 100 glossary terms).
  3. Singapore insurance context: SGD amounts, SG regions, PRU-style products.

Run:  python seed_data.py
Requires:  pip install duckdb
"""
from __future__ import annotations

import hashlib
import json
import os
import random
import sys
import uuid
from datetime import date, datetime, timedelta
from pathlib import Path

import duckdb

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
DATA_DIR = PROJECT_ROOT / "data"

random.seed(20260610)


def resolve_duckdb_path() -> str:
    """DUCKDB_PATH from environment, then database\\.env, then default."""
    value = os.environ.get("DUCKDB_PATH", "").strip()
    if value:
        return value
    env_file = SCRIPT_DIR / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("DUCKDB_PATH="):
                return line.split("=", 1)[1].strip().strip('"')
    return str(SCRIPT_DIR / "insurance_v2.duckdb")


DUCKDB_PATH = resolve_duckdb_path()

# ---------------------------------------------------------------------------
# V1 CSV -> V2 table mapping (renames handled here)
# ---------------------------------------------------------------------------
CSV_TABLE_MAP: dict[str, str] = {
    "parties.csv": "parties",
    "customers.csv": "customers",
    "addresses.csv": "addresses",
    "customer_digital_events.csv": "customer_digital_events",
    "customer_behavior_daily.csv": "customer_behavior_daily",
    "customer_engagement_events.csv": "customer_engagement_events",
    "customer_satisfaction_surveys.csv": "customer_satisfaction_survey",  # rename
    "customer_service_requests.csv": "customer_service_requests",
    "customer_complaints.csv": "customer_complaints",
    "policies.csv": "policies",
    "policy_coverages.csv": "policy_coverage",  # rename
    "policy_renewals.csv": "policy_renewals",
    "policy_events.csv": "policy_events",
    "policy_lapse_events.csv": "policy_lapse_events",
    "agents.csv": "agents",
    "agent_mapa_metrics.csv": "agent_performance",  # V2 rollup table
    "agent_training.csv": "agent_training",
    "agent_calls.csv": "agent_calls",
    "agent_meetings.csv": "agent_meetings",
    "agent_commissions.csv": "agent_commissions",
    "agent_targets.csv": "agent_targets",
    "leads.csv": "leads",
    "opportunities.csv": "opportunities",
    "proposals.csv": "proposals",
    "applications.csv": "applications",
    "quotes.csv": "quotes",
    "claim_parties.csv": "claim_parties",
    "campaigns.csv": "campaigns",
    "campaign_responses.csv": "campaign_responses",
    "campaign_targets.csv": "campaign_targets",
    "next_best_actions.csv": "next_best_actions",
    "claims.csv": "claims",
    "claim_fraud_indicators.csv": "claim_fraud_indicators",
    "claim_assessments.csv": "claim_assessments",
    "products.csv": "products",
    "payments.csv": "payments",
    "premiums.csv": "premiums",
    "model_predictions.csv": "model_predictions",
    "model_features.csv": "model_features",
    "model_scores.csv": "model_scores",
    "underwriting_decisions.csv": "underwriting_decisions",
    "semantic_documents.csv": "semantic_documents",
    "query_audit_log.csv": "query_audit_log",
    "business_glossary.csv": "business_glossary",
}

# Special CSV->table column renames (csv_column -> table_column)
COLUMN_RENAMES: dict[str, dict[str, str]] = {
    "agent_performance": {"agent_mapa_metric_id": "agent_performance_id"},
}

MIN_COUNTS = {
    "customers": 500,
    "agents": 200,
    "policies": 1000,
    "campaigns": 50,
    "claims": 200,
    "semantic_documents": 30,
    "business_glossary": 100,
}

SG_REGIONS = ["SG Central", "SG East", "SG West", "SG North", "SG North-East"]
SG_SEGMENTS = [
    "Young family", "Established professional", "Pre-retiree",
    "Affluent investor", "New-to-workforce", "Silver generation",
]
PRU_PRODUCTS = [
    ("PRUShield Premier", "Health"), ("PRUExtra Premier CoPay", "Health"),
    ("PRUActive Life III", "Protection"), ("PRUTerm Vantage", "Protection"),
    ("PRUWealth Plus", "Savings"), ("PRUSave Flexi", "Savings"),
    ("PRULink Enhanced Growth", "Investment"), ("PRUVantage Assure", "Investment"),
    ("PRUActive Cash", "Savings"), ("PRUCancer 360", "Health"),
    ("PRUEarly Stage Crisis Cover", "Protection"), ("PRURetirement Income", "Savings"),
]
SG_FIRST = ["Wei Ling", "Mei", "Jun Jie", "Hui Min", "Kai", "Siti", "Arun", "Priya",
            "Daniel", "Rachel", "Marcus", "Aisyah", "Zhi Hao", "Nurul", "Ethan", "Grace"]
SG_LAST = ["Tan", "Lim", "Lee", "Ng", "Wong", "Chua", "Goh", "Ong",
           "Kumar", "Rahman", "Teo", "Koh", "Chen", "Ho", "Yeo", "Ismail"]


def uid() -> str:
    return str(uuid.uuid4())


def rand_date(start_year=2022, end_year=2026) -> date:
    start = date(start_year, 1, 1)
    span = (date(end_year, 5, 31) - start).days
    return start + timedelta(days=random.randint(0, span))


def now() -> datetime:
    return datetime.now()


def log(msg: str) -> None:
    print(f"[seed] {msg}")


# ---------------------------------------------------------------------------
# CSV loading (column-name intersection + TRY_CAST to schema types)
# ---------------------------------------------------------------------------
def table_columns(conn, table: str) -> dict[str, str]:
    rows = conn.execute(f"PRAGMA table_info('{table}')").fetchall()
    return {row[1]: row[2] for row in rows}  # name -> type


def load_csv(conn, table: str, csv_path: Path) -> int:
    cols = table_columns(conn, table)
    renames = COLUMN_RENAMES.get(table, {})
    csv_cols = [
        row[0]
        for row in conn.execute(
            "DESCRIBE SELECT * FROM read_csv_auto(?, header=true, all_varchar=true)",
            [str(csv_path)],
        ).fetchall()
    ]
    pairs = []  # (csv_col, table_col, type)
    for c in csv_cols:
        target = renames.get(c, c)
        if target in cols:
            pairs.append((c, target, cols[target]))
    if not pairs:
        log(f"WARN {table}: no overlapping columns with {csv_path.name}; skipped")
        return 0
    select_list = ", ".join(f'TRY_CAST("{c}" AS {t}) AS "{tc}"' for c, tc, t in pairs)
    insert_cols = ", ".join(f'"{tc}"' for _, tc, _ in pairs)
    conn.execute(f'DELETE FROM "{table}"')
    conn.execute(
        f'INSERT INTO "{table}" ({insert_cols}) '
        f"SELECT {select_list} FROM read_csv_auto(?, header=true, all_varchar=true)",
        [str(csv_path)],
    )
    n = conn.execute(f'SELECT count(*) FROM "{table}"').fetchone()[0]
    log(f"{table}: loaded {n} rows from {csv_path.name}")
    return n


# ---------------------------------------------------------------------------
# Top-up generators (only fire when V1 data is below the required minimum)
# ---------------------------------------------------------------------------
def ids(conn, table: str, col: str) -> list[str]:
    return [r[0] for r in conn.execute(f'SELECT "{col}" FROM "{table}"').fetchall()]


def top_up_customers(conn, need: int) -> None:
    rows = []
    for i in range(need):
        pid, cid = uid(), uid()
        name = f"{random.choice(SG_FIRST)} {random.choice(SG_LAST)}"
        conn.execute(
            "INSERT INTO parties (party_id, party_type, display_name, first_name, last_name, email, phone, created_at, updated_at) "
            "VALUES (?, 'person', ?, ?, ?, ?, ?, ?, ?)",
            [pid, name, name.split()[0], name.split()[-1],
             f"cust{i}@example.sg", f"+65 9{random.randint(1000000, 9999999)}", now(), now()],
        )
        rows.append([cid, pid, f"CUST-G{i:05d}", random.choice(SG_SEGMENTS),
                     random.choice(["prospect", "active", "loyal", "at_risk"]),
                     rand_date(), random.choice(["LOW", "MEDIUM", "HIGH"]),
                     round(random.uniform(0.1, 0.99), 3), None, None, now(), now()])
    conn.executemany(
        "INSERT INTO customers (customer_id, party_id, customer_number, customer_segment, lifecycle_stage, "
        "acquisition_date, risk_tier, engagement_score, household_party_id, customer_type_code, created_at, updated_at) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", rows)


def top_up_agents(conn, need: int) -> None:
    rows = []
    for i in range(need):
        pid, aid = uid(), uid()
        name = f"{random.choice(SG_FIRST)} {random.choice(SG_LAST)}"
        conn.execute(
            "INSERT INTO parties (party_id, party_type, display_name, created_at, updated_at) VALUES (?, 'person', ?, ?, ?)",
            [pid, name, now(), now()],
        )
        rows.append([aid, pid, f"AGT-G{i:05d}", None, "SG", f"LIC{random.randint(100000, 999999)}",
                     random.choice(["agency", "bancassurance", "digital", "partner"]),
                     random.choice(SG_REGIONS), rand_date(2018, 2025), None, "active", now(), now()])
    conn.executemany(
        "INSERT INTO agents (agent_id, party_id, agent_number, agency_party_id, license_state, license_number, "
        "channel, territory_code, appointment_date, termination_date, status, created_at, updated_at) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", rows)


def top_up_policies(conn, need: int) -> None:
    customer_ids = ids(conn, "customers", "customer_id")
    agent_ids = ids(conn, "agents", "agent_id")
    product_ids = ids(conn, "products", "product_id")
    rows = []
    for i in range(need):
        eff = rand_date(2021, 2026)
        premium = round(random.uniform(800, 28000), 2)  # SGD
        rows.append([uid(), f"POL-G{i:06d}", random.choice(customer_ids), random.choice(agent_ids),
                     random.choice(product_ids) if product_ids else None, None, None,
                     random.choices(["active", "in_force", "lapsed", "cancelled"], weights=[55, 25, 12, 8])[0],
                     eff, eff + timedelta(days=365), eff, None,
                     random.choice(["agency", "bancassurance", "digital", "partner"]),
                     random.choice(["annual", "semi_annual", "monthly"]),
                     premium, round(premium * random.uniform(0.9, 1.0), 2), now(), now()])
    conn.executemany(
        "INSERT INTO policies (policy_id, policy_number, customer_id, agent_id, product_id, opportunity_id, "
        "prior_policy_id, policy_status, effective_date, expiration_date, issue_date, cancellation_date, "
        "source_channel, payment_plan, annual_premium, written_premium, created_at, updated_at) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", rows)


def top_up_campaigns(conn, need: int) -> None:
    objectives = ["Health cross-sell", "Retirement income upgrade", "Lapse prevention",
                  "New customer acquisition", "Rider attach", "Investment top-up"]
    rows = []
    for i in range(need):
        start = rand_date(2024, 2026)
        rows.append([uid(), f"CMP-G{i:04d}", f"{random.choice(objectives)} {start.year} Q{(start.month - 1) // 3 + 1}",
                     random.choice(["cross_sell", "retention", "acquisition", "upsell"]),
                     random.choice(["email", "sms", "agency", "digital", "telemarketing"]),
                     random.choice(objectives), random.choice(["Health", "Savings", "Protection", "Investment"]),
                     start, start + timedelta(days=random.randint(30, 120)),
                     round(random.uniform(20000, 400000), 2), random.choice(["active", "completed", "planned"]),
                     now(), now()])
    conn.executemany(
        "INSERT INTO campaigns (campaign_id, campaign_code, campaign_name, campaign_type, channel, objective, "
        "target_line_of_business, start_date, end_date, budget_amount, status, created_at, updated_at) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", rows)


def top_up_claims(conn, need: int) -> None:
    pol = conn.execute("SELECT policy_id, customer_id FROM policies LIMIT 5000").fetchall()
    agent_ids = ids(conn, "agents", "agent_id")
    causes = ["hospitalisation", "critical_illness", "accident", "outpatient_surgery", "death", "disability"]
    rows = []
    for i in range(need):
        p = random.choice(pol)
        loss = rand_date(2023, 2026)
        paid = round(random.uniform(500, 180000), 2)
        rows.append([uid(), f"CLM-G{i:06d}", p[0], p[1], None, random.choice(agent_ids),
                     loss, loss + timedelta(days=random.randint(1, 30)), None,
                     random.choices(["open", "approved", "paid", "denied"], weights=[30, 25, 35, 10])[0],
                     random.choice(causes), "Synthetic generated claim for V2 seed.",
                     paid, round(paid * random.uniform(0.0, 0.5), 2), False, False, now(), now()])
    conn.executemany(
        "INSERT INTO claims (claim_id, claim_number, policy_id, customer_id, policy_coverage_id, assigned_agent_id, "
        "loss_date, report_date, close_date, claim_status, loss_cause, loss_description, paid_amount, reserve_amount, "
        "litigation_flag, catastrophe_flag, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", rows)


def top_up_glossary(conn, need: int) -> None:
    kpis = ["Lapse rate", "Persistency 13M", "Persistency 25M", "Claims ratio", "Loss ratio",
            "Conversion rate", "Response rate", "New business premium", "Annualised premium equivalent",
            "Sum assured", "Rider attach rate", "Agent activity ratio", "MAPA contacts",
            "Quote-to-bind ratio", "Average case size", "Churn propensity", "CLV",
            "Premium at risk", "Renewal retention rate", "First year commission"]
    rows = []
    for i in range(need):
        base = kpis[i % len(kpis)]
        term = base if i < len(kpis) else f"{base} (variant {i // len(kpis)})"
        rows.append([uid(), term, random.choice(["policy", "claims", "campaign", "agent", "customer"]),
                     f"{base} — standard Singapore life & health insurance KPI used in the V2 PoC.",
                     None, base.lower().replace(" ", "_"), "data_office", True, now(), now()])
    conn.executemany(
        "INSERT INTO business_glossary (glossary_id, term, domain, definition, calculation_sql, synonyms, owner, "
        "active_flag, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?)", rows)


def top_up_semantic_documents(conn, need: int) -> None:
    rows = []
    for i in range(need):
        title = f"V2 context document {i + 1}"
        content = ("Describes how to join policies to customers and products for Singapore book analytics. "
                   "Premium amounts are SGD. Use policy_status in ('active','in_force') for in-force KPIs.")
        rows.append([uid(), None, "table", "main", "policies", None, title, content,
                     "v2,seed", hashlib.sha256(content.encode()).hexdigest(), None, None, True, now(), now()])
    conn.executemany(
        "INSERT INTO semantic_documents (semantic_document_id, glossary_id, document_type, source_schema, source_table, "
        "source_column, title, content, tags, content_hash, embedding_model, embedding, active_flag, created_at, updated_at) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", rows)


TOP_UP = {
    "customers": top_up_customers,
    "agents": top_up_agents,
    "policies": top_up_policies,
    "campaigns": top_up_campaigns,
    "claims": top_up_claims,
    "business_glossary": top_up_glossary,
    "semantic_documents": top_up_semantic_documents,
}


# ---------------------------------------------------------------------------
# New V2 tables — generated content
# ---------------------------------------------------------------------------
def seed_customer_type(conn) -> None:
    rows = [
        ("INDIV", "Individual", "Individual retail customer", "MEDIUM"),
        ("HNW", "High net worth", "Affluent / private-client customer", "LOW"),
        ("SME", "SME business owner", "Small business owner with keyman needs", "MEDIUM"),
        ("CORP", "Corporate", "Corporate group policy holder", "LOW"),
        ("YOUTH", "Young adult", "New-to-workforce customer under 30", "MEDIUM"),
        ("SENIOR", "Senior", "Silver generation customer 60+", "HIGH"),
    ]
    conn.executemany(
        "INSERT INTO customer_type (customer_type_code, type_name, description, default_risk_tier, active_flag, created_at) "
        "VALUES (?,?,?,?, true, ?)", [[*r, now()] for r in rows])
    conn.execute(
        "UPDATE customers SET customer_type_code = "
        "CASE WHEN customer_segment ILIKE '%afflu%' THEN 'HNW' "
        "     WHEN customer_segment ILIKE '%silver%' OR customer_segment ILIKE '%retire%' THEN 'SENIOR' "
        "     WHEN customer_segment ILIKE '%workforce%' OR customer_segment ILIKE '%young adult%' THEN 'YOUTH' "
        "     ELSE 'INDIV' END "
        "WHERE customer_type_code IS NULL")
    log("customer_type: 6 rows + customers backfilled")


def seed_households(conn) -> None:
    cust = conn.execute(
        "SELECT customer_id, coalesce(household_party_id, customer_id) AS hh_key, customer_segment "
        "FROM customers").fetchall()
    by_hh: dict[str, list] = {}
    for c in cust:
        by_hh.setdefault(c[1], []).append(c)
    hh_rows, member_rows = [], []
    for hh_key, members in list(by_hh.items())[:400]:
        hh_id = uid()
        hh_rows.append([hh_id, f"Household {hh_key[:8]}", members[0][0], members[0][2],
                        len(members), round(random.uniform(2000, 60000), 2),
                        random.choice(SG_REGIONS), now(), now()])
        for j, m in enumerate(members):
            member_rows.append([uid(), hh_id, m[0],
                                "head" if j == 0 else random.choice(["spouse", "child", "parent", "other"]),
                                j == 0, rand_date(2019, 2025), now(), now()])
    conn.executemany(
        "INSERT INTO households (household_id, household_name, primary_customer_id, household_segment, member_count, "
        "total_annual_premium, region, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?)", hh_rows)
    conn.executemany(
        "INSERT INTO household_members (household_member_id, household_id, customer_id, relationship_to_head, "
        "is_primary, joined_date, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?)", member_rows)
    log(f"households: {len(hh_rows)} rows; household_members: {len(member_rows)} rows")


def seed_policy_type_config(conn) -> None:
    rows = [
        ("ISP", "Integrated Shield Plan", "Health", 12, 30, 600, 2000000, True, True),
        ("TERM", "Term Life", "Protection", 240, 30, 400, 4000000, True, True),
        ("WL", "Whole Life", "Protection", 1188, 60, 1200, 5000000, False, True),
        ("ENDOW", "Endowment Savings", "Savings", 120, 30, 1500, 1000000, False, True),
        ("ILP", "Investment-Linked Plan", "Investment", 600, 60, 1800, 3000000, False, True),
        ("CI", "Critical Illness", "Health", 240, 30, 500, 2000000, True, True),
        ("PA", "Personal Accident", "Protection", 12, 14, 150, 1000000, True, False),
        ("RET", "Retirement Income", "Savings", 360, 60, 2400, 2000000, False, True),
    ]
    conn.executemany(
        "INSERT INTO policy_type_config (policy_type_code, policy_type_name, line_of_business, default_term_months, "
        "grace_period_days, min_annual_premium, max_sum_assured, renewable_flag, rider_allowed_flag, active_flag, created_at) "
        "VALUES (?,?,?,?,?,?,?,?,?, true, ?)", [[*r, now()] for r in rows])
    log("policy_type_config: 8 rows")


def derive_agent_performance(conn) -> None:
    conn.execute(
        "UPDATE agent_performance SET "
        "conversion_rate = CASE WHEN coalesce(quotes_count,0) > 0 "
        "  THEN round(policies_bound_count * 1.0 / quotes_count, 4) ELSE NULL END, "
        "performance_band = CASE "
        "  WHEN coalesce(new_business_premium,0) > 80000 THEN 'Top' "
        "  WHEN coalesce(policies_bound_count,0) = 0 THEN 'Coaching' "
        "  ELSE 'Stable' END")
    log("agent_performance: derived conversion_rate + performance_band")


def seed_agent_service_events(conn, n=300) -> None:
    agent_ids = ids(conn, "agents", "agent_id")
    pol = conn.execute("SELECT policy_id, customer_id FROM policies LIMIT 3000").fetchall()
    rows = []
    for _ in range(n):
        p = random.choice(pol)
        rows.append([uid(), random.choice(agent_ids), p[1], p[0],
                     datetime.combine(rand_date(2024, 2026), datetime.min.time()) + timedelta(minutes=random.randint(540, 1080)),
                     random.choice(["policy_servicing", "claim_support", "renewal_follow_up", "onboarding"]),
                     random.choice(["call", "whatsapp", "branch", "email"]),
                     random.choice(["resolved", "follow_up_required", "escalated"]),
                     random.randint(5, 90), "Generated service event for V2 seed.", now()])
    conn.executemany(
        "INSERT INTO agent_service_events (agent_service_event_id, agent_id, customer_id, policy_id, event_ts, "
        "event_type, channel, outcome, duration_minutes, notes, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)", rows)
    log(f"agent_service_events: {n} rows")


def seed_agent_assessments(conn, n=200) -> None:
    agent_ids = ids(conn, "agents", "agent_id")
    rows = []
    for _ in range(n):
        overall = round(random.uniform(45, 98), 1)
        rows.append([uid(), random.choice(agent_ids), rand_date(2024, 2026),
                     random.choice(["annual_review", "compliance_audit", "sales_quality", "mystery_shop"]),
                     random.choice(["Agency Manager", "Compliance Office", "Sales QA"]),
                     overall, round(random.uniform(50, 100), 1), round(random.uniform(40, 100), 1),
                     round(random.uniform(40, 100), 1),
                     "Exceeds" if overall >= 85 else ("Meets" if overall >= 65 else "Needs improvement"),
                     "Generated assessment for V2 seed.", now()])
    conn.executemany(
        "INSERT INTO agent_assessments (agent_assessment_id, agent_id, assessment_date, assessment_type, assessor, "
        "overall_score, compliance_score, sales_quality_score, customer_outcome_score, result_band, remarks, created_at) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", rows)
    log(f"agent_assessments: {n} rows")


def seed_model_versions(conn) -> None:
    pairs = conn.execute(
        "SELECT DISTINCT model_name, coalesce(model_version, '1.0') FROM model_scores "
        "UNION SELECT DISTINCT model_name, coalesce(model_version, '1.0') FROM model_predictions").fetchall()
    if not pairs:
        pairs = [("policy_lapse", "1.0"), ("propensity_to_buy", "1.0"), ("customer_churn", "1.0"),
                 ("next_best_product", "1.0"), ("agent_attrition", "1.0"), ("fraud_detection", "1.0")]
    rows = []
    for name, version in pairs:
        rows.append([uid(), name, version, random.choice(["gradient_boosting", "logistic_regression", "random_forest"]),
                     rand_date(2025, 2026), round(random.uniform(0.72, 0.93), 3), round(random.uniform(0.6, 0.9), 3),
                     round(random.uniform(0.55, 0.88), 3), f"{name}_features", "production", "ml_platform",
                     "Registered during V2 seed from observed scores.", now()])
    conn.executemany(
        "INSERT INTO model_versions (model_version_id, model_name, model_version, algorithm, training_date, auc, "
        "precision_score, recall_score, feature_set_name, status, registered_by, notes, created_at) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", rows)
    log(f"model_versions: {len(rows)} rows")


def seed_vector_index_log(conn) -> None:
    docs = conn.execute(
        "SELECT semantic_document_id, left(coalesce(content, title, ''), 400) FROM semantic_documents LIMIT 500").fetchall()
    rows = [["semantic_documents", d[0], d[1], now(), "pending-embedding", 768, "semantic_documents_lance"] for d in docs]
    conn.executemany(
        "INSERT INTO vector_index_log (table_name, record_id, chunk_text, embedded_at, model_used, vector_dims, lance_table) "
        "VALUES (?,?,?,?,?,?,?)", rows)
    log(f"vector_index_log: {len(rows)} rows (queued for LanceDB embedding)")


def seed_agent_reasoning_log(conn) -> None:
    agents_chain = ["intent_classifier", "context_retriever", "sql_agent", "validator", "insight_agent"]
    rows = []
    for q in range(8):
        qid = uid()
        for name in agents_chain:
            rows.append([qid, name, f"sample question {q + 1}", f"{name} completed",
                         random.randint(5, 2200), random.randint(50, 4000), random.random() < 0.3, now()])
    conn.executemany(
        "INSERT INTO agent_reasoning_log (query_id, agent_name, input_summary, output_summary, duration_ms, "
        "tokens_used, cache_hit, created_at) VALUES (?,?,?,?,?,?,?,?)", rows)
    log(f"agent_reasoning_log: {len(rows)} sample rows")


def seed_semantic_cache(conn) -> None:
    samples = [
        ("Executive Leadership", "What is our current lapse rate?",
         "The current portfolio lapse rate is 11.8% across 1,000+ policies, concentrated in savings plans."),
        ("Campaign Manager", "Which campaign generated the highest policy conversion?",
         "Health cross-sell agency campaigns lead conversion at 14.7%, driven by PRUShield upgrade offers."),
        ("Insurance Agent", "Which customers should I contact first this week?",
         "Top priority: customers with HIGH lapse-risk scores and premium at risk above S$5,000."),
        ("Claims Manager", "Which products have the highest claims ratio?",
         "PRUShield Premier shows the highest incurred claims ratio, followed by PRUCancer 360."),
        ("Sales Director", "What product line has the largest premium concentration?",
         "Health leads premium concentration at ~38% of annualised premium, followed by Savings at 27%."),
    ]
    rows = []
    for role, q, a in samples:
        rows.append([hashlib.sha256(q.lower().strip().encode()).hexdigest(), q, a,
                     json.dumps({"tables": ["policies", "campaigns", "claims"], "source": "v2-seed"}),
                     role, 0.92, now() + timedelta(days=7), now()])
    conn.executemany(
        "INSERT INTO semantic_cache (question_hash, question_text, answer_text, context_used, role, "
        "similarity_threshold, expires_at, created_at) VALUES (?,?,?,?,?,?,?,?)", rows)
    log(f"semantic_cache: {len(rows)} sample rows")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> int:
    if not DATA_DIR.exists():
        print(f"ERROR: V1 data folder not found: {DATA_DIR}")
        return 1
    log(f"DuckDB: {DUCKDB_PATH}")
    conn = duckdb.connect(DUCKDB_PATH)
    try:
        # 1. Load every available V1 CSV
        for csv_name, table in CSV_TABLE_MAP.items():
            path = DATA_DIR / csv_name
            if path.exists():
                try:
                    load_csv(conn, table, path)
                except Exception as exc:
                    log(f"ERROR loading {csv_name} -> {table}: {exc}")
            else:
                log(f"WARN: {csv_name} not found, table {table} left for generation")

        # 2. Top up minimum counts
        for table, minimum in MIN_COUNTS.items():
            have = conn.execute(f'SELECT count(*) FROM "{table}"').fetchone()[0]
            if have < minimum:
                log(f"{table}: {have} < {minimum}, generating {minimum - have} rows")
                TOP_UP[table](conn, minimum - have)

        # 3. New V2 tables
        seed_customer_type(conn)
        seed_households(conn)
        seed_policy_type_config(conn)
        derive_agent_performance(conn)
        seed_agent_service_events(conn)
        seed_agent_assessments(conn)
        seed_model_versions(conn)
        seed_vector_index_log(conn)
        seed_agent_reasoning_log(conn)
        seed_semantic_cache(conn)

        # 4. Summary
        print("\n=== Seed summary ===")
        tables = [r[0] for r in conn.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema='main' ORDER BY table_name").fetchall()]
        total = 0
        for t in tables:
            n = conn.execute(f'SELECT count(*) FROM "{t}"').fetchone()[0]
            total += n
            print(f"  {t:<38} {n:>8}")
        print(f"  {'TOTAL':<38} {total:>8}")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
