"""Mini-MORRIE — natural-language decision-rule capture.

parse_rule() asks Gemini to extract structured condition/threshold/action/role
from free text like:
    "if lapse score above 70% and premium over S$50K escalate to branch manager"
A deterministic regex fallback runs when Gemini is unavailable, so capture
still works offline.

capture_rule() validates that every referenced metric exists as a concept node,
inserts the rule as status='draft', links it into graph_edges, and writes an
audit entry to agent_reasoning_log.
"""
from __future__ import annotations

import json
import re
import sys
import uuid
from pathlib import Path
from typing import Any

import duckdb

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

DB_PATH = str(PROJECT_ROOT / "database" / "insurance_v2.duckdb")

# Known metric vocabulary (concept node slug -> friendly synonyms).
METRIC_SYNONYMS: dict[str, list[str]] = {
    "lapse_risk": ["lapse score", "lapse risk", "lapse probability"],
    "lapse_rate": ["lapse rate"],
    "premium_at_risk": ["premium at risk", "premium", "annual premium"],
    "persistency": ["persistency"],
    "campaign_conversion": ["campaign conversion", "conversion rate"],
    "propensity_to_buy": ["propensity", "propensity to buy", "buy propensity"],
    "clv": ["clv", "lifetime value", "customer lifetime value"],
    "agent_target_achievement": ["target achievement", "attainment", "quota"],
}

ROLE_HINTS = {
    "branch manager": "Agency Manager",
    "agency manager": "Agency Manager",
    "sales director": "Sales Director",
    "campaign manager": "Campaign Manager",
    "claims manager": "Claims Manager",
    "agent": "Insurance Agent",
    "executive": "Executive Leadership",
    "analyst": "Data Analyst",
}

GEMINI_PROMPT = """You convert an insurance business rule written in plain English into JSON.

Allowed metric names (use EXACTLY these snake_case ids): {metrics}
Allowed roles: Executive Leadership, Agency Manager, Campaign Manager, Sales Director, Insurance Agent, Claims Manager, Data Analyst

RULE: {rule}

Return JSON only (no markdown fences) with this shape:
{{"condition_json": [{{"metric": "<one of the allowed ids>", "operator": "> | >= | < | <= | =", "value": <number>}}],
  "threshold_json": {{"<metric>": <number>}},
  "action_text": "<imperative action>",
  "assigned_role": "<one of the allowed roles>"}}
Percentages become decimals only for *_risk / *_rate / persistency / propensity / conversion metrics (70% -> 0.70); premium/value stay absolute (S$50K -> 50000).
CRITICAL: Only emit a clause when the referenced quantity clearly matches one of the allowed metric ids. If a referenced quantity is NOT in the allowed list (e.g. "moon phase", "temperature"), OMIT that clause entirely — never force-map it to an unrelated allowed metric. If no clause maps, return "condition_json": []."""


def _connect(read_only: bool = False) -> duckdb.DuckDBPyConnection:
    from graph.db_util import robust_connect
    return robust_connect(DB_PATH, read_only=read_only)


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------
def _gemini_parse(rule_text: str) -> dict[str, Any] | None:
    try:
        import google.generativeai as genai
        from backend_v2.config import GEMINI_MODEL, require_api_key

        genai.configure(api_key=require_api_key())
        model = genai.GenerativeModel(GEMINI_MODEL)
        prompt = GEMINI_PROMPT.format(metrics=", ".join(METRIC_SYNONYMS.keys()), rule=rule_text)
        resp = model.generate_content(prompt, generation_config={"temperature": 0.0})
        text = (getattr(resp, "text", "") or "").strip()
        text = re.sub(r"^```(?:json)?|```$", "", text, flags=re.IGNORECASE | re.MULTILINE).strip()
        m = re.search(r"\{.*\}", text, flags=re.DOTALL)
        return json.loads(m.group(0)) if m else None
    except Exception:
        return None


def _regex_parse(rule_text: str) -> dict[str, Any]:
    """Deterministic fallback: pull (metric, operator, value) clauses + role."""
    t = rule_text.lower()
    conditions: list[dict[str, Any]] = []
    thresholds: dict[str, float] = {}

    def resolve_metric(span: str) -> str | None:
        for mid, syns in METRIC_SYNONYMS.items():
            if any(s in span for s in syns):
                return mid
        return None

    # operator words -> symbols
    op_map = [("at least", ">="), ("no less than", ">="), ("above", ">"), ("over", ">"),
              ("greater than", ">"), ("more than", ">"), ("below", "<"), ("under", "<"),
              ("less than", "<"), ("at most", "<="), ("equal to", "="), ("equals", "=")]

    # split on 'and' to find clauses
    for clause in re.split(r"\band\b", t):
        op = next((sym for word, sym in op_map if word in clause), None)
        if not op:
            continue
        metric = resolve_metric(clause)
        if not metric:
            continue
        num = re.search(r"(s\$|sgd|\$)?\s*([\d,]+(?:\.\d+)?)\s*(%|k|m)?", clause)
        if not num:
            continue
        value = float(num.group(2).replace(",", ""))
        suffix = num.group(3)
        if suffix == "%":
            value = value / 100.0
        elif suffix == "k":
            value *= 1_000
        elif suffix == "m":
            value *= 1_000_000
        conditions.append({"metric": metric, "operator": op, "value": value})
        thresholds[metric] = value

    role = next((r for key, r in ROLE_HINTS.items() if key in t), None)
    action = rule_text
    m = re.search(r"\b(escalate|assign|route|notify|coach|review|flag|add)\b.*$", t)
    if m:
        action = m.group(0).strip().capitalize()
    return {"condition_json": conditions, "threshold_json": thresholds,
            "action_text": action, "assigned_role": role}


def parse_rule(natural_language_rule: str, role: str) -> dict[str, Any]:
    """Return {condition_json, threshold_json, action_text, assigned_role, parser}."""
    parsed = _gemini_parse(natural_language_rule)
    parser = "gemini"
    if not parsed or not parsed.get("condition_json"):
        parsed = _regex_parse(natural_language_rule)
        parser = "regex-fallback"
    parsed.setdefault("assigned_role", None)
    if not parsed.get("assigned_role"):
        parsed["assigned_role"] = role
    parsed["parser"] = parser
    return parsed


# ---------------------------------------------------------------------------
# Validation + persistence
# ---------------------------------------------------------------------------
def _validate_metrics(con, condition_json: list[dict[str, Any]]) -> tuple[list[str], list[str]]:
    """Return (valid_metric_node_ids, unknown_metric_names)."""
    valid, unknown = [], []
    for cond in condition_json or []:
        metric = str(cond.get("metric", "")).strip()
        node_id = f"metric::{metric}"
        exists = con.execute("select 1 from concept_nodes where node_id = ?", [node_id]).fetchone()
        if exists:
            valid.append(node_id)
        else:
            unknown.append(metric)
    return valid, unknown


def capture_rule(natural_language_rule: str, role: str, created_by: str = "console.user",
                 reason: str = "captured via Mini-MORRIE") -> dict[str, Any]:
    parsed = parse_rule(natural_language_rule, role)
    con = _connect(read_only=False)
    try:
        valid_metrics, unknown = _validate_metrics(con, parsed.get("condition_json", []))
        if unknown:
            return {"status": "rejected", "reason": "unknown_metrics", "unknown_metrics": unknown,
                    "hint": f"Known metrics: {', '.join(METRIC_SYNONYMS.keys())}", "parsed": parsed}
        if not valid_metrics:
            return {"status": "rejected", "reason": "no_recognized_metric", "parsed": parsed}

        rule_id = str(uuid.uuid4())
        name = (parsed.get("action_text") or natural_language_rule)[:80]
        con.execute(
            "insert into decision_rules (rule_id, name, condition_text, condition_json, threshold_json, "
            "action_text, assigned_role, priority, status, created_by, reason) "
            "values (?,?,?,?,?,?,?,?,?,?,?)",
            [rule_id, name, natural_language_rule, json.dumps(parsed.get("condition_json")),
             json.dumps(parsed.get("threshold_json")), parsed.get("action_text"),
             parsed.get("assigned_role"), 5, "draft", created_by, reason],
        )
        # register the rule as a decision concept node + considers edges to metrics
        rule_node = f"rule::{rule_id}"
        con.execute(
            "insert or replace into concept_nodes (node_id, node_type, name, definition, subject_area, owner_role) "
            "values (?,?,?,?,?,?)",
            [rule_node, "decision", name, natural_language_rule, "decisioning", parsed.get("assigned_role")],
        )
        con.execute("insert or ignore into graph_nodes_all values (?,?,?,?)",
                    [rule_node, "decision", name, "decisioning"])
        for mnode in valid_metrics:
            con.execute(
                "insert into graph_edges (edge_id, src_node_id, src_node_type, dst_node_id, dst_node_type, edge_type) "
                "values (?,?,?,?,?,?)",
                [str(uuid.uuid4()), rule_node, "decision", mnode, "metric", "considers"],
            )
        con.commit()

        _audit(rule_id, created_by, reason, parsed)
        return {"status": "draft", "rule_id": rule_id, "name": name,
                "condition_json": parsed.get("condition_json"),
                "threshold_json": parsed.get("threshold_json"),
                "action_text": parsed.get("action_text"),
                "assigned_role": parsed.get("assigned_role"),
                "validated_metrics": valid_metrics, "parser": parsed.get("parser")}
    finally:
        con.close()


def _audit(rule_id: str, created_by: str, reason: str, parsed: dict[str, Any]) -> None:
    """Best-effort audit row in agent_reasoning_log (never raises)."""
    try:
        from backend_v2.observability import tracer
        tracer.log_step(
            query_id=f"rule-capture-{rule_id}", agent_name="rule_capture",
            input_summary=f"by={created_by} reason={reason}",
            output_summary=f"draft rule {rule_id}: {json.dumps(parsed)[:400]}",
            duration_ms=0,
        )
    except Exception as exc:  # pragma: no cover
        print(f"[rule_capture] audit warn: {exc}", file=sys.stderr)


if __name__ == "__main__":
    rule = " ".join(sys.argv[1:]) or "if lapse score above 70% and premium over S$50K escalate to branch manager"
    print("RULE:", rule)
    out = capture_rule(rule, role="Agency Manager")
    print(json.dumps(out, indent=2))
