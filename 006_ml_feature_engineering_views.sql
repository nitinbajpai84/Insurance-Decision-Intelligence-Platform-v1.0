-- Leakage-safe ML feature views for the insurance analytics platform.
--
-- Convention:
--   features use data strictly before snapshot_date
--   labels use data on/after prediction_window_start and before prediction_window_end
--   training_window_* documents historical feature lookback
--   prediction_window_* documents future outcome horizon

create or replace view public.v_ml_monthly_snapshots as
select
  gs::date as snapshot_date,
  (gs::date - interval '365 days')::date as training_window_start,
  gs::date as training_window_end,
  gs::date as prediction_window_start,
  (gs::date + interval '180 days')::date as prediction_window_end
from generate_series(date '2023-01-01', date '2025-12-01', interval '1 month') gs;

comment on view public.v_ml_monthly_snapshots is
'Monthly ML as-of dates. Feature windows end at snapshot_date and prediction windows start at snapshot_date to prevent leakage.';

create or replace view public.v_propensity_to_buy_features as
select
  c.customer_id as entity_id,
  s.snapshot_date,
  coalesce(c.engagement_score, 0) as engagement_score,
  coalesce(pol.active_policy_count, 0) as active_policy_count,
  coalesce(dig.digital_events_90d, 0) as digital_events_90d,
  coalesce(dig.quote_requests_180d, 0) as quote_requests_180d,
  coalesce(resp.positive_campaign_responses_prior, 0) as positive_campaign_responses_prior,
  coalesce(comp.complaint_count_prior, 0) as complaint_count_prior,
  coalesce(pay.missed_payment_count_prior, 0) as missed_payment_count_prior,
  coalesce(beh.tenure_days, greatest(s.snapshot_date - c.acquisition_date, 0)) as tenure_days,
  case when exists (
    select 1
    from public.policies fp
    where fp.customer_id = c.customer_id
      and fp.effective_date >= s.prediction_window_start
      and fp.effective_date < s.prediction_window_end
  ) then 1 else 0 end as target_label,
  s.training_window_start,
  s.training_window_end,
  s.prediction_window_start,
  s.prediction_window_end,
  c.customer_segment
from public.customers c
cross join public.v_ml_monthly_snapshots s
left join lateral (
  select count(*) as active_policy_count
  from public.policies p
  where p.customer_id = c.customer_id
    and p.effective_date < s.snapshot_date
    and p.policy_status in ('active','issued','renewed')
) pol on true
left join lateral (
  select
    count(*) filter (where de.event_ts >= (s.snapshot_date - interval '90 days')) as digital_events_90d,
    count(*) filter (where de.event_name = 'quote_request' and de.event_ts >= (s.snapshot_date - interval '180 days')) as quote_requests_180d
  from public.customer_digital_events de
  where de.customer_id = c.customer_id
    and de.event_ts < s.snapshot_date
) dig on true
left join lateral (
  select count(*) as positive_campaign_responses_prior
  from public.campaign_responses cr
  where cr.customer_id = c.customer_id
    and cr.response_ts < s.snapshot_date
    and cr.response_type in ('opened','clicked','called','quoted','converted')
) resp on true
left join lateral (
  select count(*) as complaint_count_prior
  from public.customer_complaints cc
  where cc.customer_id = c.customer_id
    and cc.complaint_date < s.snapshot_date
) comp on true
left join lateral (
  select count(*) as missed_payment_count_prior
  from public.payments pay
  where pay.customer_id = c.customer_id
    and pay.payment_date < s.snapshot_date
    and pay.payment_status in ('failed','past_due')
) pay on true
left join lateral (
  select max((cbd.feature_snapshot ->> 'tenure_days')::numeric) as tenure_days
  from public.customer_behavior_daily cbd
  where cbd.customer_id = c.customer_id
    and cbd.behavior_date < s.snapshot_date
) beh on true
where c.acquisition_date < s.snapshot_date
;

comment on view public.v_propensity_to_buy_features is
'Propensity-to-buy features. All predictors are restricted to events before snapshot_date; target_label is future policy purchase in the prediction window.';

create or replace view public.v_next_best_product_features as
select
  c.customer_id as entity_id,
  s.snapshot_date,
  prod.product_id as candidate_product_id,
  prod.line_of_business as candidate_line_of_business,
  coalesce(c.engagement_score, 0) as engagement_score,
  count(distinct owned.policy_id) filter (where owned.effective_date < s.snapshot_date and owned.product_id = prod.product_id) as prior_same_product_count,
  count(distinct owned.policy_id) filter (where owned.effective_date < s.snapshot_date) as prior_policy_count,
  count(distinct de.customer_digital_event_id) filter (where de.product_id = prod.product_id and de.event_ts < s.snapshot_date) as product_digital_interest_count,
  count(distinct q.quote_id) filter (where q.product_id = prod.product_id and q.quote_date < s.snapshot_date) as prior_quote_count,
  count(distinct cr.campaign_response_id) filter (where cr.response_ts < s.snapshot_date and cr.response_type in ('clicked','quoted','converted')) as positive_campaign_responses_prior,
  case when exists (
    select 1
    from public.policies fp
    where fp.customer_id = c.customer_id
      and fp.product_id = prod.product_id
      and fp.effective_date >= s.prediction_window_start
      and fp.effective_date < s.prediction_window_end
  ) then 1 else 0 end as target_label,
  s.training_window_start,
  s.training_window_end,
  s.prediction_window_start,
  s.prediction_window_end,
  c.customer_id as customer_id
from public.customers c
cross join public.v_ml_monthly_snapshots s
join public.products prod on prod.product_component_type = 'base' and prod.active_flag = true
left join public.policies owned on owned.customer_id = c.customer_id and owned.effective_date < s.snapshot_date
left join public.customer_digital_events de on de.customer_id = c.customer_id and de.event_ts < s.snapshot_date
left join public.quotes q on q.customer_id = c.customer_id and q.quote_date < s.snapshot_date
left join public.campaign_responses cr on cr.customer_id = c.customer_id and cr.response_ts < s.snapshot_date
where c.acquisition_date < s.snapshot_date
group by c.customer_id, s.snapshot_date, s.training_window_start, s.training_window_end, s.prediction_window_start, s.prediction_window_end, prod.product_id, prod.line_of_business, c.engagement_score;

comment on view public.v_next_best_product_features is
'Next-best-product customer-product candidate features. Product interest features are pre-snapshot; target_label is purchase of that candidate product in the future window.';

create or replace view public.v_customer_churn_features as
select
  c.customer_id as entity_id,
  s.snapshot_date,
  coalesce(c.engagement_score, 0) as engagement_score,
  count(distinct p.policy_id) filter (where p.effective_date < s.snapshot_date and p.policy_status in ('active','issued','renewed')) as active_policy_count,
  count(distinct pay.payment_id) filter (where pay.payment_status in ('failed','past_due') and pay.payment_date >= (s.snapshot_date - interval '180 days') and pay.payment_date < s.snapshot_date) as missed_payments_180d,
  count(distinct cc.customer_complaint_id) filter (where cc.complaint_date >= (s.snapshot_date - interval '365 days') and cc.complaint_date < s.snapshot_date) as complaints_365d,
  avg(nps.nps_score) filter (where nps.survey_date < s.snapshot_date) as avg_nps_prior,
  count(distinct csr.customer_service_request_id) filter (where csr.request_ts < s.snapshot_date and csr.sla_breached) as sla_breaches_prior,
  greatest(s.snapshot_date - c.acquisition_date, 0) as tenure_days,
  case when exists (
    select 1
    from public.policy_lapse_events ple
    where ple.customer_id = c.customer_id
      and ple.lapse_stage in ('lapsed','cancelled')
      and ple.lapse_event_date >= s.prediction_window_start
      and ple.lapse_event_date < s.prediction_window_end
  ) then 1 else 0 end as target_label,
  s.training_window_start,
  s.training_window_end,
  s.prediction_window_start,
  s.prediction_window_end,
  c.customer_segment
from public.customers c
cross join public.v_ml_monthly_snapshots s
left join public.policies p on p.customer_id = c.customer_id and p.effective_date < s.snapshot_date
left join public.payments pay on pay.customer_id = c.customer_id and pay.payment_date < s.snapshot_date
left join public.customer_complaints cc on cc.customer_id = c.customer_id and cc.complaint_date < s.snapshot_date
left join public.customer_nps nps on nps.customer_id = c.customer_id and nps.survey_date < s.snapshot_date
left join public.customer_service_requests csr on csr.customer_id = c.customer_id and csr.request_ts < s.snapshot_date
where c.acquisition_date < s.snapshot_date
group by c.customer_id, s.snapshot_date, s.training_window_start, s.training_window_end, s.prediction_window_start, s.prediction_window_end, c.customer_segment, c.engagement_score, c.acquisition_date;

comment on view public.v_customer_churn_features is
'Customer churn features. Complaint, payment, NPS, service, and policy signals are pre-snapshot; target_label is future lapse/cancel event in the prediction window.';

create or replace view public.v_policy_lapse_features as
select
  p.policy_id as entity_id,
  s.snapshot_date,
  p.customer_id,
  p.agent_id,
  p.product_id,
  p.annual_premium,
  greatest(s.snapshot_date - p.effective_date, 0) as policy_tenure_days,
  coalesce(pay.missed_payment_count_prior, 0) as missed_payment_count_prior,
  coalesce(comp.complaint_count_prior, 0) as complaint_count_prior,
  coalesce(clm.prior_claim_count, 0) as prior_claim_count,
  ren.latest_premium_change_pct,
  case when exists (
    select 1
    from public.policy_lapse_events fle
    where fle.policy_id = p.policy_id
      and fle.lapse_stage in ('lapsed','cancelled')
      and fle.lapse_event_date >= s.prediction_window_start
      and fle.lapse_event_date < s.prediction_window_end
  ) then 1 else 0 end as target_label,
  s.training_window_start,
  s.training_window_end,
  s.prediction_window_start,
  s.prediction_window_end
from public.policies p
join public.v_ml_monthly_snapshots s on p.effective_date < s.snapshot_date and p.expiration_date >= s.snapshot_date
left join lateral (
  select count(*) as missed_payment_count_prior
  from public.payments pay
  where pay.policy_id = p.policy_id
    and pay.payment_date < s.snapshot_date
    and pay.payment_status in ('failed','past_due')
) pay on true
left join lateral (
  select count(*) as complaint_count_prior
  from public.customer_complaints cc
  where cc.policy_id = p.policy_id
    and cc.complaint_date < s.snapshot_date
) comp on true
left join lateral (
  select count(*) as prior_claim_count
  from public.claims cl
  where cl.policy_id = p.policy_id
    and cl.loss_date < s.snapshot_date
) clm on true
left join lateral (
  select max(pren.premium_change_pct) as latest_premium_change_pct
  from public.policy_renewals pren
  where pren.policy_id = p.policy_id
    and pren.renewal_offer_date < s.snapshot_date
) ren on true
;

comment on view public.v_policy_lapse_features is
'Policy lapse features. Payment, complaint, claim, and premium-change signals are pre-snapshot; target_label is future lapse/cancel in the prediction window.';

create or replace view public.v_agent_performance_features as
select
  a.agent_id as entity_id,
  s.snapshot_date,
  count(distinct ac.agent_call_id) filter (where ac.call_ts >= s.snapshot_date - interval '90 days' and ac.call_ts < s.snapshot_date) as calls_90d,
  count(distinct am.agent_meeting_id) filter (where am.meeting_ts >= s.snapshot_date - interval '90 days' and am.meeting_ts < s.snapshot_date) as meetings_90d,
  sum(m.quotes_count) filter (where m.metric_month >= s.snapshot_date - interval '180 days' and m.metric_month < s.snapshot_date) as quotes_180d,
  sum(m.policies_bound_count) filter (where m.metric_month >= s.snapshot_date - interval '180 days' and m.metric_month < s.snapshot_date) as bound_180d,
  sum(m.new_business_premium) filter (where m.metric_month >= s.snapshot_date - interval '180 days' and m.metric_month < s.snapshot_date) as nbp_180d,
  avg(t.attainment_pct) filter (where t.target_period_end < s.snapshot_date) as avg_target_attainment_prior,
  case when coalesce(sum(fm.new_business_premium), 0) > 50000 then 1 else 0 end as target_label,
  s.training_window_start,
  s.training_window_end,
  s.prediction_window_start,
  s.prediction_window_end,
  a.territory_code
from public.agents a
cross join public.v_ml_monthly_snapshots s
left join public.agent_calls ac on ac.agent_id = a.agent_id and ac.call_ts < s.snapshot_date
left join public.agent_meetings am on am.agent_id = a.agent_id and am.meeting_ts < s.snapshot_date
left join public.agent_mapa_metrics m on m.agent_id = a.agent_id and m.metric_month < s.snapshot_date
left join public.agent_targets t on t.agent_id = a.agent_id and t.target_period_end < s.snapshot_date
left join public.agent_mapa_metrics fm on fm.agent_id = a.agent_id and fm.metric_month >= s.prediction_window_start and fm.metric_month < s.prediction_window_end
where a.appointment_date < s.snapshot_date
group by a.agent_id, a.territory_code, s.snapshot_date, s.training_window_start, s.training_window_end, s.prediction_window_start, s.prediction_window_end;

comment on view public.v_agent_performance_features is
'Agent performance features. Activity and target attainment are pre-snapshot; target_label is future high NBP performance in the prediction window.';

create or replace view public.v_next_best_customer_features as
with candidates as (
  select distinct agent_id, customer_id from public.policies where agent_id is not null
  union
  select distinct assigned_agent_id, customer_id from public.leads where assigned_agent_id is not null and customer_id is not null
)
select
  c.agent_id as entity_id,
  c.customer_id,
  s.snapshot_date,
  coalesce(cust.engagement_score, 0) as customer_engagement_score,
  coalesce(calls.prior_agent_calls, 0) as prior_agent_calls,
  coalesce(meetings.prior_agent_meetings, 0) as prior_agent_meetings,
  coalesce(pol.prior_customer_policy_count, 0) as prior_customer_policy_count,
  coalesce(leads.prior_lead_count, 0) as prior_lead_count,
  case when exists (
    select 1 from public.policies fp
    where fp.agent_id = c.agent_id
      and fp.customer_id = c.customer_id
      and fp.effective_date >= s.prediction_window_start
      and fp.effective_date < s.prediction_window_end
  ) then 1 else 0 end as target_label,
  s.training_window_start,
  s.training_window_end,
  s.prediction_window_start,
  s.prediction_window_end,
  c.agent_id as agent_id
from candidates c
join public.customers cust on cust.customer_id = c.customer_id
cross join public.v_ml_monthly_snapshots s
left join lateral (
  select count(*) as prior_agent_calls
  from public.agent_calls ac
  where ac.agent_id = c.agent_id
    and ac.customer_id = c.customer_id
    and ac.call_ts < s.snapshot_date
) calls on true
left join lateral (
  select count(*) as prior_agent_meetings
  from public.agent_meetings am
  where am.agent_id = c.agent_id
    and am.customer_id = c.customer_id
    and am.meeting_ts < s.snapshot_date
) meetings on true
left join lateral (
  select count(*) as prior_customer_policy_count
  from public.policies p
  where p.customer_id = c.customer_id
    and p.effective_date < s.snapshot_date
) pol on true
left join lateral (
  select count(*) as prior_lead_count
  from public.leads l
  where l.customer_id = c.customer_id
    and l.assigned_agent_id = c.agent_id
    and l.received_at < s.snapshot_date
) leads on true
;

comment on view public.v_next_best_customer_features is
'Next-best-customer features for agent-customer candidates. Prior interactions and customer history are pre-snapshot; target_label is future policy by the agent/customer pair.';

create or replace view public.v_lead_conversion_features as
select
  l.lead_id as entity_id,
  s.snapshot_date,
  l.customer_id,
  l.assigned_agent_id as agent_id,
  l.product_id,
  l.score as lead_score,
  coalesce(c.engagement_score, 0) as customer_engagement_score,
  coalesce(calls.calls_before_snapshot, 0) as calls_before_snapshot,
  coalesce(meetings.meetings_before_snapshot, 0) as meetings_before_snapshot,
  coalesce(quotes.quotes_before_snapshot, 0) as quotes_before_snapshot,
  case when exists (
    select 1 from public.policies fp
    where fp.customer_id = l.customer_id
      and fp.product_id = l.product_id
      and fp.effective_date >= s.prediction_window_start
      and fp.effective_date < s.prediction_window_end
  ) then 1 else 0 end as target_label,
  s.training_window_start,
  s.training_window_end,
  s.prediction_window_start,
  s.prediction_window_end,
  l.campaign_id
from public.leads l
join public.v_ml_monthly_snapshots s on l.received_at < s.snapshot_date
left join public.customers c on c.customer_id = l.customer_id
left join lateral (
  select count(*) as calls_before_snapshot
  from public.agent_calls ac
  where ac.lead_id = l.lead_id
    and ac.call_ts < s.snapshot_date
) calls on true
left join lateral (
  select count(*) as meetings_before_snapshot
  from public.agent_meetings am
  where am.lead_id = l.lead_id
    and am.meeting_ts < s.snapshot_date
) meetings on true
left join lateral (
  select count(*) as quotes_before_snapshot
  from public.quotes q
  where q.lead_id = l.lead_id
    and q.quote_date < s.snapshot_date
) quotes on true
;

comment on view public.v_lead_conversion_features is
'Lead conversion features. Calls, meetings, and quotes are pre-snapshot; target_label is future policy issue for the lead customer/product.';

create or replace view public.v_agent_attrition_features as
select
  a.agent_id as entity_id,
  s.snapshot_date,
  greatest(s.snapshot_date - a.appointment_date, 0) as agent_tenure_days,
  sum(comm.commission_amount) filter (where comm.commission_period >= s.snapshot_date - interval '180 days' and comm.commission_period < s.snapshot_date) as commissions_180d,
  sum(comm.commission_amount) filter (where comm.commission_period >= s.snapshot_date - interval '365 days' and comm.commission_period < s.snapshot_date - interval '180 days') as prior_commissions_180d,
  count(distinct comm.agent_commission_id) filter (where comm.chargeback_flag and comm.commission_period < s.snapshot_date) as chargebacks_prior,
  count(distinct tr.agent_training_id) filter (where tr.completion_status = 'completed' and tr.completed_date < s.snapshot_date) as completed_training_prior,
  avg(t.attainment_pct) filter (where t.target_period_end < s.snapshot_date) as avg_target_attainment_prior,
  case when exists (
    select 1 from public.agent_attrition_events ae
    where ae.agent_id = a.agent_id
      and ae.attrition_stage in ('notice','terminated','inactive')
      and ae.event_date >= s.prediction_window_start
      and ae.event_date < s.prediction_window_end
  ) then 1 else 0 end as target_label,
  s.training_window_start,
  s.training_window_end,
  s.prediction_window_start,
  s.prediction_window_end,
  a.territory_code
from public.agents a
cross join public.v_ml_monthly_snapshots s
left join public.agent_commissions comm on comm.agent_id = a.agent_id and comm.commission_period < s.snapshot_date
left join public.agent_training tr on tr.agent_id = a.agent_id and coalesce(tr.completed_date, tr.assigned_date) < s.snapshot_date
left join public.agent_targets t on t.agent_id = a.agent_id and t.target_period_end < s.snapshot_date
where a.appointment_date < s.snapshot_date
group by a.agent_id, a.territory_code, s.snapshot_date, s.training_window_start, s.training_window_end, s.prediction_window_start, s.prediction_window_end, a.appointment_date;

comment on view public.v_agent_attrition_features is
'Agent attrition features. Commission, chargeback, training, and target features are pre-snapshot; target_label is future attrition event.';

create or replace view public.v_claim_prediction_features as
select
  c.customer_id as entity_id,
  s.snapshot_date,
  count(distinct p.policy_id) filter (where p.effective_date < s.snapshot_date and p.policy_status in ('active','renewed','issued')) as active_policy_count,
  sum(p.annual_premium) filter (where p.effective_date < s.snapshot_date and p.policy_status in ('active','renewed','issued')) as active_annual_premium,
  count(distinct cl.claim_id) filter (where cl.loss_date < s.snapshot_date) as prior_claim_count,
  sum(cl.paid_amount + cl.reserve_amount) filter (where cl.loss_date < s.snapshot_date) as prior_incurred_claims,
  count(distinct pc.policy_coverage_id) filter (where pc.is_rider) as rider_count,
  case when exists (
    select 1 from public.claims fc
    where fc.customer_id = c.customer_id
      and fc.loss_date >= s.prediction_window_start
      and fc.loss_date < s.prediction_window_end
  ) then 1 else 0 end as target_label,
  s.training_window_start,
  s.training_window_end,
  s.prediction_window_start,
  s.prediction_window_end,
  c.customer_id as customer_id
from public.customers c
cross join public.v_ml_monthly_snapshots s
left join public.policies p on p.customer_id = c.customer_id and p.effective_date < s.snapshot_date
left join public.policy_coverages pc on pc.policy_id = p.policy_id
left join public.claims cl on cl.customer_id = c.customer_id and cl.loss_date < s.snapshot_date
where c.acquisition_date < s.snapshot_date
group by c.customer_id, s.snapshot_date, s.training_window_start, s.training_window_end, s.prediction_window_start, s.prediction_window_end;

comment on view public.v_claim_prediction_features is
'Claim occurrence features. Prior policies, riders, and claims are pre-snapshot; target_label is future claim occurrence.';

create or replace view public.v_fraud_detection_features as
select
  cl.claim_id as entity_id,
  cl.report_date as snapshot_date,
  cl.customer_id,
  cl.policy_id,
  cl.paid_amount,
  cl.reserve_amount,
  cl.incurred_amount,
  (cl.report_date - cl.loss_date) as report_lag_days,
  coalesce(prior_claims.prior_customer_claim_count, 0) as prior_customer_claim_count,
  coalesce(prior_claims.prior_customer_incurred, 0) as prior_customer_incurred,
  coalesce(prior_fraud.prior_fraud_indicators, 0) as prior_fraud_indicators,
  case when exists (
    select 1 from public.claim_fraud_indicators fi
    where fi.claim_id = cl.claim_id
      and fi.indicator_date >= cl.report_date
      and fi.indicator_date < cl.report_date + interval '180 days'
      and coalesce(fi.indicator_score, 0) >= 0.55
  ) then 1 else 0 end as target_label,
  (cl.report_date - interval '365 days')::date as training_window_start,
  cl.report_date as training_window_end,
  cl.report_date as prediction_window_start,
  (cl.report_date + interval '180 days')::date as prediction_window_end
from public.claims cl
left join lateral (
  select
    count(*) as prior_customer_claim_count,
    sum(pcl.paid_amount + pcl.reserve_amount) as prior_customer_incurred
  from public.claims pcl
  where pcl.customer_id = cl.customer_id
    and pcl.loss_date < cl.report_date
) prior_claims on true
left join lateral (
  select count(*) as prior_fraud_indicators
  from public.claim_fraud_indicators cfi
  where cfi.customer_id = cl.customer_id
    and cfi.indicator_date < cl.report_date
) prior_fraud on true
;

comment on view public.v_fraud_detection_features is
'Fraud detection claim features. Prior customer claim/fraud history is before claim report date; target_label is future high-score fraud indicator.';

create or replace view public.v_customer_lifetime_value_features as
select
  c.customer_id as entity_id,
  s.snapshot_date,
  count(distinct p.policy_id) filter (where p.effective_date < s.snapshot_date) as prior_policy_count,
  sum(pr.earned_premium_amount) filter (where pr.transaction_date < s.snapshot_date) as prior_earned_premium,
  sum(cl.paid_amount + cl.reserve_amount) filter (where cl.loss_date < s.snapshot_date) as prior_incurred_claims,
  count(distinct cc.customer_complaint_id) filter (where cc.complaint_date < s.snapshot_date) as complaint_count_prior,
  greatest(s.snapshot_date - c.acquisition_date, 0) as tenure_days,
  coalesce((
    select sum(fp.written_premium)
    from public.policies fp
    where fp.customer_id = c.customer_id
      and fp.effective_date >= s.prediction_window_start
      and fp.effective_date < (s.prediction_window_start + interval '365 days')
  ), 0) as target_label,
  s.training_window_start,
  s.training_window_end,
  s.prediction_window_start,
  (s.prediction_window_start + interval '365 days')::date as prediction_window_end,
  c.customer_segment
from public.customers c
cross join public.v_ml_monthly_snapshots s
left join public.policies p on p.customer_id = c.customer_id and p.effective_date < s.snapshot_date
left join public.premiums pr on pr.policy_id = p.policy_id and pr.transaction_date < s.snapshot_date
left join public.claims cl on cl.customer_id = c.customer_id and cl.loss_date < s.snapshot_date
left join public.customer_complaints cc on cc.customer_id = c.customer_id and cc.complaint_date < s.snapshot_date
where c.acquisition_date < s.snapshot_date
group by c.customer_id, s.snapshot_date, s.training_window_start, s.training_window_end, s.prediction_window_start, c.customer_segment, c.acquisition_date;

comment on view public.v_customer_lifetime_value_features is
'Customer lifetime value features. Prior premium, claim, complaint, and tenure features are pre-snapshot; target_label is future written premium over 365 days.';

create or replace view public.v_campaign_response_features as
select
  ct.campaign_target_id as entity_id,
  s.snapshot_date,
  ct.customer_id,
  ct.lead_id,
  ct.campaign_id,
  camp.channel,
  camp.campaign_type,
  coalesce(c.engagement_score, 0) as engagement_score,
  count(distinct prior_cr.campaign_response_id) filter (where prior_cr.response_ts < s.snapshot_date and prior_cr.response_type in ('opened','clicked','called','quoted','converted')) as prior_positive_responses,
  count(distinct de.customer_digital_event_id) filter (where de.event_ts >= s.snapshot_date - interval '90 days' and de.event_ts < s.snapshot_date) as digital_events_90d,
  count(distinct cc.customer_complaint_id) filter (where cc.complaint_date < s.snapshot_date) as complaint_count_prior,
  case when exists (
    select 1 from public.campaign_responses fcr
    where fcr.campaign_target_id = ct.campaign_target_id
      and fcr.response_ts >= s.prediction_window_start
      and fcr.response_ts < s.prediction_window_end
      and fcr.response_type in ('opened','clicked','called','quoted','converted')
  ) then 1 else 0 end as target_label,
  s.training_window_start,
  s.training_window_end,
  s.prediction_window_start,
  s.prediction_window_end
from public.campaign_targets ct
join public.campaigns camp on camp.campaign_id = ct.campaign_id
join public.v_ml_monthly_snapshots s on ct.selected_at < s.snapshot_date
left join public.customers c on c.customer_id = ct.customer_id
left join public.campaign_responses prior_cr on prior_cr.customer_id = ct.customer_id and prior_cr.response_ts < s.snapshot_date
left join public.customer_digital_events de on de.customer_id = ct.customer_id and de.event_ts < s.snapshot_date
left join public.customer_complaints cc on cc.customer_id = ct.customer_id and cc.complaint_date < s.snapshot_date
group by ct.campaign_target_id, s.snapshot_date, s.training_window_start, s.training_window_end, s.prediction_window_start, s.prediction_window_end, ct.customer_id, ct.lead_id, ct.campaign_id, camp.channel, camp.campaign_type, c.engagement_score;

comment on view public.v_campaign_response_features is
'Campaign response features. Prior responses, digital engagement, complaints, and customer attributes are pre-snapshot; target_label is future positive campaign response.';
