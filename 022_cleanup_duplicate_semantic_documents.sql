-- Cleanup duplicate semantic documents after a partial embedding run.
--
-- Use when embed_semantic_documents.py fails with:
--   duplicate key value violates unique constraint
--   semantic_documents_document_type_content_hash_embedding_mod_key
--
-- The pipeline computes a richer content_hash from the full semantic payload.
-- If a previous partial run embedded one copy and left duplicate pending rows,
-- this script deactivates the pending duplicates before rerunning embeddings.

with duplicate_pending as (
  select
    pending.semantic_document_id,
    pending.title,
    pending.document_type,
    pending.content_hash,
    pending.embedding_model,
    embedded.semantic_document_id as matching_embedded_document_id,
    row_number() over (
      partition by pending.document_type, pending.title, pending.content
      order by pending.created_at, pending.semantic_document_id
    ) as pending_rank
  from public.semantic_documents pending
  join public.semantic_documents embedded
    on embedded.semantic_document_id <> pending.semantic_document_id
   and embedded.active_flag = true
   and embedded.embedding is not null
   and embedded.embedding_model = 'nomic-embed-text'
   and embedded.document_type = pending.document_type
   and embedded.title = pending.title
   and embedded.content = pending.content
  where pending.active_flag = true
    and pending.embedding is null
    and pending.embedding_model in ('pending', 'nomic-embed-text')
),
updated as (
  update public.semantic_documents sd
  set active_flag = false,
      embedding_model = left('duplicate-nomic-embed-text-' || sd.semantic_document_id::text, 120),
      updated_at = now()
  from duplicate_pending d
  where sd.semantic_document_id = d.semantic_document_id
  returning sd.semantic_document_id, sd.title, d.matching_embedded_document_id
)
select
  'deactivated_duplicate_pending_semantic_documents' as cleanup_status,
  count(*) as rows_deactivated
from updated;

-- Diagnostic: remaining active rows without embeddings.
select
  document_type,
  embedding_model,
  count(*) as remaining_active_missing_embeddings
from public.semantic_documents
where active_flag = true
  and embedding is null
group by document_type, embedding_model
order by remaining_active_missing_embeddings desc, document_type, embedding_model;

-- Diagnostic: active embedded count.
select
  embedding_model,
  count(*) as active_embedded_documents
from public.semantic_documents
where active_flag = true
  and embedding is not null
group by embedding_model
order by active_embedded_documents desc;

