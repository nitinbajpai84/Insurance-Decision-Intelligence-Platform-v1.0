"""
Seed governed decision_rules the demo's talkable agents actually need.

The three pre-existing rules (High-value lapse escalation, Hot cross-sell lead,
Coaching trigger on attainment) cover lapse_risk, propensity_to_buy and
agent_target_achievement. A21 (the PruAction-style coaching flagship) and O9
(proactive renewals) naturally query `persistency` — no active rule referenced
it, so their answers had nothing governed to cite and either invented a
threshold or (after the insight-prompt fix) went vague instead.

Inserted directly with status='active' (not via rule_capture's NL parser) so
the exact numbers are deliberate and reviewable in this file, not LLM-guessed.
Idempotent: skipped if a rule with the same name already exists.

Usage: venv\\Scripts\\python.exe context_layer\\seed_norms.py
"""
from __future__ import annotations

import json
import sys
import uuid
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend_v2.config import DUCKDB_PATH
from graph.db_util import robust_connect

# NOTE: the ontology has TWO separate persistency metric nodes —
# metric::persistency (general) and metric::agent_persistency (agent-scoped,
# what binding_resolver actually resolves to for Agency-Manager-role questions
# like A21's). Both are wired here so the rule surfaces regardless of which
# resolution path a given question takes. This duplication is a pre-existing
# ontology gap, not introduced by this seed — worth merging in a later pass.
RULES = [
    {
        "name": "Persistency coaching intervention",
        "condition_text": "13-month persistency below 70% triggers mandatory coaching",
        "condition_json": [
            {"metric": "persistency", "operator": "<", "value": 0.70},
            {"metric": "agent_persistency", "operator": "<", "value": 0.70},
        ],
        "threshold_json": {"persistency": 0.70},
        "action_text": "Assign agent to mandatory coaching track; escalate to Agency Manager if unresolved after one cycle",
        "assigned_role": "Agency Manager",
        "priority": 2,
        "reason": "SG/HK persistency governance baseline (context-layer norms pack, B1)",
    },
    {
        "name": "Renewal at-risk outreach",
        "condition_text": "Persistency below 80% and premium at risk above S$20K triggers proactive renewal outreach",
        "condition_json": [
            {"metric": "persistency", "operator": "<", "value": 0.80},
            {"metric": "agent_persistency", "operator": "<", "value": 0.80},
            {"metric": "premium_at_risk", "operator": ">", "value": 20000},
        ],
        "threshold_json": {"persistency": 0.80, "premium_at_risk": 20000},
        "action_text": "Trigger proactive renewal outreach call within 5 business days",
        "assigned_role": "Insurance Agent",
        "priority": 3,
        "reason": "SG/HK persistency governance baseline (context-layer norms pack, B1)",
    },
]


def main() -> int:
    con = robust_connect(DUCKDB_PATH, read_only=False)
    try:
        existing = {r[0] for r in con.execute("select name from decision_rules").fetchall()}
        inserted = 0
        for rule in RULES:
            if rule["name"] in existing:
                print(f"[skip] already exists: {rule['name']}")
                continue

            metric_ids = []
            for cond in rule["condition_json"]:
                node_id = f"metric::{cond['metric']}"
                if con.execute("select 1 from concept_nodes where node_id = ?", [node_id]).fetchone():
                    metric_ids.append(node_id)
                else:
                    print(f"[warn] unknown metric '{cond['metric']}' referenced by '{rule['name']}' — skipping edge")

            rule_id = str(uuid.uuid4())
            con.execute(
                "insert into decision_rules (rule_id, name, condition_text, condition_json, threshold_json, "
                "action_text, assigned_role, priority, status, created_by, reason) "
                "values (?,?,?,?,?,?,?,?,'active',?,?)",
                [rule_id, rule["name"], rule["condition_text"], json.dumps(rule["condition_json"]),
                 json.dumps(rule["threshold_json"]), rule["action_text"], rule["assigned_role"],
                 rule["priority"], "context_layer.seed_norms", rule["reason"]],
            )
            rule_node = f"rule::{rule_id}"
            con.execute(
                "insert into concept_nodes (node_id, node_type, name, definition, subject_area, owner_role) "
                "values (?, 'decision', ?, ?, 'decisioning', ?)",
                [rule_node, rule["name"], rule["condition_text"], rule["assigned_role"]],
            )
            con.execute("insert or ignore into graph_nodes_all values (?,?,?,?)",
                        [rule_node, "decision", rule["name"], "decisioning"])
            for mnode in metric_ids:
                con.execute(
                    "insert into graph_edges (edge_id, src_node_id, src_node_type, dst_node_id, dst_node_type, edge_type) "
                    "values (?,?,?,?,?,?)",
                    [str(uuid.uuid4()), rule_node, "decision", mnode, "metric", "considers"],
                )
            inserted += 1
            print(f"[insert] {rule['name']} (rule_id={rule_id}, metrics={metric_ids})")

        con.commit()
        total = con.execute("select count(*) from decision_rules where status = 'active'").fetchone()[0]
        print(f"\n{inserted} new rule(s) inserted. {total} active rule(s) total.")
    finally:
        con.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
