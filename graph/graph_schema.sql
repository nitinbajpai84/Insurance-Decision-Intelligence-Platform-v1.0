-- =====================================================================
-- Insurance PoC V2.0 — Graph / Ontology layer (DuckDB + DuckPGQ)
--
-- Three core tables:
--   concept_nodes  : the ontology (terms, metrics, processes, decisions,
--                    entity classes)
--   decision_rules : captured business rules (Mini-MORRIE), draft->active
--   graph_edges    : typed edges; endpoints may be ontology nodes OR data
--                    rows (customer_id, policy_id, ...)
--
-- Because DuckPGQ's PROPERTY GRAPH needs a single vertex table, we also
-- maintain graph_nodes_all — the union of concept nodes and hydrated entity
-- nodes — which build_graph.py (re)fills. Edges always resolve into it.
-- =====================================================================

create table if not exists concept_nodes (
  node_id            varchar primary key,            -- e.g. 'term::lapse', 'metric::lapse_rate'
  node_type          varchar not null,               -- term|metric|process|decision|entity_class
  name               varchar not null,
  definition         varchar,
  formula            varchar,
  default_grain      varchar,                        -- e.g. 'policy', 'customer', 'agent-month'
  subject_area       varchar,
  owner_role         varchar,
  source_glossary_id varchar,                        -- business_glossary.glossary_id when seeded from it
  created_at         timestamp default current_timestamp,
  updated_at         timestamp default current_timestamp
);

create table if not exists decision_rules (
  rule_id        varchar primary key,
  name           varchar not null,
  condition_text varchar not null,                   -- original natural-language condition
  condition_json json,                               -- structured: [{metric, operator, value}]
  threshold_json json,                               -- {metric: threshold} quick lookup
  action_text    varchar not null,
  assigned_role  varchar,
  priority       integer default 5,                  -- 1 = highest
  status         varchar default 'draft',            -- draft|active|locked
  created_by     varchar,
  reason         varchar,
  created_at     timestamp default current_timestamp
);

create table if not exists graph_edges (
  edge_id       varchar primary key default uuid(),
  src_node_id   varchar not null,
  src_node_type varchar not null,                    -- concept type OR entity class (customer, policy, ...)
  dst_node_id   varchar not null,
  dst_node_type varchar not null,
  edge_type     varchar not null,                    -- owns|scored_by|triggers|considers|routes_to|
                                                     -- measured_by|defined_by|informs|escalates_to|
                                                     -- targets|manages|against|component_of
  weight        double,                              -- e.g. score value on scored_by edges
  valid_from    date default current_date,
  valid_to      date,
  metadata      json,
  created_at    timestamp default current_timestamp
);

create index if not exists idx_graph_edges_src on graph_edges (src_node_id);
create index if not exists idx_graph_edges_dst on graph_edges (dst_node_id);
create index if not exists idx_graph_edges_type on graph_edges (edge_type);

-- Unified vertex table for DuckPGQ (concept nodes + hydrated entity nodes).
create table if not exists graph_nodes_all (
  node_id      varchar primary key,
  node_type    varchar not null,
  name         varchar,
  subject_area varchar
);
