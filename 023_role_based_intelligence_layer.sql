-- Role-based intelligence layer for the Insurance Decision Intelligence Copilot.
--
-- Run after the core analytics schema. This layer stores role-specific product
-- configuration for KPIs, questions, dashboard widgets, action templates, data
-- access scope, model recommendations, and default insight patterns.

create extension if not exists pgcrypto;

create table if not exists public.role_definitions (
  role_definition_id uuid primary key default gen_random_uuid(),
  role_code text not null unique,
  role_name text not null,
  role_category text not null check (role_category in ('frontline', 'manager', 'executive', 'analytics')),
  description text not null,
  primary_objectives text[] not null default '{}',
  recommended_ml_models text[] not null default '{}',
  default_insights text[] not null default '{}',
  typical_actions text[] not null default '{}',
  data_access_scope jsonb not null default '{}'::jsonb,
  recommended_follow_up_questions text[] not null default '{}',
  active_flag boolean not null default true,
  display_order integer not null default 100,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

comment on table public.role_definitions is
  'Role configuration for the Insurance Decision Intelligence Copilot, including objectives, model recommendations, access scope, insights, and follow-up prompts.';
comment on column public.role_definitions.role_code is
  'Stable machine-readable role identifier used by API and frontend routing.';
comment on column public.role_definitions.primary_objectives is
  'Business objectives the copilot should optimize for this role.';
comment on column public.role_definitions.recommended_ml_models is
  'ML models most relevant to this role.';
comment on column public.role_definitions.default_insights is
  'Default insight narratives shown when the role lands on the copilot.';
comment on column public.role_definitions.typical_actions is
  'Common next actions expected for this role.';
comment on column public.role_definitions.data_access_scope is
  'Declarative data access scope used by the application authorization layer.';

create table if not exists public.role_kpis (
  role_kpi_id uuid primary key default gen_random_uuid(),
  role_definition_id uuid not null references public.role_definitions(role_definition_id) on delete cascade,
  kpi_code text not null,
  kpi_name text not null,
  business_domain text not null,
  definition text not null,
  calculation_sql text,
  target_direction text not null check (target_direction in ('higher_is_better', 'lower_is_better', 'range_is_better', 'informational')),
  default_visualization text not null check (default_visualization in ('number', 'trend', 'bar', 'line', 'table', 'funnel', 'heatmap', 'scatter')),
  related_tables text[] not null default '{}',
  related_metrics text[] not null default '{}',
  display_order integer not null default 100,
  active_flag boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (role_definition_id, kpi_code)
);

comment on table public.role_kpis is
  'Role-specific KPI definitions and default visualization metadata.';
comment on column public.role_kpis.calculation_sql is
  'Optional governed SQL template or fragment used by analytics services; execute only through validated read-only query paths.';

create table if not exists public.role_default_questions (
  role_default_question_id uuid primary key default gen_random_uuid(),
  role_definition_id uuid not null references public.role_definitions(role_definition_id) on delete cascade,
  question_text text not null,
  question_type text not null check (question_type in ('overview', 'diagnostic', 'prediction', 'next_action', 'drill_down', 'comparison')),
  business_domain text not null,
  related_tables text[] not null default '{}',
  related_models text[] not null default '{}',
  related_metrics text[] not null default '{}',
  suggested_visualization text,
  display_order integer not null default 100,
  active_flag boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (role_definition_id, question_text)
);

comment on table public.role_default_questions is
  'Frequently asked and recommended starter questions shown by role in the copilot UI.';

create table if not exists public.role_dashboard_widgets (
  role_dashboard_widget_id uuid primary key default gen_random_uuid(),
  role_definition_id uuid not null references public.role_definitions(role_definition_id) on delete cascade,
  widget_code text not null,
  widget_title text not null,
  widget_type text not null check (widget_type in ('kpi_card', 'trend_chart', 'bar_chart', 'table', 'funnel', 'heatmap', 'map', 'alert_list', 'action_queue')),
  business_domain text not null,
  description text not null,
  default_query_prompt text,
  related_kpi_codes text[] not null default '{}',
  related_tables text[] not null default '{}',
  related_models text[] not null default '{}',
  refresh_cadence text not null default 'daily',
  layout_config jsonb not null default '{}'::jsonb,
  display_order integer not null default 100,
  active_flag boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (role_definition_id, widget_code)
);

comment on table public.role_dashboard_widgets is
  'Default role dashboard widget configuration for the copilot frontend.';

create table if not exists public.role_action_templates (
  role_action_template_id uuid primary key default gen_random_uuid(),
  role_definition_id uuid not null references public.role_definitions(role_definition_id) on delete cascade,
  action_code text not null,
  action_name text not null,
  action_category text not null check (action_category in ('customer_outreach', 'service_recovery', 'campaign_optimization', 'claims_review', 'agent_coaching', 'sales_management', 'executive_review', 'analysis')),
  trigger_condition text not null,
  recommended_owner text not null,
  suggested_message_template text,
  related_tables text[] not null default '{}',
  related_models text[] not null default '{}',
  expected_outcome text,
  priority_rule text,
  active_flag boolean not null default true,
  display_order integer not null default 100,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (role_definition_id, action_code)
);

comment on table public.role_action_templates is
  'Role-specific action templates used to turn insights and model scores into operational next steps.';

create index if not exists idx_role_definitions_active_order
  on public.role_definitions (active_flag, display_order, role_name);
create index if not exists idx_role_definitions_scope_gin
  on public.role_definitions using gin (data_access_scope);
create index if not exists idx_role_kpis_role_order
  on public.role_kpis (role_definition_id, active_flag, display_order);
create index if not exists idx_role_questions_role_order
  on public.role_default_questions (role_definition_id, active_flag, display_order);
create index if not exists idx_role_widgets_role_order
  on public.role_dashboard_widgets (role_definition_id, active_flag, display_order);
create index if not exists idx_role_actions_role_order
  on public.role_action_templates (role_definition_id, active_flag, display_order);
create index if not exists idx_role_kpis_related_tables_gin
  on public.role_kpis using gin (related_tables);
create index if not exists idx_role_questions_related_models_gin
  on public.role_default_questions using gin (related_models);
create index if not exists idx_role_widgets_related_models_gin
  on public.role_dashboard_widgets using gin (related_models);

create or replace view public.v_role_intelligence_profile as
select
  rd.role_definition_id,
  rd.role_code,
  rd.role_name,
  rd.role_category,
  rd.display_order,
  rd.description,
  rd.primary_objectives,
  rd.recommended_ml_models,
  rd.default_insights,
  rd.typical_actions,
  rd.data_access_scope,
  rd.recommended_follow_up_questions,
  coalesce(kpis.kpis, '[]'::jsonb) as kpis,
  coalesce(questions.questions, '[]'::jsonb) as default_questions,
  coalesce(widgets.widgets, '[]'::jsonb) as dashboard_widgets,
  coalesce(actions.actions, '[]'::jsonb) as action_templates
from public.role_definitions rd
left join lateral (
  select jsonb_agg(
    jsonb_build_object(
      'kpi_code', k.kpi_code,
      'kpi_name', k.kpi_name,
      'business_domain', k.business_domain,
      'definition', k.definition,
      'target_direction', k.target_direction,
      'default_visualization', k.default_visualization,
      'related_tables', k.related_tables,
      'related_metrics', k.related_metrics
    )
    order by k.display_order, k.kpi_name
  ) as kpis
  from public.role_kpis k
  where k.role_definition_id = rd.role_definition_id
    and k.active_flag = true
) kpis on true
left join lateral (
  select jsonb_agg(
    jsonb_build_object(
      'question_text', q.question_text,
      'question_type', q.question_type,
      'business_domain', q.business_domain,
      'related_tables', q.related_tables,
      'related_models', q.related_models,
      'related_metrics', q.related_metrics,
      'suggested_visualization', q.suggested_visualization
    )
    order by q.display_order, q.question_text
  ) as questions
  from public.role_default_questions q
  where q.role_definition_id = rd.role_definition_id
    and q.active_flag = true
) questions on true
left join lateral (
  select jsonb_agg(
    jsonb_build_object(
      'widget_code', w.widget_code,
      'widget_title', w.widget_title,
      'widget_type', w.widget_type,
      'business_domain', w.business_domain,
      'description', w.description,
      'default_query_prompt', w.default_query_prompt,
      'related_kpi_codes', w.related_kpi_codes,
      'related_tables', w.related_tables,
      'related_models', w.related_models,
      'refresh_cadence', w.refresh_cadence,
      'layout_config', w.layout_config
    )
    order by w.display_order, w.widget_title
  ) as widgets
  from public.role_dashboard_widgets w
  where w.role_definition_id = rd.role_definition_id
    and w.active_flag = true
) widgets on true
left join lateral (
  select jsonb_agg(
    jsonb_build_object(
      'action_code', a.action_code,
      'action_name', a.action_name,
      'action_category', a.action_category,
      'trigger_condition', a.trigger_condition,
      'recommended_owner', a.recommended_owner,
      'suggested_message_template', a.suggested_message_template,
      'related_tables', a.related_tables,
      'related_models', a.related_models,
      'expected_outcome', a.expected_outcome,
      'priority_rule', a.priority_rule
    )
    order by a.display_order, a.action_name
  ) as actions
  from public.role_action_templates a
  where a.role_definition_id = rd.role_definition_id
    and a.active_flag = true
) actions on true
where rd.active_flag = true;

comment on view public.v_role_intelligence_profile is
  'API-ready role profile including objectives, KPIs, starter questions, widgets, actions, models, and access scope.';

insert into public.role_definitions (
  role_code,
  role_name,
  role_category,
  description,
  primary_objectives,
  recommended_ml_models,
  default_insights,
  typical_actions,
  data_access_scope,
  recommended_follow_up_questions,
  display_order
)
values
(
  'insurance_agent',
  'Insurance Agent',
  'frontline',
  'Frontline producer or servicing agent focused on customer conversations, retention, cross-sell, and lead conversion.',
  array['Prioritize customers to contact today','Protect policies at risk of lapse','Convert high-quality leads','Cross-sell suitable products','Resolve service issues before selling'],
  array['propensity_to_buy','policy_lapse','customer_churn','next_best_product','lead_conversion','customer_lifetime_value','campaign_response'],
  array['Top customers needing retention calls','High-propensity customers missing health coverage','Leads most likely to convert','Customers with open complaints suppressing sales actions'],
  array['Call customer','Schedule renewal review','Follow up on campaign response','Resolve complaint','Create opportunity','Recommend next best product'],
  '{"customer_scope":"assigned_book","policy_scope":"assigned_customers","claims_scope":"assigned_customers","campaign_scope":"assigned_targets","agent_scope":"self","pii_level":"standard"}'::jsonb,
  array['Which customers should I contact first today?','Which policies are at highest lapse risk?','Which customer is best for health cross-sell?','Which leads should I follow up within 7 days?'],
  10
),
(
  'agency_manager',
  'Agency Manager',
  'manager',
  'Manager responsible for agent productivity, pipeline health, sales coaching, persistency, and territory performance.',
  array['Improve agent productivity','Coach low-performing agents','Increase persistency','Balance lead allocation','Monitor territory movement and sales outcomes'],
  array['agent_performance','next_best_customer','agent_attrition','lead_conversion','policy_lapse','customer_lifetime_value'],
  array['Agents with declining MAPA activity','Agents at attrition risk','Lead pools needing reallocation','Territories with improving or declining sales'],
  array['Coach agent','Reassign leads','Review agent pipeline','Approve campaign support','Investigate persistency drop'],
  '{"customer_scope":"agency_book","policy_scope":"agency_book","claims_scope":"agency_book","campaign_scope":"agency_campaigns","agent_scope":"managed_agents","pii_level":"manager"}'::jsonb,
  array['Which agents have declining MAPA productivity?','Which agents need coaching this month?','Which agents are overloaded?','Which territories improved after movement?'],
  20
),
(
  'campaign_manager',
  'Campaign Manager',
  'manager',
  'Marketing role focused on campaign targeting, response, conversion, attribution, suppression, and audience optimization.',
  array['Improve campaign conversion','Optimize targeting and suppression','Measure attributed policy conversion','Identify responsive segments','Coordinate agent follow-up'],
  array['campaign_response','propensity_to_buy','next_best_product','lead_conversion','customer_lifetime_value'],
  array['Campaigns with highest policy conversion','Segments with strong response but low conversion','Customers needing agent follow-up','Suppression leakage from opt-outs or complaints'],
  array['Launch segment campaign','Suppress ineligible customers','Create follow-up queue','Adjust offer mix','Review conversion funnel'],
  '{"customer_scope":"campaign_audiences","policy_scope":"aggregated_campaign_attribution","claims_scope":"aggregate_only","campaign_scope":"all_campaigns","agent_scope":"campaign_assigned_agents","pii_level":"marketing"}'::jsonb,
  array['Which campaigns generated the highest policy conversion?','Which segments respond best to health campaigns?','Where are campaign responders failing to convert?','Which campaign targets need follow-up this week?'],
  30
),
(
  'claims_manager',
  'Claims Manager',
  'manager',
  'Claims leader focused on loss cost, claims operations, fraud indicators, service quality, and customer impact.',
  array['Reduce claims leakage','Identify fraud risk','Monitor claim severity','Protect customer experience during claims','Coordinate service recovery'],
  array['claims_prediction','fraud_risk','customer_churn','customer_lifetime_value'],
  array['Claims with high fraud indicators','Segments with high claim ratio','High-value customers with recent claims and churn risk','Open claims with service recovery need'],
  array['Review suspicious claim','Assign claim assessment','Escalate severe claim','Trigger service recovery','Monitor claim cycle time'],
  '{"customer_scope":"claims_customers","policy_scope":"claim_linked_policies","claims_scope":"managed_claims","campaign_scope":"none","agent_scope":"claim_assigned_agents","pii_level":"claims"}'::jsonb,
  array['Which claims have the highest fraud risk?','Which customer segments have the highest claim ratio?','Which claimants have rising churn risk?','Which claims need manager review today?'],
  40
),
(
  'sales_director',
  'Sales Director',
  'executive',
  'Sales leader responsible for premium growth, persistency, channel performance, product mix, and agency execution.',
  array['Grow new business premium','Improve product mix','Increase persistency','Identify high-performing channels','Prioritize sales interventions'],
  array['agent_performance','next_best_customer','propensity_to_buy','next_best_product','policy_lapse','customer_lifetime_value'],
  array['Sales growth by channel and territory','Product mix opportunities','Persistency risks by agency','Top next-best-customer pools by expected value'],
  array['Set sales target','Prioritize agency coaching','Adjust product campaign focus','Review persistency plan','Allocate leads'],
  '{"customer_scope":"regional_aggregate_plus_priority_segments","policy_scope":"regional_book","claims_scope":"aggregate_only","campaign_scope":"regional_campaigns","agent_scope":"regional_agents","pii_level":"director"}'::jsonb,
  array['Where is new business premium growing fastest?','Which agencies have the highest persistency risk?','Which products should we prioritize next quarter?','Which channels convert high-CLV customers?'],
  50
),
(
  'executive_leadership',
  'Executive Leadership',
  'executive',
  'Senior leadership role focused on portfolio performance, risk, growth, profitability, customer health, and strategic execution.',
  array['Track enterprise growth and profitability','Monitor customer and policy health','Understand risk concentration','Review strategic campaign outcomes','Prioritize executive interventions'],
  array['customer_lifetime_value','policy_lapse','customer_churn','claims_prediction','fraud_risk','campaign_response','agent_performance'],
  array['Enterprise growth and persistency summary','Profitability and claims ratio hotspots','Strategic campaign performance','Customer churn and lapse risk trend'],
  array['Review executive dashboard','Request deep-dive analysis','Approve strategic initiative','Escalate risk hotspot','Set portfolio priorities'],
  '{"customer_scope":"aggregate_by_segment","policy_scope":"enterprise_aggregate","claims_scope":"enterprise_aggregate","campaign_scope":"enterprise_aggregate","agent_scope":"aggregate_by_channel","pii_level":"aggregate"}'::jsonb,
  array['What are the top portfolio risks this month?','Which segments drive growth and profitability?','Where is lapse risk increasing?','Which campaigns are creating profitable growth?'],
  60
),
(
  'data_analyst',
  'Data Analyst',
  'analytics',
  'Analyst role focused on ad hoc exploration, metric validation, model monitoring, SQL generation, and semantic context testing.',
  array['Answer business questions accurately','Validate KPI definitions','Monitor data quality','Explain model drivers','Support governed text-to-SQL analysis'],
  array['propensity_to_buy','policy_lapse','customer_churn','agent_performance','lead_conversion','claims_prediction','fraud_risk','customer_lifetime_value','campaign_response'],
  array['Data freshness and row-count checks','Feature table readiness','Model score distributions','Metric definition coverage in semantic documents'],
  array['Run analysis','Validate metric','Inspect SQL','Check data quality','Create insight brief'],
  '{"customer_scope":"authorized_analysis_dataset","policy_scope":"authorized_analysis_dataset","claims_scope":"authorized_analysis_dataset","campaign_scope":"authorized_analysis_dataset","agent_scope":"authorized_analysis_dataset","pii_level":"analyst_controlled"}'::jsonb,
  array['Which feature tables are stale?','Are model scores distributed as expected?','Which joins define customer 360?','What SQL calculates campaign conversion?'],
  70
)
on conflict (role_code) do update
set role_name = excluded.role_name,
    role_category = excluded.role_category,
    description = excluded.description,
    primary_objectives = excluded.primary_objectives,
    recommended_ml_models = excluded.recommended_ml_models,
    default_insights = excluded.default_insights,
    typical_actions = excluded.typical_actions,
    data_access_scope = excluded.data_access_scope,
    recommended_follow_up_questions = excluded.recommended_follow_up_questions,
    display_order = excluded.display_order,
    active_flag = true,
    updated_at = now();

with role_map as (
  select role_definition_id, role_code from public.role_definitions
),
kpi_seed(role_code, kpi_code, kpi_name, business_domain, definition, target_direction, default_visualization, related_tables, related_metrics, display_order) as (
  values
  ('insurance_agent','today_priority_actions','Today Priority Actions','next_best_action','Count of active next-best-actions assigned to the agent and expiring soon.','higher_is_better','number',array['next_best_actions','model_scores'],array['priority_score','confidence_score'],10),
  ('insurance_agent','lapse_risk_book','Book Lapse Risk','policy','Share of assigned active policies with high lapse risk.','lower_is_better','trend',array['policies','model_scores'],array['lapse_risk'],20),
  ('insurance_agent','lead_conversion_pipeline','Lead Conversion Pipeline','sales','Open leads ranked by conversion score and next-step urgency.','higher_is_better','funnel',array['leads','opportunities','model_scores'],array['lead_conversion_score'],30),
  ('agency_manager','mapa_productivity','MAPA Productivity','agent','Monthly activity and production indicators across managed agents.','higher_is_better','bar',array['agent_mapa_metrics','agents'],array['contacts_count','applications_count','policies_bound_count'],10),
  ('agency_manager','agent_capacity_risk','Agent Capacity Risk','agent','Agents with high workload, low performance, or declining productivity.','lower_is_better','table',array['agents','agent_mapa_metrics','model_scores'],array['agent_performance_score'],20),
  ('campaign_manager','campaign_policy_conversion','Campaign Policy Conversion','campaign','Campaign targets that converted into policies divided by eligible targets.','higher_is_better','bar',array['campaigns','campaign_targets','campaign_responses','policies'],array['conversion_rate'],10),
  ('campaign_manager','response_to_conversion_gap','Response Conversion Gap','campaign','Gap between campaign response rate and policy conversion rate.','lower_is_better','funnel',array['campaign_responses','opportunities','policies'],array['response_rate','conversion_rate'],20),
  ('claims_manager','claim_ratio','Claim Ratio','claims','Incurred claims divided by earned or written premium for the selected segment.','lower_is_better','trend',array['claims','premiums','policies'],array['claim_ratio','incurred_amount'],10),
  ('claims_manager','fraud_review_queue','Fraud Review Queue','claims','Claims with high fraud risk model score or fraud indicators.','lower_is_better','table',array['claims','claim_fraud_indicators','model_scores'],array['fraud_risk'],20),
  ('sales_director','new_business_premium','New Business Premium','sales','New written premium for selected channel, territory, or product.','higher_is_better','trend',array['policies','premiums','agents','products'],array['new_business_premium'],10),
  ('sales_director','persistency_rate','Policy Persistency','policy','Active or renewed policies retained through the measurement window.','higher_is_better','trend',array['policies','agent_mapa_metrics'],array['persistency_rate'],20),
  ('executive_leadership','portfolio_growth','Portfolio Growth','executive','Growth in premium, policies, and customer value across the enterprise portfolio.','higher_is_better','trend',array['policies','premiums','customers'],array['premium_growth','policy_growth'],10),
  ('executive_leadership','enterprise_risk_hotspots','Enterprise Risk Hotspots','executive','Segments or regions with elevated lapse, churn, claims, or fraud risk.','lower_is_better','heatmap',array['model_scores','claims','policies','customers'],array['lapse_risk','churn_risk','claim_ratio','fraud_risk'],20),
  ('data_analyst','feature_table_coverage','Feature Table Coverage','analytics','Readiness of ML feature tables by row count, null rate, and target distribution.','higher_is_better','table',array['model_features','model_scores'],array['row_count','null_rate','target_distribution'],10),
  ('data_analyst','semantic_retrieval_coverage','Semantic Retrieval Coverage','analytics','Coverage and freshness of glossary, semantic documents, and embeddings.','higher_is_better','table',array['semantic_documents','business_glossary'],array['embedded_documents','missing_embeddings'],20)
)
insert into public.role_kpis (
  role_definition_id, kpi_code, kpi_name, business_domain, definition, target_direction,
  default_visualization, related_tables, related_metrics, display_order
)
select rm.role_definition_id, s.kpi_code, s.kpi_name, s.business_domain, s.definition, s.target_direction,
       s.default_visualization, s.related_tables, s.related_metrics, s.display_order
from kpi_seed s
join role_map rm on rm.role_code = s.role_code
on conflict (role_definition_id, kpi_code) do update
set kpi_name = excluded.kpi_name,
    business_domain = excluded.business_domain,
    definition = excluded.definition,
    target_direction = excluded.target_direction,
    default_visualization = excluded.default_visualization,
    related_tables = excluded.related_tables,
    related_metrics = excluded.related_metrics,
    display_order = excluded.display_order,
    active_flag = true,
    updated_at = now();

with role_map as (
  select role_definition_id, role_code from public.role_definitions
),
question_seed(role_code, question_text, question_type, business_domain, related_tables, related_models, related_metrics, suggested_visualization, display_order) as (
  values
  ('insurance_agent','Which customers should I contact first today?','next_action','next_best_action',array['next_best_actions','customers','model_scores'],array['propensity_to_buy','policy_lapse','customer_churn'],array['priority_score','confidence_score'],'action_queue',10),
  ('insurance_agent','Which customers have high lapse risk and recent payment delays?','diagnostic','policy',array['customers','policies','payments','model_scores'],array['policy_lapse'],array['lapse_risk'],'table',20),
  ('insurance_agent','Which high-CLV customers lack health coverage?','prediction','customer',array['customers','policies','products','model_scores'],array['next_best_product','customer_lifetime_value'],array['clv','propensity_to_buy'],'table',30),
  ('agency_manager','Which agents have declining MAPA productivity?','diagnostic','agent',array['agents','agent_mapa_metrics'],array['agent_performance'],array['contacts_count','applications_count'],'trend',10),
  ('agency_manager','Which agents should receive fewer leads due to low capacity?','next_action','agent',array['agents','agent_mapa_metrics','leads'],array['agent_performance','next_best_customer'],array['agent_capacity_status'],'table',20),
  ('campaign_manager','Which campaigns generated the highest policy conversion?','overview','campaign',array['campaigns','campaign_targets','campaign_responses','policies'],array['campaign_response'],array['conversion_rate'],'bar',10),
  ('campaign_manager','Which campaign responders should agents follow up within 7 days?','next_action','campaign',array['campaign_responses','campaign_targets','next_best_actions'],array['campaign_response'],array['campaign_response_score'],'action_queue',20),
  ('claims_manager','Which claims have high fraud risk and high severity?','prediction','claims',array['claims','claim_fraud_indicators','model_scores'],array['fraud_risk','claims_prediction'],array['fraud_risk','incurred_amount'],'table',10),
  ('claims_manager','Which customer segments have the highest claim ratio?','overview','claims',array['claims','premiums','customers','policies'],array['claims_prediction'],array['claim_ratio'],'bar',20),
  ('sales_director','What is policy persistency by product and agency?','overview','policy',array['policies','products','agents','agent_mapa_metrics'],array['policy_lapse','agent_performance'],array['persistency_rate'],'heatmap',10),
  ('sales_director','Which territories have the highest next-best-customer value?','prediction','sales',array['customers','agents','model_scores','next_best_actions'],array['next_best_customer','customer_lifetime_value'],array['expected_value','priority_score'],'heatmap',20),
  ('executive_leadership','What are the top portfolio risks this month?','overview','executive',array['model_scores','claims','policies','customers'],array['policy_lapse','customer_churn','fraud_risk','claims_prediction'],array['risk_score'],'heatmap',10),
  ('executive_leadership','Which growth initiatives are producing profitable customers?','comparison','executive',array['campaigns','customers','policies','claims','model_scores'],array['campaign_response','customer_lifetime_value'],array['clv','conversion_rate','claim_ratio'],'table',20),
  ('data_analyst','Which feature tables have zero rows or stale snapshots?','diagnostic','analytics',array['model_features','model_scores'],array['all_models'],array['row_count','snapshot_date'],'table',10),
  ('data_analyst','Which semantic documents are missing embeddings?','diagnostic','semantic',array['semantic_documents'],array['pgvector_retrieval'],array['missing_embeddings'],'table',20)
)
insert into public.role_default_questions (
  role_definition_id, question_text, question_type, business_domain, related_tables,
  related_models, related_metrics, suggested_visualization, display_order
)
select rm.role_definition_id, s.question_text, s.question_type, s.business_domain, s.related_tables,
       s.related_models, s.related_metrics, s.suggested_visualization, s.display_order
from question_seed s
join role_map rm on rm.role_code = s.role_code
on conflict (role_definition_id, question_text) do update
set question_type = excluded.question_type,
    business_domain = excluded.business_domain,
    related_tables = excluded.related_tables,
    related_models = excluded.related_models,
    related_metrics = excluded.related_metrics,
    suggested_visualization = excluded.suggested_visualization,
    display_order = excluded.display_order,
    active_flag = true,
    updated_at = now();

with role_map as (
  select role_definition_id, role_code from public.role_definitions
),
widget_seed(role_code, widget_code, widget_title, widget_type, business_domain, description, default_query_prompt, related_kpi_codes, related_tables, related_models, refresh_cadence, display_order) as (
  values
  ('insurance_agent','today_action_queue','Today Action Queue','action_queue','next_best_action','Prioritized customer actions with reasons, product recommendation, confidence, and expiry date.','Show my next-best-actions for today ordered by priority.',array['today_priority_actions'],array['next_best_actions','customers','model_scores'],array['propensity_to_buy','policy_lapse','customer_churn'],'hourly',10),
  ('insurance_agent','lapse_watchlist','Lapse Watchlist','table','policy','Assigned policies with high lapse risk, payment delays, or renewal within 60 days.','Which of my assigned policies are most likely to lapse?',array['lapse_risk_book'],array['policies','payments','model_scores'],array['policy_lapse'],'daily',20),
  ('agency_manager','agent_productivity_board','Agent Productivity Board','bar_chart','agent','MAPA productivity and policy bind trends by managed agent.','Compare MAPA productivity across my agents.',array['mapa_productivity'],array['agents','agent_mapa_metrics'],array['agent_performance'],'daily',10),
  ('agency_manager','capacity_alerts','Capacity Alerts','alert_list','agent','Agents with low performance, high workload, or excessive open follow-up actions.','Which agents are overloaded or need coaching?',array['agent_capacity_risk'],array['agents','agent_mapa_metrics','next_best_actions'],array['agent_performance'],'daily',20),
  ('campaign_manager','campaign_conversion_funnel','Campaign Conversion Funnel','funnel','campaign','Targets, responses, quotes, opportunities, and converted policies by campaign.','Show campaign conversion funnel by campaign.',array['campaign_policy_conversion','response_to_conversion_gap'],array['campaigns','campaign_targets','campaign_responses','opportunities','policies'],array['campaign_response'],'daily',10),
  ('claims_manager','fraud_review_queue','Fraud Review Queue','table','claims','High-risk claims needing assessment or fraud review.','Which claims should be reviewed for fraud risk today?',array['fraud_review_queue'],array['claims','claim_fraud_indicators','model_scores'],array['fraud_risk'],'hourly',10),
  ('sales_director','sales_growth_trend','Sales Growth Trend','trend_chart','sales','New business premium and policy growth by channel, product, and agency.','Show sales growth by channel and product.',array['new_business_premium'],array['policies','premiums','agents','products'],array['agent_performance'],'daily',10),
  ('executive_leadership','enterprise_risk_heatmap','Enterprise Risk Heatmap','heatmap','executive','Enterprise-level hotspots across lapse, churn, claims, fraud, and profitability indicators.','Summarize enterprise risk hotspots this month.',array['enterprise_risk_hotspots'],array['model_scores','claims','policies','customers'],array['policy_lapse','customer_churn','fraud_risk'],'daily',10),
  ('data_analyst','semantic_health','Semantic Retrieval Health','table','semantic','Semantic document and embedding coverage for pgvector retrieval.','Which semantic documents are missing embeddings or stale?',array['semantic_retrieval_coverage'],array['semantic_documents','business_glossary'],array['pgvector_retrieval'],'daily',10)
)
insert into public.role_dashboard_widgets (
  role_definition_id, widget_code, widget_title, widget_type, business_domain, description,
  default_query_prompt, related_kpi_codes, related_tables, related_models, refresh_cadence,
  layout_config, display_order
)
select rm.role_definition_id, s.widget_code, s.widget_title, s.widget_type, s.business_domain, s.description,
       s.default_query_prompt, s.related_kpi_codes, s.related_tables, s.related_models, s.refresh_cadence,
       jsonb_build_object('width', 6, 'height', 4), s.display_order
from widget_seed s
join role_map rm on rm.role_code = s.role_code
on conflict (role_definition_id, widget_code) do update
set widget_title = excluded.widget_title,
    widget_type = excluded.widget_type,
    business_domain = excluded.business_domain,
    description = excluded.description,
    default_query_prompt = excluded.default_query_prompt,
    related_kpi_codes = excluded.related_kpi_codes,
    related_tables = excluded.related_tables,
    related_models = excluded.related_models,
    refresh_cadence = excluded.refresh_cadence,
    layout_config = excluded.layout_config,
    display_order = excluded.display_order,
    active_flag = true,
    updated_at = now();

with role_map as (
  select role_definition_id, role_code from public.role_definitions
),
action_seed(role_code, action_code, action_name, action_category, trigger_condition, recommended_owner, suggested_message_template, related_tables, related_models, expected_outcome, priority_rule, display_order) as (
  values
  ('insurance_agent','retention_call','Retention Call','customer_outreach','policy_lapse score is HIGH or policy renewal is within 60 days','assigned_agent','I would like to review your policy and make sure it still fits your needs.',array['next_best_actions','policies','model_scores'],array['policy_lapse','customer_churn'],'Reduced lapse risk and improved persistency','priority_score desc, expiry_date asc',10),
  ('insurance_agent','health_cross_sell','Health Cross-Sell','customer_outreach','propensity_to_buy is HIGH and customer lacks active health policy','assigned_agent','Based on your current protection needs, it may be worth reviewing health coverage options.',array['customers','policies','products','model_scores'],array['propensity_to_buy','next_best_product'],'New opportunity or policy conversion','propensity_to_buy_score desc',20),
  ('agency_manager','agent_coaching','Agent Coaching','agent_coaching','agent performance score is LOW or MAPA activity is declining','agency_manager','Let us review pipeline activity, follow-up quality, and conversion blockers.',array['agents','agent_mapa_metrics','model_scores'],array['agent_performance'],'Improved agent productivity and conversion','agent_performance_score asc',10),
  ('campaign_manager','campaign_followup','Campaign Follow-Up Queue','campaign_optimization','campaign_response score is HIGH and customer has marketing opt-in','campaign_manager','Create agent follow-up queue for high-response campaign targets.',array['campaign_targets','campaign_responses','next_best_actions'],array['campaign_response'],'Higher response-to-conversion rate','campaign_response_score desc',10),
  ('claims_manager','fraud_review','Fraud Review','claims_review','fraud_risk score is HIGH or fraud indicator count exceeds threshold','claims_manager','Review claim evidence, assessment notes, and fraud indicators before settlement.',array['claims','claim_fraud_indicators','model_scores'],array['fraud_risk'],'Reduced claims leakage','fraud_risk desc, incurred_amount desc',10),
  ('sales_director','persistency_intervention','Persistency Intervention','sales_management','agency or product persistency falls below target','sales_director','Prioritize renewal outreach and coaching in low-persistency agencies.',array['policies','agents','agent_mapa_metrics','model_scores'],array['policy_lapse','agent_performance'],'Improved renewal and retention performance','persistency_gap desc',10),
  ('executive_leadership','risk_hotspot_review','Risk Hotspot Review','executive_review','portfolio risk hotspot appears across lapse, churn, claims, or fraud','executive_sponsor','Review hotspot, assign owner, and request root-cause analysis.',array['model_scores','claims','policies','customers'],array['policy_lapse','customer_churn','fraud_risk','claims_prediction'],'Executive intervention and risk mitigation','composite_risk_score desc',10),
  ('data_analyst','metric_validation','Metric Validation','analysis','KPI result changes materially or semantic context is incomplete','data_analyst','Validate SQL, join path, filters, and semantic definitions before publishing.',array['business_glossary','semantic_documents','query_audit_log'],array['pgvector_retrieval'],'Trusted governed metric output','data_quality_risk desc',10)
)
insert into public.role_action_templates (
  role_definition_id, action_code, action_name, action_category, trigger_condition, recommended_owner,
  suggested_message_template, related_tables, related_models, expected_outcome, priority_rule, display_order
)
select rm.role_definition_id, s.action_code, s.action_name, s.action_category, s.trigger_condition, s.recommended_owner,
       s.suggested_message_template, s.related_tables, s.related_models, s.expected_outcome, s.priority_rule, s.display_order
from action_seed s
join role_map rm on rm.role_code = s.role_code
on conflict (role_definition_id, action_code) do update
set action_name = excluded.action_name,
    action_category = excluded.action_category,
    trigger_condition = excluded.trigger_condition,
    recommended_owner = excluded.recommended_owner,
    suggested_message_template = excluded.suggested_message_template,
    related_tables = excluded.related_tables,
    related_models = excluded.related_models,
    expected_outcome = excluded.expected_outcome,
    priority_rule = excluded.priority_rule,
    display_order = excluded.display_order,
    active_flag = true,
    updated_at = now();

select
  role_code,
  role_name,
  jsonb_array_length(kpis) as kpi_count,
  jsonb_array_length(default_questions) as question_count,
  jsonb_array_length(dashboard_widgets) as widget_count,
  jsonb_array_length(action_templates) as action_template_count
from public.v_role_intelligence_profile
order by display_order nulls last, role_name;
