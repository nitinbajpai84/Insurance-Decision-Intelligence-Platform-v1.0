-- =====================================================================
-- Insurance PoC V2.0 — Process model layer (Prompt 17)
--
-- Models end-to-end business processes as subgraphs: typed stage nodes,
-- sequence edges, and the metric that quantifies each stage. Each process also
-- has a process_instance_view that reconstructs real instances from the seeded
-- data so the stage metrics are computable end-to-end.
-- =====================================================================

create table if not exists process_nodes (
  process_id    varchar primary key,
  process_name  varchar not null,
  description   varchar,
  subject_area  varchar,
  owner_role    varchar,
  instance_view varchar,
  created_at    timestamp default current_timestamp
);

create table if not exists process_stages (
  stage_id                     varchar primary key,
  process_id                   varchar not null,          -- FK -> process_nodes.process_id
  stage_name                   varchar not null,
  stage_order                  integer not null,
  entity_table                 varchar,                   -- DuckDB table reconstructing this stage
  stage_metric_id              varchar,                   -- FK -> concept_nodes.node_id
  conversion_to_next_metric_id varchar,                   -- FK -> concept_nodes.node_id
  typical_lag_days             integer,
  drop_off_reasons             json,
  created_at                   timestamp default current_timestamp
);
create index if not exists idx_process_stages_proc on process_stages (process_id, stage_order);

create table if not exists process_edges (
  edge_id       varchar primary key,
  process_id    varchar not null,
  from_stage_id varchar not null,
  to_stage_id   varchar not null,
  edge_type     varchar not null,                         -- advances_to|drops_to|repeats|feeds
  weight        double default 1.0,
  created_at    timestamp default current_timestamp
);
