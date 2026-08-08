# Insurance PoC V2.0 — Database (DuckDB)

Local analytical database for the V2 agentic AI stack. Replaces V1's Supabase
Postgres with an embedded DuckDB file, seeded from the V1 synthetic CSVs in
`..\data\`.

## Files

| File | Purpose |
|---|---|
| `schema.sql` | DDL for all ~48 tables (customer, policy, agent, sales, campaign, claims, product/payment, ML/AI layer, V2 agentic tables) |
| `seed_data.py` | Loads V1 CSVs + generates data for new V2 tables and minimum-count top-ups |
| `db_connection.py` | Reusable connection module (`read_connection`, `write_connection`, `execute_query`, `health_check`, `get_table_schema`, `get_all_tables`) |
| `run_schema.bat` | One-click schema creation via the DuckDB CLI |
| `.env` | `DUCKDB_PATH` for this database |
| `insurance_v2.duckdb` | The database file (created by step 1) |

## Prerequisites

- DuckDB CLI at `D:\Projects\CLD Projects\duckdb_cli-windows-amd64\duckdb.exe`
- Python 3.10+ with the DuckDB package: `pip install duckdb`
  (a ready-made virtualenv exists at `database\.venv` — use
  `database\.venv\Scripts\python.exe` to run the scripts without installing anything)

## Step 1 — Create the schema

Double-click or run from a terminal:

```bat
cd /d "D:\Projects\CLD Projects\Insurance PoC - V2.0\database"
run_schema.bat
```

Expected output: `Schema created successfully`. This creates
`insurance_v2.duckdb` with all empty tables, sequences, and FK comments.
The script is idempotent (`CREATE TABLE IF NOT EXISTS`).

## Step 2 — Seed the data

```bat
cd /d "D:\Projects\CLD Projects\Insurance PoC - V2.0\database"
python seed_data.py
```

What it does:

1. Loads every V1 CSV from `..\data\` into the matching table
   (renames handled: `policy_coverages.csv` → `policy_coverage`,
   `customer_satisfaction_surveys.csv` → `customer_satisfaction_survey`,
   `agent_mapa_metrics.csv` → `agent_performance`).
2. Tops up minimum row counts where V1 data is short:
   500 customers, 200 agents, 1,000 policies, 50 campaigns, 200 claims,
   30 semantic documents, 100 glossary terms — Singapore context
   (SGD amounts, SG territories, PRU-style product names).
3. Generates the V2-only tables: `customer_type`, `households`,
   `household_members`, `policy_type_config`, `agent_service_events`,
   `agent_assessments`, `model_versions`, `vector_index_log`,
   `agent_reasoning_log`, `semantic_cache`, and derives
   `agent_performance.conversion_rate` / `performance_band`.
4. Prints a per-table row-count summary.

Re-running is safe: CSV-backed tables are truncated and reloaded.
(Generated-only tables are appended — drop/recreate the DB file for a fully
clean rebuild: delete `insurance_v2.duckdb`, run steps 1–2 again.)

## Step 3 — Query via the CLI

```bat
"D:\Projects\CLD Projects\duckdb_cli-windows-amd64\duckdb.exe" "D:\Projects\CLD Projects\Insurance PoC - V2.0\database\insurance_v2.duckdb"
```

Useful commands inside the shell:

```sql
.tables                                  -- list all tables
SELECT count(*) FROM policies;
SELECT line_of_business, count(*) AS policies, round(sum(annual_premium),0) AS premium_sgd
FROM policies p JOIN products pr USING (product_id)
GROUP BY 1 ORDER BY premium_sgd DESC;
SELECT * FROM semantic_cache;            -- V2 answer cache
SELECT * FROM agent_reasoning_log LIMIT 10;
.quit
```

Read-only open (recommended while the app is running):

```bat
duckdb.exe -readonly "...\insurance_v2.duckdb"
```

## Step 4 — Use from Python

```python
from database.db_connection import execute_query, health_check, get_all_tables

print(health_check())
rows, cols = execute_query("SELECT count(*) AS n FROM customers")
catalog = get_all_tables()        # full schema for SQL-agent context building
```

`DUCKDB_PATH` resolution order: OS env var → `database\.env` → project-root
`.env` → default `database\insurance_v2.duckdb`.

## Notes

- DuckDB allows **one writer at a time** — use `read_connection()` everywhere
  except seeding/logging paths.
- Vectors are NOT stored in DuckDB; `vector_index_log` tracks which rows have
  been chunked/embedded into LanceDB (`lance_table` column).
- All V1 files remain untouched; everything in this folder is new for V2.
