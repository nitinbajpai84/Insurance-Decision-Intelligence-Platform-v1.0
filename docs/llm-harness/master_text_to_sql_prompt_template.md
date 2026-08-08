# Master Text-to-SQL Prompt Template

## Role
{{role}}

## User Question
{{question}}

## Intent
{{intent}}

## Allowed Active Tables Only
{{allowed_active_tables}}

## Allowed Columns Only
{{allowed_columns}}

## KPI Registry Entries
{{kpi_registry_entries}}

## Model Registry Entries
{{model_registry_entries}}

## Verified Join Paths
{{verified_join_paths}}

## SQL Generation Rules
- Generate only SELECT or WITH statements.
- Use only ACT tables with `ai_sql_allowed = true`.
- Do not use TRUN tables.
- Do not invent missing tables, columns, KPIs, or models.
- Use the latest record per entity when score tables are involved.
- Add LIMIT for detail-level queries.

## Missing Data Rules
- If a required physical table is missing, respond with `NOT_SUPPORTED`.
- If a required column is missing, explain the missing column and offer the closest supported question.
- If a KPI or model is partial, mark the answer partial.

## Output JSON Contract
```json
{
  "answerability": "SUPPORTED | PARTIAL | NOT_SUPPORTED",
  "sql": "",
  "business_logic": "",
  "tables_used": [],
  "columns_used": [],
  "kpis_used": [],
  "models_used": [],
  "missing_tables": [],
  "missing_columns": [],
  "missing_data_points": [],
  "assumptions": [],
  "confidence_score": 0.0
}
```
