# Client Deliverables

This folder contains client-ready deliverables generated from the architecture and documentation pack.

## Deliverables Created

- Master Excel documentation workbook in `excel/`.
- Focused Excel mapping workbooks in `excel/`.
- Mermaid diagrams exported to PNG in `diagrams-png/`.
- Mermaid diagrams exported to JPG in `diagrams-jpg/`.
- Diagram indexes and quality report.

## Excel Workbooks

| Workbook | Purpose |
|---|---|
| `excel/Insurance_Decision_Intelligence_Documentation_Pack.xlsx` | Master documentation pack |
| `excel/Insurance_Decision_Intelligence_Documentation_Pack_latest.xlsx` | Latest refreshed master documentation pack copy |
| `excel/ETL_Mapping.xlsx` | ETL Mapping |
| `excel/Data_Model_Subject_Area_Mapping.xlsx` | Data Model Subject Area Mapping |
| `excel/ML_Model_Feature_Mapping.xlsx` | ML Model Feature Mapping |
| `excel/KPI_Definitions_and_Formulas.xlsx` | KPI Definitions and Formulas |
| `excel/Context_and_Embedding_Mapping.xlsx` | Context and Embedding Mapping |
| `excel/UI_Tab_Feature_Matrix.xlsx` | UI Tab Feature Matrix |
| `excel/API_and_Service_Catalog.xlsx` | API and Service Catalog |

Use the master workbook for end-to-end client review. Use focused workbooks when a client team wants to review one area only, such as ETL, ML features, KPIs, context mapping, or API catalog.

## Diagram Outputs

- PNG diagrams: `diagrams-png/` (10 rendered)
- JPG diagrams: `diagrams-jpg/` (10 rendered)
- Diagram index files are available in both diagram folders.

## Available Diagrams

| Diagram | Description |
|---|---|
| `01-overall-solution-architecture` | Overall solution architecture |
| `02-data-architecture` | Layered data architecture |
| `03-insurance-subject-area-model` | Insurance subject-area relationship model |
| `04-etl-elt-data-flow` | ETL and ELT flow |
| `05-ml-feature-and-scoring-flow` | ML feature and scoring flow |
| `06-context-pgvector-retrieval-flow` | Context and pgvector retrieval flow |
| `07-text-to-sql-flow` | Text-to-SQL flow |
| `08-ai-intelligence-sequence` | AI Intelligence sequence |
| `09-insight-evidence-lineage` | Insight Evidence Hub lineage |
| `10-ui-navigation-data-products` | UI navigation and data products |

## Render Failures

No diagram render failures were recorded.

## Regenerating Diagrams

From the project root, run:

```powershell
npx.cmd -y @mermaid-js/mermaid-cli -i docs/client-documentation/diagrams/<diagram>.mmd -o docs/client-deliverables/diagrams-png/<diagram>.png -b white -s 2
```

Then convert PNG to JPG with Pillow or rerun the refresh script.

## Refreshing Excel Documentation

From the project root, run:

```powershell
& 'C:\Users\Nitin\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\create_client_deliverables.py
```
