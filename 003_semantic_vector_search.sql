-- pgvector similarity search helper for semantic_documents.
-- Apply after 001 and 002 migrations.

create or replace function public.match_semantic_documents(
  query_embedding vector(1536),
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
  related_metrics text[],
  example_questions text[],
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
    sd.related_metrics,
    sd.example_questions,
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

comment on function public.match_semantic_documents(
  vector,
  integer,
  double precision,
  text,
  text
) is 'Returns semantic_documents ranked by cosine similarity for LLM text-to-SQL retrieval.';
