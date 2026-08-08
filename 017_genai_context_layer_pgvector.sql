-- GenAI Copilot pgvector context layer for insurance analytics, ML, and NBA decisioning.
-- Run after:
--   001_insurance_analytics_mvp_schema.sql
--   002_semantic_layer_enrichment.sql
--   003_semantic_vector_search.sql
--
-- This migration enriches semantic_documents and adds hybrid retrieval functions
-- that combine vector similarity, keyword match, metadata/table/model match, and
-- business-domain match.

create extension if not exists vector;

alter table public.semantic_documents
  add column if not exists business_domain text,
  add column if not exists related_tables text[] default '{}',
  add column if not exists related_metrics text[] default '{}',
  add column if not exists example_questions text[] default '{}',
  add column if not exists related_columns text[] not null default '{}',
  add column if not exists related_models text[] not null default '{}',
  add column if not exists sql_examples text[] not null default '{}';

update public.semantic_documents
set related_tables = coalesce(related_tables, '{}'::text[]),
    related_metrics = coalesce(related_metrics, '{}'::text[]),
    example_questions = coalesce(example_questions, '{}'::text[]),
    related_columns = coalesce(related_columns, '{}'::text[]),
    related_models = coalesce(related_models, '{}'::text[]),
    sql_examples = coalesce(sql_examples, '{}'::text[]);

alter table public.semantic_documents
  alter column related_tables set default '{}',
  alter column related_tables set not null,
  alter column related_metrics set default '{}',
  alter column related_metrics set not null,
  alter column example_questions set default '{}',
  alter column example_questions set not null,
  alter column related_columns set default '{}',
  alter column related_columns set not null,
  alter column related_models set default '{}',
  alter column related_models set not null,
  alter column sql_examples set default '{}',
  alter column sql_examples set not null;

alter table public.semantic_documents
  drop constraint if exists semantic_documents_document_type_check;

alter table public.semantic_documents
  add constraint semantic_documents_document_type_check
  check (
    document_type in (
      'table',
      'column',
      'metric',
      'join',
      'example_question',
      'glossary',
      'policy_note',
      'claim_note',
      'campaign_summary',
      'agent_summary',
      'business_glossary',
      'kpi_definition',
      'table_description',
      'column_description',
      'join_path',
      'metric_rule',
      'sample_question',
      'sql_template',
      'policy_definition',
      'agent_definition',
      'campaign_definition',
      'customer_segmentation',
      'business_context',
      'schema_context',
      'metric_context',
      'model_context',
      'sql_example',
      'ml_context',
      'decisioning_context'
    )
  );

comment on column public.semantic_documents.related_columns is
  'Column names relevant to the context document, used for text-to-SQL grounding.';
comment on column public.semantic_documents.related_models is
  'ML model names relevant to the context document, such as propensity_to_buy or policy_lapse.';
comment on column public.semantic_documents.sql_examples is
  'SQL snippets or templates that demonstrate safe query patterns for the context document.';

create index if not exists idx_semantic_documents_related_columns_gin
  on public.semantic_documents using gin (related_columns);

create index if not exists idx_semantic_documents_related_models_gin
  on public.semantic_documents using gin (related_models);

create index if not exists idx_semantic_documents_sql_examples_gin
  on public.semantic_documents using gin (sql_examples);

create index if not exists idx_semantic_documents_domain_type
  on public.semantic_documents (business_domain, document_type)
  where active_flag = true;

create index if not exists idx_semantic_documents_title_content_fts
  on public.semantic_documents
  using gin (to_tsvector('english', coalesce(title, '') || ' ' || coalesce(content, '')))
  where active_flag = true;

create index if not exists idx_semantic_documents_embedding_hnsw
  on public.semantic_documents
  using hnsw (embedding vector_cosine_ops)
  where active_flag = true and embedding is not null;

create or replace function public.semantic_context_bucket(p_document_type text)
returns text
language sql
immutable
as $$
  select case
    when p_document_type in ('table', 'column', 'table_description', 'column_description', 'join', 'join_path', 'schema_context')
      then 'schema_context'
    when p_document_type in ('metric', 'kpi_definition', 'metric_rule', 'metric_context')
      then 'metric_context'
    when p_document_type in ('model_context', 'ml_context', 'decisioning_context')
      then 'model_context'
    when p_document_type in ('sql_template', 'sql_example')
      then 'sql_examples'
    else 'business_context'
  end;
$$;

comment on function public.semantic_context_bucket(text) is
  'Maps semantic document types to LLM context buckets.';

drop function if exists public.match_semantic_documents(vector, integer, double precision, text, text);
drop function if exists public.hybrid_match_semantic_documents(text, vector, integer, double precision, text);

create or replace function public.match_semantic_documents(
  query_embedding vector(768),
  match_count integer default 8,
  match_threshold double precision default 0.0,
  filter_business_domain text default null,
  filter_document_type text default null
)
returns table (
  semantic_document_id uuid,
  title text,
  document_type text,
  business_domain text,
  content text,
  related_tables text[],
  related_columns text[],
  related_models text[],
  related_metrics text[],
  example_questions text[],
  sql_examples text[],
  similarity double precision
)
language sql
stable
as $$
  select
    sd.semantic_document_id,
    sd.title,
    sd.document_type,
    sd.business_domain,
    sd.content,
    sd.related_tables,
    sd.related_columns,
    sd.related_models,
    sd.related_metrics,
    sd.example_questions,
    sd.sql_examples,
    1 - (sd.embedding <=> query_embedding) as similarity
  from public.semantic_documents sd
  where sd.active_flag = true
    and sd.embedding is not null
    and (filter_business_domain is null or sd.business_domain = filter_business_domain)
    and (filter_document_type is null or sd.document_type = filter_document_type)
    and (1 - (sd.embedding <=> query_embedding)) >= match_threshold
  order by sd.embedding <=> query_embedding
  limit least(greatest(match_count, 1), 50);
$$;

comment on function public.match_semantic_documents(vector, integer, double precision, text, text) is
  'Returns semantic_documents ranked by cosine similarity for LLM retrieval.';

create or replace function public.hybrid_match_semantic_documents(
  query_text text,
  query_embedding vector(768),
  match_count integer default 12,
  match_threshold double precision default 0.0,
  filter_business_domain text default null
)
returns table (
  semantic_document_id uuid,
  title text,
  document_type text,
  business_domain text,
  context_bucket text,
  content text,
  related_tables text[],
  related_columns text[],
  related_models text[],
  related_metrics text[],
  example_questions text[],
  sql_examples text[],
  vector_similarity double precision,
  keyword_score double precision,
  metadata_score double precision,
  hybrid_score double precision
)
language sql
stable
as $$
  with scored as (
    select
      sd.semantic_document_id,
      sd.title,
      sd.document_type,
      sd.business_domain,
      public.semantic_context_bucket(sd.document_type) as context_bucket,
      sd.content,
      sd.related_tables,
      sd.related_columns,
      sd.related_models,
      sd.related_metrics,
      sd.example_questions,
      sd.sql_examples,
      case
        when sd.embedding is null then 0::double precision
        else 1 - (sd.embedding <=> query_embedding)
      end as vector_similarity,
      ts_rank_cd(
        to_tsvector('english', coalesce(sd.title, '') || ' ' || coalesce(sd.content, '')),
        plainto_tsquery('english', coalesce(query_text, ''))
      )::double precision as keyword_score,
      (
        case when sd.business_domain is not null and position(lower(sd.business_domain) in lower(coalesce(query_text, ''))) > 0 then 0.15 else 0 end
        + case when exists (select 1 from unnest(sd.related_tables) t where position(lower(t) in lower(coalesce(query_text, ''))) > 0) then 0.20 else 0 end
        + case when exists (select 1 from unnest(sd.related_columns) c where position(lower(c) in lower(coalesce(query_text, ''))) > 0) then 0.15 else 0 end
        + case when exists (select 1 from unnest(sd.related_models) m where position(lower(m) in lower(coalesce(query_text, ''))) > 0) then 0.20 else 0 end
        + case when exists (select 1 from unnest(sd.related_metrics) mt where position(lower(mt) in lower(coalesce(query_text, ''))) > 0) then 0.15 else 0 end
      )::double precision as metadata_score
    from public.semantic_documents sd
    where sd.active_flag = true
      and (filter_business_domain is null or sd.business_domain = filter_business_domain)
  )
  select
    s.semantic_document_id,
    s.title,
    s.document_type,
    s.business_domain,
    s.context_bucket,
    s.content,
    s.related_tables,
    s.related_columns,
    s.related_models,
    s.related_metrics,
    s.example_questions,
    s.sql_examples,
    s.vector_similarity,
    s.keyword_score,
    s.metadata_score,
    (
      (0.65 * s.vector_similarity)
      + (0.20 * least(s.keyword_score, 1.0))
      + (0.15 * least(s.metadata_score, 1.0))
    )::double precision as hybrid_score
  from scored s
  where (
    s.vector_similarity >= match_threshold
    or s.keyword_score > 0
    or s.metadata_score > 0
  )
  order by hybrid_score desc, vector_similarity desc, keyword_score desc
  limit least(greatest(match_count, 1), 50);
$$;

comment on function public.hybrid_match_semantic_documents(text, vector, integer, double precision, text) is
  'Hybrid semantic retrieval using pgvector similarity, full-text keyword score, table/model/metric metadata matches, and business-domain filtering.';
