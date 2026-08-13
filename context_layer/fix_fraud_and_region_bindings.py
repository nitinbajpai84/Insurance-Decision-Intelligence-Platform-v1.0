"""
Fixes two grounding gaps found in the 2026-08-12 smoke test, both instances
of the same root pattern as the Melissa Welch bug: a question needed data
that exists and joins correctly, but no metric_binding pointed to it, so the
SQL agent free-formed a plausible-looking but wrong query instead of using
(or refusing to bypass) real governed data.

1. "Claims fraud exposure" returned SGD 0.0 -- no fraud metric_binding
   existed at all, so the LLM filtered generic claims.claim_status='open'
   instead of the real, populated claim_fraud_indicators table (225 rows,
   132 claims with an unresolved indicator, $490,988 paid + $715,001 reserve
   in genuine exposure). Adds v_claims_fraud_exposure + metric::fraud_exposure.

2. "Average premium in Hong Kong" filtered products.line_of_business =
   'Hong Kong' (that column is Health/Savings/Investment/Protection, never a
   region -- policies have no region column; only agents.territory_code
   does). The join data already exists and is already governed under
   metric::premium_at_risk (which points to v_lapse_policy_risk, already
   has region + annual_premium + policy_id) -- but that metric is framed
   around lapse risk, so a plain "average premium" question never retrieves
   it. Adds metric::average_premium reusing the same proven view/columns
   under a name a plain premium question will actually match.

Metric discovery (graph/binding_resolver._vector_metric_ids) has two paths:
glossary vector search filtered to bound metric_ids, and a keyword fallback
matching metric_id's name (underscores -> spaces) literally in the question.
Both new metric_ids are chosen so the keyword fallback alone makes them
discoverable immediately, without waiting on an embedding pipeline rerun --
verify with the questions above.

Usage: venv\\Scripts\\python.exe context_layer\\fix_fraud_and_region_bindings.py
Idempotent: every insert is on-conflict-do-nothing / guarded.
"""
from __future__ import annotations

import json
import sys
import uuid
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from graph.db_util import robust_connect
from backend_v2.config import DUCKDB_PATH

FRAUD_VIEW_SQL = """
create or replace view v_claims_fraud_exposure as
select
  f.claim_fraud_indicator_id,
  f.claim_id,
  c.claim_number,
  f.customer_id,
  c.assigned_agent_id as agent_id,
  f.indicator_type,
  f.severity,
  f.indicator_score,
  f.resolved_flag,
  f.indicator_date,
  c.claim_status,
  c.loss_cause,
  c.paid_amount,
  c.reserve_amount,
  coalesce(c.paid_amount, 0) + coalesce(c.reserve_amount, 0) as total_exposure,
  a.territory_code as branch,
  case when a.territory_code like 'HK%' then 'Hong Kong' else 'Singapore' end as region
from claim_fraud_indicators f
join claims c on c.claim_id = f.claim_id
left join agents a on a.agent_id = c.assigned_agent_id
"""


def main() -> None:
    con = robust_connect(DUCKDB_PATH, read_only=False)
    try:
        con.execute(FRAUD_VIEW_SQL)
        print("[view] v_claims_fraud_exposure created/replaced")

        # --- concept_nodes: keep the ontology coherent, not just the binding ---
        con.execute(
            "insert into concept_nodes (node_id, node_type, name, definition, formula, "
            "default_grain, subject_area) values (?,?,?,?,?,?,?) "
            "on conflict (node_id) do nothing",
            ["metric::fraud_exposure", "metric", "Claims Fraud Exposure",
             "Total paid + reserved amount on claims carrying an unresolved fraud indicator "
             "(early_claim, duplicate_claim, inflated_amount, or provider_flag).",
             "SUM(paid_amount + reserve_amount) FILTER (WHERE resolved_flag = false)",
             "claim", "claims"],
        )
        con.execute(
            "insert into concept_nodes (node_id, node_type, name, definition, formula, "
            "default_grain, subject_area) values (?,?,?,?,?,?,?) "
            "on conflict (node_id) do nothing",
            ["metric::average_premium", "metric", "Average Premium",
             "Average annual premium per policy; can be broken down by region, product, "
             "or line of business. Same underlying data as premium_at_risk, framed for a "
             "general premium question rather than a lapse-risk one.",
             "AVG(annual_premium)", "policy", "policy"],
        )

        # --- metric_bindings: the actual SQL contract ---
        con.execute(
            "insert into metric_bindings (binding_id, metric_id, canonical_view, allowed_tables, "
            "allowed_columns, required_joins, default_filters, grain, formula_sql, sample_question, "
            "status, created_by) values (?,?,?,?,?,?,?,?,?,?,'active','audit-2026-08-12') "
            "on conflict (metric_id) do nothing",
            [str(uuid.uuid4()), "metric::fraud_exposure", "v_claims_fraud_exposure",
             json.dumps(["v_claims_fraud_exposure", "claim_fraud_indicators", "claims"]),
             json.dumps(["v_claims_fraud_exposure.claim_id", "v_claims_fraud_exposure.claim_number",
                        "v_claims_fraud_exposure.customer_id", "v_claims_fraud_exposure.agent_id",
                        "v_claims_fraud_exposure.indicator_type", "v_claims_fraud_exposure.severity",
                        "v_claims_fraud_exposure.indicator_score", "v_claims_fraud_exposure.resolved_flag",
                        "v_claims_fraud_exposure.claim_status", "v_claims_fraud_exposure.paid_amount",
                        "v_claims_fraud_exposure.reserve_amount", "v_claims_fraud_exposure.total_exposure",
                        "v_claims_fraud_exposure.region", "v_claims_fraud_exposure.branch"]),
             json.dumps([]), json.dumps(["resolved_flag = false"]), "claim",
             "SUM(paid_amount + reserve_amount) FILTER (WHERE resolved_flag = false)",
             "What is our claims fraud exposure right now?"],
        )
        con.execute(
            "insert into metric_bindings (binding_id, metric_id, canonical_view, allowed_tables, "
            "allowed_columns, required_joins, default_filters, grain, formula_sql, sample_question, "
            "status, created_by) values (?,?,?,?,?,?,?,?,?,?,'active','audit-2026-08-12') "
            "on conflict (metric_id) do nothing",
            [str(uuid.uuid4()), "metric::average_premium", "v_lapse_policy_risk",
             json.dumps(["v_lapse_policy_risk", "policies"]),
             json.dumps(["v_lapse_policy_risk.annual_premium", "v_lapse_policy_risk.policy_id",
                        "v_lapse_policy_risk.agent_id", "v_lapse_policy_risk.customer_id",
                        "v_lapse_policy_risk.region", "v_lapse_policy_risk.branch",
                        "v_lapse_policy_risk.product_name", "v_lapse_policy_risk.line_of_business",
                        "v_lapse_policy_risk.customer_segment", "policies.annual_premium",
                        "policies.policy_id"]),
             json.dumps([]), json.dumps([]), "policy", "AVG(annual_premium)",
             "What is average premium per policy in Hong Kong?"],
        )

        # --- graph_edges: link each new metric to the entity it's computed from,
        #     mirroring the existing computed_from/defined_by pattern (e.g. lapse_rate). ---
        for src, dst, etype in [
            ("metric::fraud_exposure", "entity_class::claim", "computed_from"),
            ("metric::average_premium", "entity_class::policy", "computed_from"),
        ]:
            exists = con.execute(
                "select 1 from concept_nodes where node_id = ?", [dst]).fetchone()
            if exists:
                con.execute(
                    "insert into graph_edges (src_node_id, src_node_type, dst_node_id, dst_node_type, "
                    "edge_type, weight, status) values (?,?,?,?,?,1.0,'active')",
                    [src, "metric", dst, "entity_class", etype],
                )

        # --- business_glossary: governed definition + future embedding source.
        #     Keyword fallback in binding_resolver works immediately without this;
        #     this makes the terms show up in the Glossary editor and, once
        #     embeddings/embed_pipeline.py is next rerun, in vector search too. ---
        for glossary_id, term, definition, domain in [
            ("metric::fraud_exposure", "Fraud Exposure",
             "Total paid + reserved claim amount carrying an unresolved fraud indicator.", "claims"),
            ("metric::average_premium", "Average Premium",
             "Average annual premium per policy, filterable by region, product, or line of business.",
             "policy"),
        ]:
            con.execute(
                "insert into business_glossary (glossary_id, term, definition, domain, active_flag) "
                "values (?,?,?,?,true) on conflict (glossary_id) do nothing",
                [glossary_id, term, definition, domain],
            )

        con.commit()
        print("[done] fraud_exposure + average_premium bindings installed")
    finally:
        con.close()


if __name__ == "__main__":
    main()
