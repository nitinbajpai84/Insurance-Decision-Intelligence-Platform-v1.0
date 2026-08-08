-- Run this once before re-embedding semantic_documents with Gemini.
-- The current MVP keeps vector(768), and Gemini embedding output is configured
-- to 768 dimensions through GEMINI_EMBEDDING_MODEL=gemini-embedding-001 and
-- EMBEDDING_DIMENSIONS=768.

update public.semantic_documents
set embedding = null,
    -- embedding_model is NOT NULL in the MVP schema. Keep a non-null marker
    -- while embedding is pending; the Python embedding job will replace it
    -- with GEMINI_EMBEDDING_MODEL after vectors are written.
    embedding_model = 'pending-gemini-embedding',
    updated_at = now()
where embedding is not null
  and coalesce(embedding_model, '') <> 'gemini-embedding-001';

select
  count(*) filter (where embedding is null) as documents_needing_gemini_embedding,
  count(*) filter (where embedding is not null) as documents_already_embedded
from public.semantic_documents
where active_flag = true;
