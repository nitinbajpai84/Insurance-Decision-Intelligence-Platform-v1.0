# Demo Runbook — Insurance PoC V2.0 (Agentic)

Smoke-tested end-to-end on 2026-07-23, then again after a user report of it "going down
after 1-2 minutes." **Root cause found and fixed: see "Instability root cause" below — always
use the updated `start_v2.bat` / commands in this file, not the old `--reload` flag.**

## What this is

A parallel, agentic rebuild of the V1 text-to-SQL stack: cooperating agents instead of a
single pipeline, local **DuckDB** instead of Supabase (no cloud dependency, no pause risk),
a **LanceDB** vector store for context + a semantic cache, and a token-by-token **SSE
stream** to the browser. V1 is untouched and lives on its own ports; V2 is fully
self-contained in `backend_v2/`, `frontend_v2/`, `database/`, `lance_store/`, `embeddings/`,
plus a `graph/` module (graph-grounded SQL generation, feedback/adaptation loop) that isn't
mentioned in `V2_README.md` but is wired in and working.

## Port map

| Component   | URL                     |
|-------------|-------------------------|
| V2 backend  | http://127.0.0.1:3001   |
| V2 frontend | http://127.0.0.1:3002   |
| V1 (other)  | http://127.0.0.1:3000 — leave alone, unrelated to this smoke test |

## Starting it

```powershell
# Backend (from project root) — use `venv`, NOT `.venv` (see note below)
.\venv\Scripts\python.exe -m uvicorn backend_v2.api.main:app --host 127.0.0.1 --port 3001

# Frontend
cd frontend_v2
npm run dev
```

Or use `start_v2.bat` from the project root, which does both plus opens the browser
(now fixed to not pass `--reload` — see below).

**Important — two venvs exist at project root:** `venv\` (created per `setup_v2.bat`) has
the real V2 dependencies (`duckdb`, `lancedb`, `google-generativeai`, `fastapi`, `uvicorn`,
`pandas`, `pyarrow`). `.venv\` is a leftover/partial copy — it's missing `duckdb` and
`lancedb` entirely and will NOT run the backend. Always use `venv\Scripts\python.exe`.

## Verified working (2026-07-23)

- **DuckDB**: `database/insurance_v2.duckdb` (476 MB) opens cleanly, not locked by any other
  tool, 85 tables.
- **LanceDB**: all 5 vector tables populated (`insurance_glossary_vectors`: 162,
  `insurance_schema_vectors`: 731, `insurance_semantic_vectors`: 50,
  `insurance_query_history`: 5 — grows as you ask questions, `insurance_entity_vectors`: 0 —
  present but unpopulated, not used by the current flow).
- **Gemini**: key present, `gemini-2.5-flash-lite` responding.
- **Backend build**: all 20+ routes smoke-tested clean across `backend_v2/api/routes.py`
  (health, roles, glossary, evidence), `data_products.py` (home KPIs, customer/agent
  search, leaderboard, campaigns, lapse-risk), `process_routes.py` (lead-conversion,
  repurchase, demand, campaign-effectiveness), and `graph/graph_routes.py` +
  `graph/feedback_routes.py` (subgraph, discoveries, model, review-queue,
  adaptation-log) — all 200 OK.
- **Full agentic pipeline verified live** via `/api/v2/ask` SSE stream: context retrieval
  → SQL generation → validation → execution → streamed insight, in ~5-9s. Real generated
  SQL executed against DuckDB, real streamed answer (e.g. "policy lapse rate stands at
  9.12%"), correct confidence scoring, and a "Governed answer" badge showing which glossary
  metrics grounded the SQL (graph-grounded SQL path, `USE_GRAPH_GROUNDED_SQL=True` by
  default).
- **Frontend build**: `npm run build` clean, 15 routes static-optimized, no type/lint
  errors.
- **Frontend live-tested** on `/ai-intelligence-v2`: asked "What is the overall policy
  lapse rate?" — full 6-step live tracker populated correctly (context retrieved 741ms →
  SQL generated 3.1s → validated 0ms → executed 70ms → result validated → insight
  generated), transparency panel showed real token-budget usage (1242/6000, schema/
  glossary/docs breakdown), evidence and reasoning trace rendered, no console errors, no
  failed network requests.
- **Evidence Hub** (`/insight-evidence-hub-v2`): shows full query history including both
  live test questions, with steps/latency/tokens/cache columns.
- **Business Glossary editor** (`/glossary-v2`): renders all seeded terms with
  definitions/owners/last-updated; edit/diff-preview/reason-required flow present (not
  exercised, but page loads and lists real data cleanly).

## All 14 frontend pages — verified individually (2026-07-23, second pass)

Every route in `frontend_v2/app/` checked with real data, no console errors, no failed
network requests:

| Route | Status |
|---|---|
| `/` | OK — landing/nav |
| `/agent-performance` | OK — leaderboard, KPIs, real agent rows (e.g. Maria Scott, S$199K) |
| `/ai-intelligence-v2` | OK — full ask flow, live tracker, transparency panel |
| `/campaign-effectiveness` | OK — funnel, ROI, real campaign list |
| `/campaign-process-v2` | OK — funnel + ROI-by-channel charts, leaderboard |
| `/context-graph-v2` | OK — force graph, 162 nodes / 129 links |
| `/demand-v2` | OK — demand index by region/product |
| `/glossary-v2` | OK — governed glossary editor, real terms |
| `/insight-evidence-hub-v2` | OK — query history with steps/latency/tokens/cache |
| `/know-your-agent` | OK — search UI (renders empty until a search is run) |
| `/know-your-customer` | OK — search UI + segment shortcuts |
| `/lead-conversion-v2` | OK — 6-stage funnel with real counts/drop-off reasons |
| `/policy-lapse-risk` | OK — hotspots by region/branch/product/agent/segment |
| `/repurchase-v2` | OK — repurchase rate by segment, time-to-repurchase chart |

(A first automated pass flagged all 14 pages as "FAIL" on a crude string search for `500`
and `"This page could not be found"` — false positive: `500` matched the Tailwind class
`text-gray-500`, and the 404 text is just Next.js's built-in fallback component shipped in
every page's JS bundle, never actually rendered. Manual browser verification confirmed all
pages are genuinely fine.)

No bugs found in this first pass — but see below for a real instability bug found and fixed
on a second pass, after the user reported the backend "going down after 1-2 minutes."

## Instability root cause (found and fixed 2026-07-23)

**Symptom:** backend becomes unresponsive/crashes within 1-2 minutes of starting via
`start_v2.bat`.

**Root cause:** `start_v2.bat` launched uvicorn with `--reload`. The `watchfiles` package
(uvicorn's efficient, OS-level file-watching reloader) is **not installed** in `venv`, so
uvicorn silently falls back to `StatReload` — a much cruder watcher that calls
`reload_dir.rglob("*.py")` (a full recursive filesystem walk) roughly every 0.25-1 second,
across **every directory under the project root**, because no `--reload-dir` was specified.
That project root contains:
- two full Python venvs (`venv/`, `.venv/`) — thousands of site-packages files each,
- `frontend_v2/node_modules` — tens of thousands of files,
- `data/`, `data_test/`, etc. — hundreds of MB of CSVs,
- the 476 MB `database/insurance_v2.duckdb` file's directory.

Measured impact: the reloader subprocess's CPU time went from ~32s to ~212s (and still
climbing) within about 10 minutes of idle-to-light-use — i.e. constant, escalating CPU spend
on a directory walk that finds nothing relevant, not on serving requests. Under real demo
load (or a slower disk, or antivirus scanning the same trees concurrently) this is enough to
make the process unresponsive or cause it to be killed — matching the "down after 1-2 min"
symptom exactly.

**Fix applied:** removed `--reload` from `start_v2.bat`. Confirmed the fix: re-ran the exact
same real questions through `/api/v2/ask` with `--reload` removed, and the process's CPU
usage stayed at ~0.015s total (vs. 212s+ and rising for the reloader alone) after 3 full
LLM-backed question/answer cycles. No functional loss for a demo — reload only matters if
you're editing backend code live while the server runs.

**If you need live reload while developing:** install `watchfiles` (`pip install watchfiles`
in `venv`) and scope the reload dirs explicitly so it never touches the venvs/node_modules/
data directories:
```powershell
.\venv\Scripts\python.exe -m uvicorn backend_v2.api.main:app --port 3001 --reload --reload-dir backend_v2 --reload-dir graph
```

## Config note (not a bug, just worth knowing)

The project-root `.env` doesn't explicitly set most V2-specific keys (`GEMINI_MODEL`,
`DUCKDB_PATH`, `LANCEDB_PATH`, `API_PORT`, `MAX_CONTEXT_TOKENS`,
`CACHE_SIMILARITY_THRESHOLD`, `CACHE_TTL_HOURS`) — `backend_v2/config.py` has sane
defaults for all of them that already point at the right files/ports, so this is fine as-is.
Only add these to `.env` if you want to override a default.

## Demo script suggestion

1. Open `/ai-intelligence-v2`, pick a role (e.g. Executive Leadership), ask one of the
   sample questions — narrate the live 6-step tracker as it fills in.
2. Point out the transparency panel (token budget, schema/glossary/docs context) and the
   "Governed answer" badge — shows the answer is grounded in named metrics, not free-form
   SQL guessing.
3. Ask the same question again (or a close paraphrase) to demonstrate the semantic cache
   hit (⚡ badge, skipped steps 2-4, near-instant answer).
4. Switch to `/insight-evidence-hub-v2`, click into the query you just ran, show the full
   agent reasoning trace and latency/token breakdown.
5. Switch to `/glossary-v2`, edit a definition, show the diff preview and reason-required
   gate, save, and mention it re-embeds immediately so the next question uses the new
   meaning.

## Known non-blockers

- `insurance_entity_vectors` LanceDB table exists but has 0 rows — not used by the current
  ask/context flow, so it doesn't affect the demo; only relevant if something later wires up
  entity-level vector search.
- Two venvs at project root (`venv` vs `.venv`) is a bit confusing — worth deleting the
  unused `.venv` at some point to avoid someone accidentally running the wrong one, but not
  urgent.
