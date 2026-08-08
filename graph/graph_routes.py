"""FastAPI routes for the graph / ontology layer.

  POST /api/v2/graph/rule        capture a natural-language decision rule
  GET  /api/v2/graph/subgraph    N-hop neighbourhood for an entity/node id
  GET  /api/v2/graph/discoveries cross-domain "combined decision" discoveries

Registered from backend_v2/api/main.py (V2-owned file).
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from graph import graph_traversal as gt
from graph.rule_capture import capture_rule

router = APIRouter(prefix="/api/v2/graph", tags=["graph"])


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
