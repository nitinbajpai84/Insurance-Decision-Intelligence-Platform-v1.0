# Supabase pgvector Embedding Pipeline

This pipeline embeds rows from `public.semantic_documents` and stores vectors in the `embedding vector(1536)` column for semantic retrieval.

## Files

- `embed_semantic_documents.py` - CLI for embedding missing rows and testing search.
- `embedding_pipeline/` - modular provider, database, config, and retry code.
- `.env.example` - configuration template.
- `003_semantic_vector_search.sql` - pgvector similarity search SQL function.

## Setup

Install dependencies:

```powershell
& 'C:\Users\Nitin\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pip install -r requirements.txt
```

Copy the environment template:

```powershell
Copy-Item .env.example .env
```

Edit `.env` and set:

```text
SUPABASE_DB_URL=postgresql://...
EMBEDDING_PROVIDER=gemini
GEMINI_API_KEY=...
GEMINI_EMBEDDING_MODEL=gemini-embedding-001
EMBEDDING_DIMENSIONS=768
```

Apply SQL migrations in Supabase:

```sql
\i 001_insurance_analytics_mvp_schema.sql
\i 002_semantic_layer_enrichment.sql
\i 004_product_riders_and_nbp_views.sql
\i 003_semantic_vector_search.sql
```

Load your semantic documents if not already loaded:

```sql
\copy public.semantic_documents (
  semantic_document_id,
  glossary_id,
  document_type,
  source_schema,
  source_table,
  source_column,
  title,
  content,
  tags,
  content_hash,
  embedding_model,
  embedding,
  active_flag,
  business_domain,
  related_tables,
  related_metrics,
  example_questions,
  created_at,
  updated_at
)
from 'semantic_layer/semantic_documents.csv'
with (format csv, header true);
```

## Run Embeddings

Dry run:

```powershell
& 'C:\Users\Nitin\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' embed_semantic_documents.py embed-missing --dry-run
```

Embed missing rows:

```powershell
& 'C:\Users\Nitin\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' embed_semantic_documents.py embed-missing
```

Limit for testing:

```powershell
& 'C:\Users\Nitin\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' embed_semantic_documents.py embed-missing --max-rows 10 --batch-size 5
```

## Test Similarity Search

```powershell
& 'C:\Users\Nitin\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' embed_semantic_documents.py search "How do I calculate loss ratio by product?"
```

Optional filters:

```powershell
& 'C:\Users\Nitin\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' embed_semantic_documents.py search "campaign conversion premium" --business-domain campaign --match-count 5
```

## Provider Options

### Gemini

```text
EMBEDDING_PROVIDER=gemini
GEMINI_API_KEY=...
GEMINI_EMBEDDING_MODEL=gemini-embedding-001
EMBEDDING_DIMENSIONS=768
```

This MVP uses Gemini embeddings at 768 dimensions so the existing Supabase `vector(768)` column continues to work.

### OpenAI

```text
EMBEDDING_PROVIDER=openai
OPENAI_API_KEY=...
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
EMBEDDING_DIMENSIONS=1536
```

### OpenAI-Compatible / Claude-Compatible Gateway

Use this for a gateway or vendor that exposes an OpenAI-style `/embeddings` endpoint. Claude itself is commonly used for generation; embeddings usually come from an embedding model exposed by the compatible gateway.

```text
EMBEDDING_PROVIDER=compatible
COMPATIBLE_API_KEY=...
COMPATIBLE_BASE_URL=https://your-gateway.example/v1
COMPATIBLE_EMBEDDING_MODEL=your-embedding-model
EMBEDDING_DIMENSIONS=1536
```

### Local Model

Install the optional local dependency:

```powershell
& 'C:\Users\Nitin\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pip install sentence-transformers
```

Then configure:

```text
EMBEDDING_PROVIDER=local
LOCAL_EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
EMBEDDING_DIMENSIONS=384
```

Important: the current database schema uses `vector(1536)`. If your local model returns 384 dimensions, alter `semantic_documents.embedding` and the `match_semantic_documents(query_embedding vector(...))` function to the same dimension before running.

## Error Handling and Retries

The pipeline includes:

- provider validation
- database URL validation
- retry with exponential backoff and jitter
- batch processing
- dimension mismatch protection
- transaction commit per successful batch
- clear failures for missing API keys or missing local dependencies

## Retrieval Design

Each embedded text combines:

- title
- document type
- business domain
- source table/column
- content
- related tables
- related metrics
- example questions
- tags

That gives the LLM enough context to retrieve the right schema objects, join paths, metric rules, and SQL examples before generating SQL.
