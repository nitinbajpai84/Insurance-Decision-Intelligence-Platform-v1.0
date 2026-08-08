from __future__ import annotations

import os
from typing import Any

import psycopg
from dotenv import load_dotenv
from psycopg.rows import dict_row


def get_db_url(env_file: str = ".env") -> str:
    load_dotenv(env_file)
    db_url = os.getenv("SUPABASE_DB_URL")
    if not db_url:
        raise RuntimeError("Missing SUPABASE_DB_URL in .env.")
    return db_url


def connect(db_url: str | None = None):
    return psycopg.connect(db_url or get_db_url(), row_factory=dict_row, connect_timeout=30)


def json_ready(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: json_ready(item) for key, item in value.items()}
    if isinstance(value, list):
        return [json_ready(item) for item in value]
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value

