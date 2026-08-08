# Insurance PoC V2.0 — Agentic Decision Intelligence

V2 is a **parallel, agentic** rebuild of the V1 text-to-SQL stack. It keeps V1's
familiar UX but replaces the sequential 6-step pipeline with cooperating agents,
swaps Supabase/Postgres for a local **DuckDB** analytics file, adds a **LanceDB**
vector store for context + a semantic cache, and **streams** the answer to the
browser token-by-token over Server-Sent Events.

> **V1 is untouched.** V2 lives in its own folders (`backend_v2/`, `frontend_v2/`,
> `database/`, `embeddings/`, `lance_store/`) and its own ports. You can run V1 and
> V2 side by side.

---

## Port map

| Component        | URL                       | Notes                          |
| ---------------- | ------------------------- | ------------------------------ |
| V1 frontend      | http://127.0.0.1:3000     | unchanged, optional            |
| **V2 API**       | http://127.0.0.1:3001     | FastAPI, `backend_v2.api.main` |
| **V2 frontend**  | http://127.0.0.1:3002     | Next.js 15, PwC theme          |

---

## Prerequisites

- **Python 3.9+** on `PATH` (3.11 recommended).
- **Node.js 18+** and npm (for the V2 frontend).
- **DuckDB CLI** (only needed for `setup_v2.bat`'s schema step and manual queries).
  Default expected path:
  `D:\Projects\CLD Projects\duckdb_cli-windows-amd64\duckdb.exe`
  — edit `setup_v2.bat` if yours lives elsewhere.
- A **Gemini API key** in the project-root `.env` (`GEMINI_API_KEY=...`).

---

## One-time setup

From the project root (`D:\Projects\CLD Projects\Insurance PoC - V2.0`):

```bat
setup_v2.bat
```

This runs six steps:

1. Create the `venv` virtual environment.
2. `pip install -r embeddings\requirements.txt` (covers FastAPI, uvicorn, DuckDB,
   LanceDB, google-generativeai, pandas, pyarrow, python-dotenv).
3. Build the DuckDB schema from `database\schema.sql` into `database\insurance_v2.duckdb`.
4. Seed synthetic insurance data (`database\seed_data.py`).
5. Initialise the LanceDB tables (`embeddings\lance_setup.py`).
6. Run the embedding pipeline (`embeddings\embed_pipeline.py`) to populate the
   glossary / schema / semantic-doc / query-history vector tables.

> **DuckDB single-writer lock:** DuckDB allows only one writer. If you have the
> `insurance_v2.duckdb` file open in **DBeaver** (or any other tool) with a
> read-write connection, the backend cannot open it and SQL execution will fail
> with an `IO Error … file is being used by another process`. **Disconnect that
> tool before running V2.**

---

## Starting V2

```bat
start_v2.bat
```

This activates `venv`, launches the API on **3001** (with `--reload`), installs
frontend deps and launches the Next.js dev server on **3002**, then opens the
browser. Two console windows ("V2 Backend" / "V2 Frontend") stay open so you can
watch logs; close them to stop the servers.

### Manual start (alternative)

```bat
call venv\Scripts\activate
python -m uvicorn backend_v2.api.main:app --port 3001 --reload
```
```bat
cd frontend_v2
npm install
npm run dev          REM serves on 127.0.0.1:3002
```

---

## Architecture overview

```
Browser (Next.js, frontend_v2)
   │  POST /api/v2/ask  (fetch + ReadableStream SSE)
   ▼
FastAPI (backend_v2/api)
   └── orchestrator.stream_pipeline()
        1. context_agent     ── 4 vector searches in PARALLEL (asyncio.gather):
        │                        glossary · semantic docs · schema · query history
        │                        + token-budget assembly (6000) + semantic-cache check
        │   (cache hit? → skip 2–4, stream the cached answer)
        2. sql_agent         ── Gemini → validated read-only DuckDB SQL (LIMIT 50)
        3. (parallel) schema pre-load for repair candidates
        4. execution_agent   ── EXPLAIN-first execute on DuckDB (read-only),
        │                        one-shot Gemini auto-repair on failure
        5. insight_agent     ── STREAMS the business answer token-by-token
        └── tracer → every step logged to DuckDB `agent_reasoning_log`
```

- **DuckDB** (`database/insurance_v2.duckdb`) — analytics tables + the
  `agent_reasoning_log` trace table + the `business_glossary` table.
- **LanceDB** (`lance_store/`) — five vector tables: `insurance_glossary_vectors`,
  `insurance_schema_vectors`, `insurance_semantic_vectors`,
  `insurance_query_history`, `insurance_entity_vectors`.
- **Gemini** — `gemini-embedding-001` (3072-dim) for retrieval; a generation model
  (default `gemini-2.5-flash-lite`, configurable) for SQL + insight.

### Frontend pages (`frontend_v2`)

| Route                          | Purpose                                                      |
| ------------------------------ | ----------------------------------------------------------- |
| `/`                            | Landing / navigation                                        |
| `/ai-intelligence-v2`          | Ask box, role switcher, streaming answer, live 6-step tracker, context viewer, recommendation, reasoning panel |
| `/insight-evidence-hub-v2`     | History browser + full evidence trace (4-column view, agent trace, latency/token charts) |
| `/glossary-v2`                 | Governed Business Glossary editor                           |

---

## Environment variables

Set in the **project-root `.env`** (V2 also reads `database\.env`). A template is in
`.env.v2.example`; the frontend reads `frontend_v2\.env.local`.

| Variable                       | Default                                   | Used by            |
| ------------------------------ | ----------------------------------------- | ------------------ |
| `GEMINI_API_KEY`               | — (required)                              | backend            |
| `GEMINI_MODEL`                 | `gemini-2.5-flash-lite`                    | backend generation |
| `EMBEDDING_MODEL`              | `models/gemini-embedding-001`             | backend retrieval  |
| `DUCKDB_PATH`                  | `database\insurance_v2.duckdb`            | backend            |
| `LANCEDB_PATH`                 | `lance_store`                             | backend            |
| `API_PORT`                     | `3001`                                    | backend            |
| `MAX_CONTEXT_TOKENS`           | `6000`                                    | context agent      |
| `CACHE_SIMILARITY_THRESHOLD`   | `0.92`                                    | semantic cache     |
| `CACHE_TTL_HOURS`              | `24`                                      | semantic cache     |
| `LLM_TIMEOUT_SECONDS`          | `60`                                      | backend            |
| `NEXT_PUBLIC_API_V2_URL`       | `http://127.0.0.1:3001`                   | frontend           |

CORS on the API allows `localhost`/`127.0.0.1` on ports **3000** and **3002**.

---

## Using the Business Glossary Editor

Open **`/glossary-v2`**. The editor is a governed control surface over the
`business_glossary` DuckDB table:

1. **Browse / filter** — search by term, subject area, or definition text.
2. **Edit** — click **Edit** on a row; the definition becomes editable and a
   **diff preview** shows the old definition (red strikethrough) vs the new
   (green) before you save.
3. **Reason required** — you must enter *why* you're changing the definition
   (audit requirement); Save is blocked without it.
4. **Save** → `POST /api/v2/glossary/update`. The backend:
   - updates the definition + `updated_at` in DuckDB,
   - **re-embeds** the term into `insurance_glossary_vectors` (LanceDB) so future
     SQL generation uses the new meaning,
   - writes an audit row to `agent_reasoning_log`.
5. **Locked terms** — inactive terms show a lock icon and cannot be edited unless
   you toggle **Admin mode**.

Because edits re-embed immediately, a changed definition influences the **next**
question's retrieved context — meaning is governed, not hard-coded.

---

## How the semantic cache works

The context agent embeds the incoming question and searches
`insurance_query_history` (past Q&A with their answers + SQL). If the best match's
cosine similarity ≥ `CACHE_SIMILARITY_THRESHOLD` (default **0.92**), it's a
**cache hit**:

- Steps 2–4 (SQL generation, validation, execution) are **skipped entirely**.
- The cached answer is streamed straight to the UI (the 6-step tracker shows those
  steps as "skipped", and the answer panel shows a ⚡ *Answered from semantic
  cache* badge with the similarity score).
- This is the big latency win versus re-running the whole pipeline.

Near-misses (below threshold) are still surfaced to the SQL agent as
*similar past queries* to steer generation, but do not short-circuit the pipeline.

---

## Querying DuckDB manually with the CLI

> Close any other read-write connection (e.g. DBeaver) first, or open read-only.

```bat
REM interactive shell
"D:\Projects\CLD Projects\duckdb_cli-windows-amd64\duckdb.exe" "database\insurance_v2.duckdb"
```

```sql
-- inside the CLI
.tables
SELECT count(*) FROM policies;
SELECT * FROM business_glossary LIMIT 10;
SELECT query_id, agent_name, duration_ms FROM agent_reasoning_log ORDER BY id DESC LIMIT 20;
.quit
```

Read-only one-liner (safe to run while the API is up):

```bat
"D:\Projects\CLD Projects\duckdb_cli-windows-amd64\duckdb.exe" -readonly "database\insurance_v2.duckdb" -c "SELECT count(*) FROM policies;"
```

---

## API endpoints (V2)

| Method | Path                              | Purpose                                   |
| ------ | --------------------------------- | ----------------------------------------- |
| POST   | `/api/v2/ask`                     | SSE stream of the agentic pipeline        |
| GET    | `/api/v2/roles`                   | available roles + descriptions            |
| GET    | `/api/v2/glossary`                | all glossary terms                        |
| POST   | `/api/v2/glossary/update`         | governed definition update + re-embed     |
| GET    | `/api/v2/evidence/recent`         | last N query traces (Evidence Hub Mode A) |
| GET    | `/api/v2/evidence/{query_id}`     | full reasoning trace (Evidence Hub Mode B)|
| GET    | `/api/v2/health`                  | DuckDB / LanceDB / Gemini status          |

Error responses are JSON: `{ "error": ..., "status_code": ..., "path": ... }`.

---

## How V2 relates to V1

- **V1 is read-only / untouched.** No V1 file is modified by V2; V1 keeps its
  Supabase backend and port 3000.
- V2 is a **parallel** stack with its own data plane (local DuckDB + LanceDB),
  its own backend (`backend_v2`, port 3001), and its own frontend
  (`frontend_v2`, port 3002, PwC-themed).
- You can demo them side by side: V1 on `:3000`, V2 on `:3002`.

---

## Troubleshooting

| Symptom                                              | Cause / fix                                                                 |
| ---------------------------------------------------- | --------------------------------------------------------------------------- |
| `sql_executed: failed`, `IO Error … used by another process` | DuckDB file locked by DBeaver/another tool — disconnect it.                 |
| `403 PERMISSION_DENIED` from Gemini                  | API key blocked/over quota — check the key in `.env`.                       |
| Health shows `lancedb: error`                        | Run `embeddings\lance_setup.py` + `embeddings\embed_pipeline.py`.           |
| Frontend can't reach API                             | Confirm API on 3001 and `NEXT_PUBLIC_API_V2_URL` in `frontend_v2\.env.local`.|
| Empty Evidence Hub                                   | No queries logged yet — ask something on `/ai-intelligence-v2` first.       |
