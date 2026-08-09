"""Build the V2 ontology graph in DuckDB.

Steps:
  1. Apply graph/graph_schema.sql (concept_nodes, decision_rules, graph_edges,
     graph_nodes_all).
  2. Seed concept_nodes from business_glossary (every term = a node).
  3. Create 7 metric nodes with formulas + component edges to source columns.
  4. Create 3 process graphs (Lapse Prevention, Cross-sell Journey,
     Agent Coaching) with typed edges, incl. seed decision_rules.
  5. Hydrate entity nodes + edges from real data (customers, policies, agents,
     campaigns, claims, scores).
  6. Register the DuckPGQ PROPERTY GRAPH over graph_nodes_all / graph_edges.
  7. Print node + edge counts per type.

Rebuild-safe: edges and hydrated nodes are wiped and rebuilt each run; concept
nodes are upserted.

Usage:  venv\\Scripts\\python.exe graph\\build_graph.py
"""
from __future__ import annotations

import sys
import uuid
from pathlib import Path

import duckdb

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
DB_PATH = str(PROJECT_ROOT / "database" / "insurance_v2.duckdb")

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
from backend_v2.config import DUCKDB_CONFIG

PROPERTY_GRAPH_DDL = """
CREATE OR REPLACE PROPERTY GRAPH insurance_graph
VERTEX TABLES (graph_nodes_all LABEL gnode)
EDGE TABLES (
  graph_edges
    SOURCE KEY (src_node_id) REFERENCES graph_nodes_all (node_id)
    DESTINATION KEY (dst_node_id) REFERENCES graph_nodes_all (node_id)
    LABEL connects
)
"""

# ---------------------------------------------------------------------------
# Ontology definitions
# ---------------------------------------------------------------------------
METRICS = [
    ("metric::lapse_rate", "lapse_rate", "Share of the policy book that has lapsed.",
     "lapsed_policies / (active + renewed + lapsed policies)", "policy", "retention",
     [("policies", "policy_status")]),
    ("metric::persistency", "persistency", "Share of in-force policies retained over 13 months.",
     "(active + renewed) / (active + renewed + lapsed)", "policy", "retention",
     [("policies", "policy_status")]),
    ("metric::premium_at_risk", "premium_at_risk", "Annual premium on in-force policies with high/very_high lapse score.",
     "SUM(annual_premium) WHERE lapse_band IN ('high','very_high')", "policy", "retention",
     [("policies", "annual_premium"), ("model_scores", "probability")]),
    ("metric::campaign_conversion", "campaign_conversion", "Campaign targets that converted to a policy.",
     "conversions / targeted", "campaign", "marketing",
     [("campaign_targets", "campaign_target_id"), ("campaign_responses", "conversion_flag")]),
    ("metric::propensity_to_buy", "propensity_to_buy", "Model probability that a customer buys an additional product.",
     "model_scores.probability WHERE score_name='propensity_to_buy'", "customer", "growth",
     [("model_scores", "probability")]),
    ("metric::clv", "CLV", "Customer lifetime value band (derived proxy from in-force annual premium).",
     "tier(SUM(annual_premium in-force))", "customer", "growth",
     [("policies", "annual_premium")]),
    ("metric::agent_target_achievement", "agent_target_achievement", "Agent attainment versus latest target period.",
     "agent_targets.actual_value / agent_targets.target_value", "agent", "distribution",
     [("agent_targets", "attainment_pct"), ("agent_performance", "new_business_premium")]),
    ("metric::lapse_risk", "lapse_risk", "Per-policy model probability of lapse.",
     "model_scores.probability WHERE score_name='lapse_risk'", "policy", "retention",
     [("model_scores", "probability")]),
]

# (node_id, type, name, subject_area)
PROCESS_NODES = [
    # a. Lapse Prevention
    ("process::lapse_review", "process", "Lapse Review", "retention"),
    ("process::retention_action", "process", "Retention Action", "retention"),
    ("decision::retention_decision", "decision", "Retention Decision", "retention"),
    ("entity_class::next_best_action", "entity_class", "next_best_actions", "decisioning"),
    ("entity_class::agent", "entity_class", "agents", "distribution"),
    ("metric::revenue_saved", "metric", "revenue_saved", "retention"),
    # b. Cross-sell Journey
    ("process::campaign_targeting", "process", "Campaign Targeting", "marketing"),
    ("entity_class::campaign", "entity_class", "campaigns", "marketing"),
    ("entity_class::lead", "entity_class", "leads", "marketing"),
    ("entity_class::opportunity", "entity_class", "opportunities", "growth"),
    ("entity_class::policy", "entity_class", "policies", "policy"),
    ("entity_class::customer", "entity_class", "customers", "customer"),
    ("entity_class::claim", "entity_class", "claims", "claims"),
    ("entity_class::model_scores", "entity_class", "model_scores", "analytics"),
    ("entity_class::agent_performance", "entity_class", "agent_performance", "distribution"),
    # c. Agent Coaching
    ("process::peer_baseline", "process", "Peer Baseline", "distribution"),
    ("decision::coaching_decision", "decision", "Coaching Decision", "distribution"),
    ("entity_class::sales_director", "entity_class", "sales_director", "distribution"),
]

# (src, dst, edge_type)
PROCESS_EDGES = [
    # a. Lapse Prevention: model_scores -> lapse_review -> retention_action ->
    #    next_best_action -> agent, measured_by revenue_saved
    ("entity_class::model_scores", "process::lapse_review", "triggers"),
    ("metric::lapse_risk", "process::lapse_review", "considers"),
    ("process::lapse_review", "decision::retention_decision", "informs"),
    ("decision::retention_decision", "process::retention_action", "triggers"),
    ("process::retention_action", "entity_class::next_best_action", "routes_to"),
    ("entity_class::next_best_action", "entity_class::agent", "routes_to"),
    ("process::retention_action", "metric::revenue_saved", "measured_by"),
    ("metric::premium_at_risk", "decision::retention_decision", "considers"),
    # b. Cross-sell Journey: propensity -> campaign_target -> lead ->
    #    opportunity -> policy
    ("metric::propensity_to_buy", "process::campaign_targeting", "considers"),
    ("process::campaign_targeting", "entity_class::campaign", "routes_to"),
    ("entity_class::campaign", "entity_class::lead", "targets"),
    ("entity_class::lead", "entity_class::opportunity", "informs"),
    ("entity_class::opportunity", "entity_class::policy", "informs"),
    ("metric::campaign_conversion", "process::campaign_targeting", "measured_by"),
    ("metric::clv", "process::campaign_targeting", "considers"),
    # c. Agent Coaching: agent_performance -> peer_baseline -> coaching_rule ->
    #    coaching_decision -> sales_director
    ("entity_class::agent_performance", "process::peer_baseline", "informs"),
    ("process::peer_baseline", "decision::coaching_decision", "informs"),
    ("decision::coaching_decision", "entity_class::sales_director", "escalates_to"),
    ("metric::agent_target_achievement", "decision::coaching_decision", "considers"),
]

SEED_RULES = [
    {
        "name": "High-value lapse escalation",
        "condition_text": "lapse_risk above 0.70 and annual premium above S$50,000",
        "condition_json": '[{"metric":"lapse_risk","operator":">","value":0.70},{"metric":"premium_at_risk","operator":">","value":50000}]',
        "threshold_json": '{"lapse_risk":0.70,"premium_at_risk":50000}',
        "action_text": "Escalate to branch manager and create a retention next-best-action",
        "assigned_role": "Agency Manager",
        "priority": 1,
        "edges": [("metric::lapse_risk", "considers"), ("metric::premium_at_risk", "considers"),
                  ("decision::retention_decision", "triggers")],
    },
    {
        "name": "Hot cross-sell lead",
        "condition_text": "propensity_to_buy above 0.80 and no campaign contact in 30 days",
        "condition_json": '[{"metric":"propensity_to_buy","operator":">","value":0.80}]',
        "threshold_json": '{"propensity_to_buy":0.80}',
        "action_text": "Add customer to the next cross-sell campaign wave",
        "assigned_role": "Campaign Manager",
        "priority": 2,
        "edges": [("metric::propensity_to_buy", "considers"), ("process::campaign_targeting", "triggers")],
    },
    {
        "name": "Coaching trigger on attainment",
        "condition_text": "agent_target_achievement below 60% for two consecutive periods",
        "condition_json": '[{"metric":"agent_target_achievement","operator":"<","value":60}]',
        "threshold_json": '{"agent_target_achievement":60}',
        "action_text": "Schedule coaching with the sales director",
        "assigned_role": "Sales Director",
        "priority": 3,
        "edges": [("metric::agent_target_achievement", "considers"), ("decision::coaching_decision", "triggers")],
    },
]


def upsert_concept(con, node_id, node_type, name, definition=None, formula=None,
                   grain=None, subject_area=None, owner_role=None, glossary_id=None):
    con.execute(
        "insert or replace into concept_nodes (node_id, node_type, name, definition, formula, "
        "default_grain, subject_area, owner_role, source_glossary_id) values (?,?,?,?,?,?,?,?,?)",
        [node_id, node_type, name, definition, formula, grain, subject_area, owner_role, glossary_id],
    )


def add_edge(con, src, src_type, dst, dst_type, edge_type, weight=None, metadata=None):
    con.execute(
        "insert into graph_edges (edge_id, src_node_id, src_node_type, dst_node_id, dst_node_type, "
        "edge_type, weight, metadata) values (?,?,?,?,?,?,?,?)",
        [str(uuid.uuid4()), src, src_type, dst, dst_type, edge_type, weight, metadata],
    )


def main() -> int:
    con = duckdb.connect(DB_PATH, read_only=False, config=DUCKDB_CONFIG)
    try:
        # 1. schema
        con.execute((SCRIPT_DIR / "graph_schema.sql").read_text(encoding="utf-8"))
        # rebuild-safe wipe of derived structures (user-captured rules persist;
        # only build-seeded rules + their concept nodes are recycled)
        con.execute("delete from graph_edges")
        con.execute("delete from graph_nodes_all")
        old_seed = [r[0] for r in con.execute(
            "select rule_id from decision_rules where created_by = 'build_graph'").fetchall()]
        if old_seed:
            ph = ",".join(["?"] * len(old_seed))
            con.execute(f"delete from concept_nodes where node_id in ({ph})",
                        [f"rule::{r}" for r in old_seed])
            con.execute(f"delete from decision_rules where rule_id in ({ph})", old_seed)
        print("[1] schema applied; edges/nodes_all wiped for rebuild")

        # 2. glossary terms -> concept nodes
        terms = con.execute(
            "select glossary_id, term, definition, coalesce(domain,'general'), coalesce(owner,'') "
            "from business_glossary"
        ).fetchall()
        for gid, term, definition, domain, owner in terms:
            slug = term.lower().replace(" ", "_").replace("(", "").replace(")", "")
            upsert_concept(con, f"term::{slug}", "term", term, definition,
                           subject_area=domain, owner_role=owner or None, glossary_id=gid)
        print(f"[2] seeded {len(terms)} glossary term nodes")

        # 3. metric nodes + component edges to source columns
        col_nodes = 0
        for node_id, name, definition, formula, grain, area, columns in METRICS:
            upsert_concept(con, node_id, "metric", name, definition, formula, grain, area)
            for table, column in columns:
                col_id = f"column::{table}.{column}"
                upsert_concept(con, col_id, "term", f"{table}.{column}",
                               f"Source column {table}.{column}", subject_area=area)
                add_edge(con, node_id, "metric", col_id, "term", "defined_by")
                col_nodes += 1
        print(f"[3] created {len(METRICS)} metric nodes + {col_nodes} column component edges")

        # 4. process graphs + seed decision rules
        for node_id, ntype, name, area in PROCESS_NODES:
            upsert_concept(con, node_id, ntype, name, subject_area=area)
        for src, dst, etype in PROCESS_EDGES:
            stype = src.split("::")[0]
            dtype = dst.split("::")[0]
            add_edge(con, src, stype, dst, dtype, etype)
        for rule in SEED_RULES:
            rid = str(uuid.uuid4())
            con.execute(
                "insert into decision_rules (rule_id, name, condition_text, condition_json, "
                "threshold_json, action_text, assigned_role, priority, status, created_by, reason) "
                "values (?,?,?,?,?,?,?,?,?,?,?)",
                [rid, rule["name"], rule["condition_text"], rule["condition_json"],
                 rule["threshold_json"], rule["action_text"], rule["assigned_role"],
                 rule["priority"], "active", "build_graph", "seed rule"],
            )
            rule_node = f"rule::{rid}"
            upsert_concept(con, rule_node, "decision", rule["name"],
                           rule["condition_text"], subject_area="decisioning",
                           owner_role=rule["assigned_role"])
            for target, etype in rule["edges"]:
                add_edge(con, rule_node, "decision", target, target.split("::")[0], etype)
        print(f"[4] process graphs ({len(PROCESS_NODES)} nodes, {len(PROCESS_EDGES)} edges) "
              f"+ {len(SEED_RULES)} seed decision rules")

        # 5. hydrate entity nodes + edges from real data (set-based inserts)
        con.execute("""
            insert into graph_nodes_all
            select node_id, node_type, name, subject_area from concept_nodes
        """)
        con.execute("""
            insert or ignore into graph_nodes_all
            select c.customer_id, 'customer', coalesce(p.display_name, c.customer_number), 'customer'
            from customers c left join parties p on p.party_id = c.party_id
        """)
        con.execute("""
            insert or ignore into graph_nodes_all
            select policy_id, 'policy', policy_number, 'policy' from policies
        """)
        con.execute("""
            insert or ignore into graph_nodes_all
            select a.agent_id, 'agent', coalesce(p.display_name, a.agent_number), 'distribution'
            from agents a left join parties p on p.party_id = a.party_id
        """)
        con.execute("""
            insert or ignore into graph_nodes_all
            select campaign_id, 'campaign', campaign_name, 'marketing' from campaigns
        """)
        con.execute("""
            insert or ignore into graph_nodes_all
            select claim_id, 'claim', claim_number, 'claims' from claims
        """)
        con.execute("""
            insert or ignore into graph_nodes_all
            select distinct lead_id, 'lead', lead_id, 'marketing'
            from campaign_targets where lead_id is not null
        """)

        hydration = [
            # customers ─owns→ policies
            ("""insert into graph_edges (edge_id, src_node_id, src_node_type, dst_node_id, dst_node_type, edge_type)
                select uuid(), customer_id, 'customer', policy_id, 'policy', 'owns' from policies
                where customer_id is not null""", "customer owns policy"),
            # policies ─scored_by→ metric::lapse_risk (weight = probability)
            ("""insert into graph_edges (edge_id, src_node_id, src_node_type, dst_node_id, dst_node_type, edge_type, weight)
                select uuid(), policy_id, 'policy', 'metric::lapse_risk', 'metric', 'scored_by', lapse_probability
                from v_policy_lapse_score""", "policy scored_by lapse_risk"),
            # customers ─scored_by→ metric::propensity_to_buy
            ("""insert into graph_edges (edge_id, src_node_id, src_node_type, dst_node_id, dst_node_type, edge_type, weight)
                select uuid(), customer_id, 'customer', 'metric::propensity_to_buy', 'metric', 'scored_by', propensity_to_buy
                from v_customer_propensity""", "customer scored_by propensity"),
            # agents ─manages→ customers (primary advisor)
            ("""insert into graph_edges (edge_id, src_node_id, src_node_type, dst_node_id, dst_node_type, edge_type)
                select uuid(), advisor_agent_id, 'agent', customer_id, 'customer', 'manages'
                from v_customer_360 where advisor_agent_id is not null""", "agent manages customer"),
            # campaigns ─targets→ leads (falls back to customers when no lead)
            ("""insert into graph_edges (edge_id, src_node_id, src_node_type, dst_node_id, dst_node_type, edge_type)
                select distinct uuid(), campaign_id, 'campaign',
                       coalesce(lead_id, customer_id), case when lead_id is not null then 'lead' else 'customer' end,
                       'targets'
                from campaign_targets where coalesce(lead_id, customer_id) is not null""", "campaign targets lead/customer"),
            # claims ─against→ policies
            ("""insert into graph_edges (edge_id, src_node_id, src_node_type, dst_node_id, dst_node_type, edge_type)
                select uuid(), claim_id, 'claim', policy_id, 'policy', 'against'
                from claims where policy_id is not null""", "claim against policy"),
            # agents ─measured_by→ metric::agent_target_achievement (weight = attainment)
            ("""insert into graph_edges (edge_id, src_node_id, src_node_type, dst_node_id, dst_node_type, edge_type, weight)
                select uuid(), agent_id, 'agent', 'metric::agent_target_achievement', 'metric', 'measured_by', target_achievement_pct
                from v_agent_360""", "agent measured_by target_achievement"),
        ]
        for sql, label in hydration:
            before = con.execute("select count(*) from graph_edges").fetchone()[0]
            con.execute(sql)
            after = con.execute("select count(*) from graph_edges").fetchone()[0]
            print(f"[5] hydrated {after - before:>6} edges: {label}")

        # prune any edge whose endpoint is missing from the vertex table
        # (keeps the DuckPGQ property graph consistent)
        con.execute("""
            delete from graph_edges
            where src_node_id not in (select node_id from graph_nodes_all)
               or dst_node_id not in (select node_id from graph_nodes_all)
        """)
        con.commit()

        # 6. register the DuckPGQ property graph
        pgq_ok = False
        try:
            con.execute("INSTALL duckpgq FROM community; LOAD duckpgq;")
            con.execute(PROPERTY_GRAPH_DDL)
            probe = con.execute("""
                select count(*) from graph_table (insurance_graph
                  MATCH (a:gnode)-[e:connects]->(b:gnode)
                  COLUMNS (a.node_id)
                ) limit 1
            """).fetchone()[0]
            pgq_ok = True
            print(f"[6] DuckPGQ property graph 'insurance_graph' registered (MATCH probe: {probe} rows)")
        except Exception as exc:
            print(f"[6] WARN DuckPGQ registration failed ({type(exc).__name__}: {str(exc)[:160]}) — "
                  "traversal will use the recursive-SQL fallback")

        # 7. counts
        print("\n=== Node counts (graph_nodes_all) ===")
        for ntype, n in con.execute(
            "select node_type, count(*) from graph_nodes_all group by 1 order by 2 desc"
        ).fetchall():
            print(f"   {ntype:<14} {n}")
        total_nodes = con.execute("select count(*) from graph_nodes_all").fetchone()[0]
        print("=== Edge counts (graph_edges) ===")
        for etype, n in con.execute(
            "select edge_type, count(*) from graph_edges group by 1 order by 2 desc"
        ).fetchall():
            print(f"   {etype:<14} {n}")
        total_edges = con.execute("select count(*) from graph_edges").fetchone()[0]
        rules = con.execute("select count(*) from decision_rules").fetchone()[0]
        print(f"\nTOTAL: {total_nodes} nodes, {total_edges} edges, {rules} decision rules, "
              f"property_graph={'registered' if pgq_ok else 'fallback-SQL'}")
        return 0 if (total_nodes > 150 and total_edges > 300) else 1
    finally:
        con.close()


if __name__ == "__main__":
    raise SystemExit(main())
