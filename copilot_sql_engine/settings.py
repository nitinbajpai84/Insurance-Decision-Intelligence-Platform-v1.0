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
class SqlEngineSettings:
    database_url: str
    llm_provider: str | None
    text_provider: str
    text_model: str
    text_api_key: str
    text_base_url: str | None
    text_temperature: float
    text_timeout_seconds: float
    row_limit: int
    statement_timeout_ms: int
    allowed_schemas: set[str]


def load_sql_engine_settings(env_file: str = ".env") -> SqlEngineSettings:
    load_dotenv(env_file)
    db_url = os.getenv("SUPABASE_DB_URL", "").strip()
    if not db_url:
        raise ValueError("SUPABASE_DB_URL is required")
    llm_provider = os.getenv("LLM_PROVIDER", "").strip().lower() or None
    provider = os.getenv("TEXT2SQL_PROVIDER", "gemini" if llm_provider == "gemini" else "compatible" if llm_provider else "mock").strip().lower()
    if provider not in {"openai", "compatible", "mock", "gemini"}:
        raise ValueError("TEXT2SQL_PROVIDER must be openai, compatible, mock, or gemini")
    if provider == "gemini" and not llm_provider:
        llm_provider = "gemini"
    if llm_provider and llm_provider != "gemini":
        raise ValueError("LLM_PROVIDER must be gemini")
    allowed = {
        item.strip()
        for item in os.getenv("TEXT2SQL_ALLOWED_SCHEMAS", "public").split(",")
        if item.strip()
    }
    return SqlEngineSettings(
        database_url=db_url,
        llm_provider=llm_provider,
        text_provider=provider,
        text_model=os.getenv("TEXT2SQL_MODEL", "qwen2.5-coder:7b"),
        text_api_key=os.getenv("TEXT2SQL_API_KEY") or os.getenv("OPENAI_API_KEY") or "ollama",
        text_base_url=os.getenv("TEXT2SQL_BASE_URL") or None,
        text_temperature=_float("TEXT2SQL_TEMPERATURE", 0.0),
        text_timeout_seconds=max(1.0, _float("LLM_TIMEOUT_SECONDS", _float("TEXT2SQL_TIMEOUT_SECONDS", 120.0))),
        row_limit=max(1, _int("TEXT2SQL_ROW_LIMIT", 500)),
        statement_timeout_ms=max(100, _int("TEXT2SQL_STATEMENT_TIMEOUT_MS", 5000)),
        allowed_schemas=allowed or {"public"},
    )
