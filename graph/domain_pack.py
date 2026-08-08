"""Insurance "industry brain" — curated domain knowledge for the graph (Prompt 15).

Seeds concept_nodes (metrics with real formulas, concepts, entity classes),
authoritative semantic_documents, and the edges connecting them, then re-embeds
the new records into LanceDB (idempotent).

Idempotent:
  * concept_nodes / graph_nodes_all / semantic_documents -> INSERT ... ON CONFLICT DO UPDATE
  * managed edges -> delete-then-insert
  * LanceDB vectors -> delete by record_id then add; logged to vector_index_log

Markets: Singapore (SGD / MAS) and Hong Kong (HKD / IA) so cross-market
demand/region analytics work.

Run AFTER build_graph.py (Prompt 10). Usage:
    python graph/domain_pack.py            # seed + re-embed
    python graph/domain_pack.py --no-embed # seed only (fast)
"""
from __future__ import annotations

import argparse
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
# 1. CORE METRICS  (id, name, definition, formula, grain, area, owner, synonyms)
# ---------------------------------------------------------------------------
METRICS = [
    ("metric::new_business_premium", "New Business Premium (NBP)",
     "Total first-year (annualised) premium from newly issued policies in a period.",
     "SUM(annual_premium) WHERE policy issued in period", "policy/month", "growth", "Sales Director",
     "NBP; new sales; first year premium; new business APE"),
    ("metric::ape", "Annualised Premium Equivalent (APE)",
     "Standard new-business measure that normalises regular and single premium.",
     "regular_premium + 0.10 * single_premium", "policy", "growth", "Executive Leadership",
     "APE; annualised premium equivalent; weighted new business"),
    ("metric::persistency_13m", "13-Month Persistency",
     "Share of policies still in force 13 months after issue — the key early-retention signal.",
     "policies_in_force_at_13m / policies_issued_13m_ago", "policy cohort", "retention", "Agency Manager",
     "13 month persistency; early persistency; retention rate; renewal rate"),
    ("metric::persistency_25m", "25-Month Persistency",
     "Share of policies still in force 25 months after issue (second-year retention).",
     "policies_in_force_at_25m / policies_issued_25m_ago", "policy cohort", "retention", "Agency Manager",
     "25 month persistency; second year persistency"),
    ("metric::lapse_rate", "Lapse Rate",
     "Proportion of in-force policies that lapsed over the period due to non-payment.",
     "lapsed_policies / average_in_force_policies", "policy/period", "retention", "Agency Manager",
     "lapse ratio; policy lapse; attrition; fall-off"),
    ("metric::surrender_rate", "Surrender Rate",
     "Proportion of policies voluntarily surrendered for cash value over the period.",
     "surrendered_policies / average_in_force_policies", "policy/period", "retention", "Agency Manager",
     "surrender ratio; voluntary termination; cash-out rate"),
    ("metric::free_look_cancellation_rate", "Free-Look Cancellation Rate",
     "Share of new policies cancelled within the regulatory free-look (cooling-off) window.",
     "free_look_cancellations / newly_issued_policies", "policy/month", "retention", "Agency Manager",
     "cooling off cancellation; free look; early cancellation"),
    ("metric::claims_ratio", "Claims Ratio (Loss Ratio)",
     "Claims incurred relative to premium earned — core underwriting profitability gauge.",
     "claims_paid / earned_premium", "product/period", "claims", "Claims Manager",
     "loss ratio; claims ratio; incurred loss ratio"),
    ("metric::expense_ratio", "Expense Ratio",
     "Operating and acquisition expenses relative to earned premium.",
     "operating_expenses / earned_premium", "company/period", "finance", "Executive Leadership",
     "cost ratio; expense ratio; acquisition cost ratio"),
    ("metric::combined_ratio", "Combined Ratio",
     "Total underwriting cost ratio; below 100% indicates an underwriting profit.",
     "claims_ratio + expense_ratio", "company/period", "finance", "Executive Leadership",
     "combined operating ratio; COR; underwriting profitability"),
    ("metric::clv", "Customer Lifetime Value (CLV)",
     "Expected economic value of a customer across their tenure, net of servicing cost.",
     "expected_annual_premium * expected_tenure_years * margin - cost_to_serve", "customer", "growth", "Executive Leadership",
     "CLV; LTV; lifetime value; customer value"),
    ("metric::cross_sell_ratio", "Cross-Sell Ratio",
     "Average number of distinct policies/products held per customer.",
     "total_active_policies / total_customers", "customer", "growth", "Sales Director",
     "policies per customer; product holding; cross holding ratio"),
    ("metric::up_sell_rate", "Up-Sell Rate",
     "Share of customers who upgraded to a higher-tier or higher-sum-assured plan.",
     "upgraded_policies / eligible_policies", "customer/period", "growth", "Sales Director",
     "upgrade rate; up-sell; plan upgrade"),
    ("metric::repurchase_rate", "Repurchase Rate",
     "Share of customers who buy an additional policy within the repurchase window (6-24 months).",
     "customers_with_2nd_policy_in_window / total_customers", "customer", "growth", "Sales Director",
     "repeat purchase; second purchase; rebuy rate; repurchase"),
    ("metric::time_to_repurchase", "Time to Repurchase",
     "Average elapsed time between a customer's first and second policy purchase.",
     "AVG(days_between_first_and_second_policy)", "customer", "growth", "Sales Director",
     "repurchase gap; days to rebuy; time between purchases"),
    ("metric::lead_conversion_rate", "Lead Conversion Rate",
     "Share of leads that convert to issued policies (overall and per funnel stage).",
     "issued_policies_from_leads / total_leads", "lead/period", "marketing", "Campaign Manager",
     "lead to policy; funnel conversion; lead win rate"),
    ("metric::quote_to_bind_rate", "Quote-to-Bind Rate",
     "Share of quotes that result in a bound (issued) policy.",
     "bound_policies / quotes_issued", "quote/period", "distribution", "Sales Director",
     "quote to bind; bind rate; quote conversion"),
    ("metric::proposal_acceptance_rate", "Proposal Acceptance Rate",
     "Share of proposals accepted by the customer and advanced to application.",
     "accepted_proposals / proposals_issued", "proposal/period", "distribution", "Sales Director",
     "proposal acceptance; offer acceptance"),
    ("metric::campaign_response_rate", "Campaign Response Rate",
     "Share of targeted prospects who responded to a campaign.",
     "campaign_responses / campaign_targets", "campaign", "marketing", "Campaign Manager",
     "response rate; open/click rate; engagement rate"),
    ("metric::campaign_conversion", "Campaign Conversion Rate",
     "Share of campaign targets that converted to a policy.",
     "campaign_conversions / campaign_targets", "campaign", "marketing", "Campaign Manager",
     "campaign conversion; campaign win rate"),
    ("metric::campaign_roi", "Campaign ROI",
     "Return on a campaign's spend from attributed converted premium.",
     "(attributed_conversion_premium - campaign_budget) / campaign_budget", "campaign", "marketing", "Campaign Manager",
     "campaign return; marketing ROI; ROAS"),
    ("metric::product_demand_index", "Product Demand Index",
     "Composite, time-aware demand signal blending quotes, leads and campaign responses by product.",
     "z(quotes) + z(leads) + z(campaign_responses) over rolling window", "product/month", "growth", "Executive Leadership",
     "demand index; demand sensing; product appetite; interest index"),
    ("metric::agent_productivity_mapa", "Agent Productivity (MAPA)",
     "Composite agent activity score across Meetings, Activities, Proposals and Applications.",
     "weighted(meetings, activities, proposals, applications)", "agent/month", "distribution", "Sales Director",
     "MAPA; agent activity; productivity; meetings activities proposals applications"),
    ("metric::agent_target_achievement", "Agent Target Achievement",
     "Agent attainment of their new-business target for the period.",
     "actual_value / target_value", "agent/period", "distribution", "Sales Director",
     "attainment; quota achievement; target achievement; goal attainment"),
    ("metric::agent_persistency", "Agent Persistency",
     "Persistency of the book sold by an agent — quality of their sales.",
     "agent_policies_in_force_at_13m / agent_policies_issued_13m_ago", "agent/cohort", "distribution", "Agency Manager",
     "agent retention; book quality; agent persistency"),
    ("metric::propensity_to_buy", "Propensity to Buy",
     "Model-estimated probability that a customer purchases an additional product.",
     "model_scores.probability WHERE score_name='propensity_to_buy'", "customer", "growth", "Sales Director",
     "buy propensity; purchase likelihood; cross-sell propensity; next best product score"),
    ("metric::churn_risk", "Churn Risk",
     "Model-estimated probability that a customer disengages or leaves the book.",
     "model_scores.probability WHERE score_name='churn'", "customer", "retention", "Agency Manager",
     "churn probability; attrition risk; disengagement risk"),
    ("metric::lapse_risk", "Lapse Propensity",
     "Per-policy model probability of lapse, used to prioritise retention action.",
     "model_scores.probability WHERE score_name='lapse_risk'", "policy", "retention", "Agency Manager",
     "lapse propensity; lapse score; lapse likelihood; lapse model"),
    ("metric::premium_at_risk", "Premium at Risk",
     "Annual premium on in-force policies with high/very-high lapse propensity.",
     "SUM(annual_premium) WHERE lapse_band IN ('high','very_high')", "policy", "retention", "Agency Manager",
     "premium at risk; revenue at risk; exposure"),
    ("metric::revenue_saved", "Revenue Saved",
     "Premium retained by successful retention interventions on at-risk policies.",
     "SUM(annual_premium) of at-risk policies retained/reinstated after intervention", "policy/period", "retention", "Agency Manager",
     "revenue saved; premium saved; retention value; saved premium"),
]

# ---------------------------------------------------------------------------
# 2. CORE CONCEPTS  (id, name, definition, subject_area, synonyms, market)
# ---------------------------------------------------------------------------
CONCEPTS = [
    ("concept::policy_lifecycle", "Policy Lifecycle",
     "The states a policy moves through: quote -> application -> underwriting -> issued -> in_force -> lapsed/surrendered/claimed/matured.",
     "policy", "policy states; policy journey; policy lifecycle", "ALL"),
    ("concept::state_quote", "Quote State", "Indicative pricing produced before application.", "policy", "quotation", "ALL"),
    ("concept::state_application", "Application State", "Formal application submitted for underwriting.", "policy", "application; proposal form", "ALL"),
    ("concept::state_underwriting", "Underwriting State", "Risk assessment and acceptance decision.", "policy", "underwriting; risk assessment", "ALL"),
    ("concept::state_issued", "Issued State", "Policy issued and contract in effect.", "policy", "issued; bound", "ALL"),
    ("concept::state_in_force", "In-Force State", "Active policy with premiums being paid.", "policy", "in force; active", "ALL"),
    ("concept::state_lapsed", "Lapsed State", "Policy terminated for non-payment after grace period.", "policy", "lapsed; non-payment termination", "ALL"),
    ("concept::state_surrendered", "Surrendered State", "Policy voluntarily terminated for cash value.", "policy", "surrendered; cash-out", "ALL"),
    ("concept::state_claimed", "Claimed State", "A covered event triggered a claim against the policy.", "claims", "claimed; claim event", "ALL"),
    ("concept::state_matured", "Matured State", "Policy reached the end of term and paid out / completed.", "policy", "matured; maturity", "ALL"),

    ("concept::distribution_channels", "Distribution Channels",
     "Routes to market: Agency, Bancassurance, Digital and Partner.", "distribution", "channels; distribution; routes to market", "ALL"),
    ("concept::channel_agency", "Agency Channel", "Tied/independent financial advisers selling face-to-face.", "distribution", "agency; FA; tied agents", "ALL"),
    ("concept::channel_bancassurance", "Bancassurance Channel", "Insurance sold through bank partners.", "distribution", "banca; bank channel", "ALL"),
    ("concept::channel_digital", "Digital Channel", "Direct online / app-based purchase.", "distribution", "digital; online; direct", "ALL"),
    ("concept::channel_partner", "Partner Channel", "Affinity, broker and ecosystem partners.", "distribution", "partner; broker; affinity", "ALL"),

    ("concept::segment_young_professional", "Young Professional", "Early-career, digitally native, protection-starter segment.", "customer", "young professional; emerging affluent", "ALL"),
    ("concept::segment_affluent_wealth", "Affluent Wealth", "High-investable-asset customers seeking wealth and legacy solutions.", "customer", "affluent; HNW; wealth", "ALL"),
    ("concept::segment_sme_owner", "SME Owner", "Business owners with keyman, employee-benefit and personal needs.", "customer", "SME; business owner; entrepreneur", "ALL"),
    ("concept::segment_established_professional", "Established Professional", "Mid-career professionals with family protection and savings goals.", "customer", "established professional; mid-career", "ALL"),
    ("concept::segment_mass_market", "Mass Market", "Price-sensitive mainstream customers; core health and term needs.", "customer", "mass market; mass", "ALL"),
    ("concept::segment_pre_retiree", "Pre-Retiree", "Customers nearing retirement focused on income and legacy.", "customer", "pre-retiree; retirement; decumulation", "ALL"),

    ("concept::line_health", "Health Line", "Hospitalisation, critical illness and medical reimbursement products.", "product", "health; medical; PRUShield; IP", "ALL"),
    ("concept::line_savings", "Savings Line", "Endowment and participating savings products.", "product", "savings; endowment; par", "ALL"),
    ("concept::line_protection", "Protection Line", "Term and whole-life mortality/morbidity protection.", "product", "protection; term; whole life", "ALL"),
    ("concept::line_investment", "Investment Line", "Investment-linked plans (ILP) with unit-linked returns.", "product", "investment; ILP; unit linked", "ALL"),
    ("concept::rider", "Rider", "Supplementary benefit attached to a base policy (e.g., CI, waiver).", "product", "rider; supplementary benefit; add-on", "ALL"),

    ("concept::uw_risk_band", "Underwriting Risk Band", "Risk classification: preferred / standard / substandard / decline.", "underwriting", "risk band; risk class; rating", "ALL"),
    ("concept::mdrt", "MDRT", "Million Dollar Round Table — elite agent production benchmark.", "distribution", "MDRT; COT; TOT; elite producer", "ALL"),
    ("concept::peer_cluster", "Peer Cluster", "Group of comparable agents used for fair benchmarking and coaching.", "distribution", "peer group; cluster; benchmark cohort", "ALL"),

    # markets
    ("concept::market_sg", "Singapore Market", "Singapore life & health market; currency SGD; regulator MAS.", "market", "Singapore; SG; SGD; MAS", "SG"),
    ("concept::market_hk", "Hong Kong Market", "Hong Kong life & health market; currency HKD; regulator IA.", "market", "Hong Kong; HK; HKD; IA", "HK"),
]

REGIONS = [
    ("concept::region_sg_central", "SG Central", "SG"), ("concept::region_sg_east", "SG East", "SG"),
    ("concept::region_sg_west", "SG West", "SG"), ("concept::region_sg_north", "SG North", "SG"),
    ("concept::region_sg_northeast", "SG North-East", "SG"),
    ("concept::region_hk_island", "HK Island", "HK"), ("concept::region_hk_kowloon", "HK Kowloon", "HK"),
    ("concept::region_hk_nt", "HK New Territories", "HK"),
]

# ---------------------------------------------------------------------------
# 3. ENTITY CLASSES  (id, name, table, area, synonyms)
# ---------------------------------------------------------------------------
ENTITY_CLASSES = [
    ("entity_class::customer", "customers", "customers", "customer", "customer; policyholder; client"),
    ("entity_class::agent", "agents", "agents", "distribution", "agent; adviser; FA; producer"),
    ("entity_class::policy", "policies", "policies", "policy", "policy; contract; cover"),
    ("entity_class::product", "products", "products", "product", "product; plan; scheme"),
    ("entity_class::campaign", "campaigns", "campaigns", "marketing", "campaign; programme"),
    ("entity_class::lead", "leads", "leads", "marketing", "lead; prospect; enquiry"),
    ("entity_class::claim", "claims", "claims", "claims", "claim; loss"),
    ("entity_class::household", "households", "households", "customer", "household; family unit"),
    ("entity_class::model_scores", "model_scores", "model_scores", "analytics", "model scores; predictions"),
    ("entity_class::next_best_action", "next_best_actions", "next_best_actions", "decisioning", "next best action; NBA; recommended action"),
]

# ---------------------------------------------------------------------------
# 4. STANDARD BUSINESS DEFINITIONS (semantic_documents) — ~20
# ---------------------------------------------------------------------------
DOCS = [
    ("doc::persistency", "Persistency: definition and why it matters", "metric", "retention",
     "Persistency measures how many policies remain in force a fixed number of months after issue — 13-month and 25-month "
     "persistency are the industry standards. It is computed as policies still in force at month N divided by the cohort issued "
     "N months earlier. High persistency signals quality sales, suitable advice and satisfied customers; low persistency erodes "
     "embedded value, wastes acquisition cost, and often foreshadows lapse. Persistency is monitored by product, channel, agent "
     "and segment because deterioration usually concentrates in specific pockets (e.g., investment-linked plans or mass-market "
     "young families)."),
    ("doc::lapse_prediction", "How lapse is predicted", "metric", "retention",
     "Lapse occurs when a policy terminates because premiums stop after the grace period. It is predicted with a model "
     "(lapse propensity / lapse_risk) trained on leading indicators: missed or late payments, falling engagement, prior "
     "complaints, payment method, tenure, product type and affordability proxies. Policies are banded LOW/MEDIUM/HIGH/VERY_HIGH; "
     "high-band, high-premium policies form the 'premium at risk' pool that retention teams work first. The earliest and "
     "strongest signal is a missed payment, so payment behaviour is weighted heavily."),
    ("doc::cross_vs_up_sell", "Cross-sell vs up-sell", "concept", "growth",
     "Cross-sell means selling a customer an additional product in a different need area (e.g., adding a health plan to a "
     "savings customer), increasing the cross-sell ratio (policies per customer). Up-sell means moving a customer to a higher "
     "tier or larger sum assured within the same need. Cross-sell widens the relationship and improves retention; up-sell "
     "deepens value per policy. Both are triggered by propensity-to-buy scores and life-stage events."),
    ("doc::repurchase_journey", "The repurchase journey", "concept", "growth",
     "Most additional purchases happen 6-24 months after the first policy, once trust is established and a life event occurs. "
     "Repurchase rate is the share of customers who buy a second policy within that window; time-to-repurchase is the average "
     "gap. Affluent and established-professional segments repurchase sooner and more often. Customers entering the repurchase "
     "window with high propensity-to-buy are prime next-best-action targets."),
    ("doc::campaign_attribution", "Campaign attribution logic", "concept", "marketing",
     "Attribution links marketing spend to outcomes: a campaign selects targets, some respond, responses become leads, leads "
     "convert through the funnel to issued policies, and the resulting premium is credited back to the campaign. Campaign ROI "
     "is (attributed converted premium − budget) / budget. Clean attribution requires the chain campaign_target -> "
     "campaign_response -> lead -> opportunity -> policy to be preserved end-to-end."),
    ("doc::demand_sensing", "Demand sensing in insurance", "concept", "growth",
     "Demand sensing blends forward-looking signals — quote volume, lead inflow, campaign responses, web/app interest and "
     "seasonality — into a product demand index per line and region. Unlike sales (a lagging outcome), demand signals lead "
     "sales by weeks, enabling capacity, pricing and campaign decisions. Q1 and Q4 typically show seasonal demand peaks in "
     "the Singapore and Hong Kong markets."),
    ("doc::mapa_framework", "The MAPA productivity framework", "concept", "distribution",
     "MAPA tracks the agent activity funnel: Meetings held, Activities logged, Proposals presented and Applications submitted. "
     "It is a leading indicator of new business — declining MAPA predicts a future sales dip even when current premium looks "
     "healthy. Managers compare an agent's MAPA against their peer cluster to target coaching fairly."),
    ("doc::nbp_ape", "New Business Premium and APE", "metric", "growth",
     "New Business Premium (NBP) is the first-year annualised premium from newly issued policies and is the headline growth "
     "number. Because single-premium products distort comparison, the industry also reports Annualised Premium Equivalent "
     "(APE) = regular premium + 10% of single premium, giving a like-for-like view of new-business value across product mixes."),
    ("doc::loss_combined_ratio", "Claims, expense and combined ratios", "metric", "finance",
     "The claims (loss) ratio is claims paid divided by earned premium; the expense ratio is operating and acquisition cost "
     "over earned premium. Their sum is the combined ratio — below 100% means the book is underwriting-profitable before "
     "investment income. Health lines typically run higher loss ratios than protection lines."),
    ("doc::clv", "Customer Lifetime Value in life insurance", "metric", "growth",
     "CLV estimates the net economic value of a customer over their expected tenure: expected annual premium × tenure × margin, "
     "less cost-to-serve. In life & health, long tenures and cross-holdings make CLV highly sensitive to persistency — a small "
     "lapse improvement compounds into large CLV gains. CLV bands prioritise high-value customers for human (vs digital) service."),
    ("doc::channels", "Distribution channels in SG and HK", "concept", "distribution",
     "Agency (tied/independent advisers) dominates complex life sales; bancassurance leverages bank customer bases for savings "
     "and protection; digital serves simple, low-ticket health and term directly; partner/affinity reaches niche ecosystems. "
     "Channel mix and channel-level persistency differ markedly and are managed separately in Singapore and Hong Kong."),
    ("doc::segmentation", "Customer segmentation", "concept", "customer",
     "Customers are grouped into actionable segments — Young Professional, Affluent Wealth, SME Owner, Established Professional, "
     "Mass Market and Pre-retiree — by life stage, investable assets and needs. Segmentation drives product fit, channel "
     "routing, pricing of effort, and the design of cross-sell and retention journeys."),
    ("doc::product_lines", "Product lines: Health, Savings, Protection, Investment", "concept", "product",
     "Health covers hospitalisation and critical illness; Savings provides endowment/participating accumulation; Protection "
     "delivers term and whole-life mortality/morbidity cover; Investment (investment-linked plans) blends protection with "
     "market-linked returns. Each line has distinct premium bands, persistency, claims behaviour and target segments."),
    ("doc::riders", "Riders explained", "concept", "product",
     "A rider is a supplementary benefit attached to a base policy — common riders add critical-illness acceleration, premium "
     "waiver on disability, hospital cash or enhanced medical limits. Riders raise premium and stickiness per policy and are a "
     "low-friction up-sell at issue and at renewal."),
    ("doc::uw_bands", "Underwriting risk bands", "concept", "underwriting",
     "Underwriting classifies applicants into risk bands — preferred, standard, substandard (rated) or decline — based on "
     "medical, financial and lifestyle assessment. The band sets the rating factor applied to premium and any exclusions, "
     "balancing acceptance (growth) against expected claims (profitability)."),
    ("doc::mdrt", "MDRT and agent tiers", "concept", "distribution",
     "MDRT (Million Dollar Round Table), with COT and TOT tiers, is the global benchmark of elite adviser production. Internally "
     "agents are also tiered (Top / Stable / Coaching) by premium, conversion and persistency, and benchmarked within peer "
     "clusters so that coaching and recognition are fair across territories and tenures."),
    ("doc::free_look_surrender", "Free-look period and surrender", "concept", "retention",
     "The free-look (cooling-off) period lets a new policyholder cancel within a regulated window (typically 14-21 days) for a "
     "near-full refund; a high free-look cancellation rate signals mis-selling or expectation gaps. Surrender is a later "
     "voluntary termination for cash value, distinct from lapse (which is non-payment driven)."),
    ("doc::lead_funnel", "Lead funnel stages and conversion", "concept", "marketing",
     "The new-business funnel runs lead -> opportunity -> quote -> proposal -> application -> issued policy, with characteristic "
     "drop-off and day-lags at each stage. Stage conversion rates (lead conversion, quote-to-bind, proposal acceptance) localise "
     "where pipeline value leaks and where coaching or process fixes pay off."),
    ("doc::quote_bind", "Quote-to-bind and proposal acceptance", "metric", "distribution",
     "Quote-to-bind rate is bound policies over quotes issued; proposal acceptance rate is accepted proposals over proposals "
     "presented. Together they measure mid-funnel sales effectiveness — low quote-to-bind often reflects price/positioning "
     "issues, while low proposal acceptance points to needs-matching or follow-up gaps."),
    ("doc::sg_hk_markets", "Singapore vs Hong Kong market context", "concept", "market",
     "The Singapore book is denominated in SGD and regulated by the Monetary Authority of Singapore (MAS); the Hong Kong book is "
     "denominated in HKD and regulated by the Insurance Authority (IA). Both are mature agency-led life & health markets with "
     "strong bancassurance, but differ in product preferences, regional segmentation and seasonality — so demand, premium and "
     "persistency analytics are reported per market."),
]

# ---------------------------------------------------------------------------
# 5. EDGES  (src, edge_type, dst)
# ---------------------------------------------------------------------------
EDGES = [
    ("metric::lapse_rate", "computed_from", "entity_class::policy"),
    ("metric::lapse_risk", "computed_from", "entity_class::model_scores"),
    ("metric::premium_at_risk", "computed_from", "entity_class::policy"),
    ("metric::persistency_13m", "measures", "concept::policy_lifecycle"),
    ("metric::persistency_25m", "measures", "concept::policy_lifecycle"),
    ("metric::surrender_rate", "measures", "concept::state_surrendered"),
    ("metric::free_look_cancellation_rate", "measures", "concept::policy_lifecycle"),
    ("metric::new_business_premium", "computed_from", "entity_class::policy"),
    ("metric::ape", "relates", "metric::new_business_premium"),
    ("metric::claims_ratio", "computed_from", "entity_class::claim"),
    ("metric::combined_ratio", "relates", "metric::claims_ratio"),
    ("metric::combined_ratio", "relates", "metric::expense_ratio"),
    ("metric::clv", "informs", "metric::propensity_to_buy"),
    ("metric::clv", "computed_from", "entity_class::customer"),
    ("metric::propensity_to_buy", "drives", "entity_class::next_best_action"),
    ("metric::churn_risk", "drives", "entity_class::next_best_action"),
    ("metric::lapse_risk", "drives", "entity_class::next_best_action"),
    ("metric::cross_sell_ratio", "relates", "metric::repurchase_rate"),
    ("metric::repurchase_rate", "relates", "metric::time_to_repurchase"),
    ("metric::repurchase_rate", "informs", "metric::propensity_to_buy"),
    ("metric::lead_conversion_rate", "computed_from", "entity_class::lead"),
    ("metric::quote_to_bind_rate", "relates", "metric::lead_conversion_rate"),
    ("metric::proposal_acceptance_rate", "relates", "metric::lead_conversion_rate"),
    ("metric::campaign_response_rate", "computed_from", "entity_class::campaign"),
    ("metric::campaign_conversion", "computed_from", "entity_class::campaign"),
    ("metric::campaign_roi", "relates", "metric::campaign_conversion"),
    ("metric::campaign_conversion", "attributed_to", "concept::line_health"),
    ("metric::campaign_conversion", "attributed_to", "concept::segment_mass_market"),
    ("metric::product_demand_index", "computed_from", "entity_class::lead"),
    ("metric::product_demand_index", "informs", "concept::line_investment"),
    ("metric::agent_productivity_mapa", "measures", "entity_class::agent"),
    ("metric::agent_target_achievement", "measures", "entity_class::agent"),
    ("metric::agent_persistency", "relates", "metric::persistency_13m"),
    # lifecycle states -> lifecycle
    ("concept::policy_lifecycle", "informs", "concept::state_in_force"),
    ("concept::policy_lifecycle", "informs", "concept::state_lapsed"),
    # channels / segments / lines hang off their parents
    ("concept::distribution_channels", "informs", "concept::channel_agency"),
    ("concept::distribution_channels", "informs", "concept::channel_bancassurance"),
    # markets
    ("concept::market_sg", "informs", "concept::region_sg_central"),
    ("concept::market_hk", "informs", "concept::region_hk_island"),
]


def upsert_concept(con, node_id, node_type, name, definition, formula, grain, area, owner, synonyms, market):
    con.execute(
        """
        INSERT INTO concept_nodes (node_id, node_type, name, definition, formula, default_grain,
            subject_area, owner_role, synonyms, market, created_at, updated_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT (node_id) DO UPDATE SET
            node_type=excluded.node_type, name=excluded.name, definition=excluded.definition,
            formula=excluded.formula, default_grain=excluded.default_grain, subject_area=excluded.subject_area,
            owner_role=excluded.owner_role, synonyms=excluded.synonyms, market=excluded.market,
            updated_at=excluded.updated_at
        """,
        [node_id, node_type, name, definition, formula, grain, area, owner, synonyms, market, NOW, NOW],
    )
    con.execute(
        """
        INSERT INTO graph_nodes_all (node_id, node_type, name, subject_area) VALUES (?,?,?,?)
        ON CONFLICT (node_id) DO UPDATE SET node_type=excluded.node_type, name=excluded.name, subject_area=excluded.subject_area
        """,
        [node_id, node_type, name, area],
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-embed", action="store_true", help="seed graph only; skip LanceDB re-embedding")
    args = ap.parse_args()

    con = robust_connect(DB_PATH, read_only=False)
    embed_records = []  # (lance_table, record_id, payload_dict, text_chunk)
    try:
        con.execute("ALTER TABLE concept_nodes ADD COLUMN IF NOT EXISTS synonyms VARCHAR")
        con.execute("ALTER TABLE concept_nodes ADD COLUMN IF NOT EXISTS market VARCHAR")

        # 1. metrics
        for nid, name, defn, formula, grain, area, owner, syn in METRICS:
            upsert_concept(con, nid, "metric", name, defn, formula, grain, area, owner, syn, "ALL")
            text = f"{name} | {defn} | formula: {formula} | also: {syn}"
            embed_records.append(("insurance_glossary_vectors", nid, {
                "term": name, "definition": defn, "business_context": f"metric; {area}; formula={formula}",
                "subject_area": area, "source_table": "concept_nodes"}, text))

        # 2. concepts + regions
        for nid, name, defn, area, syn, market in CONCEPTS:
            upsert_concept(con, nid, "concept", name, defn, None, None, area, None, syn, market)
            text = f"{name} | {defn} | also: {syn}"
            embed_records.append(("insurance_glossary_vectors", nid, {
                "term": name, "definition": defn, "business_context": f"concept; {area}; market={market}",
                "subject_area": area, "source_table": "concept_nodes"}, text))
        for nid, name, market in REGIONS:
            upsert_concept(con, nid, "concept", name, f"{name} sales region ({market}).", None, None, "market", None, name, market)

        # 3. entity classes
        for nid, name, table, area, syn in ENTITY_CLASSES:
            upsert_concept(con, nid, "entity_class", name, f"Entity class backed by DuckDB table '{table}'.",
                           None, table, area, None, syn, "ALL")

        # 4. semantic_documents
        for did, title, content_type, area, content in DOCS:
            chash = str(abs(hash(content)))
            con.execute(
                """
                INSERT INTO semantic_documents (semantic_document_id, document_type, source_table, title, content,
                    tags, content_hash, embedding_model, active_flag, created_at, updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT (semantic_document_id) DO UPDATE SET
                    document_type=excluded.document_type, title=excluded.title, content=excluded.content,
                    tags=excluded.tags, content_hash=excluded.content_hash, updated_at=excluded.updated_at
                """,
                [did, content_type, "concept_nodes", title, content, area, chash,
                 "models/gemini-embedding-001", True, NOW, NOW],
            )
            embed_records.append(("insurance_semantic_vectors", did, {
                "document_title": title, "document_type": content_type, "content_chunk": content,
                "chunk_index": 0, "source_table": "semantic_documents"}, f"{title}. {content}"))

        # 5. edges (managed: delete-then-insert so re-runs don't duplicate)
        managed = [(s, e, d) for s, e, d in EDGES]
        for src, etype, dst in managed:
            con.execute("DELETE FROM graph_edges WHERE src_node_id=? AND dst_node_id=? AND edge_type=?", [src, etype, dst])
            con.execute(
                """
                INSERT INTO graph_edges (edge_id, src_node_id, src_node_type, dst_node_id, dst_node_type,
                    edge_type, weight, status, created_at)
                SELECT ?, ?, n1.node_type, ?, n2.node_type, ?, 1.2, 'active', ?
                FROM graph_nodes_all n1, graph_nodes_all n2 WHERE n1.node_id=? AND n2.node_id=?
                """,
                [str(uuid.uuid4()), src, dst, etype, NOW, src, dst],
            )
        con.commit()
        print(f"[seed] metrics={len(METRICS)} concepts={len(CONCEPTS)+len(REGIONS)} "
              f"entity_classes={len(ENTITY_CLASSES)} docs={len(DOCS)} edges={len(EDGES)}")

        # ---- re-embed into LanceDB (idempotent) ----
        embedded = 0
        if not args.no_embed:
            import lancedb
            from embeddings.vector_search import LANCEDB_PATH, embed_text
            db = lancedb.connect(LANCEDB_PATH)
            tables_cache = {}
            for lance_table, rid, payload, text in embed_records:
                try:
                    if lance_table not in tables_cache:
                        tables_cache[lance_table] = db.open_table(lance_table)
                    tbl = tables_cache[lance_table]
                    vec = embed_text(text)
                    safe = str(rid).replace("'", "''")
                    tbl.delete(f"record_id = '{safe}'")
                    row = {"id": uuid.uuid4().hex, **payload, "record_id": rid, "text_chunk": text,
                           "metadata": "{\"source\":\"domain_pack\"}", "vector": vec}
                    tbl.add([row])
                    con.execute("DELETE FROM vector_index_log WHERE record_id=? AND lance_table=?", [rid, lance_table])
                    con.execute(
                        "INSERT INTO vector_index_log (table_name, record_id, chunk_text, embedded_at, model_used, vector_dims, lance_table) "
                        "VALUES (?,?,?,?,?,?,?)",
                        ["concept_nodes" if lance_table == "insurance_glossary_vectors" else "semantic_documents",
                         rid, text[:500], NOW, "models/gemini-embedding-001", len(vec), lance_table],
                    )
                    embedded += 1
                except Exception as exc:
                    print(f"  embed warn {rid}: {type(exc).__name__}: {exc}", file=sys.stderr)
            con.commit()
        print(f"[embed] re-embedded {embedded}/{len(embed_records)} records into LanceDB")

        # ---------------- VERIFY ----------------
        print("\n" + "=" * 60)
        mc = con.execute("select count(*) from concept_nodes where node_type='metric'").fetchone()[0]
        cc = con.execute("select count(*) from concept_nodes where node_type='concept'").fetchone()[0]
        ec = con.execute("select count(*) from concept_nodes where node_type='entity_class'").fetchone()[0]
        dc = con.execute("select count(*) from semantic_documents").fetchone()[0]
        edg = con.execute("select count(*) from graph_edges").fetchone()[0]
        print(f"metric nodes={mc} concept nodes={cc} entity_class nodes={ec} semantic_documents={dc} edges={edg}")
        missing = con.execute(
            "select count(*) from concept_nodes where node_type='metric' and (formula is null or formula='' or definition is null or definition='')"
        ).fetchone()[0]
        print(f"metric nodes missing formula/definition: {missing}  ->", "OK" if missing == 0 else "BAD")
        vlog = con.execute("select count(*) from vector_index_log where embedded_at >= ?", [NOW]).fetchone()[0]
        print(f"vector_index_log rows from this run: {vlog}")

        # spot check
        if not args.no_embed:
            try:
                import asyncio
                from embeddings.vector_search import search_glossary
                hits = asyncio.run(search_glossary("how do we measure customer loyalty", top_k=6))
                names = [h.get("term") for h in hits]
                print("spot-check 'customer loyalty' ->", names[:6])
                loyalty_terms = {"13-Month Persistency", "25-Month Persistency", "Repurchase Rate",
                                 "Customer Lifetime Value (CLV)", "Churn Risk", "Cross-Sell Ratio"}
                hit = any(n in loyalty_terms for n in names)
                print("  loyalty concepts surfaced:", "OK" if hit else "CHECK")
            except Exception as exc:
                print(f"  spot-check warn: {exc}")
        print("=" * 60)
        print(f"\nPrompt 15 complete. Domain pack seeded: {mc} metrics, {cc} concepts, {ec} entity classes, "
              f"{dc} documents, {edg} edges. Re-embedded {embedded} records into LanceDB.")
        return 0
    finally:
        con.close()


if __name__ == "__main__":
    raise SystemExit(main())
