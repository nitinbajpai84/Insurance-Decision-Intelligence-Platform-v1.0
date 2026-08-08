"""Author metric bindings (data contracts) + role table-access policies (Prompt 16).

Each metric concept_node gets a binding: canonical view, allowed tables/columns,
sanctioned joins, default filters, grain, and a reference formula_sql. These are
the guardrails the SQL agent must obey. Idempotent (upsert by metric_id).

Run AFTER domain_pack.py (Prompt 15).  python graph/build_metric_bindings.py
"""
from __future__ import annotations

import json
import sys
import uuid
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from graph.db_util import robust_connect

DB_PATH = str(PROJECT_ROOT / "database" / "insurance_v2.duckdb")
NOW = datetime.now()

# ---------------------------------------------------------------------------
# Metric bindings — keyed by concept_nodes.node_id
# Each: (canonical_view, allowed_tables, allowed_columns, required_joins,
#        default_filters, grain, formula_sql, sample_question)
# allowed_tables always includes the canonical view AND its base tables so the
# SQL agent may query either surface.
# ---------------------------------------------------------------------------
BINDINGS = {
    "metric::new_business_premium": dict(
        view="v_home_kpis", grain="policy/month",
        tables=["v_home_kpis", "v_agent_leaderboard", "policies", "products"],
        columns=["policies.annual_premium", "policies.issue_date", "policies.policy_status",
                 "policies.product_id", "policies.policy_id", "products.product_id",
                 "products.line_of_business", "v_home_kpis.new_business_premium_90d",
                 "v_agent_leaderboard.premium"],
        joins=["products.product_id = policies.product_id"],
        filters=["policies.policy_status in ('active','renewed','issued')"],
        formula="SELECT SUM(annual_premium) AS new_business_premium FROM policies "
                "WHERE issue_date > (SELECT max(issue_date) FROM policies) - INTERVAL 90 DAY",
        sample="What was new business premium in the last 90 days?"),

    "metric::ape": dict(
        view="", grain="policy",
        tables=["policies"],
        columns=["policies.annual_premium", "policies.written_premium", "policies.payment_plan", "policies.policy_id"],
        joins=[], filters=["policies.policy_status in ('active','renewed','issued')"],
        formula="SELECT SUM(annual_premium) AS ape FROM policies WHERE policy_status in ('active','renewed','issued')",
        sample="What is our annualised premium equivalent?"),

    "metric::persistency_13m": dict(
        view="v_home_kpis", grain="policy cohort",
        tables=["v_home_kpis", "v_agent_360", "policies"],
        columns=["policies.policy_status", "policies.policy_id", "v_home_kpis.persistency_13m",
                 "v_agent_360.persistency_rate"],
        joins=[], filters=["policies.policy_status in ('active','renewed','lapsed')"],
        formula="SELECT 100.0 * count(*) filter (where policy_status in ('active','renewed')) "
                "/ nullif(count(*) filter (where policy_status in ('active','renewed','lapsed')),0) AS persistency_13m FROM policies",
        sample="What is our 13-month persistency?"),

    "metric::persistency_25m": dict(
        view="v_agent_360", grain="policy cohort",
        tables=["v_agent_360", "agent_performance", "policies"],
        columns=["agent_performance.retained_policy_count", "agent_performance.lapsed_policy_count",
                 "agent_performance.agent_id", "v_agent_360.persistency_rate", "policies.policy_status"],
        joins=[], filters=[],
        formula="SELECT 100.0 * sum(retained_policy_count) / nullif(sum(retained_policy_count)+sum(lapsed_policy_count),0) AS persistency_25m FROM agent_performance",
        sample="What is second-year persistency by agent?"),

    "metric::lapse_rate": dict(
        view="v_lapse_risk_summary", grain="policy/period",
        tables=["v_lapse_risk_summary", "v_lapse_policy_risk", "policies", "policy_lapse_events"],
        columns=["policies.policy_status", "policies.policy_id", "policies.annual_premium",
                 "policy_lapse_events.policy_id", "policy_lapse_events.lapse_event_date",
                 "v_lapse_risk_summary.policies_at_risk", "v_lapse_risk_summary.premium_at_risk"],
        joins=["policy_lapse_events.policy_id = policies.policy_id"],
        filters=["policies.policy_status in ('active','renewed','issued','lapsed')"],
        formula="SELECT 100.0 * count(*) filter (where policy_status='lapsed') / nullif(count(*),0) AS lapse_rate FROM policies",
        sample="What is the overall policy lapse rate?"),

    "metric::surrender_rate": dict(
        view="", grain="policy/period",
        tables=["policies", "policy_events"],
        columns=["policies.policy_status", "policies.policy_id", "policy_events.event_type", "policy_events.policy_id"],
        joins=[], filters=[],
        formula="SELECT 100.0 * count(*) filter (where policy_status='surrendered') / nullif(count(*),0) AS surrender_rate FROM policies",
        sample="What is the surrender rate?"),

    "metric::free_look_cancellation_rate": dict(
        view="", grain="policy/month",
        tables=["policies", "policy_events"],
        columns=["policies.policy_id", "policies.issue_date", "policies.cancellation_date",
                 "policy_events.event_type", "policy_events.policy_id"],
        joins=[], filters=[],
        formula="SELECT 100.0 * count(*) filter (where cancellation_date is not null and date_diff('day', issue_date, cancellation_date) <= 21) "
                "/ nullif(count(*),0) AS free_look_rate FROM policies",
        sample="What is our free-look cancellation rate?"),

    "metric::claims_ratio": dict(
        view="", grain="product/period",
        tables=["claims", "policies", "products"],
        columns=["claims.paid_amount", "claims.policy_id", "claims.claim_status", "policies.policy_id",
                 "policies.annual_premium", "policies.product_id", "products.product_id", "products.line_of_business"],
        joins=["claims.policy_id = policies.policy_id", "products.product_id = policies.product_id"],
        filters=[],
        formula="SELECT 100.0 * sum(c.paid_amount) / nullif(sum(p.annual_premium),0) AS claims_ratio "
                "FROM claims c JOIN policies p ON p.policy_id = c.policy_id",
        sample="What is the claims ratio by product line?"),

    "metric::expense_ratio": dict(
        view="", grain="company/period",
        tables=["agent_commissions", "policies"],
        columns=["agent_commissions.commission_amount", "policies.annual_premium"],
        joins=[], filters=[],
        formula="SELECT 100.0 * sum(commission_amount) / nullif((SELECT sum(annual_premium) FROM policies),0) AS expense_ratio FROM agent_commissions",
        sample="What is our expense ratio?"),

    "metric::combined_ratio": dict(
        view="", grain="company/period",
        tables=["claims", "policies", "agent_commissions"],
        columns=["claims.paid_amount", "policies.annual_premium", "agent_commissions.commission_amount"],
        joins=[], filters=[],
        formula="SELECT (SELECT 100.0*sum(paid_amount) FROM claims)/nullif((SELECT sum(annual_premium) FROM policies),0) "
                "+ (SELECT 100.0*sum(commission_amount) FROM agent_commissions)/nullif((SELECT sum(annual_premium) FROM policies),0) AS combined_ratio",
        sample="What is the combined ratio?"),

    "metric::clv": dict(
        view="v_customer_360", grain="customer",
        tables=["v_customer_360", "customers", "policies"],
        columns=["v_customer_360.clv_band", "v_customer_360.annual_premium", "v_customer_360.customer_id",
                 "customers.customer_id", "policies.annual_premium", "policies.customer_id", "policies.policy_status"],
        joins=["policies.customer_id = customers.customer_id"],
        filters=["policies.policy_status in ('active','renewed','issued')"],
        formula="SELECT customer_id, clv_band, annual_premium FROM v_customer_360",
        sample="Which customers have the highest lifetime value?"),

    "metric::cross_sell_ratio": dict(
        view="", grain="customer",
        tables=["policies", "customers"],
        columns=["policies.policy_id", "policies.customer_id", "policies.policy_status", "customers.customer_id"],
        joins=[], filters=["policies.policy_status in ('active','renewed','issued')"],
        formula="SELECT count(*)::double / nullif(count(distinct customer_id),0) AS cross_sell_ratio "
                "FROM policies WHERE policy_status in ('active','renewed','issued')",
        sample="What is the average number of policies per customer?"),

    "metric::up_sell_rate": dict(
        view="", grain="customer/period",
        tables=["policies"],
        columns=["policies.policy_id", "policies.customer_id", "policies.prior_policy_id", "policies.annual_premium"],
        joins=["policies.prior_policy_id = policies.policy_id"],
        filters=[],
        formula="SELECT 100.0 * count(*) filter (where p.annual_premium > pp.annual_premium) / nullif(count(*),0) AS up_sell_rate "
                "FROM policies p JOIN policies pp ON pp.policy_id = p.prior_policy_id",
        sample="What share of repeat purchases were upgrades?"),

    "metric::repurchase_rate": dict(
        view="", grain="customer",
        tables=["policies", "customers"],
        columns=["policies.policy_id", "policies.customer_id", "policies.prior_policy_id",
                 "policies.effective_date", "customers.customer_id"],
        joins=["policies.prior_policy_id = policies.policy_id"],
        filters=[],
        formula="SELECT 100.0 * count(distinct p.customer_id) / nullif((SELECT count(*) FROM customers),0) AS repurchase_rate "
                "FROM policies p JOIN policies pp ON pp.policy_id = p.prior_policy_id "
                "WHERE date_diff('day', pp.effective_date, p.effective_date) BETWEEN 180 AND 730",
        sample="What is the repurchase rate?"),

    "metric::time_to_repurchase": dict(
        view="", grain="customer",
        tables=["policies"],
        columns=["policies.policy_id", "policies.prior_policy_id", "policies.effective_date", "policies.customer_id"],
        joins=["policies.prior_policy_id = policies.policy_id"],
        filters=[],
        formula="SELECT avg(date_diff('day', pp.effective_date, p.effective_date)) AS time_to_repurchase_days "
                "FROM policies p JOIN policies pp ON pp.policy_id = p.prior_policy_id",
        sample="How long until customers buy a second policy?"),

    "metric::lead_conversion_rate": dict(
        view="", grain="lead/period",
        tables=["leads", "opportunities", "quotes", "proposals", "applications", "policies"],
        columns=["leads.lead_id", "leads.lead_status", "opportunities.lead_id", "opportunities.opportunity_id",
                 "opportunities.opportunity_stage", "quotes.opportunity_id", "quotes.quote_status",
                 "proposals.quote_id", "proposals.proposal_status", "applications.proposal_id",
                 "applications.application_status", "policies.opportunity_id"],
        joins=["opportunities.lead_id = leads.lead_id", "quotes.opportunity_id = opportunities.opportunity_id",
               "proposals.quote_id = quotes.quote_id", "applications.proposal_id = proposals.proposal_id"],
        filters=[],
        formula="SELECT 100.0 * count(distinct a.application_id) filter (where a.application_status='issued') "
                "/ nullif((SELECT count(*) FROM leads),0) AS lead_conversion_rate "
                "FROM applications a JOIN proposals pr ON pr.proposal_id=a.proposal_id "
                "JOIN quotes q ON q.quote_id=pr.quote_id JOIN opportunities o ON o.opportunity_id=q.opportunity_id "
                "WHERE o.lead_id IS NOT NULL",
        sample="What is our lead-to-policy conversion rate by stage?"),

    "metric::quote_to_bind_rate": dict(
        view="", grain="quote/period",
        tables=["quotes", "policies", "applications"],
        columns=["quotes.quote_id", "quotes.quote_status", "applications.quote_id",
                 "applications.application_status", "policies.policy_id"],
        joins=["applications.quote_id = quotes.quote_id"],
        filters=[],
        formula="SELECT 100.0 * count(*) filter (where application_status='issued') / nullif((SELECT count(*) FROM quotes),0) AS quote_to_bind_rate FROM applications",
        sample="What is the quote-to-bind rate?"),

    "metric::proposal_acceptance_rate": dict(
        view="", grain="proposal/period",
        tables=["proposals", "applications"],
        columns=["proposals.proposal_id", "proposals.proposal_status", "applications.proposal_id"],
        joins=["applications.proposal_id = proposals.proposal_id"],
        filters=[],
        formula="SELECT 100.0 * count(*) filter (where proposal_status='accepted') / nullif(count(*),0) AS proposal_acceptance_rate FROM proposals",
        sample="What is the proposal acceptance rate?"),

    "metric::campaign_response_rate": dict(
        view="v_campaign_effectiveness", grain="campaign",
        tables=["v_campaign_effectiveness", "campaigns", "campaign_targets", "campaign_responses"],
        columns=["v_campaign_effectiveness.response_rate", "v_campaign_effectiveness.campaign_id",
                 "campaign_targets.campaign_id", "campaign_targets.campaign_target_id",
                 "campaign_responses.campaign_id", "campaign_responses.response_type"],
        joins=["campaign_responses.campaign_id = campaigns.campaign_id", "campaign_targets.campaign_id = campaigns.campaign_id"],
        filters=[],
        formula="SELECT 100.0 * (SELECT count(*) FROM campaign_responses) / nullif((SELECT count(*) FROM campaign_targets),0) AS campaign_response_rate",
        sample="What is the campaign response rate?"),

    "metric::campaign_conversion": dict(
        view="v_campaign_effectiveness", grain="campaign",
        tables=["v_campaign_effectiveness", "campaigns", "campaign_targets", "campaign_responses"],
        columns=["v_campaign_effectiveness.conversion_rate", "v_campaign_effectiveness.campaign_id",
                 "campaign_responses.conversion_flag", "campaign_responses.campaign_id",
                 "campaign_targets.campaign_id", "campaign_targets.campaign_target_id"],
        joins=["campaign_responses.campaign_id = campaigns.campaign_id"],
        filters=[],
        formula="SELECT 100.0 * (SELECT count(*) FROM campaign_responses WHERE conversion_flag) "
                "/ nullif((SELECT count(*) FROM campaign_targets),0) AS campaign_conversion_rate",
        sample="Which campaign channel converts best?"),

    "metric::campaign_roi": dict(
        view="v_campaign_effectiveness", grain="campaign",
        tables=["v_campaign_effectiveness", "campaigns", "campaign_responses"],
        columns=["v_campaign_effectiveness.roi_multiple", "v_campaign_effectiveness.premium_generated",
                 "v_campaign_effectiveness.budget_amount", "v_campaign_effectiveness.campaign_id",
                 "campaigns.budget_amount", "campaigns.campaign_id", "campaign_responses.conversion_premium",
                 "campaign_responses.conversion_flag", "campaign_responses.campaign_id"],
        joins=["campaign_responses.campaign_id = campaigns.campaign_id"],
        filters=[],
        formula="SELECT c.campaign_id, round(sum(r.conversion_premium) filter (where r.conversion_flag) / nullif(c.budget_amount,0),2) AS roi_multiple "
                "FROM campaigns c LEFT JOIN campaign_responses r ON r.campaign_id=c.campaign_id GROUP BY c.campaign_id, c.budget_amount",
        sample="What is the ROI of our campaigns?"),

    "metric::product_demand_index": dict(
        view="", grain="product/month",
        tables=["leads", "quotes", "campaign_responses", "products"],
        columns=["leads.product_id", "leads.received_at", "quotes.product_id", "quotes.quote_date",
                 "campaign_responses.response_ts", "products.product_id", "products.line_of_business"],
        joins=["quotes.product_id = products.product_id", "leads.product_id = products.product_id"],
        filters=[],
        formula="SELECT pr.line_of_business, count(distinct l.lead_id) + count(distinct q.quote_id) AS demand_signal "
                "FROM products pr LEFT JOIN leads l ON l.product_id=pr.product_id LEFT JOIN quotes q ON q.product_id=pr.product_id "
                "GROUP BY pr.line_of_business",
        sample="Which product line has the strongest demand?"),

    "metric::agent_productivity_mapa": dict(
        view="v_agent_mapa", grain="agent/month",
        tables=["v_agent_mapa", "agent_performance", "agent_meetings"],
        columns=["v_agent_mapa.meetings", "v_agent_mapa.activities", "v_agent_mapa.proposals",
                 "v_agent_mapa.applications", "v_agent_mapa.agent_id", "v_agent_mapa.metric_month",
                 "agent_performance.contacts_count", "agent_performance.quotes_count",
                 "agent_performance.applications_count", "agent_performance.agent_id",
                 "agent_meetings.agent_id", "agent_meetings.meeting_ts"],
        joins=["agent_meetings.agent_id = agent_performance.agent_id"],
        filters=[],
        formula="SELECT agent_id, metric_month, meetings, activities, proposals, applications FROM v_agent_mapa",
        sample="Show MAPA activity for an agent over time."),

    "metric::agent_target_achievement": dict(
        view="v_agent_360", grain="agent/period",
        tables=["v_agent_360", "agent_targets", "agents"],
        columns=["v_agent_360.target_achievement_pct", "v_agent_360.agent_id", "agent_targets.agent_id",
                 "agent_targets.target_value", "agent_targets.actual_value", "agent_targets.attainment_pct"],
        joins=["agent_targets.agent_id = agents.agent_id"],
        filters=[],
        formula="SELECT agent_id, attainment_pct AS target_achievement_pct FROM agent_targets",
        sample="Which agents are below target?"),

    "metric::agent_persistency": dict(
        view="v_agent_leaderboard", grain="agent/cohort",
        tables=["v_agent_leaderboard", "agent_performance"],
        columns=["v_agent_leaderboard.persistency_rate", "v_agent_leaderboard.agent_id",
                 "agent_performance.retained_policy_count", "agent_performance.lapsed_policy_count", "agent_performance.agent_id"],
        joins=[], filters=[],
        formula="SELECT agent_id, 100.0*sum(retained_policy_count)/nullif(sum(retained_policy_count)+sum(lapsed_policy_count),0) AS agent_persistency "
                "FROM agent_performance GROUP BY agent_id",
        sample="Which agents have the best book persistency?"),

    "metric::propensity_to_buy": dict(
        view="v_customer_propensity", grain="customer",
        tables=["v_customer_propensity", "v_customer_360", "model_scores", "customers"],
        columns=["v_customer_propensity.propensity_to_buy", "v_customer_propensity.customer_id",
                 "model_scores.entity_id", "model_scores.entity_type", "model_scores.score_name",
                 "model_scores.probability", "model_scores.score_band", "customers.customer_id"],
        joins=["model_scores.entity_id = customers.customer_id"],
        filters=["model_scores.entity_type = 'customer'", "model_scores.score_name = 'propensity_to_buy'"],
        formula="SELECT entity_id AS customer_id, probability AS propensity_to_buy FROM model_scores "
                "WHERE entity_type='customer' AND score_name='propensity_to_buy'",
        sample="Which customers are most likely to buy?"),

    "metric::churn_risk": dict(
        view="v_customer_360", grain="customer",
        tables=["v_customer_360", "model_scores", "customers"],
        columns=["v_customer_360.churn_risk_band", "v_customer_360.customer_id", "model_scores.entity_id",
                 "model_scores.entity_type", "model_scores.score_name", "model_scores.probability", "customers.customer_id"],
        joins=["model_scores.entity_id = customers.customer_id"],
        filters=["model_scores.entity_type = 'customer'", "model_scores.score_name = 'churn'"],
        formula="SELECT entity_id AS customer_id, probability AS churn_risk FROM model_scores "
                "WHERE entity_type='customer' AND score_name='churn'",
        sample="Which customers are at risk of churning?"),

    "metric::lapse_risk": dict(
        view="v_policy_lapse_score", grain="policy",
        tables=["v_policy_lapse_score", "v_lapse_policy_risk", "model_scores", "policies"],
        columns=["v_policy_lapse_score.lapse_probability", "v_policy_lapse_score.policy_id",
                 "v_policy_lapse_score.lapse_band", "model_scores.entity_id", "model_scores.entity_type",
                 "model_scores.score_name", "model_scores.probability", "model_scores.score_band", "policies.policy_id"],
        joins=["model_scores.entity_id = policies.policy_id"],
        filters=["model_scores.entity_type = 'policy'", "model_scores.score_name = 'lapse_risk'"],
        formula="SELECT entity_id AS policy_id, probability AS lapse_risk, score_band FROM model_scores "
                "WHERE entity_type='policy' AND score_name='lapse_risk'",
        sample="Which policies have the highest lapse risk?"),

    "metric::premium_at_risk": dict(
        view="v_lapse_policy_risk", grain="policy (breakdown by agent/region/product/segment)",
        tables=["v_lapse_policy_risk", "v_lapse_risk_summary", "policies", "model_scores"],
        columns=["v_lapse_risk_summary.premium_at_risk", "v_lapse_policy_risk.annual_premium",
                 "v_lapse_policy_risk.at_risk", "v_lapse_policy_risk.lapse_band", "v_lapse_policy_risk.policy_id",
                 "v_lapse_policy_risk.agent_id", "v_lapse_policy_risk.customer_id", "v_lapse_policy_risk.region",
                 "v_lapse_policy_risk.branch", "v_lapse_policy_risk.product_name", "v_lapse_policy_risk.line_of_business",
                 "v_lapse_policy_risk.customer_segment", "v_lapse_policy_risk.lapse_probability",
                 "policies.annual_premium", "policies.policy_id"],
        joins=[], filters=["v_lapse_policy_risk.at_risk = true"],
        formula="SELECT agent_id, round(sum(annual_premium) filter (where at_risk),2) AS premium_at_risk "
                "FROM v_lapse_policy_risk GROUP BY agent_id ORDER BY premium_at_risk DESC",
        sample="Which agents have the highest premium at risk?"),

    "metric::revenue_saved": dict(
        view="v_lapse_risk_summary", grain="policy/period",
        tables=["v_lapse_risk_summary", "policies", "policy_lapse_events"],
        columns=["v_lapse_risk_summary.revenue_saved", "policies.annual_premium", "policies.policy_id",
                 "policy_lapse_events.policy_id", "policy_lapse_events.reinstatement_date"],
        joins=["policy_lapse_events.policy_id = policies.policy_id"],
        filters=["policy_lapse_events.reinstatement_date is not null"],
        formula="SELECT sum(p.annual_premium) AS revenue_saved FROM policies p "
                "WHERE p.policy_id IN (SELECT policy_id FROM policy_lapse_events WHERE reinstatement_date IS NOT NULL)",
        sample="How much premium did retention save?"),
}

# ---------------------------------------------------------------------------
# Role table-access policy
# ---------------------------------------------------------------------------
ROLES = ["Executive Leadership", "Sales Director", "Agency Manager", "Insurance Agent",
         "Campaign Manager", "Claims Manager", "Data Analyst"]

POLICY_TABLES = [
    "policies", "customers", "agents", "products", "campaigns", "campaign_targets", "campaign_responses",
    "claims", "claim_fraud_indicators", "claim_assessments", "leads", "opportunities", "quotes", "proposals",
    "applications", "payments", "policy_lapse_events", "policy_events", "policy_coverage", "model_scores",
    "model_predictions", "next_best_actions", "agent_performance", "agent_targets", "agent_commissions",
    "agent_meetings", "parties", "addresses", "households",
    # views
    "v_home_kpis", "v_customer_360", "v_customer_policies", "v_customer_recommended_action", "v_agent_360",
    "v_agent_mapa", "v_agent_leaderboard", "v_campaign_effectiveness", "v_lapse_risk_summary", "v_lapse_hotspots",
    "v_lapse_policy_risk", "v_policy_lapse_score", "v_customer_propensity", "v_policy_sum_assured",
]

# Insurance Agent is scoped to their own book.
AGENT_ROW_FILTER = {
    "policies": "agent_id = :current_agent",
    "leads": "assigned_agent_id = :current_agent",
    "opportunities": "agent_id = :current_agent",
    "quotes": "agent_id = :current_agent",
    "proposals": "agent_id = :current_agent",
    "applications": "agent_id = :current_agent",
    "claims": "assigned_agent_id = :current_agent",
    "next_best_actions": "agent_id = :current_agent",
    "agent_performance": "agent_id = :current_agent",
    "agent_targets": "agent_id = :current_agent",
    "agent_commissions": "agent_id = :current_agent",
    "agent_meetings": "agent_id = :current_agent",
    "v_agent_360": "agent_id = :current_agent",
    "v_agent_mapa": "agent_id = :current_agent",
    "v_agent_leaderboard": "agent_id = :current_agent",
    "customers": "customer_id IN (SELECT customer_id FROM policies WHERE agent_id = :current_agent)",
    "v_customer_360": "advisor_agent_id = :current_agent",
    "v_customer_policies": "customer_id IN (SELECT customer_id FROM policies WHERE agent_id = :current_agent)",
    "payments": "policy_id IN (SELECT policy_id FROM policies WHERE agent_id = :current_agent)",
    "policy_lapse_events": "agent_id = :current_agent",
}


def main() -> int:
    con = robust_connect(DB_PATH, read_only=False)
    try:
        con.execute((SCRIPT_DIR / "metric_bindings_schema.sql").read_text(encoding="utf-8"))

        # author bindings for explicitly-listed metrics + a default for any other metric node
        all_metric_ids = [r[0] for r in con.execute(
            "select node_id from concept_nodes where node_type='metric'").fetchall()]
        authored = 0
        for mid in all_metric_ids:
            b = BINDINGS.get(mid)
            if b is None:
                # default thin binding from the concept node (keeps coverage at 100%)
                cn = con.execute("select name, formula, default_grain, subject_area from concept_nodes where node_id=?", [mid]).fetchone()
                b = dict(view="", grain=(cn[2] if cn else None) or "n/a",
                         tables=["policies"], columns=["policies.policy_id"], joins=[], filters=[],
                         formula=(cn[1] if cn else "") or "SELECT 1", sample=f"How is {cn[0] if cn else mid} computed?")
            con.execute(
                """
                INSERT INTO metric_bindings (binding_id, metric_id, canonical_view, allowed_tables, allowed_columns,
                    required_joins, default_filters, grain, formula_sql, sample_question, status, created_by, created_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT (metric_id) DO UPDATE SET
                    canonical_view=excluded.canonical_view, allowed_tables=excluded.allowed_tables,
                    allowed_columns=excluded.allowed_columns, required_joins=excluded.required_joins,
                    default_filters=excluded.default_filters, grain=excluded.grain, formula_sql=excluded.formula_sql,
                    sample_question=excluded.sample_question, status='active'
                """,
                [str(uuid.uuid4()), mid, b["view"], json.dumps(b["tables"]), json.dumps(b["columns"]),
                 json.dumps(b["joins"]), json.dumps(b["filters"]), b["grain"], b["formula"], b["sample"],
                 "active", "build_metric_bindings", NOW],
            )
            authored += 1

        # role table-access policy
        taps = 0
        for role in ROLES:
            for table in POLICY_TABLES:
                row_filter = None
                if role == "Insurance Agent":
                    row_filter = AGENT_ROW_FILTER.get(table)
                con.execute(
                    """
                    INSERT INTO table_access_policy (policy_id, role, table_name, allowed, row_filter, created_at)
                    VALUES (?,?,?,?,?,?)
                    ON CONFLICT (role, table_name) DO UPDATE SET allowed=excluded.allowed, row_filter=excluded.row_filter
                    """,
                    [str(uuid.uuid4()), role, table, True, row_filter, NOW],
                )
                taps += 1
        con.commit()

        # ---- coverage report ----
        print("=" * 72)
        print(f"METRIC BINDING COVERAGE ({authored} metrics)")
        print(f"  {'metric':<34} {'canonical_view':<26} #cols")
        rows = con.execute(
            "select metric_id, coalesce(nullif(canonical_view,''),'(base tables)'), "
            "json_array_length(allowed_columns) from metric_bindings order by metric_id").fetchall()
        for mid, view, ncols in rows:
            print(f"  {mid:<34} {view:<26} {ncols}")
        print(f"\nTotal bindings: {len(rows)} | table_access_policy rows: {taps} ({len(ROLES)} roles x {len(POLICY_TABLES)} tables)")
        ia_filters = con.execute(
            "select count(*) from table_access_policy where role='Insurance Agent' and row_filter is not null").fetchone()[0]
        print(f"Insurance Agent row-filters set on {ia_filters} tables (own-book scoping)")
        print("=" * 72)
        print(f"\nPrompt 16 builder done. {authored} metric bindings authored, {taps} access-policy rows.")
        return 0
    finally:
        con.close()


if __name__ == "__main__":
    raise SystemExit(main())
