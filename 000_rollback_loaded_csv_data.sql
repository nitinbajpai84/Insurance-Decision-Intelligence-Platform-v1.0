-- Rollback script for already-loaded synthetic insurance CSV data.
--
-- Execute this FIRST if you already loaded the old CSVs and now want to reload
-- the updated rider-aware CSV dataset.
--
-- This script intentionally preserves table structures, extensions, indexes,
-- triggers, and functions. It only removes loaded data and drops derived views
-- that can be recreated by later migrations.
--
-- Recommended next steps after this script:
--   1. Run 004_product_riders_and_nbp_views.sql if not already applied.
--   2. Reload CSV files in the README load order.
--   3. Reload/regenerate semantic_documents and embeddings if needed.

begin;

-- Drop dependent analytics views before truncating/recreating rider-aware logic.
drop view if exists public.v_new_business_premium_by_rider;
drop view if exists public.v_policy_rider_tags;

-- Clear all generated/loadable tables.
-- CASCADE handles FK dependencies safely if your local table set differs
-- slightly because of later migrations.
truncate table
  public.query_audit_log,
  public.semantic_documents,
  public.business_glossary,
  public.customer_engagement_events,
  public.campaign_responses,
  public.campaign_targets,
  public.claims,
  public.payments,
  public.premiums,
  public.policy_coverages,
  public.policies,
  public.opportunities,
  public.leads,
  public.campaigns,
  public.products,
  public.agent_mapa_metrics,
  public.agent_movements,
  public.agents,
  public.addresses,
  public.customers,
  public.parties
restart identity cascade;

commit;
