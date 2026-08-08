-- =====================================================================
-- Insurance PoC V2.0 — Semantic Views (DuckDB)
-- Read-only analytic views that power the V2 business-workspace pages.
-- Built against the seeded DuckDB schema (54 tables). All CREATE OR REPLACE.
--
-- Conventions discovered in the data:
--   * Lapse score:  model_scores (entity_type='policy', score_name='lapse_risk',
--                   probability=lapse prob, score_band in low/medium/high/very_high)
--   * Propensity:   model_scores (entity_type='customer', score_name='propensity_to_buy')
--   * Sum assured:  policy_coverage.limit_amount (non-rider coverages)
--   * Region:       agents.territory_code  ('HK-*' -> Hong Kong, else Singapore)
--   * Date anchor:  max(policies.issue_date) is treated as "today" for 90d windows.
--   * churn_risk_band / clv_band are NOT modelled in source data — they are
--     DERIVED PROXIES (documented per view) so the UI has consistent bands.
-- =====================================================================

-- ---------------------------------------------------------------------
-- Helper views (not in the public 10, reused below)
-- ---------------------------------------------------------------------

-- Latest lapse score per policy.
drop view if exists v_policy_lapse_score cascade;
create or replace view v_policy_lapse_score as
select
  ms.entity_id            as policy_id,
  coalesce(ms.probability, ms.score_value, 0) as lapse_probability,
  lower(ms.score_band)    as lapse_band
from model_scores ms
where ms.entity_type = 'policy' and ms.score_name = 'lapse_risk'
qualify row_number() over (partition by ms.entity_id order by ms.score_ts desc nulls last) = 1;

-- Latest propensity-to-buy score per customer.
drop view if exists v_customer_propensity cascade;
create or replace view v_customer_propensity as
select
  ms.entity_id            as customer_id,
  coalesce(ms.probability, ms.score_value, 0) as propensity_to_buy,
  lower(ms.score_band)    as propensity_band
from model_scores ms
where ms.entity_type = 'customer' and ms.score_name = 'propensity_to_buy'
qualify row_number() over (partition by ms.entity_id order by ms.score_ts desc nulls last) = 1;

-- Base sum-assured per policy (non-rider coverage limits).
drop view if exists v_policy_sum_assured cascade;
create or replace view v_policy_sum_assured as
select policy_id, sum(limit_amount) filter (where not coalesce(is_rider, false)) as sum_assured
from policy_coverage
group by policy_id;

-- Policy-level lapse risk with region/product/segment dims (feeds summary + hotspots).
drop view if exists v_lapse_policy_risk cascade;
create or replace view v_lapse_policy_risk as
select
  p.policy_id,
  p.policy_number,
  p.customer_id,
  p.agent_id,
  p.annual_premium,
  pr.product_name,
  pr.line_of_business,
  c.customer_segment,
  case when a.territory_code like 'HK%' then 'Hong Kong' else 'Singapore' end as region,
  a.territory_code as branch,
  coalesce(ls.lapse_probability, 0)       as lapse_probability,
  coalesce(ls.lapse_band, 'low')          as lapse_band,
  (coalesce(ls.lapse_band,'low') in ('high','very_high')) as at_risk
from policies p
left join products pr on pr.product_id = p.product_id
left join customers c on c.customer_id = p.customer_id
left join agents a on a.agent_id = p.agent_id
left join v_policy_lapse_score ls on ls.policy_id = p.policy_id
where p.policy_status in ('active','renewed','issued');

-- =====================================================================
-- 1. v_home_kpis
--    Business: executive command-center headline KPIs for the Home page.
--    Formula:
--      new_business_premium_90d = SUM(annual_premium) for policies issued in the
--        90 days up to the latest issue_date; delta vs the prior 90-day window.
--      persistency_13m = active+renewed / (active+renewed+lapsed) of in-force book.
--      high_lapse_exposure_count = # policies with lapse_band in (high, very_high).
--      campaign_conversion_rate = conversions / targeted across all campaigns.
--      portfolio_momentum_monthly = last 12 months of NBP, indexed to 100 at month 1.
--      sales_mix_by_product_line / distribution_channel_mix = premium share lists.
--    Sources: policies, products, model_scores, campaign_targets, campaign_responses.
-- =====================================================================
drop view if exists v_home_kpis cascade;
create or replace view v_home_kpis as
with anchor as (select max(issue_date) as d from policies),
nbp as (
  select
    sum(annual_premium) filter (where issue_date > (select d from anchor) - interval 90 day)                                         as nbp_90d,
    sum(annual_premium) filter (where issue_date <= (select d from anchor) - interval 90 day
                                  and issue_date > (select d from anchor) - interval 180 day)                                        as nbp_prior_90d
  from policies
),
persistency as (
  select
    100.0 * count(*) filter (where policy_status in ('active','renewed'))
      / nullif(count(*) filter (where policy_status in ('active','renewed','lapsed')), 0) as persistency_13m
  from policies
),
lapse as (
  select count(*) as high_lapse_exposure_count
  from v_policy_lapse_score where lapse_band in ('high','very_high')
),
camp as (
  select 100.0 * (select count(*) from campaign_responses where conversion_flag)
    / nullif((select count(*) from campaign_targets), 0) as campaign_conversion_rate
),
momentum as (
  -- month explicitly CAST AS DATE and premium/index_value AS DOUBLE so the
  -- emitted STRUCT signature is stable (prevents the cached-view BinderException).
  select list(struct_pack(month := m, premium := cast(prem as double), index_value := cast(idx as double)) order by m) as portfolio_momentum_monthly
  from (
    select m, prem, round(100.0 * prem / nullif(first_value(prem) over (order by m), 0), 1) as idx
    from (
      select cast(date_trunc('month', issue_date) as date) as m, cast(sum(annual_premium) as double) as prem
      from policies
      where issue_date > (select d from anchor) - interval 12 month
      group by 1
    )
  )
),
sales_mix as (
  select list(struct_pack(line_of_business := lob, premium := cast(prem as double), pct := cast(pct as double)) order by prem desc) as sales_mix_by_product_line
  from (
    select lob, prem, round(100.0 * prem / nullif(sum(prem) over (), 0), 1) as pct
    from (
      select pr.line_of_business as lob, cast(sum(p.annual_premium) as double) as prem
      from policies p join products pr on pr.product_id = p.product_id
      where p.policy_status in ('active','renewed','issued')
      group by 1
    )
  )
),
channel_mix as (
  select list(struct_pack(channel := ch, premium := cast(prem as double), pct := cast(pct as double)) order by prem desc) as distribution_channel_mix
  from (
    select ch, prem, round(100.0 * prem / nullif(sum(prem) over (), 0), 1) as pct
    from (
      select coalesce(source_channel,'unknown') as ch, cast(sum(annual_premium) as double) as prem
      from policies
      where policy_status in ('active','renewed','issued')
      group by 1
    )
  )
)
select
  cast(round(coalesce(nbp.nbp_90d,0), 2) as double)                                          as new_business_premium_90d,
  cast(round(100.0 * (nbp.nbp_90d - nbp.nbp_prior_90d) / nullif(nbp.nbp_prior_90d,0), 1) as double) as new_business_premium_delta_pct,
  cast(round(persistency.persistency_13m, 1) as double)                                       as persistency_13m,
  cast(lapse.high_lapse_exposure_count as bigint)                                             as high_lapse_exposure_count,
  cast(round(camp.campaign_conversion_rate, 1) as double)                                     as campaign_conversion_rate,
  momentum.portfolio_momentum_monthly,
  sales_mix.sales_mix_by_product_line,
  channel_mix.distribution_channel_mix
from nbp, persistency, lapse, camp, momentum, sales_mix, channel_mix;

-- =====================================================================
-- 2. v_customer_360
--    Business: single-row 360 profile per customer for Know-Your-Customer.
--    Formula: profile + in-force policy rollups + joined model scores.
--      lapse_risk_band = worst lapse_band among the customer's in-force policies.
--      churn_risk_band = DERIVED proxy from engagement_score + lapse exposure.
--      clv_band        = DERIVED proxy from total in-force annual premium tiers.
--      income_band     = DERIVED proxy from annual premium tiers (no income source).
--      next_best_product = product of the top offer_product next_best_action.
--    Sources: customers, parties, addresses, policies, products, policy_coverage,
--             v_customer_propensity, v_policy_lapse_score, next_best_actions.
-- =====================================================================
drop view if exists v_customer_360 cascade;
create or replace view v_customer_360 as
with cust_pol as (
  select
    p.customer_id,
    count(*) filter (where p.policy_status in ('active','renewed','issued'))      as active_policy_count,
    sum(p.annual_premium) filter (where p.policy_status in ('active','renewed','issued')) as annual_premium,
    min(p.expiration_date) filter (where p.policy_status in ('active','renewed') and p.expiration_date >= current_date) as next_renewal_date,
    max(ls.lapse_band)                                                            as worst_lapse_band
  from policies p
  left join v_policy_lapse_score ls on ls.policy_id = p.policy_id
  group by p.customer_id
),
cust_sa as (
  select p.customer_id, sum(sa.sum_assured) as total_sum_assured
  from policies p join v_policy_sum_assured sa on sa.policy_id = p.policy_id
  where p.policy_status in ('active','renewed','issued')
  group by p.customer_id
),
primary_agent as (
  select customer_id, agent_id from (
    select p.customer_id, p.agent_id,
           row_number() over (partition by p.customer_id order by p.issue_date desc nulls last) rn
    from policies p where p.agent_id is not null
  ) where rn = 1
),
nbp_prod as (
  select customer_id, product_id from (
    select nba.customer_id, nba.product_id,
           row_number() over (partition by nba.customer_id order by nba.priority_score desc nulls last) rn
    from next_best_actions nba where nba.action_type = 'offer_product' and nba.product_id is not null
  ) where rn = 1
),
curr_addr as (
  -- one address per party (a party can have multiple current addresses)
  select party_id, city from (
    select party_id, city,
           row_number() over (partition by party_id order by coalesce(is_current,false) desc, effective_date desc nulls last) rn
    from addresses
  ) where rn = 1
)
select
  c.customer_id,
  c.customer_number,
  coalesce(pa.display_name, c.customer_number)            as display_name,
  c.customer_segment,
  c.lifecycle_stage,
  c.risk_tier,
  round(c.engagement_score, 3)                            as engagement_score,
  c.acquisition_date                                     as customer_since,
  date_diff('year', pa.date_of_birth, current_date)      as age,
  pa.preferred_contact_method                            as preferred_channel,
  addr.city,
  case when ag.territory_code like 'HK%' then 'Hong Kong' else 'Singapore' end as region,
  prim.agent_id                                          as advisor_agent_id,
  coalesce(apar.display_name, prim.agent_id)             as advisor_name,
  coalesce(cp.active_policy_count, 0)                    as active_policy_count,
  round(coalesce(cp.annual_premium, 0), 2)              as annual_premium,
  round(coalesce(cs.total_sum_assured, 0), 2)           as total_sum_assured,
  cp.next_renewal_date,
  round(coalesce(prop.propensity_to_buy, 0), 3)         as propensity_to_buy,
  coalesce(prop.propensity_band, 'low')                 as propensity_band,
  coalesce(cp.worst_lapse_band, 'low')                  as lapse_risk_band,
  -- DERIVED churn proxy
  case
    when cp.worst_lapse_band = 'very_high' or c.engagement_score < 0.25 then 'very_high'
    when cp.worst_lapse_band = 'high' or c.engagement_score < 0.45 then 'high'
    when c.engagement_score < 0.65 then 'medium' else 'low'
  end                                                    as churn_risk_band,
  -- DERIVED CLV proxy from annual premium tiers
  case
    when coalesce(cp.annual_premium,0) >= 12000 then 'very_high'
    when coalesce(cp.annual_premium,0) >= 6000  then 'high'
    when coalesce(cp.annual_premium,0) >= 2000  then 'medium' else 'low'
  end                                                    as clv_band,
  -- DERIVED income band proxy
  case
    when coalesce(cp.annual_premium,0) >= 12000 then 'high_net_worth'
    when coalesce(cp.annual_premium,0) >= 6000  then 'affluent'
    when coalesce(cp.annual_premium,0) >= 2000  then 'mass_affluent' else 'mass'
  end                                                    as income_band,
  npr.product_name                                       as next_best_product
from customers c
left join parties pa on pa.party_id = c.party_id
left join cust_pol cp on cp.customer_id = c.customer_id
left join cust_sa cs on cs.customer_id = c.customer_id
left join v_customer_propensity prop on prop.customer_id = c.customer_id
left join primary_agent prim on prim.customer_id = c.customer_id
left join agents ag on ag.agent_id = prim.agent_id
left join parties apar on apar.party_id = ag.party_id
left join curr_addr addr on addr.party_id = c.party_id
left join nbp_prod np on np.customer_id = c.customer_id
left join products npr on npr.product_id = np.product_id;

-- =====================================================================
-- 3. v_customer_policies
--    Business: one row per policy for a customer (portfolio table).
--    Formula: policies joined to products + coverage sum-assured + servicing agent.
--    Sources: policies, products, v_policy_sum_assured, v_policy_lapse_score, agents/parties.
-- =====================================================================
drop view if exists v_customer_policies cascade;
create or replace view v_customer_policies as
select
  p.customer_id,
  p.policy_id,
  p.policy_number,
  pr.product_name,
  pr.line_of_business,
  p.policy_status,
  round(p.annual_premium, 2)            as annual_premium,
  round(coalesce(sa.sum_assured,0), 2)  as sum_assured,
  p.effective_date,
  p.expiration_date,
  p.issue_date,
  coalesce(apar.display_name, p.agent_id) as servicing_agent,
  coalesce(ls.lapse_band, 'low')        as lapse_band
from policies p
left join products pr on pr.product_id = p.product_id
left join v_policy_sum_assured sa on sa.policy_id = p.policy_id
left join agents ag on ag.agent_id = p.agent_id
left join parties apar on apar.party_id = ag.party_id
left join v_policy_lapse_score ls on ls.policy_id = p.policy_id;

-- =====================================================================
-- 4. v_customer_recommended_action
--    Business: the single top next-best-action per customer (KYC action card).
--    Formula: highest priority_score open action; confidence proxied by priority;
--      preferred_channel from party contact preference; suggested_message templated.
--    Sources: next_best_actions, products, customers, parties.
-- =====================================================================
drop view if exists v_customer_recommended_action cascade;
create or replace view v_customer_recommended_action as
select
  customer_id,
  action_type,
  round(priority_score, 3)                              as priority,
  round(priority_score, 3)                              as confidence,
  product_name                                          as recommended_product,
  preferred_channel,
  action_reason                                         as reason,
  suggested_message,
  due_date,
  action_status,
  round(expected_value, 2)                              as expected_value
from (
  select
    nba.*,
    pr.product_name,
    pp.preferred_contact_method as preferred_channel,
    case nba.action_type
      when 'offer_product'      then 'Hi ' || coalesce(pp.first_name,'there') || ', based on your profile a ' || coalesce(pr.product_name,'new plan') || ' may strengthen your cover. Can we set up a short review?'
      when 'retention_outreach' then 'Hi ' || coalesce(pp.first_name,'there') || ', we''d love to review your policy and make sure it still fits your needs.'
      when 'renewal_follow_up'  then 'Hi ' || coalesce(pp.first_name,'there') || ', your renewal is coming up — happy to walk you through the options.'
      when 'call_customer'      then 'Hi ' || coalesce(pp.first_name,'there') || ', I''d like to check in on your coverage and answer any questions.'
      when 'service_recovery'   then 'Hi ' || coalesce(pp.first_name,'there') || ', thank you for your patience — let''s resolve your recent request together.'
      else 'Hi ' || coalesce(pp.first_name,'there') || ', we have a personalized recommendation ready for you.'
    end as suggested_message,
    row_number() over (partition by nba.customer_id order by nba.priority_score desc nulls last, nba.action_rank asc) as rn
  from next_best_actions nba
  left join products pr on pr.product_id = nba.product_id
  left join customers c on c.customer_id = nba.customer_id
  left join parties pp on pp.party_id = c.party_id
  where nba.customer_id is not null
    and nba.action_status in ('open','recommended','assigned','accepted')
)
where rn = 1;

-- =====================================================================
-- 5. v_agent_360
--    Business: single-row 360 profile per agent for Know-Your-Agent.
--    Formula: profile + latest-month performance from agent_performance,
--      target attainment from agent_targets, commission from agent_commissions.
--      region from territory_code; tenure from appointment_date.
--    Sources: agents, parties, agent_performance, agent_targets, agent_commissions.
-- =====================================================================
drop view if exists v_agent_360 cascade;
create or replace view v_agent_360 as
with perf as (
  select agent_id, metric_month, new_business_premium, policies_bound_count, conversion_rate,
         retained_policy_count, lapsed_policy_count,
         lag(new_business_premium) over (partition by agent_id order by metric_month) as prev_premium,
         row_number() over (partition by agent_id order by metric_month desc) as rn
  from agent_performance
),
perf_latest as (select * from perf where rn = 1),
persist as (
  select agent_id,
         100.0 * sum(retained_policy_count) / nullif(sum(retained_policy_count)+sum(lapsed_policy_count),0) as persistency_rate
  from agent_performance group by agent_id
),
target_latest as (
  select agent_id, attainment_pct from (
    select agent_id, attainment_pct,
           row_number() over (partition by agent_id order by target_period_end desc) rn
    from agent_targets
  ) where rn = 1
),
commission_latest as (
  select agent_id, sum(commission_amount) as commission_rolling_month
  from agent_commissions
  where commission_period = (select max(commission_period) from agent_commissions ac2 where ac2.agent_id = agent_commissions.agent_id)
  group by agent_id
)
select
  a.agent_id,
  a.agent_number,
  coalesce(pa.display_name, a.agent_number)              as display_name,
  a.channel,
  case when a.territory_code like 'HK%' then 'Hong Kong' else 'Singapore' end as region,
  a.territory_code                                       as branch,
  a.status,
  a.appointment_date,
  round(date_diff('day', a.appointment_date, current_date) / 365.25, 1) as tenure_years,
  round(coalesce(pl.new_business_premium,0), 2)          as monthly_premium,
  round(100.0 * (pl.new_business_premium - pl.prev_premium) / nullif(pl.prev_premium,0), 1) as monthly_premium_delta_pct,
  coalesce(pl.policies_bound_count, 0)                   as policies_sold_mtd,
  round(coalesce(pl.conversion_rate,0), 3)              as conversion_rate,
  round(coalesce(ps.persistency_rate,0), 1)            as persistency_rate,
  round(coalesce(tl.attainment_pct,0), 1)              as target_achievement_pct,
  round(coalesce(cl.commission_rolling_month,0), 2)    as commission_rolling_month
from agents a
left join parties pa on pa.party_id = a.party_id
left join perf_latest pl on pl.agent_id = a.agent_id
left join persist ps on ps.agent_id = a.agent_id
left join target_latest tl on tl.agent_id = a.agent_id
left join commission_latest cl on cl.agent_id = a.agent_id;

-- =====================================================================
-- 6. v_agent_mapa
--    Business: monthly MAPA funnel per agent (Meetings, Activities, Proposals, Applications).
--    Formula: meetings = count(agent_meetings) by month; activities = contacts_count;
--      proposals = quotes_count; applications = applications_count (from agent_performance).
--    Sources: agent_performance, agent_meetings.
-- =====================================================================
drop view if exists v_agent_mapa cascade;
create or replace view v_agent_mapa as
with meetings as (
  select agent_id, cast(date_trunc('month', meeting_ts) as date) as metric_month, count(*) as meetings
  from agent_meetings group by 1,2
)
select
  ap.agent_id,
  cast(ap.metric_month as date)  as metric_month,
  coalesce(m.meetings, 0)        as meetings,
  coalesce(ap.contacts_count, 0) as activities,
  coalesce(ap.quotes_count, 0)   as proposals,
  coalesce(ap.applications_count, 0) as applications,
  coalesce(ap.policies_bound_count, 0) as policies_bound
from agent_performance ap
left join meetings m on m.agent_id = ap.agent_id and m.metric_month = ap.metric_month;

-- =====================================================================
-- 7. v_agent_leaderboard
--    Business: ranked agents by trailing-12m new-business premium with cluster label.
--    Formula: premium = SUM(new_business_premium) last 12 months; growth_pct = last
--      6m vs prior 6m; cluster: MDRT (premium >= p90), Elite (>= p75),
--      Rising Stars (growth_pct >= 20 and premium >= median), else Core.
--    Sources: agent_performance, agents, parties.
-- =====================================================================
drop view if exists v_agent_leaderboard cascade;
create or replace view v_agent_leaderboard as
with bounds as (select max(metric_month) as mx from agent_performance),
agg as (
  select
    ap.agent_id,
    sum(ap.new_business_premium) filter (where ap.metric_month > (select mx from bounds) - interval 12 month) as premium_12m,
    sum(ap.policies_bound_count) filter (where ap.metric_month > (select mx from bounds) - interval 12 month) as policies_12m,
    avg(ap.conversion_rate)      filter (where ap.metric_month > (select mx from bounds) - interval 12 month) as conversion_rate,
    100.0 * sum(ap.retained_policy_count) / nullif(sum(ap.retained_policy_count)+sum(ap.lapsed_policy_count),0) as persistency_rate,
    sum(ap.new_business_premium) filter (where ap.metric_month > (select mx from bounds) - interval 6 month)  as prem_recent6,
    sum(ap.new_business_premium) filter (where ap.metric_month <= (select mx from bounds) - interval 6 month
                                          and ap.metric_month > (select mx from bounds) - interval 12 month)  as prem_prior6
  from agent_performance ap
  group by ap.agent_id
),
ranked as (
  select
    agg.*,
    coalesce(pa.display_name, a.agent_number) as display_name,
    a.agent_number,
    case when a.territory_code like 'HK%' then 'Hong Kong' else 'Singapore' end as region,
    a.channel,
    100.0 * (prem_recent6 - prem_prior6) / nullif(prem_prior6, 0) as growth_pct,
    percent_rank() over (order by premium_12m) as prem_pct_rank,
    median(premium_12m) over () as prem_median,
    rank() over (order by premium_12m desc) as premium_rank
  from agg
  join agents a on a.agent_id = agg.agent_id
  left join parties pa on pa.party_id = a.party_id
)
select
  agent_id, agent_number, display_name, region, channel,
  round(coalesce(premium_12m,0), 2)   as premium,
  coalesce(policies_12m, 0)           as policies,
  round(coalesce(conversion_rate,0), 3) as conversion_rate,
  round(coalesce(persistency_rate,0), 1) as persistency_rate,
  round(coalesce(growth_pct,0), 1)    as growth_pct,
  premium_rank,
  case
    when prem_pct_rank >= 0.90 then 'MDRT'
    when prem_pct_rank >= 0.75 then 'Elite'
    when coalesce(growth_pct,0) >= 20 and premium_12m >= prem_median then 'Rising Stars'
    else 'Core'
  end as cluster
from ranked;

-- =====================================================================
-- 8. v_campaign_effectiveness
--    Business: per-campaign funnel + ROI for Campaign Effectiveness page.
--    Formula: targeted = count(campaign_targets); delivered/opened/clicked from
--      campaign_responses.response_type; responded = engaged responses;
--      conversions = conversion_flag; premium_generated = SUM(conversion_premium);
--      roi_multiple = premium_generated / budget_amount; response_rate = responded/targeted.
--    Sources: campaigns, campaign_targets, campaign_responses.
-- =====================================================================
drop view if exists v_campaign_effectiveness cascade;
create or replace view v_campaign_effectiveness as
with tgt as (select campaign_id, count(*) as targeted from campaign_targets group by 1),
resp as (
  -- seeded response_type vocabulary is ('click','call','reply','visit'); every
  -- recorded response implies delivered+engaged, so delivered/responded = all.
  select campaign_id,
    count(*)                                                       as delivered,
    count(*) filter (where response_type in ('click','reply','call')) as opened,
    count(*) filter (where response_type = 'click')                as clicked,
    count(*)                                                       as responded,
    count(*) filter (where conversion_flag)                        as conversions,
    sum(conversion_premium) filter (where conversion_flag)         as premium_generated
  from campaign_responses group by 1
)
select
  c.campaign_id,
  c.campaign_code,
  c.campaign_name,
  c.campaign_type,
  c.channel                                   as medium,
  c.objective,
  c.status,
  c.start_date,
  c.end_date,
  round(coalesce(c.budget_amount,0), 2)       as budget_amount,
  coalesce(t.targeted, 0)                     as targeted,
  coalesce(r.delivered, 0)                    as delivered,
  coalesce(r.opened, 0)                       as opened,
  coalesce(r.clicked, 0)                      as clicked,
  coalesce(r.responded, 0)                    as responded,
  coalesce(r.conversions, 0)                  as conversions,
  round(coalesce(r.premium_generated,0), 2)   as premium_generated,
  round(coalesce(r.premium_generated,0) / nullif(c.budget_amount,0), 2) as roi_multiple,
  round(100.0 * coalesce(r.responded,0) / nullif(t.targeted,0), 1)      as response_rate,
  round(100.0 * coalesce(r.conversions,0) / nullif(t.targeted,0), 1)    as conversion_rate,
  round(100.0 * coalesce(r.opened,0) / nullif(r.delivered,0), 1)        as open_rate,
  round(100.0 * coalesce(r.clicked,0) / nullif(r.opened,0), 1)          as click_rate
from campaigns c
left join tgt t on t.campaign_id = c.campaign_id
left join resp r on r.campaign_id = c.campaign_id;

-- =====================================================================
-- 9. v_lapse_risk_summary
--    Business: single-row portfolio lapse exposure for the Policy Lapse Risk page.
--    Formula (over in-force policies, at_risk = lapse_band in high/very_high):
--      policies_at_risk, customers_at_risk (distinct), premium_at_risk = SUM(premium|at_risk),
--      revenue_saved = SUM(annual_premium) of policies with a reinstated lapse event,
--      avg_lapse_probability, top_risk_product / top_risk_segment by premium_at_risk.
--    Sources: v_lapse_policy_risk, policies, policy_lapse_events.
-- =====================================================================
drop view if exists v_lapse_risk_summary cascade;
create or replace view v_lapse_risk_summary as
with base as (select * from v_lapse_policy_risk),
saved as (
  select sum(p.annual_premium) as revenue_saved
  from policies p
  where p.policy_id in (select policy_id from policy_lapse_events where reinstatement_date is not null)
),
top_prod as (
  select line_of_business from base where at_risk group by line_of_business
  order by sum(annual_premium) desc limit 1
),
top_seg as (
  select customer_segment from base where at_risk group by customer_segment
  order by sum(annual_premium) desc limit 1
)
select
  count(*) filter (where at_risk)                                  as policies_at_risk,
  count(distinct customer_id) filter (where at_risk)               as customers_at_risk,
  round(sum(annual_premium) filter (where at_risk), 2)             as premium_at_risk,
  round(coalesce((select revenue_saved from saved),0), 2)         as revenue_saved,
  round(avg(lapse_probability), 4)                                 as avg_lapse_probability,
  (select line_of_business from top_prod)                          as top_risk_product,
  (select customer_segment from top_seg)                           as top_risk_segment
from base;

-- =====================================================================
-- 10. v_lapse_hotspots
--     Business: highest lapse-exposure cell per dimension (heatmap row).
--     Formula: for each dimension (region, branch, product, agent, customer_segment),
--       group at-risk in-force policies and return the TOP-1 cell by premium_at_risk
--       with policy_count and avg_lapse_score.
--     Sources: v_lapse_policy_risk, agents, parties.
-- =====================================================================
drop view if exists v_lapse_hotspots cascade;
create or replace view v_lapse_hotspots as
with base as (select * from v_lapse_policy_risk where at_risk)
select * from (
  select 'region' as dimension, region as dimension_value,
         count(*) as policy_count, round(sum(annual_premium),2) as premium_at_risk, round(avg(lapse_probability),4) as avg_lapse_score
  from base group by region
  qualify row_number() over (order by sum(annual_premium) desc) = 1
)
union all
select * from (
  select 'branch', branch, count(*), round(sum(annual_premium),2), round(avg(lapse_probability),4)
  from base group by branch
  qualify row_number() over (order by sum(annual_premium) desc) = 1
)
union all
select * from (
  select 'product', line_of_business, count(*), round(sum(annual_premium),2), round(avg(lapse_probability),4)
  from base group by line_of_business
  qualify row_number() over (order by sum(annual_premium) desc) = 1
)
union all
select * from (
  select 'agent', coalesce(pa.display_name, b.agent_id), count(*), round(sum(b.annual_premium),2), round(avg(b.lapse_probability),4)
  from base b left join agents a on a.agent_id=b.agent_id left join parties pa on pa.party_id=a.party_id
  group by coalesce(pa.display_name, b.agent_id)
  qualify row_number() over (order by sum(b.annual_premium) desc) = 1
)
union all
select * from (
  select 'customer_segment', customer_segment, count(*), round(sum(annual_premium),2), round(avg(lapse_probability),4)
  from base group by customer_segment
  qualify row_number() over (order by sum(annual_premium) desc) = 1
);
