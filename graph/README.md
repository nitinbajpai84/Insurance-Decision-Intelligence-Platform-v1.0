# V2.0 Graph / Ontology Layer (DuckDB + DuckPGQ + NetworkX)

A knowledge-graph layer over the V2 DuckDB warehouse. It turns the business
glossary, metrics, decision processes, and real data rows into a typed graph,
registers a **DuckPGQ property graph** for SQL/PGQ traversal, and powers
**GraphRAG** retrieval + natural-language **decision-rule capture** (Mini-MORRIE).

## Prerequisites

- DuckDB **1.4.4** (DuckPGQ has no Windows build for 1.5.3 — see note below).
- `pip install networkx` and the DuckPGQ community extension:
  ```
  python -c "import duckdb; c=duckdb.connect(); c.execute('INSTALL duckpgq FROM community; LOAD duckpgq;')"
  ```

> **DuckPGQ / DuckDB version note:** the community DuckPGQ extension is published
> for DuckDB ≤ 1.4.4 on `windows_amd64` (no `v1.5.3` build at time of writing).
> The venv was pinned to `duckdb==1.4.4`. Existing `insurance_v2.duckdb` opens
> unchanged under 1.4.4. Every traversal also has a **recursive-SQL fallback**,
> so the layer still works if the extension can't load.

## Files

| File | Purpose |
|------|---------|
| `graph_schema.sql` | `concept_nodes`, `decision_rules`, `graph_edges`, `graph_nodes_all` |
| `build_graph.py` | seed + hydrate the graph, register the property graph |
| `graph_traversal.py` | `get_subgraph`, `find_decision_paths`, `cross_domain_scan`, `to_networkx`, `export_graph_json` |
| `graph_context_agent.py` | GraphRAG: vector recall + subgraph + rules → `GraphContext` |
| `rule_capture.py` | Mini-MORRIE NL→rule parser + validator + persistence |
| `graph_routes.py` | FastAPI routes (`/api/v2/graph/*`) |

## Build

```
venv\Scripts\python.exe graph\build_graph.py
```
Prints node/edge counts per type and registers the DuckPGQ property graph
`insurance_graph`. Re-runnable (idempotent): hydrated nodes/edges and
build-seeded rules are recycled each run; **user-captured rules persist**.

Current scale: **~51k nodes, ~143k edges** (105 glossary terms, 9 metrics,
4 processes, 5 decisions, 11 entity classes + hydrated customers/policies/
agents/campaigns/claims/leads).

## Ontology model

- **concept_nodes** — `node_type ∈ {term, metric, process, decision, entity_class}`,
  with `definition`, `formula`, `default_grain`, `subject_area`, `owner_role`.
- **graph_edges** — typed edges. Endpoints can be ontology nodes **or data rows**
  (`dst_node_type='customer'`, `dst_node_id=<customer_id>`). Edge types:
  `owns, scored_by, triggers, considers, routes_to, measured_by, defined_by,
  informs, escalates_to, targets, manages, against`.
- **graph_nodes_all** — unified vertex table (concepts + hydrated entities) that
  the DuckPGQ property graph binds to.

### Three process graphs

1. **Lapse Prevention** — `model_scores → Lapse Review → Retention Decision →
   Retention Action → next_best_action → agent`, `measured_by revenue_saved`.
2. **Cross-sell Journey** — `propensity_to_buy → Campaign Targeting → campaign →
   lead → opportunity → policy`.
3. **Agent Coaching** — `agent_performance → Peer Baseline → Coaching Decision →
   sales_director`.

## Query — sample SQL/PGQ

```sql
LOAD duckpgq;
-- 1-hop neighbours of a metric
SELECT * FROM graph_table (insurance_graph
  MATCH (a:gnode)-[e:connects]->(b:gnode)
  WHERE a.node_id = 'metric::lapse_risk'
  COLUMNS (a.node_id AS src, e.edge_type, b.node_id AS dst)
) LIMIT 20;
```

Recursive-SQL fallback (no extension needed) is built into
`graph_traversal.get_subgraph`.

## Python API

```python
from graph import graph_traversal as gt
sg    = gt.get_subgraph(["metric::lapse_risk"], hops=2)   # {nodes, edges, engine}
rules = gt.find_decision_paths(["metric::premium_at_risk"])
disc  = gt.cross_domain_scan()                            # bridging 2+ subject areas
G     = gt.to_networkx()                                  # NetworkX DiGraph
fjson = gt.export_graph_json(sg)                          # {nodes, links} for force-graph
```

## GraphRAG flow (`graph_context_agent.get_graph_context`)

```
question ─► vector_search.search_all (LanceDB)         # glossary/schema hits
         ─► map hits ─► concept node_ids
         ─► get_subgraph(hops=2)                        # compact concept neighbourhood
         ─► find_decision_paths                         # rules within 3 hops
         ─► GraphContext { entry_nodes,
                           subgraph_summary [triples],
                           applicable_rules,
                           traversal_path }
```
This is a **separate module** — it does not modify `context_agent.py`; the
orchestrator can `asyncio.gather` it as an extra parallel context branch.

## Decision-rule capture (Mini-MORRIE)

```
POST /api/v2/graph/rule
{ "rule": "if lapse score above 70% and premium over S$50K escalate to branch manager",
  "role": "Agency Manager", "created_by": "n.bajpai", "reason": "Q3 retention policy" }
```
`parse_rule` uses Gemini (with a deterministic regex fallback) to extract
`condition_json / threshold_json / action_text / assigned_role`. Referenced
metrics are validated against `concept_nodes`; unknown metrics → `422` with a
hint. Valid rules are stored `status='draft'`, linked into the graph with
`considers` edges, and audited to `agent_reasoning_log`.

## Routes

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/api/v2/graph/rule` | capture a rule (draft) |
| GET | `/api/v2/graph/subgraph?entity_id=&hops=` | force-graph JSON for a node/entity |
| GET | `/api/v2/graph/discoveries?min_areas=&limit=` | cross-domain discoveries |

## Extending

- **New metric:** add to `METRICS` in `build_graph.py` (formula + source columns)
  and to `METRIC_SYNONYMS` in `rule_capture.py` so rules can reference it.
- **New process/edge type:** add nodes to `PROCESS_NODES`, edges to
  `PROCESS_EDGES`; extend the `edge_type` vocabulary in `graph_schema.sql`'s comment.
- **New entity hydration:** add an `insert ... select` block to step 5 of
  `build_graph.py`.
