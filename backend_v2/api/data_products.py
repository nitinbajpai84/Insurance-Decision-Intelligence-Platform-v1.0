"""
V2 Data-Product APIs — read-only endpoints over the DuckDB semantic views
(database/semantic_views.sql). Every endpoint:
  * opens a read-only DuckDB connection (never writes),
  * reads only from v_* semantic views,
  * accepts a `role` param for row-level filtering (Insurance Agent -> own book).

Registered in api/main.py via include_router.
"""
from __future__ import annotations

import sys
from datetime import date, datetime
from decimal import Decimal
from functools import lru_cache
from pathlib import Path
from typing import Any

import duckdb
from fastapi import APIRouter, HTTPException, Query

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend_v2.config import DUCKDB_CONFIG, DUCKDB_PATH

router = APIRouter(prefix="/api/v2", tags=["data-products"])


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------
def _json_safe(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    return value


def query(sql: str, params: list[Any] | None = None) -> list[dict[str, Any]]:
    conn = duckdb.connect(DUCKDB_PATH, read_only=True, config=DUCKDB_CONFIG)
    try:
        cur = conn.execute(sql, params or [])
        cols = [d[0] for d in (cur.description or [])]
        return [{c: _json_safe(v) for c, v in zip(cols, row)} for row in cur.fetchall()]
    except duckdb.Error as exc:
        raise HTTPException(status_code=500, detail=f"query failed: {type(exc).__name__}: {exc}") from exc
    finally:
        conn.close()


def query_one(sql: str, params: list[Any] | None = None) -> dict[str, Any] | None:
    rows = query(sql, params)
    return rows[0] if rows else None


# ---------------------------------------------------------------------------
# Role scoping
# ---------------------------------------------------------------------------
def _norm_role(role: str | None) -> str:
    return (role or "").strip().lower().replace(" ", "_")


@lru_cache(maxsize=1)
def _default_demo_agent() -> str | None:
    """A deterministic agent (the one with the most customers) used when the
    Insurance Agent role is selected without an explicit agent_id."""
    row = query_one(
        "select advisor_agent_id, count(*) n from v_customer_360 "
        "where advisor_agent_id is not null group by 1 order by 2 desc, 1 limit 1"
    )
    return row["advisor_agent_id"] if row else None


def resolve_agent_scope(role: str | None, agent_id: str | None) -> str | None:
    """Return the agent_id an Insurance Agent is restricted to, else None (no scope)."""
    if _norm_role(role) == "insurance_agent":
        return agent_id or _default_demo_agent()
    return None


# ---------------------------------------------------------------------------
# Home
# ---------------------------------------------------------------------------
@router.get("/home/kpis")
def home_kpis() -> dict[str, Any]:
    row = query_one("select * from v_home_kpis")
    if not row:
        raise HTTPException(status_code=404, detail="home KPIs unavailable")
    # Top-3 decision queue from next_best_actions
    queue = query(
        """
        select nba.next_best_action_id, nba.action_type, round(nba.priority_score,3) as priority,
               round(nba.expected_value,2) as expected_value, nba.action_reason as reason,
               coalesce(pp.display_name, nba.customer_id) as customer_name,
               pr.product_name
        from next_best_actions nba
        left join customers c on c.customer_id = nba.customer_id
        left join parties pp on pp.party_id = c.party_id
        left join products pr on pr.product_id = nba.product_id
        where nba.action_status in ('recommended','assigned')
        order by nba.priority_score desc nulls last
        limit 3
        """
    )
    row["decision_queue"] = queue
    return row


# ---------------------------------------------------------------------------
# Customers
# ---------------------------------------------------------------------------
@router.get("/customers/search")
def customers_search(
    q: str = Query("", description="name, customer id/number, or policy number"),
    role: str | None = None,
    agent_id: str | None = None,
    limit: int = 25,
) -> dict[str, Any]:
    scope = resolve_agent_scope(role, agent_id)
    where = []
    params: list[Any] = []
    if q.strip():
        like = f"%{q.strip()}%"
        where.append(
            "(display_name ilike ? or customer_number ilike ? or customer_id ilike ? "
            "or customer_id in (select customer_id from policies where policy_number ilike ?))"
        )
        params += [like, like, like, like]
    if scope:
        where.append("advisor_agent_id = ?")
        params.append(scope)
    clause = (" where " + " and ".join(where)) if where else ""
    rows = query(
        f"select customer_id, customer_number, display_name, customer_segment, region, "
        f"active_policy_count, annual_premium, advisor_name, churn_risk_band, propensity_band "
        f"from v_customer_360{clause} order by annual_premium desc limit {int(limit)}",
        params,
    )
    return {"role_scope": scope, "count": len(rows), "results": rows}


@router.get("/customers/{customer_id}")
def customer_detail(customer_id: str, role: str | None = None, agent_id: str | None = None) -> dict[str, Any]:
    profile = query_one("select * from v_customer_360 where customer_id = ?", [customer_id])
    if not profile:
        raise HTTPException(status_code=404, detail=f"customer not found: {customer_id}")
    scope = resolve_agent_scope(role, agent_id)
    if scope and profile.get("advisor_agent_id") != scope:
        raise HTTPException(status_code=403, detail="customer outside your book")
    policies = query(
        "select * from v_customer_policies where customer_id = ? order by annual_premium desc", [customer_id]
    )
    action = query_one("select * from v_customer_recommended_action where customer_id = ?", [customer_id])
    # product mix from the policy portfolio
    mix = query(
        "select line_of_business, round(sum(annual_premium),2) as premium "
        "from v_customer_policies where customer_id = ? and policy_status in ('active','renewed','issued') "
        "group by 1 order by 2 desc",
        [customer_id],
    )
    total = sum(m["premium"] or 0 for m in mix) or 1
    for m in mix:
        m["pct"] = round(100.0 * (m["premium"] or 0) / total, 1)
    return {"profile": profile, "policies": policies, "recommended_action": action, "product_mix": mix}


# ---------------------------------------------------------------------------
# Agents
# ---------------------------------------------------------------------------
@router.get("/agents/search")
def agents_search(q: str = "", role: str | None = None, agent_id: str | None = None, limit: int = 25) -> dict[str, Any]:
    scope = resolve_agent_scope(role, agent_id)
    where = []
    params: list[Any] = []
    if q.strip():
        like = f"%{q.strip()}%"
        where.append("(display_name ilike ? or agent_number ilike ? or agent_id ilike ?)")
        params += [like, like, like]
    if scope:
        where.append("agent_id = ?")
        params.append(scope)
    clause = (" where " + " and ".join(where)) if where else ""
    rows = query(
        f"select agent_id, agent_number, display_name, channel, region, branch, status, "
        f"monthly_premium, policies_sold_mtd, conversion_rate, persistency_rate, target_achievement_pct "
        f"from v_agent_360{clause} order by monthly_premium desc limit {int(limit)}",
        params,
    )
    return {"role_scope": scope, "count": len(rows), "results": rows}


@router.get("/agents/leaderboard")
def agents_leaderboard(
    region: str | None = None,
    segment: str | None = None,
    customer_type: str | None = None,
    product: str | None = None,
    role: str | None = None,
    agent_id: str | None = None,
    limit: int = 50,
) -> dict[str, Any]:
    scope = resolve_agent_scope(role, agent_id)
    where = []
    params: list[Any] = []
    if region:
        where.append("region = ?")
        params.append(region)
    if scope:
        where.append("agent_id = ?")
        params.append(scope)
    clause = (" where " + " and ".join(where)) if where else ""
    rows = query(f"select * from v_agent_leaderboard{clause} order by premium_rank limit {int(limit)}", params)
    rising = [r for r in rows if r.get("cluster") == "Rising Stars"]
    mdrt = [r for r in rows if r.get("cluster") == "MDRT"]
    return {
        "role_scope": scope,
        "filters_applied": {"region": region, "segment": segment, "customer_type": customer_type, "product": product},
        "note": "segment/customer_type/product are accepted but not part of agent-level leaderboard grain; region filter is applied.",
        "count": len(rows),
        "leaderboard": rows,
        "rising_stars": rising,
        "mdrt": mdrt,
    }


@router.get("/agents/{agent_id}")
def agent_detail(agent_id: str, role: str | None = None) -> dict[str, Any]:
    profile = query_one("select * from v_agent_360 where agent_id = ?", [agent_id])
    if not profile:
        raise HTTPException(status_code=404, detail=f"agent not found: {agent_id}")
    scope = resolve_agent_scope(role, agent_id)
    if scope and scope != agent_id:
        raise HTTPException(status_code=403, detail="agent outside your scope")
    mapa = query(
        "select metric_month, meetings, activities, proposals, applications, policies_bound "
        "from v_agent_mapa where agent_id = ? order by metric_month desc limit 12",
        [agent_id],
    )
    mapa.reverse()
    portfolio = query_one(
        """
        select count(distinct customer_id) as customers, count(*) as policies,
               round(sum(annual_premium),2) as annual_premium
        from policies where agent_id = ? and policy_status in ('active','renewed','issued')
        """,
        [agent_id],
    )
    mix = query(
        """
        select pr.line_of_business, round(sum(p.annual_premium),2) as premium
        from policies p join products pr on pr.product_id = p.product_id
        where p.agent_id = ? and p.policy_status in ('active','renewed','issued')
        group by 1 order by 2 desc
        """,
        [agent_id],
    )
    return {"profile": profile, "mapa": mapa, "portfolio": portfolio or {}, "product_mix": mix}


# ---------------------------------------------------------------------------
# Campaigns
# ---------------------------------------------------------------------------
@router.get("/campaigns")
def campaigns(
    search: str = "",
    medium: str | None = None,
    date_from: str | None = Query(None, alias="from"),
    date_to: str | None = Query(None, alias="to"),
) -> dict[str, Any]:
    where = []
    params: list[Any] = []
    if search.strip():
        like = f"%{search.strip()}%"
        where.append("(campaign_name ilike ? or campaign_code ilike ?)")
        params += [like, like]
    if medium:
        where.append("medium = ?")
        params.append(medium)
    if date_from:
        where.append("start_date >= ?")
        params.append(date_from)
    if date_to:
        where.append("start_date <= ?")
        params.append(date_to)
    clause = (" where " + " and ".join(where)) if where else ""
    rows = query(f"select * from v_campaign_effectiveness{clause} order by premium_generated desc", params)
    return {"count": len(rows), "results": rows}


@router.get("/campaigns/{campaign_id}")
def campaign_detail(campaign_id: str) -> dict[str, Any]:
    row = query_one("select * from v_campaign_effectiveness where campaign_id = ?", [campaign_id])
    if not row:
        raise HTTPException(status_code=404, detail=f"campaign not found: {campaign_id}")
    funnel = [
        {"stage": "Targeted", "count": row.get("targeted", 0)},
        {"stage": "Delivered", "count": row.get("delivered", 0)},
        {"stage": "Opened", "count": row.get("opened", 0)},
        {"stage": "Clicked", "count": row.get("clicked", 0)},
        {"stage": "Responded", "count": row.get("responded", 0)},
        {"stage": "Conversions", "count": row.get("conversions", 0)},
    ]
    return {"overview": row, "funnel": funnel}


# ---------------------------------------------------------------------------
# Lapse risk
# ---------------------------------------------------------------------------
def _lapse_filters(region: str | None, product: str | None, segment: str | None) -> tuple[str, list[Any]]:
    where = ["at_risk"]
    params: list[Any] = []
    if region:
        where.append("region = ?")
        params.append(region)
    if product:
        where.append("line_of_business = ?")
        params.append(product)
    if segment:
        where.append("customer_segment = ?")
        params.append(segment)
    return " where " + " and ".join(where), params


@router.get("/lapse-risk/summary")
def lapse_summary(region: str | None = None, product: str | None = None, segment: str | None = None) -> dict[str, Any]:
    # No filters -> the precomputed overall view; otherwise recompute from policy-level base.
    if not (region or product or segment):
        row = query_one("select * from v_lapse_risk_summary")
        return row or {}
    clause, params = _lapse_filters(region, product, segment)
    row = query_one(
        f"""
        select count(*) as policies_at_risk,
               count(distinct customer_id) as customers_at_risk,
               round(sum(annual_premium),2) as premium_at_risk,
               round(avg(lapse_probability),4) as avg_lapse_probability,
               (select line_of_business from v_lapse_policy_risk{clause} group by line_of_business order by sum(annual_premium) desc limit 1) as top_risk_product,
               (select customer_segment from v_lapse_policy_risk{clause} group by customer_segment order by sum(annual_premium) desc limit 1) as top_risk_segment
        from v_lapse_policy_risk{clause}
        """,
        params * 3,
    )
    return row or {}


@router.get("/lapse-risk/hotspots")
def lapse_hotspots(region: str | None = None, product: str | None = None, segment: str | None = None) -> dict[str, Any]:
    if not (region or product or segment):
        return {"hotspots": query("select * from v_lapse_hotspots")}
    clause, params = _lapse_filters(region, product, segment)
    dims = [("region", "region"), ("branch", "branch"), ("product", "line_of_business"),
            ("customer_segment", "customer_segment")]
    out: list[dict[str, Any]] = []
    for label, col in dims:
        r = query_one(
            f"select '{label}' as dimension, {col} as dimension_value, count(*) as policy_count, "
            f"round(sum(annual_premium),2) as premium_at_risk, round(avg(lapse_probability),4) as avg_lapse_score "
            f"from v_lapse_policy_risk{clause} group by {col} order by sum(annual_premium) desc limit 1",
            params,
        )
        if r:
            out.append(r)
    return {"hotspots": out}
