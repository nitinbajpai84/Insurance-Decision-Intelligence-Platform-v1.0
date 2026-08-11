"""FastAPI routes for the graph / ontology layer.

  POST /api/v2/graph/rule            capture a natural-language decision rule
  GET  /api/v2/graph/rules           list all governed decision rules
  PATCH /api/v2/graph/rules/{id}     edit a rule (demotes to draft — see below)
  POST /api/v2/graph/rules/{id}/activate    draft -> active, reason required
  POST /api/v2/graph/rules/{id}/deactivate  active -> draft, reason required
  GET  /api/v2/graph/subgraph        N-hop neighbourhood for an entity/node id
  GET  /api/v2/graph/discoveries     cross-domain "combined decision" discoveries

Registered from backend_v2/api/main.py (V2-owned file).
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from graph import graph_traversal as gt
from graph.db_util import robust_connect
from graph.rule_capture import capture_rule

router = APIRouter(prefix="/api/v2/graph", tags=["graph"])

DB_PATH = str(PROJECT_ROOT / "database" / "insurance_v2.duckdb")


class RuleRequest(BaseModel):
    rule: str = Field(min_length=6, max_length=2000)
    role: str = Field(default="Agency Manager")
    created_by: str = Field(default="console.user")
    reason: str = Field(default="captured via Mini-MORRIE")


@router.post("/rule")
def post_rule(body: RuleRequest) -> dict[str, Any]:
    result = capture_rule(body.rule, body.role, body.created_by, body.reason)
    if result.get("status") == "rejected":
        # 422: parsed but failed metric validation
        raise HTTPException(status_code=422, detail=result)
    return result


def _rule_dict(row: tuple, cols: list[str]) -> dict[str, Any]:
    out = dict(zip(cols, row))
    for key in ("condition_json", "threshold_json"):
        if isinstance(out.get(key), str):
            try:
                out[key] = json.loads(out[key])
            except (ValueError, TypeError):
                out[key] = None
    if hasattr(out.get("created_at"), "isoformat"):
        out["created_at"] = out["created_at"].isoformat()
    return out


def _audit_rule_change(rule_id: str, action: str, actor: str, reason: str, detail: str) -> None:
    """Best-effort audit row — mirrors rule_capture._audit. Never raises."""
    try:
        from backend_v2.observability import tracer
        tracer.log_step(
            query_id=f"rule-{action}-{rule_id}", agent_name=f"rule_{action}",
            input_summary=f"by={actor} reason={reason}", output_summary=detail[:400],
            duration_ms=0,
        )
    except Exception as exc:  # pragma: no cover
        print(f"[graph_routes] rule audit warn: {exc}", file=sys.stderr)


@router.get("/rules")
def list_rules(status: str | None = None) -> dict[str, Any]:
    """All governed decision rules — the norms an agent can cite. status=active
    filters to what actually governs answers today; omit to see drafts too."""
    con = robust_connect(DB_PATH, read_only=True)
    try:
        cols = ["rule_id", "name", "condition_text", "condition_json", "threshold_json",
               "action_text", "assigned_role", "priority", "status", "created_by",
               "reason", "created_at"]
        sql = f"select {', '.join(cols)} from decision_rules"
        params: list[Any] = []
        if status:
            sql += " where status = ?"
            params.append(status)
        sql += " order by priority, name"
        rows = con.execute(sql, params).fetchall()
        rules = [_rule_dict(r, cols) for r in rows]
        return {"count": len(rules), "rules": rules}
    finally:
        con.close()


class RuleEditRequest(BaseModel):
    condition_text: str | None = None
    threshold_json: dict[str, float] | None = None
    condition_json: list[dict[str, Any]] | None = None
    action_text: str | None = None
    assigned_role: str | None = None
    priority: int | None = None
    updated_by: str = Field(min_length=1)
    reason: str = Field(min_length=3, max_length=500)


@router.patch("/rules/{rule_id}")
def edit_rule(rule_id: str, body: RuleEditRequest) -> dict[str, Any]:
    """Edit a rule's condition/threshold/action. Always demotes status to
    'draft' — an edited rule must be explicitly re-activated before it governs
    answers again, so a threshold change can never silently take effect
    without a reviewer confirming it (mirrors the glossary editor's
    reason-required pattern, plus this extra governance step since rules
    directly gate business decisions, not just definitions)."""
    con = robust_connect(DB_PATH, read_only=False)
    try:
        existing = con.execute(
            "select name, condition_text, threshold_json from decision_rules where rule_id = ?",
            [rule_id]).fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail=f"rule not found: {rule_id}")
        name, old_condition, old_threshold = existing

        updates: dict[str, Any] = {}
        if body.condition_text is not None:
            updates["condition_text"] = body.condition_text
        if body.threshold_json is not None:
            updates["threshold_json"] = json.dumps(body.threshold_json)
        if body.condition_json is not None:
            updates["condition_json"] = json.dumps(body.condition_json)
        if body.action_text is not None:
            updates["action_text"] = body.action_text
        if body.assigned_role is not None:
            updates["assigned_role"] = body.assigned_role
        if body.priority is not None:
            updates["priority"] = body.priority
        if not updates:
            raise HTTPException(status_code=422, detail="no fields to update")

        updates["status"] = "draft"
        updates["reason"] = body.reason
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        con.execute(f"update decision_rules set {set_clause} where rule_id = ?",
                   list(updates.values()) + [rule_id])
        con.commit()

        _audit_rule_change(
            rule_id, "edit", body.updated_by, body.reason,
            f"'{name}': threshold {old_threshold} -> {body.threshold_json or old_threshold}, "
            f"condition '{old_condition}' -> '{body.condition_text or old_condition}'; demoted to draft",
        )
        return {"status": "draft", "rule_id": rule_id, "name": name,
               "message": "Rule updated and demoted to draft — activate it to make the change governing."}
    finally:
        con.close()


class RuleStatusRequest(BaseModel):
    updated_by: str = Field(min_length=1)
    reason: str = Field(min_length=3, max_length=500)


@router.post("/rules/{rule_id}/activate")
def activate_rule(rule_id: str, body: RuleStatusRequest) -> dict[str, Any]:
    """Promote draft/needs_review -> active. Only active rules govern answers
    (see graph_traversal.find_decision_paths)."""
    con = robust_connect(DB_PATH, read_only=False)
    try:
        row = con.execute("select name, status from decision_rules where rule_id = ?", [rule_id]).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail=f"rule not found: {rule_id}")
        name, status = row
        if status == "active":
            return {"status": "active", "rule_id": rule_id, "name": name, "message": "already active"}
        con.execute("update decision_rules set status = 'active', reason = ? where rule_id = ?",
                   [body.reason, rule_id])
        con.commit()
        _audit_rule_change(rule_id, "activate", body.updated_by, body.reason, f"'{name}' {status} -> active")
        return {"status": "active", "rule_id": rule_id, "name": name}
    finally:
        con.close()


@router.post("/rules/{rule_id}/deactivate")
def deactivate_rule(rule_id: str, body: RuleStatusRequest) -> dict[str, Any]:
    """Demote active -> draft. Immediately stops governing answers."""
    con = robust_connect(DB_PATH, read_only=False)
    try:
        row = con.execute("select name, status from decision_rules where rule_id = ?", [rule_id]).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail=f"rule not found: {rule_id}")
        name, status = row
        con.execute("update decision_rules set status = 'draft', reason = ? where rule_id = ?",
                   [body.reason, rule_id])
        con.commit()
        _audit_rule_change(rule_id, "deactivate", body.updated_by, body.reason, f"'{name}' {status} -> draft")
        return {"status": "draft", "rule_id": rule_id, "name": name}
    finally:
        con.close()


@router.get("/subgraph")
def get_subgraph(entity_id: str, hops: int = 2) -> dict[str, Any]:
    hops = max(1, min(hops, 4))
    # Resolve a raw data id (customer/policy/agent/...) — it is already a node_id
    # in graph_nodes_all after hydration; concept ids work too.
    con = gt._connect()
    try:
        exists = con.execute("select node_type, name from graph_nodes_all where node_id = ?",
                             [entity_id]).fetchone()
        if not exists:
            raise HTTPException(status_code=404, detail=f"node not found: {entity_id}")
        sub = gt.get_subgraph([entity_id], hops=hops, con=con)
        out = gt.export_graph_json(sub)
        out["entry"] = {"id": entity_id, "type": exists[0], "name": exists[1]}
        out["engine"] = sub["engine"]
        out["counts"] = {"nodes": len(out["nodes"]), "links": len(out["links"])}
        return out
    finally:
        con.close()


@router.get("/discoveries")
def get_discoveries(min_areas: int = 2, limit: int = 50) -> dict[str, Any]:
    rows = gt.cross_domain_scan(min_areas=max(2, min_areas), limit=min(max(limit, 1), 200))
    return {"count": len(rows), "discoveries": rows}
