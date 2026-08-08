"""FastAPI routes for the governed graph-feedback loop (Prompt 13).

  GET  /api/v2/graph/model            ontology nodes+links for the force graph
  GET  /api/v2/graph/node/{node_id}   full node detail + feedback history
  POST /api/v2/graph/feedback         record_* dispatcher (node|edge|rule|answer)
  POST /api/v2/graph/propose-edge     propose a missing relationship (review)
  GET  /api/v2/graph/review-queue     pending_review items (admin roles)
  POST /api/v2/graph/review/{id}      approve/reject a pending item
  GET  /api/v2/graph/adaptation-log   recent auto + approved changes (transparency)

Registered from backend_v2/api/main.py.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import duckdb

from graph import feedback_engine as fe
from graph import graph_traversal as gt

router = APIRouter(prefix="/api/v2/graph", tags=["graph-feedback"])

CONCEPT_TYPES = ("term", "metric", "process", "decision", "entity_class")
ADMIN_ROLES = {"Executive Leadership", "admin", "Data Analyst"}


# ---------------------------------------------------------------------------
# GET /model — the semantic/ontology graph (concept-level, not 51k entities)
# ---------------------------------------------------------------------------
@router.get("/model")
def get_model(subject_area: str | None = None, depth: int = 2,
              node_type: str | None = None) -> dict[str, Any]:
    from graph.db_util import robust_connect
    con = robust_connect(fe.DB_PATH, read_only=True)
    try:
        type_filter = list(CONCEPT_TYPES)
        if node_type:
            type_filter = [node_type]
        ph = ",".join("?" * len(type_filter))
        params: list[Any] = list(type_filter)
        area_clause = ""
        if subject_area:
            area_clause = " and coalesce(subject_area,'') = ?"
            params.append(subject_area)
        node_rows = con.execute(
            f"select node_id, node_type, name, subject_area from concept_nodes "
            f"where node_type in ({ph}){area_clause}", params).fetchall()
        node_ids = {r[0] for r in node_rows}
        if not node_ids:
            return {"nodes": [], "links": [], "subject_area": subject_area}
        ids_ph = ",".join("?" * len(node_ids))
        edge_rows = con.execute(
            f"select edge_id, src_node_id, dst_node_id, edge_type, coalesce(weight,1.0), coalesce(status,'active') "
            f"from graph_edges where src_node_id in ({ids_ph}) and dst_node_id in ({ids_ph}) "
            f"and coalesce(status,'active') <> 'inactive'",
            list(node_ids) + list(node_ids)).fetchall()
    finally:
        con.close()

    health = fe.node_health_map()
    # degree for node sizing
    degree: dict[str, int] = {nid: 0 for nid in node_ids}
    for _eid, s, d, *_ in edge_rows:
        degree[s] = degree.get(s, 0) + 1
        degree[d] = degree.get(d, 0) + 1

    sub = {
        "nodes": [{"id": r[0], "type": r[1], "name": r[2], "subject_area": r[3]} for r in node_rows],
        "edges": [{"id": r[0], "src": r[1], "dst": r[2], "type": r[3], "weight": r[4]} for r in edge_rows],
    }
    out = gt.export_graph_json(sub)
    for n in out["nodes"]:
        n["degree"] = degree.get(n["id"], 0)
        n["health"] = health.get(n["id"])
    for li, er in zip(out["links"], edge_rows):
        li["id"] = er[0]
        li["weight"] = er[4]
        li["status"] = er[5]
    out["subject_area"] = subject_area
    out["counts"] = {"nodes": len(out["nodes"]), "links": len(out["links"])}
    return out


# ---------------------------------------------------------------------------
# GET /node/{node_id}
# ---------------------------------------------------------------------------
@router.get("/node/{node_id:path}")
def get_node(node_id: str) -> dict[str, Any]:
    detail = fe.node_detail(node_id)
    if detail.get("error"):
        raise HTTPException(status_code=404, detail=detail)
    return detail


# ---------------------------------------------------------------------------
# POST /feedback — dispatcher
# ---------------------------------------------------------------------------
class FeedbackRequest(BaseModel):
    target_type: str = Field(description="node|edge|rule|answer")
    target_id: str | None = None
    feedback_type: str | None = None          # confirm|reject|missing|edit
    rating: int | None = None
    comment: str | None = None
    proposed_change: dict | None = None
    thumbs: str | None = None                 # answer: up|down
    query_id: str | None = None               # answer
    role: str | None = None
    user: str = "console.user"
    user_role: str = "Data Analyst"


@router.post("/feedback")
def post_feedback(body: FeedbackRequest) -> dict[str, Any]:
    t = body.target_type
    if t == "node":
        if not body.target_id or not body.feedback_type:
            raise HTTPException(422, "node feedback requires target_id + feedback_type")
        return fe.record_node_feedback(body.target_id, body.feedback_type, body.rating, body.comment,
                                       body.proposed_change, body.user, body.user_role)
    if t == "edge":
        if not body.target_id or not body.feedback_type:
            raise HTTPException(422, "edge feedback requires target_id + feedback_type")
        res = fe.record_edge_feedback(body.target_id, body.feedback_type, body.rating, body.user, body.user_role)
        if res.get("error"):
            raise HTTPException(404, res)
        return res
    if t == "rule":
        if not body.target_id or not body.feedback_type:
            raise HTTPException(422, "rule feedback requires target_id + feedback_type")
        return fe.record_rule_feedback(body.target_id, body.feedback_type, body.rating, body.user, body.user_role)
    if t == "answer":
        if not body.query_id or not body.thumbs:
            raise HTTPException(422, "answer feedback requires query_id + thumbs")
        return fe.record_answer_feedback(body.query_id, body.thumbs, body.comment, body.rating, body.role)
    raise HTTPException(422, f"unknown target_type: {t}")


# ---------------------------------------------------------------------------
# POST /propose-edge
# ---------------------------------------------------------------------------
class ProposeEdgeRequest(BaseModel):
    src: str
    dst: str
    edge_type: str = Field(default="informs")
    comment: str | None = None
    user: str = "console.user"
    user_role: str = "Data Analyst"


@router.post("/propose-edge")
def post_propose_edge(body: ProposeEdgeRequest) -> dict[str, Any]:
    res = fe.propose_edge(body.src, body.dst, body.edge_type, body.user, body.user_role, body.comment)
    if res.get("error"):
        raise HTTPException(404, res)
    return res


# ---------------------------------------------------------------------------
# GET /review-queue (admin roles)
# ---------------------------------------------------------------------------
@router.get("/review-queue")
def get_review_queue(role: str = Query(default="Data Analyst")) -> dict[str, Any]:
    if role not in ADMIN_ROLES:
        raise HTTPException(403, f"role '{role}' is not permitted to view the review queue")
    return {"items": fe.get_review_queue()}


# ---------------------------------------------------------------------------
# POST /review/{feedback_id}
# ---------------------------------------------------------------------------
class ReviewRequest(BaseModel):
    decision: str = Field(description="approve|reject")
    reviewer: str = "reviewer"
    role: str = "Executive Leadership"


@router.post("/review/{feedback_id}")
def post_review(feedback_id: str, body: ReviewRequest) -> dict[str, Any]:
    if body.role not in ADMIN_ROLES:
        raise HTTPException(403, f"role '{body.role}' cannot apply reviews")
    res = fe.apply_review(feedback_id, body.decision, body.reviewer)
    if res.get("error"):
        raise HTTPException(400, res)
    return res


# ---------------------------------------------------------------------------
# GET /adaptation-log
# ---------------------------------------------------------------------------
@router.get("/adaptation-log")
def get_adaptation_log(limit: int = 50) -> dict[str, Any]:
    return {"items": fe.adaptation_log(min(max(limit, 1), 200))}
