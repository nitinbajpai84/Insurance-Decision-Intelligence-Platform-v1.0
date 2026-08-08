from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


def _int(name: str, default: int) -> int:
    value = os.getenv(name)
    return default if value in {None, ""} else int(value)


def _float(name: str, default: float) -> float:
    value = os.getenv(name)
    return default if value in {None, ""} else float(value)


@dataclass(frozen=True)
class AgentSettings:
    database_url: str
    embedding_provider: str
    embedding_dimensions: int
    semantic_match_count: int
    semantic_threshold: float
    text_provider: str
    text_model: str
    text_api_key: str | None
    text_base_url: str | None
    text_temperature: float
    row_limit: int
    statement_timeout_ms: int
    allowed_schemas: set[str]


def load_agent_settings(env_file: str | None = ".env") -> AgentSettings:
    if env_file:
        load_dotenv(env_file)
    database_url = os.getenv("SUPABASE_DB_URL", "").strip()
    if not database_url:
        raise ValueError("SUPABASE_DB_URL is required")
    provider = os.getenv("TEXT2SQL_PROVIDER", "openai").strip().lower()
    if provider not in {"openai", "compatible", "mock"}:
        raise ValueError("TEXT2SQL_PROVIDER must be one of: openai, compatible, mock")
    allowed = {
        item.strip()
        for item in os.getenv("TEXT2SQL_ALLOWED_SCHEMAS", "public").split(",")
        if item.strip()
    }
    return AgentSettings(
        database_url=database_url,
        embedding_provider=os.getenv("EMBEDDING_PROVIDER", "openai").strip().lower(),
        embedding_dimensions=_int("EMBEDDING_DIMENSIONS", 1536),
        semantic_match_count=_int("TEXT2SQL_SEMANTIC_MATCH_COUNT", 8),
        semantic_threshold=_float("TEXT2SQL_SEMANTIC_THRESHOLD", 0.0),
        text_provider=provider,
        text_model=os.getenv("TEXT2SQL_MODEL", "gpt-4.1-mini"),
        text_api_key=os.getenv("TEXT2SQL_API_KEY") or os.getenv("OPENAI_API_KEY"),
        text_base_url=os.getenv("TEXT2SQL_BASE_URL") or None,
        text_temperature=_float("TEXT2SQL_TEMPERATURE", 0.0),
        row_limit=max(1, _int("TEXT2SQL_ROW_LIMIT", 500)),
        statement_timeout_ms=max(100, _int("TEXT2SQL_STATEMENT_TIMEOUT_MS", 5000)),
        allowed_schemas=allowed or {"public"},
    )
