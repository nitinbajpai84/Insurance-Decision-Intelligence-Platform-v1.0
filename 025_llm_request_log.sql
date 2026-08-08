create table if not exists public.llm_request_log (
  request_id uuid primary key,
  provider varchar,
  model varchar,
  task_type varchar,
  latency_ms int,
  prompt_tokens_estimate int,
  response_tokens_estimate int,
  success_flag boolean,
  timeout_flag boolean,
  error_message text,
  created_at timestamp with time zone default now()
);

comment on table public.llm_request_log is
  'Metadata-only audit log for LLM calls. Stores provider, model, latency, token estimates, and status without storing full prompts or API keys.';

comment on column public.llm_request_log.provider is 'LLM provider used for the request, such as gemini or ollama.';
comment on column public.llm_request_log.model is 'Provider model identifier used for the request.';
comment on column public.llm_request_log.task_type is 'Logical task type such as sql_generation, explanation, recommendation, intent, or health.';
comment on column public.llm_request_log.prompt_tokens_estimate is 'Approximate prompt tokens based on character length; prompt text is intentionally not stored.';
comment on column public.llm_request_log.response_tokens_estimate is 'Approximate response tokens based on character length; response text is intentionally not stored.';

create index if not exists idx_llm_request_log_created_at
  on public.llm_request_log (created_at desc);

create index if not exists idx_llm_request_log_provider_model
  on public.llm_request_log (provider, model, task_type, created_at desc);
