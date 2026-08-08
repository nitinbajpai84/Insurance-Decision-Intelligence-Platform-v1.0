# Role-Based Intelligence Layer

This layer turns the Insurance Decision Intelligence Copilot into a role-aware experience. It configures what each user sees first, which KPIs matter, which questions are recommended, which widgets appear, which ML models are relevant, and what operational actions the copilot should suggest.

## SQL Setup

Run in Supabase SQL Editor:

```text
023_role_based_intelligence_layer.sql
```

Smoke check:

```sql
select
  role_code,
  role_name,
  jsonb_array_length(kpis) as kpi_count,
  jsonb_array_length(default_questions) as question_count,
  jsonb_array_length(dashboard_widgets) as widget_count,
  jsonb_array_length(action_templates) as action_template_count
from public.v_role_intelligence_profile
order by role_name;
```

Expected: seven roles are returned.

## Tables

- `role_definitions`: role identity, objectives, models, default insights, actions, data access scope, and follow-up questions.
- `role_kpis`: KPI definitions and visualization metadata by role.
- `role_default_questions`: role-specific starter questions for the copilot.
- `role_dashboard_widgets`: dashboard/widget configuration for the frontend.
- `role_action_templates`: action playbooks triggered by model scores, rules, and operational states.
- `v_role_intelligence_profile`: API-ready profile joining all role configuration into one payload.

## API Design

Start the local API:

```powershell
uvicorn role_intelligence_service:app --reload --port 8020
```

### List Roles

```http
GET /api/roles
```

Returns:

```json
[
  {
    "role_code": "insurance_agent",
    "role_name": "Insurance Agent",
    "role_category": "frontline",
    "description": "Frontline producer or servicing agent..."
  }
]
```

SQL source:

```sql
select role_code, role_name, role_category, description
from public.role_definitions
where active_flag = true
order by display_order, role_name;
```

### Get Role Profile

```http
GET /api/roles/{role_code}/profile
```

SQL source:

```sql
select *
from public.v_role_intelligence_profile
where role_code = :role_code;
```

Returns role objectives, KPIs, default questions, widgets, action templates, recommended models, access scope, default insights, and follow-up questions.

### Get Role Copilot Context

```http
POST /api/copilot/context
Content-Type: application/json

{
  "role_code": "agency_manager",
  "question": "Which agents have declining MAPA productivity?"
}
```

Recommended retrieval flow:

1. Load `v_role_intelligence_profile` for `role_code`.
2. Retrieve semantic context from pgvector using the question plus role objectives.
3. Add role KPIs, widgets, and action templates as system context.
4. Generate SQL or business explanation with access scope constraints.
5. Log to `query_audit_log` or `nba_decision_audit` depending on workflow.

### Get Role Actions

```http
GET /api/roles/{role_code}/actions
```

Returns action templates plus live `next_best_actions` filtered by the role’s access scope.

## Frontend Behavior

### Role Selector

Show a role selector at the top of the copilot experience. The selected role controls:

- Default dashboard layout
- Sample questions
- KPI cards
- Allowed domains
- Explanation tone
- Recommended actions
- Follow-up question suggestions

### Landing State

When a user selects a role:

1. Load `v_role_intelligence_profile`.
2. Render `dashboard_widgets` in `display_order`.
3. Show `default_insights` as insight chips.
4. Show `role_default_questions` as sample query buttons.
5. Load relevant `next_best_actions` when the role is operational.

### Query Experience

When the user asks a question:

1. Include role objectives and data access scope in the prompt.
2. Retrieve pgvector context from `semantic_documents`.
3. Retrieve KPI definitions from `role_kpis`.
4. Generate SQL only within the role’s scope.
5. Return answer, SQL, retrieved context, confidence, and follow-up questions.

### Role-Specific Defaults

- Insurance Agent: action queue first, customer-level output, short guidance, next contact.
- Agency Manager: agent comparison, productivity trends, coaching opportunities.
- Campaign Manager: funnel, response/conversion, suppression and attribution.
- Claims Manager: severity, fraud risk, claim ratio, review queues.
- Sales Director: premium growth, persistency, product mix, channel and agency performance.
- Executive Leadership: aggregate portfolio view, risk hotspots, strategic summary.
- Data Analyst: SQL, lineage, data quality, model score distribution, semantic retrieval health.

## Example Outputs

### Insurance Agent Profile

```json
{
  "role_code": "insurance_agent",
  "role_name": "Insurance Agent",
  "primary_objectives": [
    "Prioritize customers to contact today",
    "Protect policies at risk of lapse",
    "Convert high-quality leads"
  ],
  "recommended_ml_models": [
    "propensity_to_buy",
    "policy_lapse",
    "customer_churn",
    "next_best_product",
    "lead_conversion"
  ],
  "default_questions": [
    {
      "question_text": "Which customers should I contact first today?",
      "question_type": "next_action"
    }
  ],
  "dashboard_widgets": [
    {
      "widget_code": "today_action_queue",
      "widget_title": "Today Action Queue",
      "widget_type": "action_queue"
    }
  ]
}
```

### Agency Manager Insight

```json
{
  "role_code": "agency_manager",
  "insight": "Three agents show declining MAPA productivity and high open-action load. Reassign new leads away from low-capacity agents and schedule coaching for agents with low conversion.",
  "recommended_follow_up_questions": [
    "Which agents are overloaded?",
    "Which agents need coaching this month?",
    "Which territories improved after movement?"
  ]
}
```

### Campaign Manager Action

```json
{
  "role_code": "campaign_manager",
  "action_name": "Campaign Follow-Up Queue",
  "trigger_condition": "campaign_response score is HIGH and customer has marketing opt-in",
  "expected_outcome": "Higher response-to-conversion rate"
}
```

## GenAI Prompt Pattern

Use this system context before SQL or insight generation:

```text
You are an Insurance Decision Intelligence Copilot.
The user role is {role_name}.
Optimize for these objectives: {primary_objectives}.
Respect this data access scope: {data_access_scope}.
Use these role KPIs: {kpis}.
Prefer these models when relevant: {recommended_ml_models}.
When recommending actions, use these templates: {action_templates}.
Retrieve business definitions from semantic_documents and business_glossary.
Do not expose data outside the role scope.
```
