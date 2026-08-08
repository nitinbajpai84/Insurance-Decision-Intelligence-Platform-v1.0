# KPI Definitions And Formulas

## KPI Formula Catalog

| KPI | Definition | Formula | Grain | Required Tables | Used By Tabs | Caveats |
|---|---|---|---|---|---|---|
| Lapse Rate | Share of eligible policies that lapse. | Lapsed policies / policies eligible for renewal | Product, agent, segment, period | `policies`, `policy_lapse_events`, `policy_renewals` | Policy Lapse Risk, AI Intelligence | Eligibility definition must be agreed. |
| Premium at Risk | Annual premium exposed to high lapse risk. | Sum annual premium for high-risk policies | Policy, customer, product, agent | `policies`, `model_scores` | Policy Lapse Risk | Requires score threshold. |
| Persistency Rate | Policies remaining active after period. | Active policies after period / policies issued in cohort | Cohort, product, agent | `policies`, `policy_renewals`, `agent_mapa_metrics` | Agent Performance | Cohort definitions vary by insurer. |
| Campaign Conversion Rate | Campaign-driven policies per target or lead. | Policies issued from campaign / targeted customers or leads | Campaign, channel, segment | `campaigns`, `campaign_targets`, `campaign_responses`, `leads`, `policies` | Campaign Effectiveness | Attribution window required. |
| Lead Conversion Rate | Share of leads converted. | Converted leads / total leads | Campaign, agent, period | `leads`, `opportunities`, `policies` | Campaign Effectiveness | Conversion stage must be defined. |
| Quote-to-Bind Rate | Share of quotes that bind. | Issued policies / quotes generated | Agent, product, period | `quotes`, `applications`, `policies`, `agent_mapa_metrics` | Agent Performance | MAPA quote count may be a proxy. |
| Claim Ratio | Claims paid over premium. | Paid claims / earned premium | Product, segment, period | `claims`, `premiums` | AI Intelligence, Claims architecture | Earned premium method required. |
| Loss Ratio | Incurred claims over earned premium. | Incurred claims / earned premium | Product, segment, period | `claims`, `premiums` | AI Intelligence, Claims architecture | Reserving timing matters. |
| Agent Conversion Rate | Agent policy conversion effectiveness. | Policies issued / applications or proposals | Agent, month | `agent_mapa_metrics`, `policies` | Agent Performance | Denominator should be selected consistently. |
| MAPA Productivity | Distribution activity measure. | Meetings + Activities + Proposals + Applications, weighted if applicable | Agent, month | `agent_mapa_metrics` | Agent Performance | Current UI uses MAPA components; weighted score is recommended if needed. |
| Customer Lifetime Value | Expected future value. | Expected future premium/profit adjusted by retention probability | Customer | `policies`, `payments`, `model_scores` | KYC, AI Intelligence | Production CLV formula requires finance assumptions. |
| Propensity Score | Probability of purchase. | Model output probability | Customer, snapshot | `model_scores`, feature tables | KYC, AI Intelligence | Score calibration needed in production. |
| Churn Risk | Probability of customer attrition. | Model output probability | Customer, snapshot | `model_scores`, `customer_churn_features` | KYC, AI Intelligence | Churn definition required. |
| Retention Success Rate | Share of retention actions that save policy/customer. | Successful saves / retention actions attempted | Agent, product, period | `next_best_actions`, `policy_lapse_events` | Planned / Recommended | Retention action outcome table not found. |
| Revenue Opportunity | Premium upside from high propensity customers. | Potential premium from high-propensity cross-sell customers | Segment, product, agent | `model_scores`, `model_predictions`, `products`, `policies` | Home, AI Intelligence | Product pricing assumption required. |

## Example SQL Snippets

### Premium At Risk

```sql
select
  prod.line_of_business,
  count(*) as high_risk_policies,
  sum(p.annual_premium) as premium_at_risk
from public.policies p
join public.products prod on prod.product_id = p.product_id
join public.v_latest_model_scores s
  on s.entity_id = p.policy_id
 and s.entity_type = 'policy'
where s.score_name ilike '%lapse%'
  and coalesce(s.score_band, '') in ('HIGH', 'VERY_HIGH')
group by prod.line_of_business
order by premium_at_risk desc;
```

### Campaign Conversion Rate

```sql
select
  c.campaign_name,
  count(distinct ct.campaign_target_id) as targeted_customers,
  count(distinct p.policy_id) as policies_issued,
  count(distinct p.policy_id)::numeric / nullif(count(distinct ct.campaign_target_id), 0) as policy_conversion_rate
from public.campaigns c
left join public.campaign_targets ct on ct.campaign_id = c.campaign_id
left join public.opportunities o on o.campaign_id = c.campaign_id
left join public.policies p on p.opportunity_id = o.opportunity_id
group by c.campaign_name
order by policy_conversion_rate desc nulls last;
```

### Agent MAPA Productivity

```sql
select
  a.agent_id,
  pa.display_name as agent_name,
  sum(m.contacts_count) as activities,
  sum(m.quotes_count) as proposals,
  sum(m.applications_count) as applications,
  sum(m.policies_bound_count) as policies_bound,
  sum(m.new_business_premium) as new_business_premium
from public.agent_mapa_metrics m
join public.agents a on a.agent_id = m.agent_id
join public.parties pa on pa.party_id = a.party_id
group by a.agent_id, pa.display_name
order by new_business_premium desc;
```

## Formula Governance Recommendations

| Need | Current Status | Recommendation |
|---|---:|---|
| KPI catalog table | Implemented | Keep `kpi_definitions` populated and reviewed by business. |
| Formula lineage | Partially implemented | Link KPI definitions to source tables and SQL examples. |
| Business approval | Not found | Add sign-off workflow for demo-to-production transition. |
| Metric versioning | Planned / Recommended | Add `effective_date`, `retired_date`, and formula versioning if not already sufficient. |

