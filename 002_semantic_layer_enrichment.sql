-- Enrich semantic_documents for LLM text-to-SQL retrieval.
-- Apply after 001_insurance_analytics_mvp_schema.sql.

alter table public.semantic_documents
  add column if not exists business_domain text,
  add column if not exists related_tables text[] not null default '{}',
  add column if not exists related_metrics text[] not null default '{}',
  add column if not exists example_questions text[] not null default '{}';

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
      'customer_segmentation'
    )
  );

create index if not exists idx_semantic_documents_business_domain
  on public.semantic_documents (business_domain)
  where active_flag = true;

create index if not exists idx_semantic_documents_related_tables_gin
  on public.semantic_documents using gin (related_tables);

create index if not exists idx_semantic_documents_related_metrics_gin
  on public.semantic_documents using gin (related_metrics);
