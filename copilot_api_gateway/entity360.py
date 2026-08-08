from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from fastapi import HTTPException

from copilot_api_gateway.db import connect, json_ready


def _fetch_one(conn, query: str, params: tuple[Any, ...]) -> dict[str, Any]:
    with conn.cursor() as cur:
        cur.execute(query, params)
        row = cur.fetchone()
    if not row:
        return {}
    return json_ready(dict(row))


def _fetch_all(conn, query: str, params: tuple[Any, ...]) -> list[dict[str, Any]]:
    with conn.cursor() as cur:
        cur.execute(query, params)
        return [json_ready(dict(row)) for row in cur.fetchall()]


def _table_columns(conn, table_name: str) -> set[str]:
    with conn.cursor() as cur:
        cur.execute(
            """
            select column_name
            from information_schema.columns
            where table_schema = 'public'
              and table_name = %s
            """,
            (table_name,),
        )
        return {row["column_name"] for row in cur.fetchall()}


def _select_expr(columns: set[str], column_name: str, alias: str | None = None, fallback: str = "null") -> str:
    output_name = alias or column_name
    if column_name in columns:
        return f"{column_name} as {output_name}"
    return f"{fallback} as {output_name}"


def _agent_region_filter_value(region: str | None) -> str | None:
    if not region:
        return None
    normalized = region.strip()
    if not normalized or normalized.lower() == "all":
        return None
    if normalized.upper().startswith("SG-"):
        return normalized[3:]
    return normalized


def _agent_region_label_expr(column_name: str) -> str:
    return (
        "case "
        f"when {column_name} is null or {column_name} = '' then 'Unassigned' "
        f"when {column_name} ~ '^[0-9]+$' then 'SG-' || {column_name} "
        f"else {column_name} "
        "end"
    )


def customer_360(customer_id: UUID) -> dict[str, Any]:
    with connect() as conn:
        summary = _fetch_one(
            conn,
            """
            select
              c.customer_id,
              c.customer_number,
              c.customer_segment,
              c.lifecycle_stage,
              c.risk_tier,
              c.engagement_score,
              p.display_name,
              p.email,
              p.phone,
              p.preferred_contact_method,
              concat_ws(', ', addr.city, addr.country_code) as location,
              c.acquisition_date
            from public.customers c
            join public.parties p on p.party_id = c.party_id
            left join lateral (
              select city, country_code
              from public.addresses
              where party_id = p.party_id
                and is_current
              order by case address_type when 'primary' then 0 else 1 end, effective_date desc nulls last
              limit 1
            ) addr on true
            where c.customer_id = %s
            """,
            (str(customer_id),),
        )
        if not summary:
            raise HTTPException(status_code=404, detail=f"Customer not found: {customer_id}")
        sections = {
            "policies": _fetch_all(
                conn,
                """
                select p.policy_id, p.policy_number, p.policy_status, p.effective_date, p.expiration_date,
                       p.annual_premium, prod.product_name, prod.line_of_business
                from public.policies p
                join public.products prod on prod.product_id = p.product_id
                where p.customer_id = %s
                order by p.effective_date desc
                limit 20
                """,
                (str(customer_id),),
            ),
            "claims": _fetch_all(
                conn,
                """
                select claim_id, claim_number, claim_status, loss_date, report_date, paid_amount,
                       reserve_amount, incurred_amount, loss_cause
                from public.claims
                where customer_id = %s
                order by report_date desc
                limit 20
                """,
                (str(customer_id),),
            ),
            "model_scores": _fetch_all(
                conn,
                """
                select model_name, model_version, score_name, score, score_band, score_ts,
                       top_reason_1, top_reason_2, top_reason_3
                from public.v_latest_model_scores
                where entity_type = 'customer'
                  and entity_id = %s
                order by score_ts desc
                limit 20
                """,
                (str(customer_id),),
            ),
            "next_best_actions": recommendations_for_entity(customer_id)["recommendations"],
        }
    return envelope("customer", customer_id, summary, sections)


def agent_360(agent_id: UUID) -> dict[str, Any]:
    with connect() as conn:
        summary = _fetch_one(
            conn,
            """
            select a.agent_id, a.agent_number, a.channel, a.territory_code, a.status,
                   a.appointment_date, a.termination_date, p.display_name, p.email, p.phone,
                   agency.display_name as agency_name
            from public.agents a
            join public.parties p on p.party_id = a.party_id
            left join public.parties agency on agency.party_id = a.agency_party_id
            where a.agent_id = %s
            """,
            (str(agent_id),),
        )
        if not summary:
            raise HTTPException(status_code=404, detail=f"Agent not found: {agent_id}")
        sections = {
            "mapa_metrics": _fetch_all(
                conn,
                """
                select metric_month, leads_count, contacts_count, quotes_count, applications_count,
                       policies_bound_count, new_business_premium, renewal_premium,
                       retained_policy_count, lapsed_policy_count, loss_ratio
                from public.agent_mapa_metrics
                where agent_id = %s
                order by metric_month desc
                limit 24
                """,
                (str(agent_id),),
            ),
            "movements": _fetch_all(
                conn,
                """
                select movement_type, from_territory_code, to_territory_code, effective_date, end_date, reason
                from public.agent_movements
                where agent_id = %s
                order by effective_date desc
                limit 20
                """,
                (str(agent_id),),
            ),
            "model_scores": _fetch_all(
                conn,
                """
                select model_name, model_version, score_name, score, score_band, score_ts,
                       top_reason_1, top_reason_2, top_reason_3
                from public.v_latest_model_scores
                where entity_type = 'agent'
                  and entity_id = %s
                order by score_ts desc
                limit 20
                """,
                (str(agent_id),),
            ),
            "recommendations": recommendations_for_entity(agent_id)["recommendations"],
            "commissions": _fetch_optional_table(
                conn,
                "agent_commissions",
                """
                select commission_period, commission_amount, commission_type, paid_date, chargeback_flag
                from public.agent_commissions
                where agent_id = %s
                order by commission_period desc
                limit 12
                """,
                (str(agent_id),),
            ),
            "targets": _fetch_optional_table(
                conn,
                "agent_targets",
                """
                select target_period_start, target_period_end, target_type, target_value,
                       actual_value, attainment_pct
                from public.agent_targets
                where agent_id = %s
                order by target_period_start desc
                limit 6
                """,
                (str(agent_id),),
            ),
            "customer_portfolio": _fetch_one(
                conn,
                """
                with assigned as (
                  select distinct customer_id
                  from public.policies
                  where agent_id = %s
                ),
                latest_scores as (
                  select entity_id, score_name, score_band, score
                  from public.v_latest_model_scores
                  where entity_type = 'customer'
                    and entity_id in (select customer_id from assigned)
                )
                select
                  count(*) as assigned_customers,
                  count(*) filter (
                    where exists (
                      select 1 from latest_scores s
                      where s.entity_id = assigned.customer_id
                        and s.score_name ilike '%%propensity%%'
                        and coalesce(s.score_band, '') in ('HIGH', 'VERY_HIGH')
                    )
                  ) as high_propensity_customers,
                  count(*) filter (
                    where exists (
                      select 1 from latest_scores s
                      where s.entity_id = assigned.customer_id
                        and s.score_name ilike '%%lapse%%'
                        and coalesce(s.score_band, '') in ('HIGH', 'VERY_HIGH')
                    )
                  ) as high_lapse_risk_customers,
                  count(*) filter (
                    where exists (
                      select 1 from latest_scores s
                      where s.entity_id = assigned.customer_id
                        and s.score_name ilike '%%lifetime%%'
                        and (coalesce(s.score_band, '') in ('HIGH', 'VERY_HIGH') or coalesce(s.score, 0) >= 0.75)
                    )
                  ) as high_clv_customers
                from assigned
                """,
                (str(agent_id),),
            ),
        }
    return envelope("agent", agent_id, summary, sections)


def campaign_360(campaign_id: UUID) -> dict[str, Any]:
    with connect() as conn:
        summary = _fetch_one(
            conn,
            """
            select campaign_id, campaign_code, campaign_name, campaign_type, channel, objective,
                   target_line_of_business, start_date, end_date, budget_amount, status
            from public.campaigns
            where campaign_id = %s
            """,
            (str(campaign_id),),
        )
        if not summary:
            raise HTTPException(status_code=404, detail=f"Campaign not found: {campaign_id}")
        sections = {
            "funnel": _fetch_one(
                conn,
                """
                select
                  (select count(distinct ct.campaign_target_id)
                   from public.campaign_targets ct
                   where ct.campaign_id = %s) as targets,
                  (select count(distinct ct.campaign_target_id)
                   from public.campaign_targets ct
                   left join public.campaign_responses cr on cr.campaign_target_id = ct.campaign_target_id
                   where ct.campaign_id = %s
                     and (ct.target_status = 'sent' or cr.response_type = 'delivered')) as delivered,
                  (select count(distinct cr.campaign_response_id)
                   from public.campaign_responses cr
                   where cr.campaign_id = %s and cr.response_type = 'opened') as opened,
                  (select count(distinct cr.campaign_response_id)
                   from public.campaign_responses cr
                   where cr.campaign_id = %s and cr.response_type = 'clicked') as clicked,
                  (select count(distinct cr.campaign_response_id)
                   from public.campaign_responses cr
                   where cr.campaign_id = %s
                     and cr.response_type in ('opened', 'clicked', 'called', 'quoted', 'converted')) as responses,
                  (select count(distinct l.lead_id)
                   from public.leads l
                   where l.campaign_id = %s) as leads_created,
                  (select count(distinct o.opportunity_id)
                   from public.opportunities o
                   where o.campaign_id = %s
                     and (o.opportunity_stage in ('quoted', 'application', 'underwriting', 'bound')
                          or o.quoted_premium is not null)) as quotes_created,
                  (select count(distinct p.policy_id)
                   from public.opportunities o
                   join public.policies p on p.opportunity_id = o.opportunity_id
                   where o.campaign_id = %s) as policies_issued,
                  coalesce(
                    (select sum(coalesce(p.annual_premium, 0))
                     from public.opportunities o
                     join public.policies p on p.opportunity_id = o.opportunity_id
                     where o.campaign_id = %s),
                    (select sum(coalesce(cr.conversion_premium, 0))
                     from public.campaign_responses cr
                     where cr.campaign_id = %s),
                    0
                  ) as conversion_premium
                """,
                tuple([str(campaign_id)] * 10),
            ),
            "responses": _fetch_all(
                conn,
                """
                select response_type, count(*) as response_count,
                       count(*) filter (where conversion_flag) as conversions,
                       sum(coalesce(conversion_premium, 0)) as conversion_premium
                from public.campaign_responses
                where campaign_id = %s
                group by response_type
                order by response_count desc
                """,
                (str(campaign_id),),
            ),
            "segment_performance": _fetch_all(
                conn,
                """
                select coalesce(c.customer_segment, 'Lead/prospect') as segment,
                       count(distinct ct.campaign_target_id) as targets,
                       count(distinct cr.campaign_response_id) filter (
                         where cr.response_type in ('opened', 'clicked', 'called', 'quoted', 'converted')
                       ) as responses,
                       count(distinct cr.campaign_response_id) filter (where cr.conversion_flag) as conversions,
                       sum(coalesce(cr.conversion_premium, 0)) as conversion_premium
                from public.campaign_targets ct
                left join public.customers c on c.customer_id = ct.customer_id
                left join public.campaign_responses cr on cr.campaign_target_id = ct.campaign_target_id
                where ct.campaign_id = %s
                group by coalesce(c.customer_segment, 'Lead/prospect')
                order by conversions desc, responses desc, targets desc
                limit 8
                """,
                (str(campaign_id),),
            ),
            "region_performance": _fetch_all(
                conn,
                """
                select coalesce(a.country_code || ' / ' || a.state_code, 'Not captured') as region,
                       count(distinct ct.campaign_target_id) as targets,
                       count(distinct cr.campaign_response_id) filter (
                         where cr.response_type in ('opened', 'clicked', 'called', 'quoted', 'converted')
                       ) as responses,
                       count(distinct cr.campaign_response_id) filter (where cr.conversion_flag) as conversions
                from public.campaign_targets ct
                left join public.customers c on c.customer_id = ct.customer_id
                left join public.parties p on p.party_id = c.party_id
                left join public.addresses a on a.party_id = p.party_id and a.is_current
                left join public.campaign_responses cr on cr.campaign_target_id = ct.campaign_target_id
                where ct.campaign_id = %s
                group by coalesce(a.country_code || ' / ' || a.state_code, 'Not captured')
                order by conversions desc, responses desc, targets desc
                limit 8
                """,
                (str(campaign_id),),
            ),
            "product_performance": _fetch_all(
                conn,
                """
                with product_activity as (
                  select coalesce(prod.product_name, camp.target_line_of_business, 'Not captured') as product,
                         count(distinct l.lead_id) as leads,
                         0::bigint as opportunities,
                         0::bigint as policies,
                         0::numeric as premium
                  from public.campaigns camp
                  left join public.leads l on l.campaign_id = camp.campaign_id
                  left join public.products prod on prod.product_id = l.product_id
                  where camp.campaign_id = %s
                  group by coalesce(prod.product_name, camp.target_line_of_business, 'Not captured')
                  union all
                  select coalesce(prod.product_name, camp.target_line_of_business, 'Not captured') as product,
                         0::bigint as leads,
                         count(distinct o.opportunity_id) as opportunities,
                         count(distinct pol.policy_id) as policies,
                         sum(coalesce(pol.annual_premium, o.quoted_premium, 0)) as premium
                  from public.campaigns camp
                  left join public.opportunities o on o.campaign_id = camp.campaign_id
                  left join public.products prod on prod.product_id = o.product_id
                  left join public.policies pol on pol.opportunity_id = o.opportunity_id
                  where camp.campaign_id = %s
                  group by coalesce(prod.product_name, camp.target_line_of_business, 'Not captured')
                )
                select product,
                       sum(leads) as leads,
                       sum(opportunities) as opportunities,
                       sum(policies) as policies,
                       sum(premium) as premium
                from product_activity
                group by product
                order by sum(policies) desc, sum(premium) desc nulls last
                limit 8
                """,
                (str(campaign_id), str(campaign_id)),
            ),
            "agent_performance": _fetch_all(
                conn,
                """
                select coalesce(p.display_name, 'Unassigned') as agent_name,
                       count(distinct ct.campaign_target_id) as targets,
                       count(distinct cr.campaign_response_id) filter (
                         where cr.response_type in ('opened', 'clicked', 'called', 'quoted', 'converted')
                       ) as responses,
                       count(distinct cr.campaign_response_id) filter (where cr.conversion_flag) as conversions,
                       sum(coalesce(cr.conversion_premium, 0)) as premium
                from public.campaign_targets ct
                left join public.agents a on a.agent_id = ct.agent_id
                left join public.parties p on p.party_id = a.party_id
                left join public.campaign_responses cr on cr.campaign_target_id = ct.campaign_target_id
                where ct.campaign_id = %s
                group by coalesce(p.display_name, 'Unassigned')
                order by conversions desc, responses desc, premium desc nulls last
                limit 8
                """,
                (str(campaign_id),),
            ),
            "model_scores": _fetch_all(
                conn,
                """
                select model_name, model_version, score_name, score, score_band, score_ts,
                       top_reason_1, top_reason_2, top_reason_3
                from public.v_latest_model_scores
                where entity_type in ('campaign', 'campaign_target')
                  and entity_id in (
                    select campaign_target_id from public.campaign_targets where campaign_id = %s
                    union all select %s::uuid
                  )
                order by score desc nulls last, score_ts desc
                limit 20
                """,
                (str(campaign_id), str(campaign_id)),
            ),
            "targets_sample": _fetch_all(
                conn,
                """
                select campaign_target_id, customer_id, lead_id, agent_id, target_status,
                       selected_at, suppression_reason
                from public.campaign_targets
                where campaign_id = %s
                order by selected_at desc
                limit 20
                """,
                (str(campaign_id),),
            ),
        }
    return envelope("campaign", campaign_id, summary, sections)


def claims_360(claim_id: UUID) -> dict[str, Any]:
    with connect() as conn:
        summary = _fetch_one(
            conn,
            """
            select cl.claim_id, cl.claim_number, cl.policy_id, cl.customer_id, cl.assigned_agent_id,
                   cl.loss_date, cl.report_date, cl.close_date, cl.claim_status, cl.loss_cause,
                   cl.loss_description, cl.paid_amount, cl.reserve_amount, cl.incurred_amount,
                   cl.litigation_flag, cl.catastrophe_flag, p.policy_number, prod.product_name
            from public.claims cl
            join public.policies p on p.policy_id = cl.policy_id
            join public.products prod on prod.product_id = p.product_id
            where cl.claim_id = %s
            """,
            (str(claim_id),),
        )
        if not summary:
            raise HTTPException(status_code=404, detail=f"Claim not found: {claim_id}")
        sections = {
            "model_scores": _fetch_all(
                conn,
                """
                select model_name, model_version, score_name, score, score_band, score_ts,
                       top_reason_1, top_reason_2, top_reason_3
                from public.v_latest_model_scores
                where entity_type = 'claim'
                  and entity_id = %s
                order by score_ts desc
                limit 20
                """,
                (str(claim_id),),
            ),
            "fraud_indicators": _fetch_optional_table(
                conn,
                "claim_fraud_indicators",
                """
                select *
                from public.claim_fraud_indicators
                where claim_id = %s
                order by created_at desc
                limit 20
                """,
                (str(claim_id),),
            ),
            "assessments": _fetch_optional_table(
                conn,
                "claim_assessments",
                """
                select *
                from public.claim_assessments
                where claim_id = %s
                order by created_at desc
                limit 20
                """,
                (str(claim_id),),
            ),
        }
    return envelope("claim", claim_id, summary, sections)


def _fetch_optional_table(conn, table_name: str, query: str, params: tuple[Any, ...]) -> list[dict[str, Any]]:
    with conn.cursor() as cur:
        cur.execute("select to_regclass(%s) as table_ref", (f"public.{table_name}",))
        exists = cur.fetchone()["table_ref"]
    if not exists:
        return []
    return _fetch_all(conn, query, params)


def search_customers(query: str = "", limit: int = 10) -> list[dict[str, Any]]:
    search_text = f"%{query.strip()}%"
    with connect() as conn:
        rows = _fetch_all(
            conn,
            """
            select
              c.customer_id,
              c.customer_number,
              p.display_name,
              c.customer_segment,
              c.lifecycle_stage,
              p.preferred_contact_method,
              min(pol.policy_number) as policy_number
            from public.customers c
            join public.parties p on p.party_id = c.party_id
            left join public.policies pol on pol.customer_id = c.customer_id
            where %s = '%%'
               or p.display_name ilike %s
               or c.customer_number ilike %s
               or pol.policy_number ilike %s
            group by c.customer_id, c.customer_number, p.display_name, c.customer_segment,
                     c.lifecycle_stage, p.preferred_contact_method
            order by
              case c.lifecycle_stage when 'active' then 0 when 'prospect' then 1 else 2 end,
              p.display_name
            limit %s
            """,
            (search_text, search_text, search_text, search_text, limit),
        )
    return rows


def search_agents(query: str = "", limit: int = 10) -> list[dict[str, Any]]:
    search_text = f"%{query.strip()}%"
    with connect() as conn:
        rows = _fetch_all(
            conn,
            """
            select
              a.agent_id,
              a.agent_number,
              p.display_name,
              a.channel,
              a.territory_code,
              a.status,
              a.appointment_date
            from public.agents a
            join public.parties p on p.party_id = a.party_id
            where %s = '%%'
               or p.display_name ilike %s
               or a.agent_number ilike %s
               or a.territory_code ilike %s
               or a.channel ilike %s
            order by
              case a.status when 'active' then 0 when 'inactive' then 1 else 2 end,
              p.display_name
            limit %s
            """,
            (search_text, search_text, search_text, search_text, search_text, limit),
        )
    return rows


def search_campaigns(
    query: str = "",
    limit: int = 10,
    channel: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> list[dict[str, Any]]:
    search_text = f"%{query.strip()}%"
    with connect() as conn:
        rows = _fetch_all(
            conn,
            """
            select
              c.campaign_id,
              c.campaign_code,
              c.campaign_name,
              c.campaign_type,
              c.channel,
              c.objective,
              c.target_line_of_business,
              c.start_date,
              c.end_date,
              c.budget_amount,
              c.status,
              count(distinct ct.campaign_target_id) as target_count,
              count(distinct cr.campaign_response_id) filter (
                where cr.response_type in ('opened', 'clicked', 'called', 'quoted', 'converted')
              ) as response_count,
              count(distinct cr.campaign_response_id) filter (where cr.conversion_flag) as conversion_count
            from public.campaigns c
            left join public.campaign_targets ct on ct.campaign_id = c.campaign_id
            left join public.campaign_responses cr on cr.campaign_target_id = ct.campaign_target_id
            where (%s = '%%'
                   or c.campaign_name ilike %s
                   or c.campaign_code ilike %s
                   or c.channel ilike %s
                   or c.target_line_of_business ilike %s
                   or coalesce(c.objective, '') ilike %s)
              and (%s::text is null or c.channel = %s::text)
              and (%s::date is null or c.end_date >= %s::date)
              and (%s::date is null or c.start_date <= %s::date)
            group by c.campaign_id, c.campaign_code, c.campaign_name, c.campaign_type,
                     c.channel, c.objective, c.target_line_of_business, c.start_date,
                     c.end_date, c.budget_amount, c.status
            order by
              case c.status when 'active' then 0 when 'planned' then 1 when 'completed' then 2 else 3 end,
              c.start_date desc,
              c.campaign_name
            limit %s
            """,
            (
                search_text,
                search_text,
                search_text,
                search_text,
                search_text,
                search_text,
                channel,
                channel,
                date_from,
                date_from,
                date_to,
                date_to,
                limit,
            ),
        )
    return rows


def agent_performance_dashboard(
    region: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> dict[str, Any]:
    with connect() as conn:
        raw_region = _agent_region_filter_value(region)
        region_label = _agent_region_label_expr("territory_code")
        filters = {
            "region": region,
            "region_raw": raw_region,
            "date_from": date_from,
            "date_to": date_to,
        }
        params = (raw_region, raw_region, date_from, date_from, date_to, date_to)
        base_cte = """
            with filtered_agents as (
              select a.agent_id, a.agent_number, a.territory_code, a.channel, a.status,
                     a.appointment_date, p.display_name
              from public.agents a
              join public.parties p on p.party_id = a.party_id
              where (%s::text is null or a.territory_code = %s::text)
            ),
            mapa as (
              select m.*
              from public.agent_mapa_metrics m
              join filtered_agents a on a.agent_id = m.agent_id
              where (%s::date is null or m.metric_month >= %s::date)
                and (%s::date is null or m.metric_month <= %s::date)
            ),
            bounds as (
              select coalesce(max(metric_month), date_trunc('month', current_date)::date) as max_month
              from mapa
            ),
            rollup as (
              select a.agent_id, a.agent_number, a.display_name, a.territory_code, a.channel,
                     a.status, a.appointment_date,
                     coalesce(sum(m.new_business_premium), 0) as premium,
                     coalesce(sum(m.policies_bound_count), 0) as policies_sold,
                     coalesce(sum(m.quotes_count), 0) as quotes,
                     coalesce(sum(m.contacts_count), 0) as activities,
                     coalesce(sum(m.applications_count), 0) as applications,
                     coalesce(sum(m.retained_policy_count), 0) as retained,
                     coalesce(sum(m.lapsed_policy_count), 0) as lapsed,
                     coalesce(sum(m.new_business_premium) filter (where m.metric_month >= b.max_month - interval '2 months'), 0) as last_3m_premium,
                     coalesce(sum(m.new_business_premium) filter (
                       where m.metric_month < b.max_month - interval '2 months'
                         and m.metric_month >= b.max_month - interval '5 months'
                     ), 0) as prior_3m_premium,
                     coalesce(sum(m.contacts_count + m.applications_count) filter (where m.metric_month >= b.max_month - interval '2 months'), 0) as last_3m_activity,
                     coalesce(sum(m.contacts_count + m.applications_count) filter (
                       where m.metric_month < b.max_month - interval '2 months'
                         and m.metric_month >= b.max_month - interval '5 months'
                     ), 0) as prior_3m_activity
              from filtered_agents a
              cross join bounds b
              left join mapa m on m.agent_id = a.agent_id
              group by a.agent_id, a.agent_number, a.display_name, a.territory_code, a.channel,
                       a.status, a.appointment_date
            ),
            targets as (
              select agent_id, avg(attainment_pct) as target_achievement
              from public.agent_targets
              group by agent_id
            ),
            customer_mix as (
              select p.agent_id, c.customer_segment, count(distinct p.customer_id) as customer_count
              from public.policies p
              join public.customers c on c.customer_id = p.customer_id
              join filtered_agents a on a.agent_id = p.agent_id
              group by p.agent_id, c.customer_segment
            ),
            top_customer_segment as (
              select distinct on (agent_id) agent_id, customer_segment, customer_count
              from customer_mix
              order by agent_id, customer_count desc
            ),
            product_mix as (
              select p.agent_id, prod.line_of_business, count(*) as policy_count,
                     sum(coalesce(p.annual_premium, 0)) as premium
              from public.policies p
              join public.products prod on prod.product_id = p.product_id
              join filtered_agents a on a.agent_id = p.agent_id
              group by p.agent_id, prod.line_of_business
            ),
            top_product as (
              select distinct on (agent_id) agent_id, line_of_business, policy_count, premium
              from product_mix
              order by agent_id, premium desc nulls last, policy_count desc
            ),
            latest_scores as (
              select entity_id as agent_id, model_name, score_name, score, score_band,
                     top_reason_1, top_reason_2, top_reason_3
              from public.v_latest_model_scores
              where entity_type = 'agent'
            ),
            enriched as (
              select r.*,
                     coalesce(t.target_achievement, 0) as target_achievement,
                     coalesce(tp.line_of_business, 'generalist') as product_focus,
                     coalesce(tcs.customer_segment, 'mixed_book') as customer_focus,
                     coalesce(ap.score, 0.5) as performance_score,
                     coalesce(aa.score, 0.2) as attrition_score,
                     case
                       when r.premium >= 1000000 then 'MDRT / elite producers'
                       when r.prior_3m_premium > 0 and (r.last_3m_premium - r.prior_3m_premium) / nullif(r.prior_3m_premium, 0) >= 0.30 then 'Rising stars'
                       when lower(coalesce(tp.line_of_business, '')) like '%%health%%' then 'Health protection specialists'
                       when lower(coalesce(tp.line_of_business, '')) like '%%wealth%%' or lower(coalesce(tp.line_of_business, '')) like '%%investment%%' then 'Wealth and retirement specialists'
                       when coalesce(sum(r.retained) over (partition by r.agent_id), 0) / nullif(coalesce(sum(r.retained + r.lapsed) over (partition by r.agent_id), 0), 0) >= 0.92 then 'Persistency champions'
                       when coalesce(tcs.customer_segment, '') in ('affluent_wealth', 'sme_owner') then 'Premier client advisors'
                       else 'Core multi-line advisors'
                     end as agent_cluster
              from rollup r
              left join targets t on t.agent_id = r.agent_id
              left join top_product tp on tp.agent_id = r.agent_id
              left join top_customer_segment tcs on tcs.agent_id = r.agent_id
              left join latest_scores ap on ap.agent_id = r.agent_id and ap.model_name = 'agent_performance'
              left join latest_scores aa on aa.agent_id = r.agent_id and aa.model_name = 'agent_attrition'
            )
        """
        with conn.cursor() as cur:
            cur.execute(
                "create temp table agent_perf_enriched on commit drop as " + base_cte + " select * from enriched",
                params,
            )
            cur.execute("analyze agent_perf_enriched")
            cur.execute(
                """
                create temp table agent_perf_mapa on commit drop as
                select m.*
                from public.agent_mapa_metrics m
                join public.agents a on a.agent_id = m.agent_id
                where (%s::text is null or a.territory_code = %s::text)
                  and (%s::date is null or m.metric_month >= %s::date)
                  and (%s::date is null or m.metric_month <= %s::date)
                """,
                params,
            )
            cur.execute("analyze agent_perf_mapa")
        kpis = _fetch_one(
            conn,
            """
            select count(*) as total_agents,
                   count(*) filter (where status = 'active') as active_agents,
                   sum(premium) as premium_generated,
                   sum(policies_sold) as policies_sold,
                   sum(policies_sold)::numeric / nullif(sum(quotes), 0) as average_conversion_rate,
                   sum(retained)::numeric / nullif(sum(retained + lapsed), 0) as average_persistency_rate
            from agent_perf_enriched
            """,
            (),
        )
        leaderboard = _fetch_all(
            conn,
            f"""
            select row_number() over (order by premium desc, policies_sold desc) as rank,
                   agent_id, agent_number, display_name as agent_name, {region_label} as region,
                   premium, policies_sold,
                   policies_sold::numeric / nullif(quotes, 0) as conversion_rate,
                   retained::numeric / nullif(retained + lapsed, 0) as persistency_rate,
                   target_achievement,
                   agent_cluster,
                   customer_focus,
                   product_focus,
                   last_3m_premium,
                   prior_3m_premium
            from agent_perf_enriched
            order by premium desc, policies_sold desc
            limit 25
            """,
            (),
        )
        region_option_details = _fetch_all(
            conn,
            f"""
            select
              { _agent_region_label_expr("a.territory_code") } as region,
              a.territory_code as region_code,
              case
                when a.territory_code ~ '^[0-9]+$' then 'SG'
                when upper(a.territory_code) like 'HK-%%' then 'HK'
                else 'Other'
              end as market,
              count(*) as agent_count,
              count(*) filter (where a.status = 'active') as active_agent_count
            from public.agents a
            group by a.territory_code
            order by
              case
                when a.territory_code ~ '^[0-9]+$' then 0
                when upper(a.territory_code) like 'HK-%%' then 1
                else 2
              end,
              { _agent_region_label_expr("a.territory_code") }
            """,
            (),
        )
        region_options = [as_region["region"] for as_region in region_option_details if as_region.get("region")]
        mapa = _fetch_one(
            conn,
            """
            select sum(coalesce(m.contacts_count, 0)) as meetings,
                   sum(coalesce(m.leads_count, 0)) as activities,
                   sum(coalesce(m.quotes_count, 0)) as proposals,
                   sum(coalesce(m.applications_count, 0)) as applications,
                   sum(coalesce(m.policies_bound_count, 0)) as policy_issuance
            from agent_perf_mapa m
            """,
            (),
        )
        trends = _fetch_all(
            conn,
            """
            select m.metric_month,
                   sum(m.new_business_premium) as premium,
                   sum(m.policies_bound_count)::numeric / nullif(sum(m.quotes_count), 0) as conversion_rate,
                   sum(m.retained_policy_count)::numeric / nullif(sum(m.retained_policy_count + m.lapsed_policy_count), 0) as persistency_rate,
                   avg(t.attainment_pct) as target_achievement
            from agent_perf_mapa m
            left join public.agent_targets t on t.agent_id = m.agent_id
              and m.metric_month between date_trunc('month', t.target_period_start)::date and date_trunc('month', t.target_period_end)::date
            group by m.metric_month
            order by m.metric_month
            """,
            (),
        )
        clusters = _fetch_all(
            conn,
            """
            select agent_cluster,
                   count(*) as agent_count,
                   sum(premium) as premium,
                   sum(policies_sold) as policies_sold,
                   sum(policies_sold)::numeric / nullif(sum(quotes), 0) as conversion_rate,
                   sum(retained)::numeric / nullif(sum(retained + lapsed), 0) as persistency_rate,
                   max(customer_focus) as dominant_customer_segment,
                   max(product_focus) as dominant_product_focus
            from agent_perf_enriched
            group by agent_cluster
            order by premium desc
            """,
            (),
        )
        customer_product_clusters = _fetch_all(
            conn,
            """
            select customer_focus, product_focus,
                   count(*) as agent_count,
                   sum(premium) as premium,
                   sum(policies_sold) as policies_sold,
                   sum(policies_sold)::numeric / nullif(sum(quotes), 0) as conversion_rate
            from agent_perf_enriched
            group by customer_focus, product_focus
            order by premium desc
            limit 12
            """,
            (),
        )
        rising_stars = _fetch_all(
            conn,
            f"""
            select agent_id, agent_number, display_name as agent_name, {region_label} as region,
                   premium, policies_sold, customer_focus, product_focus,
                   (last_3m_premium - prior_3m_premium) / nullif(prior_3m_premium, 0) as growth_rate
            from agent_perf_enriched
            where prior_3m_premium > 0
            order by growth_rate desc nulls last, premium desc
            limit 10
            """,
            (),
        )
        mdrt_agents = _fetch_all(
            conn,
            f"""
            select agent_id, agent_number, display_name as agent_name, {region_label} as region,
                   premium, policies_sold,
                   policies_sold::numeric / nullif(quotes, 0) as conversion_rate,
                   retained::numeric / nullif(retained + lapsed, 0) as persistency_rate,
                   customer_focus, product_focus
            from agent_perf_enriched
            where premium >= 1000000
            order by premium desc
            limit 10
            """,
            (),
        )
        risk_alerts = _fetch_all(
            conn,
            """
            select alert_type, count(*) as agent_count, max(severity) as severity
            from (
              select 'Underperforming agents' as alert_type, agent_id,
                     case when target_achievement < 0.60 or performance_score < 0.35 then 'High' else 'Medium' end as severity
              from agent_perf_enriched
              where target_achievement < 0.80 or performance_score < 0.45
              union all
              select 'High attrition risk agents', agent_id,
                     case when attrition_score >= 0.75 then 'High' else 'Medium' end
              from agent_perf_enriched
              where attrition_score >= 0.55
              union all
              select 'Agents with declining activities', agent_id,
                     case when last_3m_activity < prior_3m_activity * 0.65 then 'High' else 'Medium' end
              from agent_perf_enriched
              where prior_3m_activity > 0 and last_3m_activity < prior_3m_activity * 0.85
              union all
              select 'Agents with poor persistency', agent_id,
                     case when retained::numeric / nullif(retained + lapsed, 0) < 0.75 then 'High' else 'Medium' end
              from agent_perf_enriched
              where retained + lapsed > 0 and retained::numeric / nullif(retained + lapsed, 0) < 0.85
            ) alerts
            group by alert_type
            order by agent_count desc
            """,
            (),
        )
        coaching = _fetch_all(
            conn,
            f"""
            select agent_id, agent_number, display_name as agent_name, {region_label} as region,
                   case
                     when retained + lapsed > 0 and retained::numeric / nullif(retained + lapsed, 0) < 0.85 then 'Persistency coaching'
                     when prior_3m_activity > 0 and last_3m_activity < prior_3m_activity * 0.85 then 'MAPA activity coaching'
                     when target_achievement < 0.80 then 'Target recovery plan'
                     else 'Pipeline conversion coaching'
                   end as intervention,
                   case
                     when retained + lapsed > 0 and retained::numeric / nullif(retained + lapsed, 0) < 0.85 then 'Persistency is below peer benchmark; review renewal scripts and customer fit.'
                     when prior_3m_activity > 0 and last_3m_activity < prior_3m_activity * 0.85 then 'Recent meetings, activities, proposals, and applications are declining.'
                     when target_achievement < 0.80 then 'Target achievement is below expected run rate.'
                     else 'Conversion can improve by pairing with a stronger peer cluster.'
                   end as why,
                   case
                     when agent_cluster = 'Rising stars' then 'Pair with MDRT mentor and allocate higher-quality leads.'
                     when product_focus in ('health', 'life') then 'Run protection-needs clinic and objection-handling practice.'
                     else 'Schedule weekly pipeline inspection and next-best-customer review.'
                   end as suggested_intervention,
                   case
                     when agent_cluster = 'Rising stars' then 'Accelerate premium growth while protecting persistency.'
                     else 'Improve conversion, retained policy count, and target attainment next month.'
                   end as expected_impact,
                   performance_score,
                   attrition_score
            from agent_perf_enriched
            where target_achievement < 0.85
               or performance_score < 0.55
               or attrition_score >= 0.55
               or (prior_3m_activity > 0 and last_3m_activity < prior_3m_activity * 0.90)
               or (retained + lapsed > 0 and retained::numeric / nullif(retained + lapsed, 0) < 0.88)
            order by attrition_score desc, performance_score asc, target_achievement asc nulls last
            limit 12
            """,
            (),
        )
        evidence = [
            {
                "source_table": "agent_mapa_metrics",
                "facts": "MAPA activity, quotes, applications, policies issued, premium, retained and lapsed policy counts.",
                "models_used": ["agent_performance", "agent_attrition"],
            },
            {
                "source_table": "agent_targets",
                "facts": "Target value, actual value, and target achievement for premium, policies, meetings, and persistency.",
                "models_used": ["agent_performance"],
            },
            {
                "source_table": "policies, customers, products",
                "facts": "Customer segment and product line-of-business mix for peer clustering.",
                "models_used": ["next_best_customer", "customer_lifetime_value"],
            },
            {
                "source_table": "v_latest_model_scores",
                "facts": "Latest model scores and bands for performance, attrition, capacity, and coaching prioritization.",
                "models_used": ["agent_performance", "agent_attrition"],
            },
        ]
    return {
        "filters": filters,
        "region_options": region_options,
        "region_option_details": region_option_details,
        "kpis": kpis or {},
        "leaderboard": leaderboard,
        "mapa_productivity": mapa or {},
        "trends": trends,
        "clusters": clusters,
        "customer_product_clusters": customer_product_clusters,
        "rising_stars": rising_stars,
        "mdrt_agents": mdrt_agents,
        "risk_alerts": risk_alerts,
        "coaching_recommendations": coaching,
        "evidence": evidence,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def policy_lapse_dashboard(region: str | None = None, product: str | None = None, segment: str | None = None) -> dict[str, Any]:
    with connect() as conn:
        filters = {"region": region, "product": product, "segment": segment}
        params = (region, region, product, product, segment, segment)
        with conn.cursor() as cur:
            cur.execute(
                """
                create temp table policy_lapse_risk on commit drop as
                with payment_agg as (
                  select policy_id,
                         count(*) filter (where payment_status in ('failed', 'past_due')) as missed_payments,
                         max(payment_date) as last_payment_date
                  from public.payments
                  group by policy_id
                ),
                complaint_agg as (
                  select customer_id, count(*) as complaint_count
                  from public.customer_complaints
                  where coalesce(status, '') not in ('closed', 'resolved')
                  group by customer_id
                ),
                service_agg as (
                  select customer_id, count(*) as service_issue_count
                  from public.customer_service_requests
                  where coalesce(status, '') not in ('closed', 'resolved')
                  group by customer_id
                ),
                event_agg as (
                  select policy_id,
                         count(*) filter (where lower(event_type) like '%%premium%%') as premium_increase_events,
                         count(*) filter (where lower(event_type) like '%%contact%%' or lower(event_type) like '%%agent%%') as contact_events
                  from public.policy_events
                  group by policy_id
                ),
                latest_lapse as (
                  select entity_id as policy_id, score, score_band, model_name, model_version,
                         top_reason_1, top_reason_2, top_reason_3
                  from public.v_latest_model_scores
                  where entity_type = 'policy'
                    and (model_name = 'policy_lapse' or score_name ilike '%%lapse%%')
                ),
                propensity as (
                  select entity_id as customer_id, score as propensity_score
                  from public.v_latest_model_scores
                  where entity_type = 'customer'
                    and (model_name = 'propensity_to_buy' or score_name ilike '%%propensity%%')
                ),
                next_actions as (
                  select distinct on (policy_id) policy_id, customer_id, agent_id, action_type,
                         coalesce(business_reason, action_reason) as action_reason,
                         priority_score, confidence_score, due_date, expected_value
                  from public.next_best_actions
                  where policy_id is not null
                  order by policy_id, priority_score desc nulls last, due_date asc nulls last
                )
                select
                  p.policy_id,
                  p.policy_number,
                  p.customer_id,
                  cp.display_name as customer_name,
                  c.customer_segment,
                  p.agent_id,
                  ap.display_name as agent_name,
                  a.territory_code as region,
                  coalesce(agency.display_name, a.channel, 'Unassigned') as branch,
                  p.product_id,
                  prod.product_name,
                  prod.line_of_business,
                  prod.product_family,
                  p.policy_status,
                  p.annual_premium,
                  p.expiration_date,
                  coalesce(pay.missed_payments, 0) as missed_payments,
                  coalesce(comp.complaint_count, 0) as complaint_count,
                  coalesce(svc.service_issue_count, 0) as service_issue_count,
                  coalesce(evt.premium_increase_events, 0) as premium_increase_events,
                  coalesce(evt.contact_events, 0) as contact_events,
                  coalesce(ll.score, 0.05) as lapse_score,
                  coalesce(ll.score_band, 'low') as score_band,
                  coalesce(propensity.propensity_score, 0.45) as propensity_score,
                  ll.model_name,
                  ll.model_version,
                  ll.top_reason_1,
                  ll.top_reason_2,
                  ll.top_reason_3,
                  nba.action_type as recommended_action_type,
                  nba.action_reason as recommended_action_reason,
                  nba.priority_score,
                  nba.confidence_score,
                  nba.due_date,
                  nba.expected_value,
                  case
                    when coalesce(pay.missed_payments, 0) >= 2 then 'Missed Payments'
                    when coalesce(evt.premium_increase_events, 0) > 0 then 'Premium Increase'
                    when coalesce(comp.complaint_count, 0) > 0 then 'Complaint History'
                    when coalesce(svc.service_issue_count, 0) > 0 then 'Poor Service Experience'
                    when p.expiration_date <= current_date + interval '60 days' then 'Renewal Window'
                    when coalesce(propensity.propensity_score, 0) < 0.25 then 'Low Engagement'
                    else coalesce(nullif(ll.top_reason_1, ''), 'Low Engagement')
                  end as primary_lapse_reason,
                  case
                    when lower(prod.line_of_business) like '%%life%%' then 'Health Rider'
                    when lower(prod.line_of_business) like '%%health%%' then 'Family Protection Bundle'
                    when lower(prod.line_of_business) like '%%motor%%' then 'Travel Insurance'
                    when lower(coalesce(c.customer_segment, '')) like '%%family%%' then 'Child Education Plan'
                    when lower(prod.line_of_business) like '%%wealth%%' then 'Retirement Income Plan'
                    else 'Protection Review'
                  end as cross_sell_product
                from public.policies p
                join public.customers c on c.customer_id = p.customer_id
                join public.parties cp on cp.party_id = c.party_id
                left join public.agents a on a.agent_id = p.agent_id
                left join public.parties ap on ap.party_id = a.party_id
                left join public.parties agency on agency.party_id = a.agency_party_id
                join public.products prod on prod.product_id = p.product_id
                left join payment_agg pay on pay.policy_id = p.policy_id
                left join complaint_agg comp on comp.customer_id = p.customer_id
                left join service_agg svc on svc.customer_id = p.customer_id
                left join event_agg evt on evt.policy_id = p.policy_id
                left join latest_lapse ll on ll.policy_id = p.policy_id
                left join propensity on propensity.customer_id = p.customer_id
                left join next_actions nba on nba.policy_id = p.policy_id
                where p.policy_status in ('active', 'issued', 'renewed')
                  and (%s::text is null or a.territory_code = %s::text)
                  and (%s::text is null or prod.product_name = %s::text)
                  and (%s::text is null or c.customer_segment = %s::text)
                """,
                params,
            )
            cur.execute("analyze policy_lapse_risk")
        high_risk_clause = "lapse_score >= 0.60 or lower(score_band) in ('high','very_high')"
        kpis = _fetch_one(
            conn,
            f"""
            select
              count(*) filter (where {high_risk_clause}) as policies_at_risk,
              count(distinct customer_id) filter (where {high_risk_clause}) as customers_at_risk,
              sum(annual_premium) filter (where {high_risk_clause}) as premium_revenue_at_risk,
              sum(coalesce(expected_value, annual_premium * 0.18)) filter (where {high_risk_clause}) as revenue_saved_through_interventions,
              avg(lapse_score) filter (where {high_risk_clause}) as average_lapse_probability,
              (select product_name from policy_lapse_risk group by product_name order by avg(lapse_score) desc nulls last limit 1) as top_vulnerable_product,
              (select customer_segment from policy_lapse_risk group by customer_segment order by avg(lapse_score) desc nulls last limit 1) as top_vulnerable_segment
            from policy_lapse_risk
            """,
            (),
        )
        trends = _fetch_one(
            conn,
            f"""
            select
              count(*) filter (where {high_risk_clause} and expiration_date <= current_date + interval '60 days') as current_month_risk,
              count(*) filter (where {high_risk_clause} and expiration_date > current_date + interval '60 days' and expiration_date <= current_date + interval '120 days') as previous_month_proxy,
              sum(annual_premium) filter (where {high_risk_clause} and expiration_date <= current_date + interval '60 days') as current_premium_risk,
              sum(annual_premium) filter (where {high_risk_clause} and expiration_date > current_date + interval '60 days' and expiration_date <= current_date + interval '120 days') as previous_premium_proxy
            from policy_lapse_risk
            """,
            (),
        )
        hotspot_query = f"""
            select {{dimension}} as dimension,
                   count(*) filter (where {high_risk_clause}) as at_risk_policies,
                   sum(annual_premium) filter (where {high_risk_clause}) as premium_at_risk,
                   avg(lapse_score) filter (where {high_risk_clause}) as average_lapse_score
            from policy_lapse_risk
            group by {{dimension}}
            having count(*) filter (where {high_risk_clause}) > 0
            order by premium_at_risk desc nulls last
            limit 10
        """
        hotspots = {
            "region": _fetch_all(conn, hotspot_query.replace("{dimension}", "coalesce(region, 'Unassigned')"), ()),
            "branch": _fetch_all(conn, hotspot_query.replace("{dimension}", "coalesce(branch, 'Unassigned')"), ()),
            "product": _fetch_all(conn, hotspot_query.replace("{dimension}", "product_name"), ()),
            "agent": _fetch_all(conn, hotspot_query.replace("{dimension}", "coalesce(agent_name, 'Unassigned')"), ()),
            "customer_segment": _fetch_all(conn, hotspot_query.replace("{dimension}", "coalesce(customer_segment, 'Unsegmented')"), ()),
        }
        top_products = _fetch_all(
            conn,
            f"""
            select product_name as product,
                   count(*) as active_policies,
                   count(*) filter (where {high_risk_clause}) as high_risk_policies,
                   sum(annual_premium) as annual_premium,
                   avg(lapse_score) as lapse_probability,
                   sum(missed_payments) as missed_payments,
                   case
                     when avg(lapse_score) > (select avg(lapse_score) from policy_lapse_risk) then
                       product_name || ' is above portfolio average due to ' ||
                       lower((array_agg(primary_lapse_reason order by missed_payments desc, lapse_score desc))[1]) || '.'
                     else product_name || ' is within portfolio lapse tolerance; monitor renewal and payment behavior.'
                   end as recommendation
            from policy_lapse_risk
            group by product_name
            order by high_risk_policies desc, lapse_probability desc
            limit 10
            """,
            (),
        )
        top_customers = _fetch_all(
            conn,
            f"""
            select customer_id, customer_name as customer, customer_segment, agent_name as agent,
                   policy_id, policy_number, product_name as product, annual_premium as premium,
                   lapse_score, primary_lapse_reason as reason, cross_sell_product as cross_sell_opportunity,
                   coalesce(recommended_action_type, 'Retention Call') as recommended_action,
                   coalesce(confidence_score, greatest(lapse_score, propensity_score)) as confidence_score
            from policy_lapse_risk
            where {high_risk_clause}
            order by lapse_score desc, annual_premium desc
            limit 20
            """,
            (),
        )
        agents = _fetch_all(
            conn,
            f"""
            select coalesce(agent_name, 'Unassigned') as agent,
                   count(distinct customer_id) filter (where {high_risk_clause}) as customers_at_risk,
                   sum(annual_premium) filter (where {high_risk_clause}) as premium_at_risk,
                   1 - avg(lapse_score) filter (where {high_risk_clause}) as retention_success_rate,
                   count(*) filter (where contact_events > 0)::numeric / nullif(count(*), 0) as mapa_score,
                   case
                     when count(*) filter (where contact_events = 0 and ({high_risk_clause})) > 0 then 'Increase agent contact cadence'
                     when avg(lapse_score) filter (where {high_risk_clause}) > 0.75 then 'Manager escalation and retention coaching'
                     else 'Monitor renewal playbook execution'
                   end as recommended_coaching_action
            from policy_lapse_risk
            group by coalesce(agent_name, 'Unassigned')
            having count(distinct customer_id) filter (where {high_risk_clause}) > 0
            order by premium_at_risk desc nulls last
            limit 12
            """,
            (),
        )
        root_causes = _fetch_all(
            conn,
            f"""
            select primary_lapse_reason as driver,
                   count(*) filter (where {high_risk_clause}) as count,
                   sum(annual_premium) filter (where {high_risk_clause}) as premium_exposure,
                   count(*) filter (where {high_risk_clause})::numeric / nullif((select count(*) from policy_lapse_risk where {high_risk_clause}), 0) as contribution
            from policy_lapse_risk
            group by primary_lapse_reason
            order by premium_exposure desc nulls last
            limit 10
            """,
            (),
        )
        cross_sell = _fetch_all(
            conn,
            f"""
            select customer_id, customer_name as customer, product_name as current_product,
                   cross_sell_product as recommended_product,
                   greatest(propensity_score, 0.35) as expected_conversion_probability,
                   annual_premium * greatest(propensity_score, 0.35) * 0.32 as expected_premium,
                   'At-risk customer with ' || lower(primary_lapse_reason) || ' signal and product-fit opportunity.' as reason
            from policy_lapse_risk
            where {high_risk_clause}
            order by expected_premium desc
            limit 12
            """,
            (),
        )
        action_center = _fetch_all(
            conn,
            f"""
            select customer_name as customer, agent_name as agent, policy_number as policy,
                   coalesce(recommended_action_type, case
                     when missed_payments > 0 then 'Offer Premium Holiday'
                     when premium_increase_events > 0 then 'Offer Bundle Discount'
                     when complaint_count > 0 then 'Escalate To Manager'
                     else 'Call Customer'
                   end) as action,
                   coalesce(expected_value, annual_premium * lapse_score * 0.55) as expected_impact,
                   coalesce(confidence_score, lapse_score) as confidence,
                   coalesce(due_date, least(expiration_date, current_date + interval '14 days')::date) as due_date
            from policy_lapse_risk
            where {high_risk_clause}
            order by expected_impact desc nulls last
            limit 15
            """,
            (),
        )
        explanation = _fetch_one(
            conn,
            f"""
            select customer_name as customer, policy_number, product_name, lapse_score,
                   primary_lapse_reason,
                   array_remove(array[top_reason_1, top_reason_2, top_reason_3], null) as supporting_facts,
                   jsonb_build_array(
                     jsonb_build_object('model', coalesce(model_name, 'policy_lapse'), 'score', lapse_score, 'band', score_band),
                     jsonb_build_object('model', 'propensity_to_buy', 'score', propensity_score)
                   ) as model_scores,
                   array['High lapse score', 'Missed payment and complaint signals increase priority', 'Renewal window increases urgency'] as business_rules,
                   array['policies','payments','model_scores','customers','agents','products','next_best_actions'] as source_tables,
                   array['policy_id','annual_premium','payment_status','score_value','customer_segment','agent_id','product_id'] as source_columns,
                   array['Policy Lapse Risk Context','Next Best Action Context','Customer Segmentation Context'] as context_documents_used,
                   coalesce(confidence_score, lapse_score) as confidence_score
            from policy_lapse_risk
            where {high_risk_clause}
            order by lapse_score desc, annual_premium desc
            limit 1
            """,
            (),
        )
        premium_at_risk = float(kpis.get("premium_revenue_at_risk") or 0)
        policies_at_risk = int(kpis.get("policies_at_risk") or 0)
        scenario_simulator = [
            {"scenario": "10% premium reduction", "policies_saved": round(policies_at_risk * 0.18), "premium_saved": round(premium_at_risk * 0.16, 2), "expected_conversion": 0.22},
            {"scenario": "Additional agent outreach", "policies_saved": round(policies_at_risk * 0.24), "premium_saved": round(premium_at_risk * 0.21, 2), "expected_conversion": 0.28},
            {"scenario": "Retention campaign", "policies_saved": round(policies_at_risk * 0.15), "premium_saved": round(premium_at_risk * 0.12, 2), "expected_conversion": 0.19},
            {"scenario": "Policy bundling", "policies_saved": round(policies_at_risk * 0.20), "premium_saved": round(premium_at_risk * 0.18, 2), "expected_conversion": 0.25},
        ]
    return {
        "filters": filters,
        "kpis": kpis,
        "trends": trends,
        "hotspots": hotspots,
        "top_products": top_products,
        "top_customers": top_customers,
        "agents": agents,
        "root_causes": root_causes,
        "cross_sell": cross_sell,
        "action_center": action_center,
        "explanation": explanation,
        "scenario_simulator": scenario_simulator,
        "schema_additions": [
            "retention_interventions",
            "retention_offers",
            "retention_outcomes",
            "product_substitution_rules",
            "competitor_product_mapping",
            "lapse_reason_classification",
            "customer_life_events",
            "retention_campaigns",
            "policy_health_score",
            "customer_health_score",
        ],
        "ml_enhancements": [
            "lapse_risk",
            "retention_success_probability",
            "next_best_product",
            "customer_lifetime_value",
            "agent_retention_effectiveness",
            "premium_recovery_prediction",
        ],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def recommendations_for_entity(entity_id: UUID) -> dict[str, Any]:
    with connect() as conn:
        columns = _table_columns(conn, "next_best_actions")
        recommended_action_expr = (
            "recommended_action as recommended_action"
            if "recommended_action" in columns
            else "action_type as recommended_action"
            if "action_type" in columns
            else "null as recommended_action"
        )
        select_columns = [
            _select_expr(columns, "next_best_action_id"),
            _select_expr(columns, "customer_id"),
            _select_expr(columns, "agent_id"),
            _select_expr(columns, "policy_id"),
            _select_expr(columns, "lead_id"),
            _select_expr(columns, "campaign_id"),
            _select_expr(columns, "product_id", "recommended_product_id"),
            _select_expr(columns, "action_type"),
            recommended_action_expr,
            _select_expr(columns, "priority_score"),
            _select_expr(columns, "business_reason"),
            _select_expr(columns, "action_reason"),
            _select_expr(columns, "suggested_message"),
            _select_expr(columns, "expiry_date"),
            _select_expr(columns, "due_date"),
            _select_expr(columns, "action_status"),
            _select_expr(columns, "confidence_score"),
            _select_expr(columns, "decision_rule"),
            _select_expr(columns, "suppression_reason"),
            _select_expr(columns, "created_at"),
        ]
        entity_filters = [
            column_name
            for column_name in ["customer_id", "agent_id", "policy_id", "lead_id", "campaign_id", "claim_id"]
            if column_name in columns
        ]
        if not entity_filters:
            return {"entity_id": entity_id, "recommendations": []}
        where_clause = " or ".join(f"{column_name} = %s" for column_name in entity_filters)
        date_order_terms = [column_name for column_name in ["expiry_date", "due_date"] if column_name in columns]
        date_order = (
            f"coalesce({', '.join(date_order_terms)}) asc nulls last"
            if len(date_order_terms) > 1
            else f"{date_order_terms[0]} asc nulls last"
            if date_order_terms
            else "created_at desc nulls last"
        )
        rows = _fetch_all(
            conn,
            f"""
            select {", ".join(select_columns)}
            from public.next_best_actions
            where {where_clause}
            order by coalesce(priority_score, 0) desc, {date_order}
            limit 50
            """,
            tuple([str(entity_id)] * len(entity_filters)),
        )
    return {"entity_id": entity_id, "recommendations": rows}


def envelope(entity_type: str, entity_id: UUID, summary: dict[str, Any], sections: dict[str, Any]) -> dict[str, Any]:
    return {
        "entity_type": entity_type,
        "entity_id": entity_id,
        "summary": summary,
        "sections": sections,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
