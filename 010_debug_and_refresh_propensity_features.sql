-- Debug and refresh propensity_to_buy_features in small chunks.
-- Use this when the Supabase SQL Editor times out on:
--   insert into public.propensity_to_buy_features select * from public.v_propensity_to_buy_features;
--
-- Run 006_ml_feature_engineering_views.sql first so the optimized view is active.

-- 1) Confirm the optimized view can return a small sample quickly.
select *
from public.v_propensity_to_buy_features
limit 10;

-- 2) Confirm expected monthly row counts from the view.
-- With 10,000 customers and 36 monthly snapshots, expect roughly <= 360,000 rows.
select snapshot_date, count(*) as row_count
from public.v_propensity_to_buy_features
group by snapshot_date
order by snapshot_date;

-- 3) Refresh the feature table one month at a time.
-- This is safer in the Supabase SQL Editor than one very large INSERT.
truncate table public.propensity_to_buy_features;

insert into public.propensity_to_buy_features
select *
from public.v_propensity_to_buy_features
where snapshot_date = date '2023-01-01';

insert into public.propensity_to_buy_features
select *
from public.v_propensity_to_buy_features
where snapshot_date = date '2023-02-01';

insert into public.propensity_to_buy_features
select *
from public.v_propensity_to_buy_features
where snapshot_date = date '2023-03-01';

insert into public.propensity_to_buy_features
select *
from public.v_propensity_to_buy_features
where snapshot_date = date '2023-04-01';

insert into public.propensity_to_buy_features
select *
from public.v_propensity_to_buy_features
where snapshot_date = date '2023-05-01';

insert into public.propensity_to_buy_features
select *
from public.v_propensity_to_buy_features
where snapshot_date = date '2023-06-01';

insert into public.propensity_to_buy_features
select *
from public.v_propensity_to_buy_features
where snapshot_date = date '2023-07-01';

insert into public.propensity_to_buy_features
select *
from public.v_propensity_to_buy_features
where snapshot_date = date '2023-08-01';

insert into public.propensity_to_buy_features
select *
from public.v_propensity_to_buy_features
where snapshot_date = date '2023-09-01';

insert into public.propensity_to_buy_features
select *
from public.v_propensity_to_buy_features
where snapshot_date = date '2023-10-01';

insert into public.propensity_to_buy_features
select *
from public.v_propensity_to_buy_features
where snapshot_date = date '2023-11-01';

insert into public.propensity_to_buy_features
select *
from public.v_propensity_to_buy_features
where snapshot_date = date '2023-12-01';

insert into public.propensity_to_buy_features
select *
from public.v_propensity_to_buy_features
where snapshot_date = date '2024-01-01';

insert into public.propensity_to_buy_features
select *
from public.v_propensity_to_buy_features
where snapshot_date = date '2024-02-01';

insert into public.propensity_to_buy_features
select *
from public.v_propensity_to_buy_features
where snapshot_date = date '2024-03-01';

insert into public.propensity_to_buy_features
select *
from public.v_propensity_to_buy_features
where snapshot_date = date '2024-04-01';

insert into public.propensity_to_buy_features
select *
from public.v_propensity_to_buy_features
where snapshot_date = date '2024-05-01';

insert into public.propensity_to_buy_features
select *
from public.v_propensity_to_buy_features
where snapshot_date = date '2024-06-01';

insert into public.propensity_to_buy_features
select *
from public.v_propensity_to_buy_features
where snapshot_date = date '2024-07-01';

insert into public.propensity_to_buy_features
select *
from public.v_propensity_to_buy_features
where snapshot_date = date '2024-08-01';

insert into public.propensity_to_buy_features
select *
from public.v_propensity_to_buy_features
where snapshot_date = date '2024-09-01';

insert into public.propensity_to_buy_features
select *
from public.v_propensity_to_buy_features
where snapshot_date = date '2024-10-01';

insert into public.propensity_to_buy_features
select *
from public.v_propensity_to_buy_features
where snapshot_date = date '2024-11-01';

insert into public.propensity_to_buy_features
select *
from public.v_propensity_to_buy_features
where snapshot_date = date '2024-12-01';

insert into public.propensity_to_buy_features
select *
from public.v_propensity_to_buy_features
where snapshot_date = date '2025-01-01';

insert into public.propensity_to_buy_features
select *
from public.v_propensity_to_buy_features
where snapshot_date = date '2025-02-01';

insert into public.propensity_to_buy_features
select *
from public.v_propensity_to_buy_features
where snapshot_date = date '2025-03-01';

insert into public.propensity_to_buy_features
select *
from public.v_propensity_to_buy_features
where snapshot_date = date '2025-04-01';

insert into public.propensity_to_buy_features
select *
from public.v_propensity_to_buy_features
where snapshot_date = date '2025-05-01';

insert into public.propensity_to_buy_features
select *
from public.v_propensity_to_buy_features
where snapshot_date = date '2025-06-01';

insert into public.propensity_to_buy_features
select *
from public.v_propensity_to_buy_features
where snapshot_date = date '2025-07-01';

insert into public.propensity_to_buy_features
select *
from public.v_propensity_to_buy_features
where snapshot_date = date '2025-08-01';

insert into public.propensity_to_buy_features
select *
from public.v_propensity_to_buy_features
where snapshot_date = date '2025-09-01';

insert into public.propensity_to_buy_features
select *
from public.v_propensity_to_buy_features
where snapshot_date = date '2025-10-01';

insert into public.propensity_to_buy_features
select *
from public.v_propensity_to_buy_features
where snapshot_date = date '2025-11-01';

insert into public.propensity_to_buy_features
select *
from public.v_propensity_to_buy_features
where snapshot_date = date '2025-12-01';

analyze public.propensity_to_buy_features;

select snapshot_date, count(*) as row_count
from public.propensity_to_buy_features
group by snapshot_date
order by snapshot_date;
