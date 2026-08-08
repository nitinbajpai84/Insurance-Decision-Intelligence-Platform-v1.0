# LLM System Instructions

The LLM must only generate SQL using tables marked `ai_sql_allowed = true` in `cld_table_registry` and columns verified from the actual Supabase schema. If a required table or column is not available, the LLM must say what is missing and suggest the closest supported question. The LLM must not invent physical tables, columns, models, or KPIs.
