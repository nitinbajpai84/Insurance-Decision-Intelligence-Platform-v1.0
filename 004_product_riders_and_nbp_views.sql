-- Adds explicit rider product components and rider-tagged NBP analytics.
-- Apply after the base MVP schema. New full installs should also use the
-- updated 001 schema, which now contains these columns.

alter table public.products
  add column if not exists parent_product_id uuid references public.products(product_id) on delete set null,
  add column if not exists product_component_type text not null default 'base',
  add column if not exists rider_category text;

alter table public.products
  drop constraint if exists products_product_component_type_check;

alter table public.products
  add constraint products_product_component_type_check
  check (product_component_type in ('base', 'rider'));

alter table public.policy_coverages
  add column if not exists product_id uuid references public.products(product_id) on delete set null,
  add column if not exists is_rider boolean not null default false,
  add column if not exists rider_tag text;

create index if not exists idx_products_parent_component
  on public.products (parent_product_id, product_component_type);

create index if not exists idx_products_component_rider_category
  on public.products (product_component_type, rider_category);

create index if not exists idx_policy_coverages_product
  on public.policy_coverages (product_id);

create index if not exists idx_policy_coverages_rider_tag
  on public.policy_coverages (is_rider, rider_tag)
  where is_rider = true;

create or replace view public.v_policy_rider_tags as
select
  p.policy_id,
  p.policy_number,
  p.customer_id,
  p.agent_id,
  p.product_id as base_product_id,
  bp.product_code as base_product_code,
  bp.product_name as base_product_name,
  bp.line_of_business,
  bp.product_family,
  count(pc.policy_coverage_id) filter (where pc.is_rider) as rider_count,
  coalesce(array_agg(distinct rp.product_code) filter (where pc.is_rider), '{}'::text[]) as rider_product_codes,
  coalesce(array_agg(distinct pc.rider_tag) filter (where pc.is_rider and pc.rider_tag is not null), '{}'::text[]) as rider_tags,
  case when count(pc.policy_coverage_id) filter (where pc.is_rider) > 0 then true else false end as has_rider,
  p.policy_status,
  p.effective_date,
  p.expiration_date,
  p.annual_premium,
  p.written_premium
from public.policies p
join public.products bp on bp.product_id = p.product_id
left join public.policy_coverages pc on pc.policy_id = p.policy_id
left join public.products rp on rp.product_id = pc.product_id and rp.product_component_type = 'rider'
group by
  p.policy_id,
  p.policy_number,
  p.customer_id,
  p.agent_id,
  p.product_id,
  bp.product_code,
  bp.product_name,
  bp.line_of_business,
  bp.product_family,
  p.policy_status,
  p.effective_date,
  p.expiration_date,
  p.annual_premium,
  p.written_premium;

comment on view public.v_policy_rider_tags is 'Policy-level rider attachment view with base product, rider product codes, rider tags, and policy premium.';

create or replace view public.v_new_business_premium_by_rider as
select
  pr.transaction_date,
  date_trunc('month', pr.transaction_date)::date as transaction_month,
  p.policy_id,
  p.policy_number,
  p.agent_id,
  p.customer_id,
  bp.product_code as base_product_code,
  bp.product_name as base_product_name,
  bp.line_of_business,
  bp.product_family,
  coalesce(rp.product_code, bp.product_code) as component_product_code,
  coalesce(rp.product_name, bp.product_name) as component_product_name,
  coalesce(rp.product_component_type, 'base') as product_component_type,
  coalesce(pc.rider_tag, 'base_policy') as rider_tag,
  coalesce(pc.is_rider, false) as is_rider,
  pr.written_premium_amount as new_business_premium
from public.premiums pr
join public.policies p on p.policy_id = pr.policy_id
join public.products bp on bp.product_id = p.product_id
left join public.policy_coverages pc on pc.policy_coverage_id = pr.policy_coverage_id
left join public.products rp on rp.product_id = pc.product_id
where pr.transaction_type = 'new_business';

comment on view public.v_new_business_premium_by_rider is 'New business premium allocated to base products and rider components using policy_coverages.product_id and rider_tag.';
