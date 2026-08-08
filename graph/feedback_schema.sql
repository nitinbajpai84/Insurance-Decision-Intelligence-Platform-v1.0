-- =====================================================================
-- Insurance PoC V2.0 — Graph feedback / adaptation layer (Prompt 13)
--
-- Governed feedback loop over the ontology graph:
--   graph_feedback   : node/edge/rule feedback (confirm|reject|missing|edit)
--   answer_feedback  : thumbs on cached answers (drives semantic-cache hygiene)
--   edge_weight_log  : full audit of every edge-weight change (reversible)
--
-- Also hardens graph_edges with weight (DEFAULT 1.0) + status so the retrieval
-- loop can rank by weight and skip inactive/proposed edges.
-- =====================================================================

create table if not exists graph_feedback (
  feedback_id     varchar primary key default uuid(),
  target_type     varchar not null,                  -- node|edge|rule
  target_id       varchar not null,
  feedback_type   varchar not null,                  -- confirm|reject|missing|edit
  rating          smallint,                          -- 1..5 (optional)
  comment         text,
  proposed_change json,                              -- {field: new_value} for edits / {src,dst,edge_type} for missing
  user_id         varchar,
  user_role       varchar,
  status          varchar not null default 'pending_review', -- auto_applied|pending_review|approved|rejected
  created_at      timestamp not null default current_timestamp,
  reviewed_by     varchar,
  reviewed_at     timestamp
);
create index if not exists idx_graph_feedback_status on graph_feedback (status);
create index if not exists idx_graph_feedback_target on graph_feedback (target_type, target_id);

create table if not exists answer_feedback (
  af_id           varchar primary key default uuid(),
  query_id        varchar,
  question        text,
  role            varchar,
  rating          smallint,
  thumbs          varchar,                           -- up|down
  comment         text,
  applied_to_cache boolean default false,
  created_at      timestamp not null default current_timestamp
);
create index if not exists idx_answer_feedback_query on answer_feedback (query_id);

create table if not exists edge_weight_log (
  id          varchar primary key default uuid(),
  edge_id     varchar not null,
  old_weight  double,
  new_weight  double,
  reason      varchar,                               -- feedback|decay|review
  changed_at  timestamp not null default current_timestamp
);
create index if not exists idx_edge_weight_log_edge on edge_weight_log (edge_id);

-- graph_edges hardening (weight already exists from graph_schema.sql; status is new).
alter table graph_edges add column if not exists weight double default 1.0;
alter table graph_edges add column if not exists status varchar default 'active';   -- active|inactive|pending_review

-- Backfill: any edge without a weight is treated as neutral 1.0; null status -> active.
update graph_edges set weight = 1.0 where weight is null;
update graph_edges set status = 'active' where status is null;
