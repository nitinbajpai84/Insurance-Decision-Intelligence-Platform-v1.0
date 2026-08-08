-- Chunked refresh helpers for physical ML feature tables.
-- Run after 006_ml_feature_engineering_views.sql and 007_ml_feature_tables.sql.
--
-- These functions let you refresh one feature table for one snapshot date or
-- date range. This avoids Supabase SQL Editor upstream timeouts caused by
-- very large INSERT ... SELECT statements.

create or replace function public.ml_feature_source_view(p_feature_table text)
returns text
language plpgsql
stable
as $$
begin
  return case p_feature_table
    when 'propensity_to_buy_features' then 'v_propensity_to_buy_features'
    when 'next_best_product_features' then 'v_next_best_product_features'
    when 'customer_churn_features' then 'v_customer_churn_features'
    when 'policy_lapse_features' then 'v_policy_lapse_features'
    when 'agent_performance_features' then 'v_agent_performance_features'
    when 'next_best_customer_features' then 'v_next_best_customer_features'
    when 'lead_conversion_features' then 'v_lead_conversion_features'
    when 'agent_attrition_features' then 'v_agent_attrition_features'
    when 'claim_prediction_features' then 'v_claim_prediction_features'
    when 'fraud_detection_features' then 'v_fraud_detection_features'
    when 'customer_lifetime_value_features' then 'v_customer_lifetime_value_features'
    when 'campaign_response_features' then 'v_campaign_response_features'
    else null
  end;
end;
$$;

comment on function public.ml_feature_source_view(text) is
  'Maps physical ML feature table names to their leakage-safe source feature views.';

create or replace function public.refresh_ml_feature_snapshot(
  p_feature_table text,
  p_snapshot_date date
)
returns table(feature_table text, snapshot_date date, inserted_rows bigint)
language plpgsql
security invoker
as $$
declare
  v_source_view text;
  v_rows bigint;
begin
  v_source_view := public.ml_feature_source_view(p_feature_table);
  if v_source_view is null then
    raise exception 'Unsupported feature table: %', p_feature_table;
  end if;

  execute format('delete from public.%I where snapshot_date = $1', p_feature_table)
  using p_snapshot_date;

  execute format(
    'insert into public.%I select * from public.%I where snapshot_date = $1',
    p_feature_table,
    v_source_view
  )
  using p_snapshot_date;

  get diagnostics v_rows = row_count;

  execute format('analyze public.%I', p_feature_table);

  feature_table := p_feature_table;
  snapshot_date := p_snapshot_date;
  inserted_rows := v_rows;
  return next;
end;
$$;

comment on function public.refresh_ml_feature_snapshot(text, date) is
  'Refreshes one physical ML feature table for one exact snapshot_date.';

create or replace function public.refresh_ml_feature_date_range(
  p_feature_table text,
  p_start_date date,
  p_end_date date
)
returns table(feature_table text, start_date date, end_date date, inserted_rows bigint)
language plpgsql
security invoker
as $$
declare
  v_source_view text;
  v_rows bigint;
begin
  if p_end_date <= p_start_date then
    raise exception 'p_end_date must be greater than p_start_date';
  end if;

  v_source_view := public.ml_feature_source_view(p_feature_table);
  if v_source_view is null then
    raise exception 'Unsupported feature table: %', p_feature_table;
  end if;

  execute format(
    'delete from public.%I where snapshot_date >= $1 and snapshot_date < $2',
    p_feature_table
  )
  using p_start_date, p_end_date;

  execute format(
    'insert into public.%I select * from public.%I where snapshot_date >= $1 and snapshot_date < $2',
    p_feature_table,
    v_source_view
  )
  using p_start_date, p_end_date;

  get diagnostics v_rows = row_count;

  execute format('analyze public.%I', p_feature_table);

  feature_table := p_feature_table;
  start_date := p_start_date;
  end_date := p_end_date;
  inserted_rows := v_rows;
  return next;
end;
$$;

comment on function public.refresh_ml_feature_date_range(text, date, date) is
  'Refreshes one physical ML feature table for a snapshot_date range. Useful for claim/fraud tables and controlled monthly batches.';

-- Examples. Run these one at a time from the SQL Editor:
--
-- select * from public.refresh_ml_feature_snapshot('propensity_to_buy_features', date '2023-01-01');
-- select * from public.refresh_ml_feature_snapshot('customer_churn_features', date '2023-01-01');
-- select * from public.refresh_ml_feature_date_range('fraud_detection_features', date '2023-01-01', date '2023-02-01');
--
-- Confirm loaded rows:
--
-- select snapshot_date, count(*)
-- from public.propensity_to_buy_features
-- group by snapshot_date
-- order by snapshot_date;
