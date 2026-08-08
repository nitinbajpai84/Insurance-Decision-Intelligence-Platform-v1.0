-- Configure semantic_documents for Ollama MVP embeddings.
--
-- Ollama nomic-embed-text returns 768-dimensional vectors. The original MVP
-- used vector(1536) for OpenAI text-embedding-3-small. Run this migration if
-- you want Ollama-only local embeddings.
--
-- This clears existing embeddings because vectors from different models and
-- dimensions should not be mixed in the same column.

create extension if not exists vector;

drop function if exists public.match_semantic_documents(vector, integer, double precision, text, text);
drop function if exists public.hybrid_match_semantic_documents(text, vector, integer, double precision, text);
drop index if exists public.idx_semantic_documents_embedding_hnsw;

alter table public.semantic_documents
  alter column embedding type vector(768)
  using null::vector(768);

update public.semantic_documents
set embedding = null,
    embedding_model = 'pending',
    updated_at = now();

create index if not exists idx_semantic_documents_embedding_hnsw
  on public.semantic_documents
  using hnsw (embedding vector_cosine_ops)
  where active_flag = true and embedding is not null;

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

select
  'semantic_documents.embedding configured for Ollama nomic-embed-text' as status,
  768 as embedding_dimensions,
  count(*) filter (where embedding is null) as documents_requiring_embedding
from public.semantic_documents;
