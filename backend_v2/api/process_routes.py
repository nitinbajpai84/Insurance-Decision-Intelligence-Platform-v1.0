"""Business-process insight APIs (Prompt 19, Part A).

Reads the Prompt-17 process instance views with filter params + role-aware
scoping. Insurance Agent is scoped to their own book (agent_id); other roles see
the portfolio. Lead-conversion is recomputed from base tables so filters + role
scoping apply uniformly; the other processes filter their views.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from graph.db_util import robust_connect
from backend_v2.config import DUCKDB_PATH

router = APIRouter(prefix="/api/v2/process", tags=["process"])


def _conn():
    return robust_connect(DUCKDB_PATH, read_only=True)


def _current_agent(con, agent_id: str | None) -> str:
    if agent_id:
        return agent_id
    row = con.execute("select agent_id from agents order by agent_id limit 1").fetchone()
    return row[0] if row else "agt_0000"


# ---------------------------------------------------------------------------
# 1. Lead-to-conversion funnel (recomputed from base tables so filters apply)
# ---------------------------------------------------------------------------
@router.get("/lead-conversion")
def lead_conversion(from_: str | None = Query(None, alias="from"), to: str | None = None, region: str | None = None,
                    segment: str | None = None, market: str | None = None,
                    role: str = "Executive Leadership", agent_id: str | None = None) -> dict[str, Any]:
    con = _conn()
    try:
        # filter predicate applied at the LEAD level, propagated by joins
        preds, params = ["1=1"], []
        if from_:
            preds.append("l.received_at >= ?"); params.append(from_)
        if to:
            preds.append("l.received_at <= ?"); params.append(to)
        if segment:
            preds.append("cu.customer_segment = ?"); params.append(segment)
        if region:
            preds.append("(case when ag.territory_code like 'HK%' then 'Hong Kong' else 'Singapore' end) = ?"); params.append(region)
        if market:
            mk = "HK%" if market.lower() in ("hk", "hong kong") else "SG%"
            preds.append("ag.territory_code like ?"); params.append(mk)
        scoped = role == "Insurance Agent"
        if scoped:
            preds.append("l.assigned_agent_id = ?"); params.append(_current_agent(con, agent_id))
        where = " and ".join(preds)
        base = f"""
          from leads l
          left join agents ag on ag.agent_id = l.assigned_agent_id
          left join customers cu on cu.customer_id = l.customer_id
          where {where}
        """
        leads_n = con.execute(f"select count(*) {base}", params).fetchone()[0]
        opp_n = con.execute(f"select count(*) from opportunities o join leads l on l.lead_id=o.lead_id "
                            f"left join agents ag on ag.agent_id=l.assigned_agent_id left join customers cu on cu.customer_id=l.customer_id "
                            f"where o.lead_id is not null and {where}", params).fetchone()[0]
        prop_n = con.execute(f"select count(*) from proposals pr join opportunities o on o.opportunity_id=pr.opportunity_id "
                             f"join leads l on l.lead_id=o.lead_id left join agents ag on ag.agent_id=l.assigned_agent_id "
                             f"left join customers cu on cu.customer_id=l.customer_id where o.lead_id is not null and {where}", params).fetchone()[0]
        app_n = con.execute(f"select count(*) from applications a join opportunities o on o.opportunity_id=a.opportunity_id "
                            f"join leads l on l.lead_id=o.lead_id left join agents ag on ag.agent_id=l.assigned_agent_id "
                            f"left join customers cu on cu.customer_id=l.customer_id where o.lead_id is not null and {where}", params).fetchone()[0]
        iss_n = con.execute(f"select count(*) from applications a join opportunities o on o.opportunity_id=a.opportunity_id "
                            f"join leads l on l.lead_id=o.lead_id left join agents ag on ag.agent_id=l.assigned_agent_id "
                            f"left join customers cu on cu.customer_id=l.customer_id where o.lead_id is not null and a.application_status='issued' and {where}", params).fetchone()[0]
        # avg time-to-issue (lead received -> issue) for issued chains
        tti = con.execute(f"""
            select avg(date_diff('day', l.received_at, a.application_date))
            from applications a join opportunities o on o.opportunity_id=a.opportunity_id
            join leads l on l.lead_id=o.lead_id left join agents ag on ag.agent_id=l.assigned_agent_id
            left join customers cu on cu.customer_id=l.customer_id
            where o.lead_id is not null and a.application_status='issued' and {where}""", params).fetchone()[0]
        drops = con.execute("select string_agg(distinct lost_reason, ', ') from opportunities where lost_reason is not null").fetchone()[0]

        def conv(a, b):
            return round(100.0 * b / a, 1) if a else None
        stages = [
            {"stage_order": 1, "stage_name": "lead", "count": leads_n, "conversion_to_next_pct": conv(leads_n, opp_n), "drop_off": "no_contact, not_qualified"},
            {"stage_order": 2, "stage_name": "opportunity", "count": opp_n, "conversion_to_next_pct": conv(opp_n, prop_n), "drop_off": drops or "not_qualified"},
            {"stage_order": 3, "stage_name": "proposal", "count": prop_n, "conversion_to_next_pct": conv(prop_n, app_n), "drop_off": "no_response, price"},
            {"stage_order": 4, "stage_name": "application", "count": app_n, "conversion_to_next_pct": 100.0, "drop_off": "incomplete"},
            {"stage_order": 5, "stage_name": "underwriting", "count": app_n, "conversion_to_next_pct": conv(app_n, iss_n), "drop_off": "medical_decline, risk_decline"},
            {"stage_order": 6, "stage_name": "issued_policy", "count": iss_n, "conversion_to_next_pct": None, "drop_off": ""},
        ]
        return {
            "process_id": "lead_to_conversion", "role": role, "scoped_to_agent": scoped,
            "filters": {"from": from_, "to": to, "region": region, "segment": segment, "market": market},
            "stages": stages,
            "overall_conversion_pct": conv(leads_n, iss_n),
            "avg_time_to_issue_days": round(tti, 1) if tti is not None else None,
            "top_drop_off_reasons": (drops or "").split(", ")[:5],
        }
    finally:
        con.close()


# ---------------------------------------------------------------------------
# 2. Repurchase
# ---------------------------------------------------------------------------
@router.get("/repurchase")
def repurchase(segment: str | None = None, product: str | None = None, market: str | None = None,
               role: str = "Executive Leadership", agent_id: str | None = None) -> dict[str, Any]:
    con = _conn()
    try:
        preds, params = ["1=1"], []
        if segment:
            preds.append("customer_segment = ?"); params.append(segment)
        if product:
            preds.append("product_line = ?"); params.append(product)
        if market:
            preds.append("region = ?"); params.append("Hong Kong" if market.lower() in ("hk", "hong kong") else "Singapore")
        scoped = role == "Insurance Agent"
        if scoped:
            ca = _current_agent(con, agent_id)
            preds.append("repeat_policy_id in (select policy_id from policies where agent_id = ?)"); params.append(ca)
        where = " and ".join(preds)
        ncust = con.execute("select count(*) from customers").fetchone()[0]
        overall = con.execute(f"select count(distinct customer_id) from v_process_repurchase where gap_days between 180 and 730 and {where}", params).fetchone()[0]
        by_seg = con.execute(f"""
            select customer_segment,
                   count(distinct customer_id) filter (where gap_days between 180 and 730) as repurchasers,
                   round(avg(gap_days) filter (where gap_days between 180 and 730),0) as avg_gap_days,
                   round(100.0*count(distinct case when gap_days between 180 and 730 then customer_id end)
                     / nullif(count(distinct customer_id),0),1) as repurchase_rate_pct
            from v_process_repurchase where {where} group by customer_segment order by repurchasers desc""", params).fetchall()
        dist = con.execute(f"""
            select case when gap_days<=180 then '0-6m' when gap_days<=365 then '6-12m'
                        when gap_days<=730 then '12-24m' else '24m+' end as bucket, count(*) n
            from v_process_repurchase where {where} group by 1
            order by case bucket when '0-6m' then 1 when '6-12m' then 2 when '12-24m' then 3 else 4 end""", params).fetchall()
        cross = con.execute(f"select round(100.0*avg(case when is_cross_line then 1 else 0 end),1) from v_process_repurchase where {where} and gap_days between 180 and 730", params).fetchone()[0]
        xsell = con.execute(f"""select round(count(*)::double / nullif(count(distinct customer_id),0),2)
            from policies where policy_status in ('active','renewed','issued')
            {"and agent_id = ?" if scoped else ""}""", ([_current_agent(con, agent_id)] if scoped else [])).fetchone()[0]
        return {
            "process_id": "customer_repurchase", "role": role, "scoped_to_agent": scoped,
            "filters": {"segment": segment, "product": product, "market": market},
            "repurchase_rate_pct": round(100.0 * overall / ncust, 1) if ncust else 0,
            "repurchasers": overall, "customers": ncust,
            "cross_line_pct": cross, "cross_sell_ratio": xsell,
            "by_segment": [{"segment": r[0], "repurchasers": r[1], "avg_gap_days": r[2], "repurchase_rate_pct": r[3]} for r in by_seg],
            "time_to_repurchase_distribution": [{"bucket": r[0], "count": r[1]} for r in dist],
        }
    finally:
        con.close()


# ---------------------------------------------------------------------------
# 3. Demand
# ---------------------------------------------------------------------------
@router.get("/demand")
def demand(product_line: str | None = None, region: str | None = None, market: str | None = None) -> dict[str, Any]:
    con = _conn()
    try:
        preds, params = ["1=1"], []
        if product_line:
            preds.append("product_line = ?"); params.append(product_line)
        if region:
            preds.append("region = ?"); params.append(region)
        if market:
            preds.append("region = ?"); params.append("Hong Kong" if market.lower() in ("hk", "hong kong") else "Singapore")
        where = " and ".join(preds)
        series = con.execute(f"""
            select month, product_line, region, leads_count, quotes_count, responses_count,
                   demand_index, policies_issued, demand_to_realized_pct
            from v_process_demand where {where} order by month""", params).fetchall()
        # rising/falling: last 3 months vs prior 3, per product_line
        callouts = con.execute(f"""
            with mx as (select max(month) m from v_process_demand),
            agg as (
              select product_line,
                sum(demand_index) filter (where month > (select m from mx) - interval 3 month) as recent3,
                sum(demand_index) filter (where month <= (select m from mx) - interval 3 month
                                            and month > (select m from mx) - interval 6 month) as prior3
              from v_process_demand where {where} group by product_line)
            select product_line, recent3, prior3,
                   round(100.0*(recent3-prior3)/nullif(prior3,0),1) as growth_pct
            from agg order by growth_pct desc nulls last""", params).fetchall()
        return {
            "process_id": "market_demand",
            "filters": {"product_line": product_line, "region": region, "market": market},
            "series": [{"month": str(r[0]), "product_line": r[1], "region": r[2], "leads": r[3], "quotes": r[4],
                        "responses": r[5], "demand_index": r[6], "policies_issued": r[7], "realized_pct": r[8]} for r in series],
            "demand_callouts": [{"product_line": r[0], "recent3": r[1], "prior3": r[2], "growth_pct": r[3],
                                 "direction": "rising" if (r[3] or 0) > 5 else "falling" if (r[3] or 0) < -5 else "stable"} for r in callouts],
        }
    finally:
        con.close()


# ---------------------------------------------------------------------------
# 4. Campaign effectiveness (process / attribution view)
# ---------------------------------------------------------------------------
@router.get("/campaign-effectiveness")
def campaign_effectiveness(channel: str | None = None, segment: str | None = None,
                           from_: str | None = Query(None, alias="from"), to: str | None = None) -> dict[str, Any]:
    con = _conn()
    try:
        preds, params = ["1=1"], []
        if channel:
            preds.append("channel = ?"); params.append(channel)
        if from_:
            preds.append("start_date >= ?"); params.append(from_)
        if to:
            preds.append("start_date <= ?"); params.append(to)
        where = " and ".join(preds)
        totals = con.execute(f"""
            select sum(targeted), sum(delivered), sum(opened), sum(clicked), sum(responded),
                   sum(conversions), round(sum(premium_generated),2), round(sum(budget_amount),2),
                   round(sum(premium_generated)/nullif(sum(budget_amount),0),2)
            from v_process_campaign where {where}""", params).fetchone()
        leaderboard = con.execute(f"""
            select campaign_name, channel, targeted, responded, conversions, premium_generated, budget_amount, roi_multiple, conversion_rate
            from v_process_campaign where {where} and conversions>0 order by roi_multiple desc nulls last limit 15""", params).fetchall()
        by_channel = con.execute(f"""
            select channel, count(*) campaigns, sum(conversions) conversions, round(sum(premium_generated),2) premium,
                   round(sum(premium_generated)/nullif(sum(budget_amount),0),2) roi
            from v_process_campaign where {where} group by channel order by roi desc nulls last""", params).fetchall()
        return {
            "process_id": "campaign_effectiveness",
            "filters": {"channel": channel, "segment": segment, "from": from_, "to": to},
            "funnel": {"targeted": totals[0], "delivered": totals[1], "opened": totals[2], "clicked": totals[3],
                       "responded": totals[4], "conversions": totals[5], "premium_generated": totals[6],
                       "budget": totals[7], "roi_multiple": totals[8]},
            "roi_leaderboard": [{"campaign": r[0], "channel": r[1], "targeted": r[2], "responded": r[3], "conversions": r[4],
                                 "premium_generated": r[5], "budget": r[6], "roi_multiple": r[7], "conversion_rate": r[8]} for r in leaderboard],
            "by_channel": [{"channel": r[0], "campaigns": r[1], "conversions": r[2], "premium": r[3], "roi": r[4]} for r in by_channel],
        }
    finally:
        con.close()


# ---------------------------------------------------------------------------
# 5. Process definition (graph: stages + metrics + bindings + formulas)
# ---------------------------------------------------------------------------
@router.get("/{process_id}/definition")
def process_definition(process_id: str) -> dict[str, Any]:
    con = _conn()
    try:
        node = con.execute("select process_id, process_name, description, subject_area, owner_role, instance_view "
                           "from process_nodes where process_id=?", [process_id]).fetchone()
        if not node:
            raise HTTPException(404, f"process not found: {process_id}")
        stages = con.execute("""
            select s.stage_order, s.stage_name, s.entity_table, s.stage_metric_id, s.typical_lag_days, s.drop_off_reasons,
                   cn.name as metric_name, b.canonical_view, b.formula_sql
            from process_stages s
            left join concept_nodes cn on cn.node_id = s.stage_metric_id
            left join metric_bindings b on b.metric_id = s.stage_metric_id
            where s.process_id=? order by s.stage_order""", [process_id]).fetchall()
        edges = con.execute("select from_stage_id, to_stage_id, edge_type, weight from process_edges where process_id=?", [process_id]).fetchall()
        return {
            "process_id": node[0], "process_name": node[1], "description": node[2],
            "subject_area": node[3], "owner_role": node[4], "instance_view": node[5],
            "stages": [{"stage_order": s[0], "stage_name": s[1], "entity_table": s[2], "metric_id": s[3],
                        "typical_lag_days": s[4], "drop_off_reasons": s[5], "metric_name": s[6],
                        "canonical_view": s[7], "formula_sql": s[8]} for s in stages],
            "edges": [{"from": e[0], "to": e[1], "edge_type": e[2], "weight": e[3]} for e in edges],
        }
    finally:
        con.close()
