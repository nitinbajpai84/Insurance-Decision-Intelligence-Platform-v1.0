from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


def _bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _int(name: str, default: int) -> int:
    value = os.getenv(name)
    return default if value in {None, ""} else int(value)


def _float(name: str, default: float) -> float:
    value = os.getenv(name)
    return default if value in {None, ""} else float(value)


@dataclass(frozen=True)
class Settings:
    database_url: str
    provider: str
    gemini_api_key: str | None
    gemini_embedding_model: str
    openai_api_key: str | None
    openai_embedding_model: str
    compatible_api_key: str | None
    compatible_base_url: str | None
    compatible_embedding_model: str
    ollama_base_url: str
    ollama_embedding_model: str
    local_embedding_model: str
    batch_size: int
    max_rows: int
    retry_attempts: int
    retry_base_seconds: float
    dry_run: bool
    embedding_dimensions: int


def load_settings(env_file: str | None = ".env") -> Settings:
    if env_file:
        load_dotenv(env_file)

    database_url = os.getenv("SUPABASE_DB_URL", "").strip()
    if not database_url:
        raise ValueError("SUPABASE_DB_URL is required. Copy .env.example to .env and set it.")

    provider = os.getenv("EMBEDDING_PROVIDER", "openai").strip().lower()
    if provider not in {"gemini", "openai", "compatible", "ollama", "local"}:
        raise ValueError("EMBEDDING_PROVIDER must be one of: gemini, openai, compatible, ollama, local")

    return Settings(
        database_url=database_url,
        provider=provider,
        gemini_api_key=os.getenv("GEMINI_API_KEY"),
        gemini_embedding_model=os.getenv("GEMINI_EMBEDDING_MODEL", "gemini-embedding-001"),
        openai_api_key=os.getenv("OPENAI_API_KEY"),
        openai_embedding_model=os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small"),
        compatible_api_key=os.getenv("COMPATIBLE_API_KEY"),
        compatible_base_url=os.getenv("COMPATIBLE_BASE_URL"),
        compatible_embedding_model=os.getenv("COMPATIBLE_EMBEDDING_MODEL", "text-embedding-3-small"),
        ollama_base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
        ollama_embedding_model=os.getenv("OLLAMA_EMBEDDING_MODEL", "nomic-embed-text"),
        local_embedding_model=os.getenv("LOCAL_EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2"),
        batch_size=max(1, _int("EMBEDDING_BATCH_SIZE", 64)),
        max_rows=max(0, _int("EMBEDDING_MAX_ROWS", 0)),
        retry_attempts=max(1, _int("EMBEDDING_RETRY_ATTEMPTS", 5)),
        retry_base_seconds=max(0.1, _float("EMBEDDING_RETRY_BASE_SECONDS", 1.0)),
        dry_run=_bool("EMBEDDING_DRY_RUN", False),
        embedding_dimensions=max(1, _int("EMBEDDING_DIMENSIONS", 1536)),
    )
