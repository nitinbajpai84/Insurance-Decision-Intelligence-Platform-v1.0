-- Insurance analytics MVP schema for Supabase Postgres.
-- Uses normalized insurance concepts inspired by common industry patterns.

create extension if not exists pgcrypto;
create extension if not exists vector;

create or replace function public.set_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

create table public.parties (
  party_id uuid primary key default gen_random_uuid(),
  party_type text not null check (party_type in ('person', 'organization', 'household')),
  display_name text not null,
  first_name text,
  middle_name text,
  last_name text,
  organization_name text,
  date_of_birth date,
  tax_id_last4 text,
  email text,
  phone text,
  preferred_contact_method text check (preferred_contact_method in ('email', 'phone', 'sms', 'mail', 'app')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

comment on table public.parties is 'Reusable person, household, or organization identity record used by customers, agents, agencies, and other insurance participants.';

create table public.customers (
  customer_id uuid primary key default gen_random_uuid(),
  party_id uuid not null unique references public.parties(party_id) on delete restrict,
  customer_number text not null unique,
  customer_segment text,
  lifecycle_stage text check (lifecycle_stage in ('prospect', 'active', 'inactive', 'lapsed', 'former')),
  acquisition_date date not null,
  risk_tier text check (risk_tier in ('low', 'medium', 'high', 'very_high')),
  engagement_score numeric(6,2) check (engagement_score between 0 and 100),
  household_party_id uuid references public.parties(party_id) on delete set null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

comment on table public.customers is 'Customer master records linked to parties, including lifecycle, risk, and engagement attributes used for analytics.';

create table public.addresses (
  address_id uuid primary key default gen_random_uuid(),
  party_id uuid not null references public.parties(party_id) on delete cascade,
  address_type text not null check (address_type in ('primary', 'mailing', 'billing', 'risk_location', 'business')),
  line1 text not null,
  line2 text,
  city text not null,
  state_code text not null,
  postal_code text not null,
  country_code text not null default 'US',
  latitude numeric(9,6),
  longitude numeric(9,6),
  is_current boolean not null default true,
  effective_date date,
  expiration_date date,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

comment on table public.addresses is 'Party addresses, including mailing, billing, and insured risk locations for geographic and territory analytics.';

create table public.agents (
  agent_id uuid primary key default gen_random_uuid(),
  party_id uuid not null unique references public.parties(party_id) on delete restrict,
  agent_number text not null unique,
  agency_party_id uuid references public.parties(party_id) on delete set null,
  license_state text,
  license_number text,
  channel text not null check (channel in ('exclusive', 'independent', 'broker', 'direct', 'partner')),
  territory_code text,
  appointment_date date not null,
  termination_date date,
  status text not null check (status in ('active', 'inactive', 'terminated', 'suspended')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

comment on table public.agents is 'Insurance producers or servicing agents, linked to party records and used for book-of-business, sales, and performance analysis.';

create table public.agent_movements (
  agent_movement_id uuid primary key default gen_random_uuid(),
  agent_id uuid not null references public.agents(agent_id) on delete cascade,
  movement_type text not null check (movement_type in ('appointment', 'transfer', 'territory_change', 'agency_change', 'termination', 'reactivation')),
  from_agency_party_id uuid references public.parties(party_id) on delete set null,
  to_agency_party_id uuid references public.parties(party_id) on delete set null,
  from_territory_code text,
  to_territory_code text,
  effective_date date not null,
  end_date date,
  reason text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  check (end_date is null or end_date >= effective_date)
);

comment on table public.agent_movements is 'Effective-dated history of agent appointments, transfers, territory changes, agency changes, terminations, and reactivations.';

create table public.agent_mapa_metrics (
  agent_mapa_metric_id uuid primary key default gen_random_uuid(),
  agent_id uuid not null references public.agents(agent_id) on delete cascade,
  metric_month date not null,
  leads_count integer not null default 0 check (leads_count >= 0),
  contacts_count integer not null default 0 check (contacts_count >= 0),
  quotes_count integer not null default 0 check (quotes_count >= 0),
  applications_count integer not null default 0 check (applications_count >= 0),
  policies_bound_count integer not null default 0 check (policies_bound_count >= 0),
  new_business_premium numeric(14,2) not null default 0,
  renewal_premium numeric(14,2) not null default 0,
  retained_policy_count integer not null default 0 check (retained_policy_count >= 0),
  lapsed_policy_count integer not null default 0 check (lapsed_policy_count >= 0),
  claims_count integer not null default 0 check (claims_count >= 0),
  loss_ratio numeric(9,4),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (agent_id, metric_month)
);

comment on table public.agent_mapa_metrics is 'Monthly agent MAPA-style activity, production, retention, and claims performance metrics.';

create table public.products (
  product_id uuid primary key default gen_random_uuid(),
  parent_product_id uuid references public.products(product_id) on delete set null,
  product_code text not null unique,
  product_name text not null,
  line_of_business text not null,
  product_family text not null,
  product_component_type text not null default 'base' check (product_component_type in ('base', 'rider')),
  rider_category text,
  product_version text,
  effective_date date,
  expiration_date date,
  active_flag boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

comment on table public.products is 'Insurance product catalog containing lines of business, product families, and product versions.';

create table public.campaigns (
  campaign_id uuid primary key default gen_random_uuid(),
  campaign_code text not null unique,
  campaign_name text not null,
  campaign_type text not null,
  channel text not null check (channel in ('email', 'sms', 'direct_mail', 'agent_call', 'web', 'app', 'social', 'partner')),
  objective text,
  target_line_of_business text,
  start_date date not null,
  end_date date not null,
  budget_amount numeric(14,2) check (budget_amount is null or budget_amount >= 0),
  status text not null check (status in ('planned', 'active', 'completed', 'cancelled')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  check (end_date >= start_date)
);

comment on table public.campaigns is 'Marketing campaign definitions used to measure targeting, response, conversion, and premium attribution.';

create table public.leads (
  lead_id uuid primary key default gen_random_uuid(),
  lead_number text not null unique,
  party_id uuid references public.parties(party_id) on delete set null,
  customer_id uuid references public.customers(customer_id) on delete set null,
  campaign_id uuid references public.campaigns(campaign_id) on delete set null,
  assigned_agent_id uuid references public.agents(agent_id) on delete set null,
  product_id uuid references public.products(product_id) on delete set null,
  lead_source text not null,
  lead_status text not null check (lead_status in ('new', 'contacted', 'qualified', 'disqualified', 'converted', 'closed')),
  received_at timestamptz not null,
  qualified_at timestamptz,
  score numeric(6,2) check (score is null or score between 0 and 100),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

comment on table public.leads is 'Prospective insurance demand records from campaigns, agents, partners, or digital channels before an opportunity is created.';

create table public.opportunities (
  opportunity_id uuid primary key default gen_random_uuid(),
  opportunity_number text not null unique,
  lead_id uuid references public.leads(lead_id) on delete set null,
  customer_id uuid references public.customers(customer_id) on delete set null,
  agent_id uuid references public.agents(agent_id) on delete set null,
  campaign_id uuid references public.campaigns(campaign_id) on delete set null,
  product_id uuid references public.products(product_id) on delete restrict,
  opportunity_stage text not null check (opportunity_stage in ('opened', 'quoted', 'application', 'underwriting', 'bound', 'lost', 'withdrawn')),
  opened_date date not null,
  close_date date,
  estimated_premium numeric(14,2) check (estimated_premium is null or estimated_premium >= 0),
  quoted_premium numeric(14,2) check (quoted_premium is null or quoted_premium >= 0),
  lost_reason text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  check (close_date is null or close_date >= opened_date)
);

comment on table public.opportunities is 'Sales pipeline records connecting leads, customers, agents, products, and campaigns through quote and bind stages.';

create table public.policies (
  policy_id uuid primary key default gen_random_uuid(),
  policy_number text not null unique,
  customer_id uuid not null references public.customers(customer_id) on delete restrict,
  agent_id uuid references public.agents(agent_id) on delete set null,
  product_id uuid not null references public.products(product_id) on delete restrict,
  opportunity_id uuid references public.opportunities(opportunity_id) on delete set null,
  prior_policy_id uuid references public.policies(policy_id) on delete set null,
  policy_status text not null check (policy_status in ('quoted', 'issued', 'active', 'cancelled', 'expired', 'renewed', 'lapsed')),
  effective_date date not null,
  expiration_date date not null,
  issue_date date,
  cancellation_date date,
  source_channel text,
  payment_plan text,
  annual_premium numeric(14,2) not null default 0 check (annual_premium >= 0),
  written_premium numeric(14,2) not null default 0,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  check (expiration_date > effective_date),
  check (cancellation_date is null or cancellation_date >= effective_date)
);

comment on table public.policies is 'Policy contract headers with customer, agent, product, status, effective period, and premium summary attributes.';

create table public.policy_coverages (
  policy_coverage_id uuid primary key default gen_random_uuid(),
  policy_id uuid not null references public.policies(policy_id) on delete cascade,
  product_id uuid references public.products(product_id) on delete set null,
  coverage_code text not null,
  coverage_name text not null,
  coverage_status text not null check (coverage_status in ('active', 'cancelled', 'expired')),
  is_rider boolean not null default false,
  rider_tag text,
  limit_amount numeric(14,2) check (limit_amount is null or limit_amount >= 0),
  deductible_amount numeric(14,2) check (deductible_amount is null or deductible_amount >= 0),
  exposure_basis text,
  exposure_value numeric(14,2),
  effective_date date not null,
  expiration_date date not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (policy_id, coverage_code, effective_date),
  check (expiration_date > effective_date)
);

comment on table public.policy_coverages is 'Coverage-level policy details such as limits, deductibles, exposure basis, and coverage effective periods.';

create table public.premiums (
  premium_id uuid primary key default gen_random_uuid(),
  policy_id uuid not null references public.policies(policy_id) on delete cascade,
  policy_coverage_id uuid references public.policy_coverages(policy_coverage_id) on delete set null,
  premium_period_start date not null,
  premium_period_end date not null,
  transaction_date date not null,
  transaction_type text not null check (transaction_type in ('new_business', 'renewal', 'endorsement', 'cancellation', 'reinstatement', 'audit')),
  written_premium_amount numeric(14,2) not null default 0,
  earned_premium_amount numeric(14,2) not null default 0,
  tax_fee_amount numeric(14,2) not null default 0,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  check (premium_period_end >= premium_period_start)
);

comment on table public.premiums is 'Premium transactions and earning records used for written premium, earned premium, and loss-ratio analytics.';

create table public.payments (
  payment_id uuid primary key default gen_random_uuid(),
  policy_id uuid not null references public.policies(policy_id) on delete cascade,
  customer_id uuid not null references public.customers(customer_id) on delete restrict,
  payment_date date not null,
  due_date date,
  payment_status text not null check (payment_status in ('scheduled', 'paid', 'failed', 'reversed', 'refunded', 'past_due')),
  payment_method text check (payment_method in ('card', 'ach', 'check', 'cash', 'wire', 'payroll', 'other')),
  billed_amount numeric(14,2) not null default 0,
  paid_amount numeric(14,2) not null default 0,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

comment on table public.payments is 'Billing and payment activity associated with policies and customers.';

create table public.claims (
  claim_id uuid primary key default gen_random_uuid(),
  claim_number text not null unique,
  policy_id uuid not null references public.policies(policy_id) on delete restrict,
  customer_id uuid not null references public.customers(customer_id) on delete restrict,
  policy_coverage_id uuid references public.policy_coverages(policy_coverage_id) on delete set null,
  assigned_agent_id uuid references public.agents(agent_id) on delete set null,
  loss_date date not null,
  report_date date not null,
  close_date date,
  claim_status text not null check (claim_status in ('open', 'closed', 'reopened', 'denied', 'subrogation')),
  loss_cause text,
  loss_description text,
  paid_amount numeric(14,2) not null default 0 check (paid_amount >= 0),
  reserve_amount numeric(14,2) not null default 0 check (reserve_amount >= 0),
  incurred_amount numeric(14,2) generated always as (paid_amount + reserve_amount) stored,
  litigation_flag boolean not null default false,
  catastrophe_flag boolean not null default false,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  check (report_date >= loss_date),
  check (close_date is null or close_date >= report_date)
);

comment on table public.claims is 'Claim headers with loss timing, status, cause, and financial measures for severity, frequency, and loss-ratio analysis.';

create table public.campaign_targets (
  campaign_target_id uuid primary key default gen_random_uuid(),
  campaign_id uuid not null references public.campaigns(campaign_id) on delete cascade,
  customer_id uuid references public.customers(customer_id) on delete cascade,
  lead_id uuid references public.leads(lead_id) on delete cascade,
  agent_id uuid references public.agents(agent_id) on delete set null,
  target_status text not null check (target_status in ('selected', 'suppressed', 'sent', 'excluded')),
  selected_at timestamptz not null default now(),
  suppression_reason text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  check (customer_id is not null or lead_id is not null)
);

comment on table public.campaign_targets is 'Campaign audience membership for customer and lead targeting, including suppressions and assigned agents.';

create table public.campaign_responses (
  campaign_response_id uuid primary key default gen_random_uuid(),
  campaign_id uuid not null references public.campaigns(campaign_id) on delete cascade,
  campaign_target_id uuid references public.campaign_targets(campaign_target_id) on delete set null,
  customer_id uuid references public.customers(customer_id) on delete set null,
  lead_id uuid references public.leads(lead_id) on delete set null,
  opportunity_id uuid references public.opportunities(opportunity_id) on delete set null,
  policy_id uuid references public.policies(policy_id) on delete set null,
  response_ts timestamptz not null,
  response_type text not null check (response_type in ('delivered', 'opened', 'clicked', 'called', 'quoted', 'converted', 'unsubscribed', 'bounced', 'no_response')),
  conversion_flag boolean not null default false,
  conversion_premium numeric(14,2) check (conversion_premium is null or conversion_premium >= 0),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  check (customer_id is not null or lead_id is not null)
);

comment on table public.campaign_responses is 'Customer and lead responses to campaigns, including quote and conversion attribution.';

create table public.customer_engagement_events (
  customer_engagement_event_id uuid primary key default gen_random_uuid(),
  customer_id uuid not null references public.customers(customer_id) on delete cascade,
  policy_id uuid references public.policies(policy_id) on delete set null,
  claim_id uuid references public.claims(claim_id) on delete set null,
  campaign_id uuid references public.campaigns(campaign_id) on delete set null,
  agent_id uuid references public.agents(agent_id) on delete set null,
  event_ts timestamptz not null,
  event_type text not null,
  channel text not null check (channel in ('web', 'mobile_app', 'email', 'sms', 'call_center', 'agent', 'mail', 'chat', 'social')),
  sentiment_score numeric(5,2) check (sentiment_score is null or sentiment_score between -1 and 1),
  duration_seconds integer check (duration_seconds is null or duration_seconds >= 0),
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

comment on table public.customer_engagement_events is 'Timestamped customer interactions across channels, optionally linked to policies, claims, campaigns, and agents.';

create table public.business_glossary (
  glossary_id uuid primary key default gen_random_uuid(),
  term text not null unique,
  domain text not null,
  definition text not null,
  calculation_sql text,
  synonyms text[] not null default '{}',
  owner text,
  active_flag boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

comment on table public.business_glossary is 'Governed business definitions, metric formulas, synonyms, and ownership metadata for semantic retrieval and text-to-SQL grounding.';

create table public.semantic_documents (
  semantic_document_id uuid primary key default gen_random_uuid(),
  glossary_id uuid references public.business_glossary(glossary_id) on delete set null,
  document_type text not null check (document_type in ('table', 'column', 'metric', 'join', 'example_question', 'glossary', 'policy_note', 'claim_note', 'campaign_summary', 'agent_summary')),
  source_schema text,
  source_table text,
  source_column text,
  title text not null,
  content text not null,
  tags text[] not null default '{}',
  content_hash text not null,
  embedding_model text not null,
  embedding vector(1536),
  active_flag boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (document_type, content_hash, embedding_model)
);

comment on table public.semantic_documents is 'Vector-searchable semantic context documents for schema descriptions, glossary terms, metrics, joins, examples, and narrative insurance summaries.';

create table public.query_audit_log (
  query_audit_log_id uuid primary key default gen_random_uuid(),
  user_id uuid references auth.users(id) on delete set null,
  session_id uuid,
  question text not null,
  retrieved_semantic_document_ids uuid[] not null default '{}',
  generated_sql text,
  execution_status text not null check (execution_status in ('started', 'validated', 'executed', 'blocked', 'failed')),
  safety_decision text,
  error_message text,
  row_count integer check (row_count is null or row_count >= 0),
  duration_ms integer check (duration_ms is null or duration_ms >= 0),
  feedback_rating integer check (feedback_rating is null or feedback_rating between 1 and 5),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

comment on table public.query_audit_log is 'Audit trail of natural-language analytics questions, retrieved semantic context, generated SQL, safety decisions, execution results, and user feedback.';

-- Updated-at triggers.
do $$
declare
  table_name text;
begin
  foreach table_name in array array[
    'parties',
    'customers',
    'addresses',
    'agents',
    'agent_movements',
    'agent_mapa_metrics',
    'products',
    'policies',
    'policy_coverages',
    'premiums',
    'payments',
    'claims',
    'campaigns',
    'campaign_targets',
    'campaign_responses',
    'leads',
    'opportunities',
    'customer_engagement_events',
    'business_glossary',
    'semantic_documents',
    'query_audit_log'
  ]
  loop
    execute format(
      'create trigger set_%I_updated_at before update on public.%I for each row execute function public.set_updated_at()',
      table_name,
      table_name
    );
  end loop;
end $$;

-- Party and customer lookup indexes.
create index idx_parties_type_name on public.parties (party_type, display_name);
create index idx_parties_email on public.parties (lower(email)) where email is not null;
create index idx_customers_party on public.customers (party_id);
create index idx_customers_segment_stage on public.customers (customer_segment, lifecycle_stage);
create index idx_customers_risk_tier on public.customers (risk_tier);
create index idx_addresses_party_current on public.addresses (party_id, is_current);
create index idx_addresses_state_postal on public.addresses (state_code, postal_code);

-- Agent analytics indexes.
create index idx_agents_party on public.agents (party_id);
create index idx_agents_agency_status on public.agents (agency_party_id, status);
create index idx_agents_channel_territory on public.agents (channel, territory_code);
create index idx_agent_movements_agent_effective on public.agent_movements (agent_id, effective_date desc);
create index idx_agent_movements_type_effective on public.agent_movements (movement_type, effective_date desc);
create index idx_agent_mapa_agent_month on public.agent_mapa_metrics (agent_id, metric_month desc);
create index idx_agent_mapa_month on public.agent_mapa_metrics (metric_month);

-- Product, policy, premium, payment, and claims indexes.
create index idx_products_lob_family on public.products (line_of_business, product_family);
create index idx_products_parent_component on public.products (parent_product_id, product_component_type);
create index idx_products_component_rider_category on public.products (product_component_type, rider_category);
create index idx_policies_customer_dates on public.policies (customer_id, effective_date desc);
create index idx_policies_agent_dates on public.policies (agent_id, effective_date desc);
create index idx_policies_product_status_dates on public.policies (product_id, policy_status, effective_date);
create index idx_policies_effective_expiration on public.policies (effective_date, expiration_date);
create index idx_policy_coverages_policy on public.policy_coverages (policy_id);
create index idx_policy_coverages_product on public.policy_coverages (product_id);
create index idx_policy_coverages_code on public.policy_coverages (coverage_code);
create index idx_policy_coverages_rider_tag on public.policy_coverages (is_rider, rider_tag) where is_rider = true;
create index idx_premiums_policy_transaction_date on public.premiums (policy_id, transaction_date desc);
create index idx_premiums_period on public.premiums (premium_period_start, premium_period_end);
create index idx_payments_policy_date on public.payments (policy_id, payment_date desc);
create index idx_payments_customer_status on public.payments (customer_id, payment_status);
create index idx_claims_policy on public.claims (policy_id);
create index idx_claims_customer_loss_date on public.claims (customer_id, loss_date desc);
create index idx_claims_status_report_date on public.claims (claim_status, report_date desc);
create index idx_claims_loss_cause on public.claims (loss_cause);

-- Campaign, lead, opportunity, and engagement indexes.
create index idx_campaigns_status_dates on public.campaigns (status, start_date, end_date);
create index idx_campaigns_channel_lob on public.campaigns (channel, target_line_of_business);
create index idx_campaign_targets_campaign_status on public.campaign_targets (campaign_id, target_status);
create index idx_campaign_targets_customer on public.campaign_targets (customer_id) where customer_id is not null;
create index idx_campaign_targets_lead on public.campaign_targets (lead_id) where lead_id is not null;
create index idx_campaign_responses_campaign_type_ts on public.campaign_responses (campaign_id, response_type, response_ts desc);
create index idx_campaign_responses_customer_ts on public.campaign_responses (customer_id, response_ts desc) where customer_id is not null;
create index idx_campaign_responses_conversion on public.campaign_responses (campaign_id, conversion_flag) where conversion_flag = true;
create index idx_leads_campaign_status on public.leads (campaign_id, lead_status);
create index idx_leads_agent_received on public.leads (assigned_agent_id, received_at desc);
create index idx_opportunities_agent_stage on public.opportunities (agent_id, opportunity_stage);
create index idx_opportunities_customer_opened on public.opportunities (customer_id, opened_date desc);
create index idx_opportunities_campaign_stage on public.opportunities (campaign_id, opportunity_stage);
create index idx_engagement_customer_ts on public.customer_engagement_events (customer_id, event_ts desc);
create index idx_engagement_policy_ts on public.customer_engagement_events (policy_id, event_ts desc) where policy_id is not null;
create index idx_engagement_campaign_ts on public.customer_engagement_events (campaign_id, event_ts desc) where campaign_id is not null;
create index idx_engagement_type_channel_ts on public.customer_engagement_events (event_type, channel, event_ts desc);
create index idx_engagement_metadata_gin on public.customer_engagement_events using gin (metadata);

-- Semantic and audit indexes.
create index idx_business_glossary_domain_active on public.business_glossary (domain, active_flag);
create index idx_business_glossary_synonyms_gin on public.business_glossary using gin (synonyms);
create index idx_semantic_documents_type_active on public.semantic_documents (document_type, active_flag);
create index idx_semantic_documents_source on public.semantic_documents (source_schema, source_table, source_column);
create index idx_semantic_documents_tags_gin on public.semantic_documents using gin (tags);
create index idx_semantic_documents_embedding_hnsw
  on public.semantic_documents
  using hnsw (embedding vector_cosine_ops)
  where embedding is not null;
create index idx_query_audit_user_created on public.query_audit_log (user_id, created_at desc);
create index idx_query_audit_status_created on public.query_audit_log (execution_status, created_at desc);
