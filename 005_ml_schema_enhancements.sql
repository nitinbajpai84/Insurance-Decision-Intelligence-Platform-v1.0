-- ML schema enhancements for the insurance analytics MVP.
-- Compatible with Supabase Postgres.
-- Adds behavior, journey, sales, underwriting, agent, claims, and model
-- scoring tables for ACORD-inspired insurance ML use cases without copying
-- proprietary ACORD definitions.

create extension if not exists pgcrypto;

create or replace function public.set_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

-- ---------------------------------------------------------------------------
-- Customer behavior and service experience
-- ---------------------------------------------------------------------------

create table if not exists public.customer_behavior_daily (
  customer_behavior_daily_id uuid primary key default gen_random_uuid(),
  customer_id uuid not null references public.customers(customer_id) on delete cascade,
  behavior_date date not null,
  active_policy_count integer not null default 0 check (active_policy_count >= 0),
  open_claim_count integer not null default 0 check (open_claim_count >= 0),
  payment_missed_count_90d integer not null default 0 check (payment_missed_count_90d >= 0),
  digital_event_count integer not null default 0 check (digital_event_count >= 0),
  service_request_count integer not null default 0 check (service_request_count >= 0),
  complaint_count integer not null default 0 check (complaint_count >= 0),
  campaign_touch_count integer not null default 0 check (campaign_touch_count >= 0),
  quote_count_90d integer not null default 0 check (quote_count_90d >= 0),
  engagement_score numeric(6,2) check (engagement_score is null or engagement_score between 0 and 100),
  churn_signal_score numeric(8,4) check (churn_signal_score is null or churn_signal_score between 0 and 1),
  feature_snapshot jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (customer_id, behavior_date)
);

comment on table public.customer_behavior_daily is 'Daily customer behavior snapshot for ML feature assembly, churn modelling, propensity, next-best-product, CLV, and campaign response modelling.';
comment on column public.customer_behavior_daily.customer_behavior_daily_id is 'Primary key for the daily customer behavior snapshot.';
comment on column public.customer_behavior_daily.customer_id is 'Customer represented by the daily behavior snapshot.';
comment on column public.customer_behavior_daily.behavior_date is 'Date of the behavior snapshot.';
comment on column public.customer_behavior_daily.active_policy_count is 'Number of active or in-force policies observed for the customer on the snapshot date.';
comment on column public.customer_behavior_daily.open_claim_count is 'Number of open claims for the customer on the snapshot date.';
comment on column public.customer_behavior_daily.payment_missed_count_90d is 'Count of missed or failed payments in the trailing 90 days.';
comment on column public.customer_behavior_daily.digital_event_count is 'Count of digital interactions on or near the snapshot period.';
comment on column public.customer_behavior_daily.service_request_count is 'Count of service requests in the snapshot period.';
comment on column public.customer_behavior_daily.complaint_count is 'Count of complaints in the snapshot period.';
comment on column public.customer_behavior_daily.campaign_touch_count is 'Count of campaign touches in the snapshot period.';
comment on column public.customer_behavior_daily.quote_count_90d is 'Count of quotes in the trailing 90 days.';
comment on column public.customer_behavior_daily.engagement_score is 'Derived 0 to 100 customer engagement score for feature engineering.';
comment on column public.customer_behavior_daily.churn_signal_score is 'Derived 0 to 1 heuristic churn signal useful for monitoring and weak labels.';
comment on column public.customer_behavior_daily.feature_snapshot is 'Optional JSON feature payload used for ML training and explainability.';
comment on column public.customer_behavior_daily.created_at is 'Timestamp when the record was created.';
comment on column public.customer_behavior_daily.updated_at is 'Timestamp when the record was last updated.';

create table if not exists public.customer_digital_events (
  customer_digital_event_id uuid primary key default gen_random_uuid(),
  customer_id uuid references public.customers(customer_id) on delete set null,
  party_id uuid references public.parties(party_id) on delete set null,
  policy_id uuid references public.policies(policy_id) on delete set null,
  campaign_id uuid references public.campaigns(campaign_id) on delete set null,
  event_ts timestamptz not null,
  session_id text,
  device_type text check (device_type is null or device_type in ('desktop', 'mobile', 'tablet', 'unknown')),
  channel text not null check (channel in ('web', 'mobile_app', 'email', 'sms', 'chat', 'social', 'partner')),
  event_name text not null,
  event_category text,
  page_name text,
  product_id uuid references public.products(product_id) on delete set null,
  dwell_seconds integer check (dwell_seconds is null or dwell_seconds >= 0),
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

comment on table public.customer_digital_events is 'Granular digital journey events for propensity, campaign response, next-best-product, churn, and digital engagement features.';
comment on column public.customer_digital_events.customer_digital_event_id is 'Primary key for the digital event.';
comment on column public.customer_digital_events.customer_id is 'Known customer associated with the digital event, if identified.';
comment on column public.customer_digital_events.party_id is 'Known party associated with the digital event, if customer mapping is unavailable.';
comment on column public.customer_digital_events.policy_id is 'Policy context associated with the event, if available.';
comment on column public.customer_digital_events.campaign_id is 'Campaign context associated with the event, if available.';
comment on column public.customer_digital_events.event_ts is 'Timestamp when the digital event occurred.';
comment on column public.customer_digital_events.session_id is 'Digital session identifier for journey sequencing.';
comment on column public.customer_digital_events.device_type is 'Device category used by the customer.';
comment on column public.customer_digital_events.channel is 'Digital channel where the event occurred.';
comment on column public.customer_digital_events.event_name is 'Event name such as quote_start, product_view, login, or claim_status_view.';
comment on column public.customer_digital_events.event_category is 'Higher-level digital event category.';
comment on column public.customer_digital_events.page_name is 'Page, screen, or experience name.';
comment on column public.customer_digital_events.product_id is 'Product context for product-view and quote-related events.';
comment on column public.customer_digital_events.dwell_seconds is 'Approximate dwell time for page or screen engagement.';
comment on column public.customer_digital_events.metadata is 'Additional event attributes for feature engineering.';
comment on column public.customer_digital_events.created_at is 'Timestamp when the record was created.';
comment on column public.customer_digital_events.updated_at is 'Timestamp when the record was last updated.';

create table if not exists public.customer_complaints (
  customer_complaint_id uuid primary key default gen_random_uuid(),
  customer_id uuid not null references public.customers(customer_id) on delete cascade,
  policy_id uuid references public.policies(policy_id) on delete set null,
  claim_id uuid references public.claims(claim_id) on delete set null,
  agent_id uuid references public.agents(agent_id) on delete set null,
  complaint_date date not null,
  complaint_channel text not null check (complaint_channel in ('call_center', 'email', 'web', 'mobile_app', 'agent', 'regulator', 'social')),
  complaint_category text not null,
  severity text not null check (severity in ('low', 'medium', 'high', 'critical')),
  status text not null check (status in ('open', 'in_review', 'resolved', 'rejected', 'escalated')),
  resolution_date date,
  resolution_days integer check (resolution_days is null or resolution_days >= 0),
  sentiment_score numeric(5,2) check (sentiment_score is null or sentiment_score between -1 and 1),
  complaint_text text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  check (resolution_date is null or resolution_date >= complaint_date)
);

comment on table public.customer_complaints is 'Customer complaint records for churn, lapse, satisfaction, conduct risk, agent quality, and service recovery features.';
comment on column public.customer_complaints.customer_complaint_id is 'Primary key for the complaint.';
comment on column public.customer_complaints.customer_id is 'Customer who raised or is associated with the complaint.';
comment on column public.customer_complaints.policy_id is 'Policy associated with the complaint, if applicable.';
comment on column public.customer_complaints.claim_id is 'Claim associated with the complaint, if applicable.';
comment on column public.customer_complaints.agent_id is 'Agent associated with the complaint, if applicable.';
comment on column public.customer_complaints.complaint_date is 'Date the complaint was received.';
comment on column public.customer_complaints.complaint_channel is 'Channel through which the complaint was received.';
comment on column public.customer_complaints.complaint_category is 'Business category of the complaint.';
comment on column public.customer_complaints.severity is 'Operational severity assigned to the complaint.';
comment on column public.customer_complaints.status is 'Current complaint handling status.';
comment on column public.customer_complaints.resolution_date is 'Date the complaint was resolved.';
comment on column public.customer_complaints.resolution_days is 'Number of calendar days to resolution.';
comment on column public.customer_complaints.sentiment_score is 'Text or handler-derived sentiment score from -1 to 1.';
comment on column public.customer_complaints.complaint_text is 'Complaint narrative for NLP features.';
comment on column public.customer_complaints.created_at is 'Timestamp when the record was created.';
comment on column public.customer_complaints.updated_at is 'Timestamp when the record was last updated.';

create table if not exists public.customer_satisfaction_surveys (
  customer_satisfaction_survey_id uuid primary key default gen_random_uuid(),
  customer_id uuid not null references public.customers(customer_id) on delete cascade,
  policy_id uuid references public.policies(policy_id) on delete set null,
  claim_id uuid references public.claims(claim_id) on delete set null,
  agent_id uuid references public.agents(agent_id) on delete set null,
  survey_date date not null,
  survey_type text not null,
  channel text check (channel is null or channel in ('email', 'sms', 'web', 'mobile_app', 'phone')),
  satisfaction_score integer check (satisfaction_score is null or satisfaction_score between 1 and 5),
  effort_score integer check (effort_score is null or effort_score between 1 and 7),
  response_text text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

comment on table public.customer_satisfaction_surveys is 'Customer satisfaction and effort survey responses for churn, service quality, and agent performance features.';
comment on column public.customer_satisfaction_surveys.customer_satisfaction_survey_id is 'Primary key for the satisfaction survey response.';
comment on column public.customer_satisfaction_surveys.customer_id is 'Customer who responded to the survey.';
comment on column public.customer_satisfaction_surveys.policy_id is 'Policy context for the survey, if applicable.';
comment on column public.customer_satisfaction_surveys.claim_id is 'Claim context for the survey, if applicable.';
comment on column public.customer_satisfaction_surveys.agent_id is 'Agent context for the survey, if applicable.';
comment on column public.customer_satisfaction_surveys.survey_date is 'Date the survey response was captured.';
comment on column public.customer_satisfaction_surveys.survey_type is 'Type of survey such as onboarding, claim, renewal, or service.';
comment on column public.customer_satisfaction_surveys.channel is 'Survey response channel.';
comment on column public.customer_satisfaction_surveys.satisfaction_score is 'Satisfaction score from 1 to 5.';
comment on column public.customer_satisfaction_surveys.effort_score is 'Customer effort score from 1 to 7.';
comment on column public.customer_satisfaction_surveys.response_text is 'Open-ended survey response text.';
comment on column public.customer_satisfaction_surveys.created_at is 'Timestamp when the record was created.';
comment on column public.customer_satisfaction_surveys.updated_at is 'Timestamp when the record was last updated.';

create table if not exists public.customer_nps (
  customer_nps_id uuid primary key default gen_random_uuid(),
  customer_id uuid not null references public.customers(customer_id) on delete cascade,
  survey_date date not null,
  touchpoint text not null,
  nps_score integer not null check (nps_score between 0 and 10),
  nps_group text generated always as (
    case
      when nps_score >= 9 then 'promoter'
      when nps_score >= 7 then 'passive'
      else 'detractor'
    end
  ) stored,
  comment_text text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

comment on table public.customer_nps is 'Net promoter score responses for loyalty, churn, lapse, campaign response, and CLV modelling.';
comment on column public.customer_nps.customer_nps_id is 'Primary key for the NPS response.';
comment on column public.customer_nps.customer_id is 'Customer who provided the NPS score.';
comment on column public.customer_nps.survey_date is 'Date of the NPS response.';
comment on column public.customer_nps.touchpoint is 'Customer journey touchpoint associated with the NPS response.';
comment on column public.customer_nps.nps_score is 'Net promoter score from 0 to 10.';
comment on column public.customer_nps.nps_group is 'Generated NPS group: promoter, passive, or detractor.';
comment on column public.customer_nps.comment_text is 'Open-ended NPS comment.';
comment on column public.customer_nps.created_at is 'Timestamp when the record was created.';
comment on column public.customer_nps.updated_at is 'Timestamp when the record was last updated.';

create table if not exists public.customer_service_requests (
  customer_service_request_id uuid primary key default gen_random_uuid(),
  customer_id uuid not null references public.customers(customer_id) on delete cascade,
  policy_id uuid references public.policies(policy_id) on delete set null,
  claim_id uuid references public.claims(claim_id) on delete set null,
  assigned_agent_id uuid references public.agents(agent_id) on delete set null,
  request_ts timestamptz not null,
  request_type text not null,
  channel text not null check (channel in ('call_center', 'email', 'web', 'mobile_app', 'agent', 'chat', 'branch')),
  priority text not null check (priority in ('low', 'normal', 'high', 'urgent')),
  status text not null check (status in ('open', 'pending_customer', 'in_progress', 'resolved', 'closed', 'cancelled')),
  first_response_ts timestamptz,
  resolved_ts timestamptz,
  sla_breached boolean not null default false,
  service_summary text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

comment on table public.customer_service_requests is 'Customer servicing case records for service quality, churn, retention, agent productivity, and next-best-action features.';
comment on column public.customer_service_requests.customer_service_request_id is 'Primary key for the service request.';
comment on column public.customer_service_requests.customer_id is 'Customer associated with the request.';
comment on column public.customer_service_requests.policy_id is 'Policy associated with the request, if applicable.';
comment on column public.customer_service_requests.claim_id is 'Claim associated with the request, if applicable.';
comment on column public.customer_service_requests.assigned_agent_id is 'Agent assigned to the request, if any.';
comment on column public.customer_service_requests.request_ts is 'Timestamp when the request was created.';
comment on column public.customer_service_requests.request_type is 'Type of servicing request.';
comment on column public.customer_service_requests.channel is 'Channel through which the request was created.';
comment on column public.customer_service_requests.priority is 'Operational priority of the request.';
comment on column public.customer_service_requests.status is 'Current request status.';
comment on column public.customer_service_requests.first_response_ts is 'Timestamp of first response to the customer.';
comment on column public.customer_service_requests.resolved_ts is 'Timestamp when the request was resolved.';
comment on column public.customer_service_requests.sla_breached is 'Whether the request breached the service-level target.';
comment on column public.customer_service_requests.service_summary is 'Short servicing summary for text features.';
comment on column public.customer_service_requests.created_at is 'Timestamp when the record was created.';
comment on column public.customer_service_requests.updated_at is 'Timestamp when the record was last updated.';

-- ---------------------------------------------------------------------------
-- Policy lifecycle and sales funnel
-- ---------------------------------------------------------------------------

create table if not exists public.policy_events (
  policy_event_id uuid primary key default gen_random_uuid(),
  policy_id uuid not null references public.policies(policy_id) on delete cascade,
  customer_id uuid references public.customers(customer_id) on delete set null,
  agent_id uuid references public.agents(agent_id) on delete set null,
  event_ts timestamptz not null,
  event_type text not null,
  event_reason text,
  source_system text,
  old_status text,
  new_status text,
  premium_delta numeric(14,2),
  event_payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

comment on table public.policy_events is 'Policy lifecycle event stream for lapse prediction, churn, retention, renewal, and sequence modelling.';
comment on column public.policy_events.policy_event_id is 'Primary key for the policy event.';
comment on column public.policy_events.policy_id is 'Policy associated with the event.';
comment on column public.policy_events.customer_id is 'Customer associated with the event.';
comment on column public.policy_events.agent_id is 'Agent associated with the event.';
comment on column public.policy_events.event_ts is 'Timestamp when the policy event occurred.';
comment on column public.policy_events.event_type is 'Type of lifecycle event such as issue, endorsement, payment_change, renewal_notice, lapse_warning, or cancellation.';
comment on column public.policy_events.event_reason is 'Business reason for the event.';
comment on column public.policy_events.source_system is 'Operational source of the event.';
comment on column public.policy_events.old_status is 'Policy status before the event.';
comment on column public.policy_events.new_status is 'Policy status after the event.';
comment on column public.policy_events.premium_delta is 'Premium change associated with the event.';
comment on column public.policy_events.event_payload is 'Additional event attributes for feature engineering.';
comment on column public.policy_events.created_at is 'Timestamp when the record was created.';
comment on column public.policy_events.updated_at is 'Timestamp when the record was last updated.';

create table if not exists public.policy_renewals (
  policy_renewal_id uuid primary key default gen_random_uuid(),
  policy_id uuid not null references public.policies(policy_id) on delete cascade,
  prior_policy_id uuid references public.policies(policy_id) on delete set null,
  renewal_policy_id uuid references public.policies(policy_id) on delete set null,
  customer_id uuid not null references public.customers(customer_id) on delete cascade,
  agent_id uuid references public.agents(agent_id) on delete set null,
  renewal_cycle_date date not null,
  renewal_offer_date date,
  renewal_due_date date,
  renewal_status text not null check (renewal_status in ('pending', 'offered', 'accepted', 'declined', 'renewed', 'lapsed', 'cancelled')),
  offered_premium numeric(14,2),
  expiring_premium numeric(14,2),
  premium_change_pct numeric(9,4),
  retention_reason text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

comment on table public.policy_renewals is 'Renewal cycle records for persistency, policy lapse, customer churn, CLV, and retention intervention modelling.';
comment on column public.policy_renewals.policy_renewal_id is 'Primary key for the renewal cycle.';
comment on column public.policy_renewals.policy_id is 'Policy being renewed or evaluated.';
comment on column public.policy_renewals.prior_policy_id is 'Prior policy in a renewal chain, if applicable.';
comment on column public.policy_renewals.renewal_policy_id is 'Resulting renewal policy, if accepted and issued.';
comment on column public.policy_renewals.customer_id is 'Customer associated with the renewal.';
comment on column public.policy_renewals.agent_id is 'Agent responsible for the renewal, if any.';
comment on column public.policy_renewals.renewal_cycle_date is 'Date representing the renewal cycle.';
comment on column public.policy_renewals.renewal_offer_date is 'Date the renewal offer was made.';
comment on column public.policy_renewals.renewal_due_date is 'Date by which the renewal must be accepted or paid.';
comment on column public.policy_renewals.renewal_status is 'Current outcome or stage of the renewal cycle.';
comment on column public.policy_renewals.offered_premium is 'Premium offered for renewal.';
comment on column public.policy_renewals.expiring_premium is 'Premium on the expiring policy term.';
comment on column public.policy_renewals.premium_change_pct is 'Percentage premium change from expiring to offered premium.';
comment on column public.policy_renewals.retention_reason is 'Reason for renewal outcome or retention intervention result.';
comment on column public.policy_renewals.created_at is 'Timestamp when the record was created.';
comment on column public.policy_renewals.updated_at is 'Timestamp when the record was last updated.';

create table if not exists public.policy_lapse_events (
  policy_lapse_event_id uuid primary key default gen_random_uuid(),
  policy_id uuid not null references public.policies(policy_id) on delete cascade,
  customer_id uuid not null references public.customers(customer_id) on delete cascade,
  agent_id uuid references public.agents(agent_id) on delete set null,
  lapse_event_date date not null,
  lapse_stage text not null check (lapse_stage in ('warning', 'grace_period', 'lapsed', 'reinstated', 'cancelled')),
  missed_payment_count integer not null default 0 check (missed_payment_count >= 0),
  days_past_due integer check (days_past_due is null or days_past_due >= 0),
  reinstatement_date date,
  lapse_reason text,
  intervention_type text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

comment on table public.policy_lapse_events is 'Policy lapse lifecycle records for lapse labels, retention intervention tracking, and survival-style modelling.';
comment on column public.policy_lapse_events.policy_lapse_event_id is 'Primary key for the policy lapse event.';
comment on column public.policy_lapse_events.policy_id is 'Policy associated with the lapse event.';
comment on column public.policy_lapse_events.customer_id is 'Customer associated with the lapse event.';
comment on column public.policy_lapse_events.agent_id is 'Agent associated with the lapse event, if any.';
comment on column public.policy_lapse_events.lapse_event_date is 'Date of the lapse event or warning.';
comment on column public.policy_lapse_events.lapse_stage is 'Stage of the lapse lifecycle.';
comment on column public.policy_lapse_events.missed_payment_count is 'Count of missed payments at event time.';
comment on column public.policy_lapse_events.days_past_due is 'Days past due at event time.';
comment on column public.policy_lapse_events.reinstatement_date is 'Date policy was reinstated, if applicable.';
comment on column public.policy_lapse_events.lapse_reason is 'Business reason or inferred reason for lapse.';
comment on column public.policy_lapse_events.intervention_type is 'Retention intervention attempted before or after lapse.';
comment on column public.policy_lapse_events.created_at is 'Timestamp when the record was created.';
comment on column public.policy_lapse_events.updated_at is 'Timestamp when the record was last updated.';

create table if not exists public.quotes (
  quote_id uuid primary key default gen_random_uuid(),
  quote_number text not null unique,
  lead_id uuid references public.leads(lead_id) on delete set null,
  opportunity_id uuid references public.opportunities(opportunity_id) on delete set null,
  customer_id uuid references public.customers(customer_id) on delete set null,
  agent_id uuid references public.agents(agent_id) on delete set null,
  product_id uuid not null references public.products(product_id) on delete restrict,
  campaign_id uuid references public.campaigns(campaign_id) on delete set null,
  quote_date date not null,
  quote_status text not null check (quote_status in ('draft', 'presented', 'accepted', 'declined', 'expired', 'withdrawn')),
  quoted_premium numeric(14,2) check (quoted_premium is null or quoted_premium >= 0),
  sum_assured numeric(14,2),
  quote_channel text,
  decline_reason text,
  quote_features jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

comment on table public.quotes is 'Quote records for lead conversion, propensity, next-best-product, price sensitivity, and sales funnel modelling.';
comment on column public.quotes.quote_id is 'Primary key for the quote.';
comment on column public.quotes.quote_number is 'Human-readable quote identifier.';
comment on column public.quotes.lead_id is 'Lead that generated the quote, if applicable.';
comment on column public.quotes.opportunity_id is 'Opportunity associated with the quote, if applicable.';
comment on column public.quotes.customer_id is 'Customer or prospect associated with the quote.';
comment on column public.quotes.agent_id is 'Agent who created or presented the quote.';
comment on column public.quotes.product_id is 'Quoted product.';
comment on column public.quotes.campaign_id is 'Campaign attribution for the quote, if applicable.';
comment on column public.quotes.quote_date is 'Date the quote was created.';
comment on column public.quotes.quote_status is 'Current quote outcome or stage.';
comment on column public.quotes.quoted_premium is 'Premium amount quoted to the customer.';
comment on column public.quotes.sum_assured is 'Quoted coverage or benefit amount.';
comment on column public.quotes.quote_channel is 'Channel through which the quote was created or presented.';
comment on column public.quotes.decline_reason is 'Reason the quote was declined, if known.';
comment on column public.quotes.quote_features is 'Additional quote attributes for ML features.';
comment on column public.quotes.created_at is 'Timestamp when the record was created.';
comment on column public.quotes.updated_at is 'Timestamp when the record was last updated.';

create table if not exists public.proposals (
  proposal_id uuid primary key default gen_random_uuid(),
  proposal_number text not null unique,
  quote_id uuid references public.quotes(quote_id) on delete set null,
  opportunity_id uuid references public.opportunities(opportunity_id) on delete set null,
  customer_id uuid references public.customers(customer_id) on delete set null,
  agent_id uuid references public.agents(agent_id) on delete set null,
  product_id uuid not null references public.products(product_id) on delete restrict,
  proposal_date date not null,
  proposal_status text not null check (proposal_status in ('created', 'presented', 'accepted', 'declined', 'expired', 'converted')),
  proposed_premium numeric(14,2) check (proposed_premium is null or proposed_premium >= 0),
  proposed_sum_assured numeric(14,2),
  proposal_payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

comment on table public.proposals is 'Proposal records between quote and application for sales funnel, next-best-product, and conversion modelling.';
comment on column public.proposals.proposal_id is 'Primary key for the proposal.';
comment on column public.proposals.proposal_number is 'Human-readable proposal identifier.';
comment on column public.proposals.quote_id is 'Quote that led to the proposal, if applicable.';
comment on column public.proposals.opportunity_id is 'Opportunity associated with the proposal.';
comment on column public.proposals.customer_id is 'Customer or prospect associated with the proposal.';
comment on column public.proposals.agent_id is 'Agent who presented the proposal.';
comment on column public.proposals.product_id is 'Proposed product.';
comment on column public.proposals.proposal_date is 'Date the proposal was created or presented.';
comment on column public.proposals.proposal_status is 'Current proposal status.';
comment on column public.proposals.proposed_premium is 'Premium amount proposed to the customer.';
comment on column public.proposals.proposed_sum_assured is 'Proposed coverage or benefit amount.';
comment on column public.proposals.proposal_payload is 'Additional proposal details for feature engineering.';
comment on column public.proposals.created_at is 'Timestamp when the record was created.';
comment on column public.proposals.updated_at is 'Timestamp when the record was last updated.';

create table if not exists public.applications (
  application_id uuid primary key default gen_random_uuid(),
  application_number text not null unique,
  proposal_id uuid references public.proposals(proposal_id) on delete set null,
  quote_id uuid references public.quotes(quote_id) on delete set null,
  opportunity_id uuid references public.opportunities(opportunity_id) on delete set null,
  customer_id uuid not null references public.customers(customer_id) on delete cascade,
  agent_id uuid references public.agents(agent_id) on delete set null,
  product_id uuid not null references public.products(product_id) on delete restrict,
  application_date date not null,
  application_status text not null check (application_status in ('submitted', 'in_underwriting', 'approved', 'declined', 'withdrawn', 'issued')),
  requested_premium numeric(14,2),
  requested_sum_assured numeric(14,2),
  medical_required boolean not null default false,
  application_payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

comment on table public.applications is 'Insurance applications for underwriting, lead conversion, policy issue probability, and next-best-action modelling.';
comment on column public.applications.application_id is 'Primary key for the application.';
comment on column public.applications.application_number is 'Human-readable application identifier.';
comment on column public.applications.proposal_id is 'Proposal that led to the application, if applicable.';
comment on column public.applications.quote_id is 'Quote that led to the application, if applicable.';
comment on column public.applications.opportunity_id is 'Opportunity associated with the application.';
comment on column public.applications.customer_id is 'Customer applying for coverage.';
comment on column public.applications.agent_id is 'Agent associated with the application.';
comment on column public.applications.product_id is 'Applied-for product.';
comment on column public.applications.application_date is 'Date the application was submitted.';
comment on column public.applications.application_status is 'Current application status.';
comment on column public.applications.requested_premium is 'Requested or illustrated premium amount.';
comment on column public.applications.requested_sum_assured is 'Requested coverage or benefit amount.';
comment on column public.applications.medical_required is 'Whether medical evidence or review is required.';
comment on column public.applications.application_payload is 'Additional application attributes for feature engineering.';
comment on column public.applications.created_at is 'Timestamp when the record was created.';
comment on column public.applications.updated_at is 'Timestamp when the record was last updated.';

create table if not exists public.underwriting_decisions (
  underwriting_decision_id uuid primary key default gen_random_uuid(),
  application_id uuid not null references public.applications(application_id) on delete cascade,
  customer_id uuid not null references public.customers(customer_id) on delete cascade,
  product_id uuid not null references public.products(product_id) on delete restrict,
  decision_date date not null,
  decision_status text not null check (decision_status in ('approved_standard', 'approved_rated', 'approved_exclusion', 'postponed', 'declined', 'withdrawn')),
  risk_class text,
  rating_factor numeric(9,4),
  exclusion_applied boolean not null default false,
  underwriting_reason text,
  decision_payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

comment on table public.underwriting_decisions is 'Underwriting outcomes for issue probability, risk selection, fraud risk, lapse, claims, and pricing-related ML features.';
comment on column public.underwriting_decisions.underwriting_decision_id is 'Primary key for the underwriting decision.';
comment on column public.underwriting_decisions.application_id is 'Application reviewed by underwriting.';
comment on column public.underwriting_decisions.customer_id is 'Customer associated with the decision.';
comment on column public.underwriting_decisions.product_id is 'Product associated with the decision.';
comment on column public.underwriting_decisions.decision_date is 'Date the underwriting decision was made.';
comment on column public.underwriting_decisions.decision_status is 'Underwriting decision outcome.';
comment on column public.underwriting_decisions.risk_class is 'Underwriting risk class or band.';
comment on column public.underwriting_decisions.rating_factor is 'Premium rating factor or loading applied by underwriting.';
comment on column public.underwriting_decisions.exclusion_applied is 'Whether a coverage exclusion was applied.';
comment on column public.underwriting_decisions.underwriting_reason is 'Reason for decision, loading, exclusion, postponement, or decline.';
comment on column public.underwriting_decisions.decision_payload is 'Additional underwriting attributes for feature engineering.';
comment on column public.underwriting_decisions.created_at is 'Timestamp when the record was created.';
comment on column public.underwriting_decisions.updated_at is 'Timestamp when the record was last updated.';

-- ---------------------------------------------------------------------------
-- Agent activity, compensation, capability, and attrition
-- ---------------------------------------------------------------------------

create table if not exists public.agent_calls (
  agent_call_id uuid primary key default gen_random_uuid(),
  agent_id uuid not null references public.agents(agent_id) on delete cascade,
  customer_id uuid references public.customers(customer_id) on delete set null,
  lead_id uuid references public.leads(lead_id) on delete set null,
  opportunity_id uuid references public.opportunities(opportunity_id) on delete set null,
  campaign_id uuid references public.campaigns(campaign_id) on delete set null,
  call_ts timestamptz not null,
  call_direction text not null check (call_direction in ('inbound', 'outbound')),
  call_outcome text not null,
  duration_seconds integer check (duration_seconds is null or duration_seconds >= 0),
  sentiment_score numeric(5,2) check (sentiment_score is null or sentiment_score between -1 and 1),
  next_step_date date,
  call_notes text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

comment on table public.agent_calls is 'Agent call activity for productivity, next-best-customer, lead conversion, churn intervention, and agent performance modelling.';
comment on column public.agent_calls.agent_call_id is 'Primary key for the agent call.';
comment on column public.agent_calls.agent_id is 'Agent who made or received the call.';
comment on column public.agent_calls.customer_id is 'Customer associated with the call.';
comment on column public.agent_calls.lead_id is 'Lead associated with the call, if applicable.';
comment on column public.agent_calls.opportunity_id is 'Opportunity associated with the call, if applicable.';
comment on column public.agent_calls.campaign_id is 'Campaign associated with the call, if applicable.';
comment on column public.agent_calls.call_ts is 'Timestamp when the call occurred.';
comment on column public.agent_calls.call_direction is 'Inbound or outbound call direction.';
comment on column public.agent_calls.call_outcome is 'Call outcome such as contacted, no_answer, appointment_set, quote_requested, or declined.';
comment on column public.agent_calls.duration_seconds is 'Duration of the call in seconds.';
comment on column public.agent_calls.sentiment_score is 'Call sentiment score from -1 to 1.';
comment on column public.agent_calls.next_step_date is 'Date of scheduled follow-up, if any.';
comment on column public.agent_calls.call_notes is 'Call notes for text features.';
comment on column public.agent_calls.created_at is 'Timestamp when the record was created.';
comment on column public.agent_calls.updated_at is 'Timestamp when the record was last updated.';

create table if not exists public.agent_meetings (
  agent_meeting_id uuid primary key default gen_random_uuid(),
  agent_id uuid not null references public.agents(agent_id) on delete cascade,
  customer_id uuid references public.customers(customer_id) on delete set null,
  lead_id uuid references public.leads(lead_id) on delete set null,
  opportunity_id uuid references public.opportunities(opportunity_id) on delete set null,
  meeting_ts timestamptz not null,
  meeting_type text not null check (meeting_type in ('initial_consultation', 'needs_analysis', 'proposal_review', 'application', 'servicing', 'renewal', 'claim_support')),
  meeting_channel text not null check (meeting_channel in ('in_person', 'video', 'phone', 'branch', 'webinar')),
  meeting_outcome text,
  duration_minutes integer check (duration_minutes is null or duration_minutes >= 0),
  product_id uuid references public.products(product_id) on delete set null,
  meeting_notes text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

comment on table public.agent_meetings is 'Agent-customer meeting records for productivity, conversion, next-best-customer, and agent performance modelling.';
comment on column public.agent_meetings.agent_meeting_id is 'Primary key for the agent meeting.';
comment on column public.agent_meetings.agent_id is 'Agent who conducted the meeting.';
comment on column public.agent_meetings.customer_id is 'Customer associated with the meeting.';
comment on column public.agent_meetings.lead_id is 'Lead associated with the meeting, if applicable.';
comment on column public.agent_meetings.opportunity_id is 'Opportunity associated with the meeting, if applicable.';
comment on column public.agent_meetings.meeting_ts is 'Timestamp when the meeting occurred.';
comment on column public.agent_meetings.meeting_type is 'Business purpose of the meeting.';
comment on column public.agent_meetings.meeting_channel is 'Meeting channel or location type.';
comment on column public.agent_meetings.meeting_outcome is 'Outcome of the meeting.';
comment on column public.agent_meetings.duration_minutes is 'Meeting duration in minutes.';
comment on column public.agent_meetings.product_id is 'Product discussed during the meeting, if applicable.';
comment on column public.agent_meetings.meeting_notes is 'Meeting notes for text features.';
comment on column public.agent_meetings.created_at is 'Timestamp when the record was created.';
comment on column public.agent_meetings.updated_at is 'Timestamp when the record was last updated.';

create table if not exists public.agent_targets (
  agent_target_id uuid primary key default gen_random_uuid(),
  agent_id uuid not null references public.agents(agent_id) on delete cascade,
  target_period_start date not null,
  target_period_end date not null,
  target_type text not null check (target_type in ('premium', 'policies', 'leads', 'meetings', 'persistency', 'product_mix', 'campaign')),
  product_id uuid references public.products(product_id) on delete set null,
  target_value numeric(14,4) not null,
  actual_value numeric(14,4),
  attainment_pct numeric(9,4),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  check (target_period_end >= target_period_start)
);

comment on table public.agent_targets is 'Agent targets and attainment for agent performance prediction, coaching, attrition, and next-best-customer allocation.';
comment on column public.agent_targets.agent_target_id is 'Primary key for the agent target.';
comment on column public.agent_targets.agent_id is 'Agent assigned the target.';
comment on column public.agent_targets.target_period_start is 'Start date of the target period.';
comment on column public.agent_targets.target_period_end is 'End date of the target period.';
comment on column public.agent_targets.target_type is 'Type of target assigned to the agent.';
comment on column public.agent_targets.product_id is 'Product-specific target, if applicable.';
comment on column public.agent_targets.target_value is 'Target value for the period.';
comment on column public.agent_targets.actual_value is 'Actual achieved value for the period.';
comment on column public.agent_targets.attainment_pct is 'Actual divided by target as a percentage or ratio.';
comment on column public.agent_targets.created_at is 'Timestamp when the record was created.';
comment on column public.agent_targets.updated_at is 'Timestamp when the record was last updated.';

create table if not exists public.agent_commissions (
  agent_commission_id uuid primary key default gen_random_uuid(),
  agent_id uuid not null references public.agents(agent_id) on delete cascade,
  policy_id uuid references public.policies(policy_id) on delete set null,
  product_id uuid references public.products(product_id) on delete set null,
  commission_period date not null,
  commission_type text not null check (commission_type in ('new_business', 'renewal', 'trail', 'bonus', 'chargeback', 'adjustment')),
  premium_basis_amount numeric(14,2),
  commission_rate numeric(9,4),
  commission_amount numeric(14,2) not null,
  paid_date date,
  chargeback_flag boolean not null default false,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

comment on table public.agent_commissions is 'Agent commission records for compensation features, production quality, persistency, attrition, and agent performance modelling.';
comment on column public.agent_commissions.agent_commission_id is 'Primary key for the commission record.';
comment on column public.agent_commissions.agent_id is 'Agent earning the commission.';
comment on column public.agent_commissions.policy_id is 'Policy associated with the commission, if applicable.';
comment on column public.agent_commissions.product_id is 'Product associated with the commission, if applicable.';
comment on column public.agent_commissions.commission_period is 'Commission accounting period.';
comment on column public.agent_commissions.commission_type is 'Type of commission or adjustment.';
comment on column public.agent_commissions.premium_basis_amount is 'Premium basis used for commission calculation.';
comment on column public.agent_commissions.commission_rate is 'Commission rate used for calculation.';
comment on column public.agent_commissions.commission_amount is 'Commission amount for the record.';
comment on column public.agent_commissions.paid_date is 'Date the commission was paid.';
comment on column public.agent_commissions.chargeback_flag is 'Whether the commission is a chargeback or tied to chargeback risk.';
comment on column public.agent_commissions.created_at is 'Timestamp when the record was created.';
comment on column public.agent_commissions.updated_at is 'Timestamp when the record was last updated.';

create table if not exists public.agent_training (
  agent_training_id uuid primary key default gen_random_uuid(),
  agent_id uuid not null references public.agents(agent_id) on delete cascade,
  training_code text not null,
  training_name text not null,
  training_category text not null,
  assigned_date date,
  completed_date date,
  completion_status text not null check (completion_status in ('assigned', 'in_progress', 'completed', 'expired', 'waived')),
  assessment_score numeric(6,2),
  certification_flag boolean not null default false,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

comment on table public.agent_training is 'Agent training and certification records for performance, compliance, product readiness, and attrition modelling.';
comment on column public.agent_training.agent_training_id is 'Primary key for the agent training record.';
comment on column public.agent_training.agent_id is 'Agent assigned or completing the training.';
comment on column public.agent_training.training_code is 'Training course code.';
comment on column public.agent_training.training_name is 'Training course name.';
comment on column public.agent_training.training_category is 'Training category such as product, compliance, sales, or leadership.';
comment on column public.agent_training.assigned_date is 'Date training was assigned.';
comment on column public.agent_training.completed_date is 'Date training was completed.';
comment on column public.agent_training.completion_status is 'Training completion status.';
comment on column public.agent_training.assessment_score is 'Training assessment score.';
comment on column public.agent_training.certification_flag is 'Whether the training confers or supports certification.';
comment on column public.agent_training.created_at is 'Timestamp when the record was created.';
comment on column public.agent_training.updated_at is 'Timestamp when the record was last updated.';

create table if not exists public.agent_attrition_events (
  agent_attrition_event_id uuid primary key default gen_random_uuid(),
  agent_id uuid not null references public.agents(agent_id) on delete cascade,
  event_date date not null,
  attrition_stage text not null check (attrition_stage in ('risk_signal', 'notice', 'terminated', 'inactive', 'reactivated', 'retained')),
  attrition_reason text,
  voluntary_flag boolean,
  manager_intervention_flag boolean not null default false,
  intervention_notes text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

comment on table public.agent_attrition_events is 'Agent attrition and retention intervention events for attrition prediction and workforce planning.';
comment on column public.agent_attrition_events.agent_attrition_event_id is 'Primary key for the agent attrition event.';
comment on column public.agent_attrition_events.agent_id is 'Agent associated with the attrition event.';
comment on column public.agent_attrition_events.event_date is 'Date of the attrition signal, notice, exit, reactivation, or retention outcome.';
comment on column public.agent_attrition_events.attrition_stage is 'Stage of the agent attrition lifecycle.';
comment on column public.agent_attrition_events.attrition_reason is 'Reason for attrition or risk signal.';
comment on column public.agent_attrition_events.voluntary_flag is 'Whether the attrition event is voluntary, if known.';
comment on column public.agent_attrition_events.manager_intervention_flag is 'Whether management intervention occurred.';
comment on column public.agent_attrition_events.intervention_notes is 'Notes about retention or coaching intervention.';
comment on column public.agent_attrition_events.created_at is 'Timestamp when the record was created.';
comment on column public.agent_attrition_events.updated_at is 'Timestamp when the record was last updated.';

-- ---------------------------------------------------------------------------
-- Claims enrichment and fraud risk
-- ---------------------------------------------------------------------------

create table if not exists public.claim_parties (
  claim_party_id uuid primary key default gen_random_uuid(),
  claim_id uuid not null references public.claims(claim_id) on delete cascade,
  party_id uuid references public.parties(party_id) on delete set null,
  customer_id uuid references public.customers(customer_id) on delete set null,
  role_type text not null check (role_type in ('claimant', 'insured', 'beneficiary', 'provider', 'repairer', 'witness', 'third_party', 'adjuster')),
  relationship_to_insured text,
  provider_specialty text,
  involvement_notes text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

comment on table public.claim_parties is 'Parties involved in a claim for network, fraud risk, claims severity, and operational analytics.';
comment on column public.claim_parties.claim_party_id is 'Primary key for the claim-party relationship.';
comment on column public.claim_parties.claim_id is 'Claim associated with the party.';
comment on column public.claim_parties.party_id is 'Party involved in the claim.';
comment on column public.claim_parties.customer_id is 'Customer involved in the claim, if applicable.';
comment on column public.claim_parties.role_type is 'Role of the party in the claim.';
comment on column public.claim_parties.relationship_to_insured is 'Relationship between the party and insured customer.';
comment on column public.claim_parties.provider_specialty is 'Specialty for provider-style claim parties.';
comment on column public.claim_parties.involvement_notes is 'Narrative notes about claim party involvement.';
comment on column public.claim_parties.created_at is 'Timestamp when the record was created.';
comment on column public.claim_parties.updated_at is 'Timestamp when the record was last updated.';

create table if not exists public.claim_assessments (
  claim_assessment_id uuid primary key default gen_random_uuid(),
  claim_id uuid not null references public.claims(claim_id) on delete cascade,
  assessed_by_agent_id uuid references public.agents(agent_id) on delete set null,
  assessment_date date not null,
  assessment_type text not null check (assessment_type in ('initial', 'medical', 'damage', 'liability', 'fraud_review', 'settlement', 'reopen_review')),
  severity_score numeric(8,4) check (severity_score is null or severity_score between 0 and 1),
  liability_pct numeric(8,4) check (liability_pct is null or liability_pct between 0 and 1),
  estimated_loss_amount numeric(14,2),
  recommended_reserve_amount numeric(14,2),
  assessment_outcome text,
  assessment_notes text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

comment on table public.claim_assessments is 'Claim assessments for severity prediction, reserve adequacy, settlement modelling, and fraud review features.';
comment on column public.claim_assessments.claim_assessment_id is 'Primary key for the claim assessment.';
comment on column public.claim_assessments.claim_id is 'Claim being assessed.';
comment on column public.claim_assessments.assessed_by_agent_id is 'Agent or adjuster represented by an agent record who performed the assessment.';
comment on column public.claim_assessments.assessment_date is 'Date of the assessment.';
comment on column public.claim_assessments.assessment_type is 'Type of claim assessment.';
comment on column public.claim_assessments.severity_score is 'Normalized assessment severity score from 0 to 1.';
comment on column public.claim_assessments.liability_pct is 'Estimated liability percentage from 0 to 1.';
comment on column public.claim_assessments.estimated_loss_amount is 'Estimated total loss amount from assessment.';
comment on column public.claim_assessments.recommended_reserve_amount is 'Recommended reserve amount from assessment.';
comment on column public.claim_assessments.assessment_outcome is 'Assessment outcome or recommendation.';
comment on column public.claim_assessments.assessment_notes is 'Assessment notes for text features.';
comment on column public.claim_assessments.created_at is 'Timestamp when the record was created.';
comment on column public.claim_assessments.updated_at is 'Timestamp when the record was last updated.';

create table if not exists public.claim_fraud_indicators (
  claim_fraud_indicator_id uuid primary key default gen_random_uuid(),
  claim_id uuid not null references public.claims(claim_id) on delete cascade,
  customer_id uuid references public.customers(customer_id) on delete set null,
  indicator_date date not null,
  indicator_type text not null,
  indicator_source text not null check (indicator_source in ('rules', 'model', 'adjuster', 'provider_network', 'external', 'manual_review')),
  indicator_score numeric(8,4) check (indicator_score is null or indicator_score between 0 and 1),
  severity text check (severity is null or severity in ('low', 'medium', 'high', 'critical')),
  resolved_flag boolean not null default false,
  resolution_outcome text,
  indicator_payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

comment on table public.claim_fraud_indicators is 'Fraud indicators and investigation signals for claim fraud risk detection and investigator workflow features.';
comment on column public.claim_fraud_indicators.claim_fraud_indicator_id is 'Primary key for the fraud indicator.';
comment on column public.claim_fraud_indicators.claim_id is 'Claim associated with the fraud indicator.';
comment on column public.claim_fraud_indicators.customer_id is 'Customer associated with the claim fraud indicator.';
comment on column public.claim_fraud_indicators.indicator_date is 'Date the fraud indicator was raised.';
comment on column public.claim_fraud_indicators.indicator_type is 'Type of fraud signal or rule.';
comment on column public.claim_fraud_indicators.indicator_source is 'Source that raised the fraud indicator.';
comment on column public.claim_fraud_indicators.indicator_score is 'Normalized fraud indicator score from 0 to 1.';
comment on column public.claim_fraud_indicators.severity is 'Operational severity of the fraud indicator.';
comment on column public.claim_fraud_indicators.resolved_flag is 'Whether the fraud indicator has been resolved.';
comment on column public.claim_fraud_indicators.resolution_outcome is 'Outcome of review or investigation.';
comment on column public.claim_fraud_indicators.indicator_payload is 'Additional fraud indicator attributes for ML and investigation.';
comment on column public.claim_fraud_indicators.created_at is 'Timestamp when the record was created.';
comment on column public.claim_fraud_indicators.updated_at is 'Timestamp when the record was last updated.';

-- ---------------------------------------------------------------------------
-- Model feature, score, prediction, and action serving layer
-- ---------------------------------------------------------------------------

create table if not exists public.model_features (
  model_feature_id uuid primary key default gen_random_uuid(),
  feature_set_name text not null,
  feature_set_version text not null,
  entity_type text not null check (entity_type in ('customer', 'policy', 'agent', 'lead', 'opportunity', 'claim', 'campaign', 'product')),
  entity_id uuid not null,
  customer_id uuid references public.customers(customer_id) on delete set null,
  policy_id uuid references public.policies(policy_id) on delete set null,
  agent_id uuid references public.agents(agent_id) on delete set null,
  lead_id uuid references public.leads(lead_id) on delete set null,
  opportunity_id uuid references public.opportunities(opportunity_id) on delete set null,
  claim_id uuid references public.claims(claim_id) on delete set null,
  campaign_id uuid references public.campaigns(campaign_id) on delete set null,
  product_id uuid references public.products(product_id) on delete set null,
  feature_date date not null,
  prediction_horizon_days integer check (prediction_horizon_days is null or prediction_horizon_days > 0),
  features jsonb not null,
  label_name text,
  label_value jsonb,
  data_split text check (data_split is null or data_split in ('train', 'validation', 'test', 'score')),
  feature_hash text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (feature_set_name, feature_set_version, entity_type, entity_id, feature_date, prediction_horizon_days)
);

comment on table public.model_features is 'Feature store style table for training data snapshots and scoring payloads across customer, policy, agent, lead, claim, campaign, and product entities.';
comment on column public.model_features.model_feature_id is 'Primary key for the model feature record.';
comment on column public.model_features.feature_set_name is 'Logical name of the feature set.';
comment on column public.model_features.feature_set_version is 'Version of the feature set definition.';
comment on column public.model_features.entity_type is 'Primary entity type represented by this feature row.';
comment on column public.model_features.entity_id is 'Primary entity identifier represented by this feature row.';
comment on column public.model_features.customer_id is 'Customer foreign key when the feature row relates to a customer.';
comment on column public.model_features.policy_id is 'Policy foreign key when the feature row relates to a policy.';
comment on column public.model_features.agent_id is 'Agent foreign key when the feature row relates to an agent.';
comment on column public.model_features.lead_id is 'Lead foreign key when the feature row relates to a lead.';
comment on column public.model_features.opportunity_id is 'Opportunity foreign key when the feature row relates to an opportunity.';
comment on column public.model_features.claim_id is 'Claim foreign key when the feature row relates to a claim.';
comment on column public.model_features.campaign_id is 'Campaign foreign key when the feature row relates to a campaign.';
comment on column public.model_features.product_id is 'Product foreign key when the feature row relates to a product.';
comment on column public.model_features.feature_date is 'As-of date for feature values and label construction.';
comment on column public.model_features.prediction_horizon_days is 'Forward prediction horizon represented by the features and label.';
comment on column public.model_features.features is 'Feature vector payload stored as JSONB for training and scoring.';
comment on column public.model_features.label_name is 'Optional supervised learning label name.';
comment on column public.model_features.label_value is 'Optional supervised learning label value.';
comment on column public.model_features.data_split is 'Training split assignment for reproducible modelling.';
comment on column public.model_features.feature_hash is 'Hash of feature payload for reproducibility and drift checks.';
comment on column public.model_features.created_at is 'Timestamp when the record was created.';
comment on column public.model_features.updated_at is 'Timestamp when the record was last updated.';

create table if not exists public.model_scores (
  model_score_id uuid primary key default gen_random_uuid(),
  model_name text not null,
  model_version text not null,
  model_feature_id uuid references public.model_features(model_feature_id) on delete set null,
  entity_type text not null check (entity_type in ('customer', 'policy', 'agent', 'lead', 'opportunity', 'claim', 'campaign', 'product')),
  entity_id uuid not null,
  score_ts timestamptz not null default now(),
  score_name text not null,
  score_value numeric(12,6) not null,
  probability numeric(12,6) check (probability is null or probability between 0 and 1),
  score_band text,
  rank_within_segment integer check (rank_within_segment is null or rank_within_segment > 0),
  explanation jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

comment on table public.model_scores is 'Reusable model score records for propensity, churn, lapse, conversion, claims, fraud, CLV, campaign response, and agent models.';
comment on column public.model_scores.model_score_id is 'Primary key for the model score.';
comment on column public.model_scores.model_name is 'Name of the model that produced the score.';
comment on column public.model_scores.model_version is 'Version of the model that produced the score.';
comment on column public.model_scores.model_feature_id is 'Feature row used to produce the score, if tracked.';
comment on column public.model_scores.entity_type is 'Entity type scored by the model.';
comment on column public.model_scores.entity_id is 'Entity identifier scored by the model.';
comment on column public.model_scores.score_ts is 'Timestamp when the score was generated.';
comment on column public.model_scores.score_name is 'Name of the score such as propensity_to_buy, lapse_risk, or fraud_risk.';
comment on column public.model_scores.score_value is 'Numeric score value generated by the model.';
comment on column public.model_scores.probability is 'Probability value when the model output is probabilistic.';
comment on column public.model_scores.score_band is 'Business-friendly score band such as low, medium, high, or very_high.';
comment on column public.model_scores.rank_within_segment is 'Optional rank within a segment for prioritization.';
comment on column public.model_scores.explanation is 'Model drivers, feature attributions, or local explanation payload.';
comment on column public.model_scores.created_at is 'Timestamp when the record was created.';
comment on column public.model_scores.updated_at is 'Timestamp when the record was last updated.';

create table if not exists public.model_predictions (
  model_prediction_id uuid primary key default gen_random_uuid(),
  model_score_id uuid references public.model_scores(model_score_id) on delete set null,
  model_name text not null,
  model_version text not null,
  prediction_type text not null check (prediction_type in ('propensity_to_buy', 'next_best_product', 'customer_churn', 'policy_lapse', 'agent_performance', 'next_best_customer', 'lead_conversion', 'agent_attrition', 'claims', 'fraud_risk', 'customer_lifetime_value', 'campaign_response')),
  entity_type text not null check (entity_type in ('customer', 'policy', 'agent', 'lead', 'opportunity', 'claim', 'campaign', 'product')),
  entity_id uuid not null,
  prediction_ts timestamptz not null default now(),
  prediction_horizon_days integer check (prediction_horizon_days is null or prediction_horizon_days > 0),
  predicted_label text,
  predicted_value numeric(18,6),
  probability numeric(12,6) check (probability is null or probability between 0 and 1),
  confidence_score numeric(12,6) check (confidence_score is null or confidence_score between 0 and 1),
  recommended_product_id uuid references public.products(product_id) on delete set null,
  prediction_payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

comment on table public.model_predictions is 'Model prediction outputs for operational use cases including next best product, churn, lapse, fraud, CLV, conversion, response, and agent predictions.';
comment on column public.model_predictions.model_prediction_id is 'Primary key for the model prediction.';
comment on column public.model_predictions.model_score_id is 'Underlying model score used by the prediction, if applicable.';
comment on column public.model_predictions.model_name is 'Name of the model that generated the prediction.';
comment on column public.model_predictions.model_version is 'Version of the model that generated the prediction.';
comment on column public.model_predictions.prediction_type is 'Business prediction type supported by the ML layer.';
comment on column public.model_predictions.entity_type is 'Entity type predicted by the model.';
comment on column public.model_predictions.entity_id is 'Entity identifier predicted by the model.';
comment on column public.model_predictions.prediction_ts is 'Timestamp when the prediction was generated.';
comment on column public.model_predictions.prediction_horizon_days is 'Forward horizon for the prediction.';
comment on column public.model_predictions.predicted_label is 'Predicted class or business label.';
comment on column public.model_predictions.predicted_value is 'Predicted numeric value such as CLV, claim amount, or expected premium.';
comment on column public.model_predictions.probability is 'Prediction probability when applicable.';
comment on column public.model_predictions.confidence_score is 'Model confidence score from 0 to 1.';
comment on column public.model_predictions.recommended_product_id is 'Recommended product for next-best-product predictions.';
comment on column public.model_predictions.prediction_payload is 'Additional model output, alternatives, and explanations.';
comment on column public.model_predictions.created_at is 'Timestamp when the record was created.';
comment on column public.model_predictions.updated_at is 'Timestamp when the record was last updated.';

create table if not exists public.next_best_actions (
  next_best_action_id uuid primary key default gen_random_uuid(),
  model_prediction_id uuid references public.model_predictions(model_prediction_id) on delete set null,
  customer_id uuid references public.customers(customer_id) on delete cascade,
  agent_id uuid references public.agents(agent_id) on delete set null,
  policy_id uuid references public.policies(policy_id) on delete set null,
  lead_id uuid references public.leads(lead_id) on delete set null,
  campaign_id uuid references public.campaigns(campaign_id) on delete set null,
  product_id uuid references public.products(product_id) on delete set null,
  action_type text not null check (action_type in ('call_customer', 'send_campaign', 'offer_product', 'retention_outreach', 'renewal_follow_up', 'claim_review', 'fraud_review', 'agent_coaching', 'assign_lead', 'service_recovery')),
  action_rank integer not null check (action_rank > 0),
  priority_score numeric(12,6) check (priority_score is null or priority_score between 0 and 1),
  expected_value numeric(18,6),
  due_date date,
  action_status text not null check (action_status in ('recommended', 'accepted', 'assigned', 'completed', 'dismissed', 'expired')),
  outcome text,
  outcome_value numeric(18,6),
  action_reason text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

comment on table public.next_best_actions is 'Operational action recommendations generated from ML predictions for customers, agents, policies, leads, claims, products, and campaigns.';
comment on column public.next_best_actions.next_best_action_id is 'Primary key for the next-best-action recommendation.';
comment on column public.next_best_actions.model_prediction_id is 'Model prediction that generated or supported the action.';
comment on column public.next_best_actions.customer_id is 'Customer targeted by the action, if applicable.';
comment on column public.next_best_actions.agent_id is 'Agent assigned to or targeted by the action, if applicable.';
comment on column public.next_best_actions.policy_id is 'Policy targeted by the action, if applicable.';
comment on column public.next_best_actions.lead_id is 'Lead targeted by the action, if applicable.';
comment on column public.next_best_actions.campaign_id is 'Campaign associated with the action, if applicable.';
comment on column public.next_best_actions.product_id is 'Product recommended or associated with the action.';
comment on column public.next_best_actions.action_type is 'Type of recommended business action.';
comment on column public.next_best_actions.action_rank is 'Rank of the action among alternatives.';
comment on column public.next_best_actions.priority_score is 'Priority score from 0 to 1.';
comment on column public.next_best_actions.expected_value is 'Expected business value of the action.';
comment on column public.next_best_actions.due_date is 'Date by which the action should be completed.';
comment on column public.next_best_actions.action_status is 'Workflow status of the action.';
comment on column public.next_best_actions.outcome is 'Observed outcome after action execution.';
comment on column public.next_best_actions.outcome_value is 'Observed value from the action outcome.';
comment on column public.next_best_actions.action_reason is 'Business-readable reason for the recommendation.';
comment on column public.next_best_actions.created_at is 'Timestamp when the record was created.';
comment on column public.next_best_actions.updated_at is 'Timestamp when the record was last updated.';

create table if not exists public.ml_training_labels (
  label_snapshot_id uuid primary key,
  entity_type text not null check (entity_type in ('customer', 'policy', 'agent', 'lead', 'claim', 'campaign_response')),
  entity_id uuid not null,
  customer_id uuid references public.customers(customer_id) on delete set null,
  agent_id uuid references public.agents(agent_id) on delete set null,
  policy_id uuid references public.policies(policy_id) on delete set null,
  lead_id uuid references public.leads(lead_id) on delete set null,
  claim_id uuid references public.claims(claim_id) on delete set null,
  campaign_id uuid references public.campaigns(campaign_id) on delete set null,
  as_of_date date not null,
  propensity_to_buy_label integer check (propensity_to_buy_label is null or propensity_to_buy_label in (0, 1)),
  next_best_product_label text,
  churn_label integer check (churn_label is null or churn_label in (0, 1)),
  lapse_label integer check (lapse_label is null or lapse_label in (0, 1)),
  lead_conversion_label integer check (lead_conversion_label is null or lead_conversion_label in (0, 1)),
  agent_attrition_label integer check (agent_attrition_label is null or agent_attrition_label in (0, 1)),
  claim_occurrence_label integer check (claim_occurrence_label is null or claim_occurrence_label in (0, 1)),
  fraud_label integer check (fraud_label is null or fraud_label in (0, 1)),
  campaign_response_label integer check (campaign_response_label is null or campaign_response_label in (0, 1)),
  feature_summary jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

comment on table public.ml_training_labels is 'Wide derived-label table for supervised ML training examples across customers, policies, leads, agents, claims, and campaign responses.';
comment on column public.ml_training_labels.label_snapshot_id is 'Primary key for the training label snapshot.';
comment on column public.ml_training_labels.entity_type is 'Type of entity represented by the label row.';
comment on column public.ml_training_labels.entity_id is 'Primary entity identifier represented by the label row.';
comment on column public.ml_training_labels.customer_id is 'Customer foreign key when applicable.';
comment on column public.ml_training_labels.agent_id is 'Agent foreign key when applicable.';
comment on column public.ml_training_labels.policy_id is 'Policy foreign key when applicable.';
comment on column public.ml_training_labels.lead_id is 'Lead foreign key when applicable.';
comment on column public.ml_training_labels.claim_id is 'Claim foreign key when applicable.';
comment on column public.ml_training_labels.campaign_id is 'Campaign foreign key when applicable.';
comment on column public.ml_training_labels.as_of_date is 'As-of date used for feature and label construction.';
comment on column public.ml_training_labels.propensity_to_buy_label is 'Binary label for customer propensity-to-buy training.';
comment on column public.ml_training_labels.next_best_product_label is 'Product code label for next-best-product training.';
comment on column public.ml_training_labels.churn_label is 'Binary label for customer churn training.';
comment on column public.ml_training_labels.lapse_label is 'Binary label for policy lapse training.';
comment on column public.ml_training_labels.lead_conversion_label is 'Binary label for lead conversion training.';
comment on column public.ml_training_labels.agent_attrition_label is 'Binary label for agent attrition training.';
comment on column public.ml_training_labels.claim_occurrence_label is 'Binary label for claim occurrence training.';
comment on column public.ml_training_labels.fraud_label is 'Binary label for claim fraud training.';
comment on column public.ml_training_labels.campaign_response_label is 'Binary label for campaign response training.';
comment on column public.ml_training_labels.feature_summary is 'Small JSON summary of generated labels and important drivers.';
comment on column public.ml_training_labels.created_at is 'Timestamp when the label row was created.';

-- ---------------------------------------------------------------------------
-- Indexes for training data assembly, model scoring, and operational retrieval
-- ---------------------------------------------------------------------------

create index if not exists idx_customer_behavior_daily_customer_date on public.customer_behavior_daily (customer_id, behavior_date desc);
create index if not exists idx_customer_behavior_daily_date on public.customer_behavior_daily (behavior_date);
create index if not exists idx_customer_behavior_daily_features_gin on public.customer_behavior_daily using gin (feature_snapshot);

create index if not exists idx_customer_digital_events_customer_ts on public.customer_digital_events (customer_id, event_ts desc);
create index if not exists idx_customer_digital_events_session on public.customer_digital_events (session_id) where session_id is not null;
create index if not exists idx_customer_digital_events_product_ts on public.customer_digital_events (product_id, event_ts desc) where product_id is not null;
create index if not exists idx_customer_digital_events_metadata_gin on public.customer_digital_events using gin (metadata);

create index if not exists idx_customer_complaints_customer_date on public.customer_complaints (customer_id, complaint_date desc);
create index if not exists idx_customer_complaints_status_severity on public.customer_complaints (status, severity);
create index if not exists idx_customer_satisfaction_customer_date on public.customer_satisfaction_surveys (customer_id, survey_date desc);
create index if not exists idx_customer_nps_customer_date on public.customer_nps (customer_id, survey_date desc);
create index if not exists idx_customer_nps_group_date on public.customer_nps (nps_group, survey_date desc);
create index if not exists idx_customer_service_customer_ts on public.customer_service_requests (customer_id, request_ts desc);
create index if not exists idx_customer_service_status_priority on public.customer_service_requests (status, priority);

create index if not exists idx_policy_events_policy_ts on public.policy_events (policy_id, event_ts desc);
create index if not exists idx_policy_events_type_ts on public.policy_events (event_type, event_ts desc);
create index if not exists idx_policy_events_payload_gin on public.policy_events using gin (event_payload);
create index if not exists idx_policy_renewals_policy_cycle on public.policy_renewals (policy_id, renewal_cycle_date desc);
create index if not exists idx_policy_renewals_status_due on public.policy_renewals (renewal_status, renewal_due_date);
create index if not exists idx_policy_lapse_policy_date on public.policy_lapse_events (policy_id, lapse_event_date desc);
create index if not exists idx_policy_lapse_stage_date on public.policy_lapse_events (lapse_stage, lapse_event_date desc);

create index if not exists idx_quotes_customer_date on public.quotes (customer_id, quote_date desc);
create index if not exists idx_quotes_agent_date on public.quotes (agent_id, quote_date desc);
create index if not exists idx_quotes_product_status on public.quotes (product_id, quote_status);
create index if not exists idx_proposals_customer_date on public.proposals (customer_id, proposal_date desc);
create index if not exists idx_proposals_agent_status on public.proposals (agent_id, proposal_status);
create index if not exists idx_applications_customer_date on public.applications (customer_id, application_date desc);
create index if not exists idx_applications_agent_status on public.applications (agent_id, application_status);
create index if not exists idx_underwriting_application_date on public.underwriting_decisions (application_id, decision_date desc);
create index if not exists idx_underwriting_status_date on public.underwriting_decisions (decision_status, decision_date desc);

create index if not exists idx_agent_calls_agent_ts on public.agent_calls (agent_id, call_ts desc);
create index if not exists idx_agent_calls_customer_ts on public.agent_calls (customer_id, call_ts desc) where customer_id is not null;
create index if not exists idx_agent_meetings_agent_ts on public.agent_meetings (agent_id, meeting_ts desc);
create index if not exists idx_agent_targets_agent_period on public.agent_targets (agent_id, target_period_start, target_period_end);
create index if not exists idx_agent_commissions_agent_period on public.agent_commissions (agent_id, commission_period desc);
create index if not exists idx_agent_training_agent_status on public.agent_training (agent_id, completion_status);
create index if not exists idx_agent_attrition_agent_date on public.agent_attrition_events (agent_id, event_date desc);
create index if not exists idx_agent_attrition_stage_date on public.agent_attrition_events (attrition_stage, event_date desc);

create index if not exists idx_claim_parties_claim_role on public.claim_parties (claim_id, role_type);
create index if not exists idx_claim_assessments_claim_date on public.claim_assessments (claim_id, assessment_date desc);
create index if not exists idx_claim_assessments_type_date on public.claim_assessments (assessment_type, assessment_date desc);
create index if not exists idx_claim_fraud_claim_date on public.claim_fraud_indicators (claim_id, indicator_date desc);
create index if not exists idx_claim_fraud_score on public.claim_fraud_indicators (indicator_score desc) where indicator_score is not null;
create index if not exists idx_claim_fraud_payload_gin on public.claim_fraud_indicators using gin (indicator_payload);

create index if not exists idx_model_features_set_entity_date on public.model_features (feature_set_name, feature_set_version, entity_type, entity_id, feature_date desc);
create index if not exists idx_model_features_customer_date on public.model_features (customer_id, feature_date desc) where customer_id is not null;
create index if not exists idx_model_features_agent_date on public.model_features (agent_id, feature_date desc) where agent_id is not null;
create index if not exists idx_model_features_policy_date on public.model_features (policy_id, feature_date desc) where policy_id is not null;
create index if not exists idx_model_features_features_gin on public.model_features using gin (features);

create index if not exists idx_model_scores_model_entity_ts on public.model_scores (model_name, model_version, entity_type, entity_id, score_ts desc);
create index if not exists idx_model_scores_name_value on public.model_scores (score_name, score_value desc);
create index if not exists idx_model_scores_probability on public.model_scores (probability desc) where probability is not null;

create index if not exists idx_model_predictions_type_entity_ts on public.model_predictions (prediction_type, entity_type, entity_id, prediction_ts desc);
create index if not exists idx_model_predictions_model_ts on public.model_predictions (model_name, model_version, prediction_ts desc);
create index if not exists idx_model_predictions_probability on public.model_predictions (probability desc) where probability is not null;
create index if not exists idx_model_predictions_payload_gin on public.model_predictions using gin (prediction_payload);

create index if not exists idx_next_best_actions_customer_status on public.next_best_actions (customer_id, action_status, action_rank) where customer_id is not null;
create index if not exists idx_next_best_actions_agent_status on public.next_best_actions (agent_id, action_status, action_rank) where agent_id is not null;
create index if not exists idx_next_best_actions_due_status on public.next_best_actions (due_date, action_status);
create index if not exists idx_next_best_actions_priority on public.next_best_actions (priority_score desc) where priority_score is not null;
create index if not exists idx_ml_training_labels_entity on public.ml_training_labels (entity_type, entity_id, as_of_date desc);
create index if not exists idx_ml_training_labels_customer on public.ml_training_labels (customer_id, as_of_date desc) where customer_id is not null;
create index if not exists idx_ml_training_labels_policy on public.ml_training_labels (policy_id, as_of_date desc) where policy_id is not null;
create index if not exists idx_ml_training_labels_feature_summary_gin on public.ml_training_labels using gin (feature_summary);

-- ---------------------------------------------------------------------------
-- Updated-at triggers
-- ---------------------------------------------------------------------------

do $$
declare
  table_name text;
begin
  foreach table_name in array array[
    'customer_behavior_daily',
    'customer_digital_events',
    'customer_complaints',
    'customer_satisfaction_surveys',
    'customer_nps',
    'customer_service_requests',
    'policy_events',
    'policy_renewals',
    'policy_lapse_events',
    'quotes',
    'proposals',
    'applications',
    'underwriting_decisions',
    'agent_calls',
    'agent_meetings',
    'agent_targets',
    'agent_commissions',
    'agent_training',
    'agent_attrition_events',
    'claim_parties',
    'claim_assessments',
    'claim_fraud_indicators',
    'model_features',
    'model_scores',
    'model_predictions',
    'next_best_actions'
  ]
  loop
    if not exists (
      select 1
      from pg_trigger t
      join pg_class c on c.oid = t.tgrelid
      join pg_namespace n on n.oid = c.relnamespace
      where t.tgname = format('set_%s_updated_at', table_name)
        and n.nspname = 'public'
        and c.relname = table_name
    ) then
      execute format(
        'create trigger set_%I_updated_at before update on public.%I for each row execute function public.set_updated_at()',
        table_name,
        table_name
      );
    end if;
  end loop;
end $$;
