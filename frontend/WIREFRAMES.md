# Insurance Decision Intelligence Frontend Wireframes

## Desktop Layout

```text
+--------------------------------------------------------------------------------+
| Insurance Decision Intelligence Platform                             API status |
+--------------------------------------------------------------------------------+
| Role | Chat | SQL | Explain | Lineage | 360                                     |
+-------------------------+------------------------------------------------------+
| Role Selector           | AI Intelligence                                      |
| - active role           | - business question input                            |
| - objectives            | - sample question buttons                            |
|                         | - answer summary                                     |
| KPI Dashboard           +--------------------------+---------------------------+
| - role KPIs             | Result Table             | Retrieved Context         |
| - dashboard widgets     | - SELECT output          | - pgvector snippets       |
|                         +--------------------------+---------------------------+
| Feedback                | Recommendation Cards     | Generated SQL Viewer      |
| - thumbs up/down        | - action, reason, score  | - read-only SQL           |
| - notes                 +--------------------------+---------------------------+
|                         | Explainability Panel     | Data Lineage Panel        |
|                         | - facts, rules, models   | - source tables/metrics   |
+-------------------------+------------------------------------------------------+
| 360 Workbench                                                                  |
| [Customer 360] [Agent 360] [Campaign 360] [Claims 360]  UUID input  Load       |
| Summary panel                       Detail sections and recent records          |
+--------------------------------------------------------------------------------+
```

## Mobile Layout

```text
+--------------------------------------+
| AI Intelligence                       |
| API status                            |
+--------------------------------------+
| Role Selector                         |
| KPI Dashboard                         |
| Feedback                              |
| Intelligence Chat                     |
| Result Table                          |
| Retrieved Context                     |
| Recommendation Cards                  |
| Generated SQL Viewer                  |
| Explainability Panel                  |
| Data Lineage Panel                    |
| 360 Workbench                         |
+--------------------------------------+
```

## Interaction Notes

- Role changes refresh dashboard KPIs, widgets, default questions, and role objectives.
- AI Intelligence calls the backend ask route and hydrates SQL, results, context, recommendations, and explainability.
- Entity 360 tabs share a UUID lookup pattern and call the matching gateway route.
- Lineage lookup accepts an `insight_lineage_id`; otherwise the panel summarizes lineage from the latest intelligence answer.
- Feedback is local for the MVP and can later be wired to an audit or user feedback table.
