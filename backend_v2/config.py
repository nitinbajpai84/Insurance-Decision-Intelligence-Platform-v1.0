"""
Insurance PoC V2.0 — backend configuration.

Single source of truth for env-driven settings. Loads the project-root .env
(the copied V1 file already carries GEMINI_API_KEY) and database\\.env, then
exposes typed constants. V2-specific keys are documented in .env.v2.example.
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BACKEND_DIR.parent

# Load order: project root .env first, then database\.env (no override)
load_dotenv(PROJECT_ROOT / ".env")
load_dotenv(PROJECT_ROOT / "database" / ".env")


def _str(name: str, default: str) -> str:
    return os.environ.get(name, "").strip() or default


def _int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, "") or default)
    except ValueError:
        return default


def _float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, "") or default)
    except ValueError:
        return default


def _bool(name: str, default: bool) -> bool:
    v = os.environ.get(name, "").strip().lower()
    if v in ("1", "true", "yes", "on"):
        return True
    if v in ("0", "false", "no", "off"):
        return False
    return default


# --- Gemini -----------------------------------------------------------------
GEMINI_API_KEY: str = _str("GEMINI_API_KEY", "")
# Generation model: GEMINI_MODEL wins; falls back to the V1 key's provisioned
# model so the copied .env works out of the box.
GEMINI_MODEL: str = _str("GEMINI_MODEL", _str("GEMINI_MODEL_SQL", "gemini-2.5-flash-lite"))
EMBEDDING_MODEL: str = _str("EMBEDDING_MODEL", "models/gemini-embedding-001")
VECTOR_DIMS: int = 3072
LLM_TIMEOUT_SECONDS: float = _float("LLM_TIMEOUT_SECONDS", 60.0)

# --- Agent selection --------------------------------------------------------
# When true the orchestrator uses the graph-grounded SQL agent (Prompt 18):
# SQL is reasoned over the graph + constrained to metric_bindings. Falls back to
# the legacy free-form sql_agent when false.
USE_GRAPH_GROUNDED_SQL: bool = _bool("USE_GRAPH_GROUNDED_SQL", True)
# When a question matches NO sanctioned metric: if false (default) refuse cleanly
# with suggestions; if true, fall back to the legacy free-SQL agent and label the
# answer "ungoverned — not validated against the semantic model".
ALLOW_UNGOVERNED_FALLBACK: bool = _bool("ALLOW_UNGOVERNED_FALLBACK", False)

# --- Storage ----------------------------------------------------------------
DUCKDB_PATH: str = _str("DUCKDB_PATH", str(PROJECT_ROOT / "database" / "insurance_v2.duckdb"))
LANCEDB_PATH: str = _str("LANCEDB_PATH", str(PROJECT_ROOT / "lance_store"))

# DuckDB caches one instance per file per process, keyed by configuration —
# opening the same file with two different configs in one process raises
# ConnectionException: "different configuration than existing connections"
# (see graph/db_util.py). So every duckdb.connect() call anywhere in the app
# MUST pass this exact same dict; do not add a differently-configured connect
# call without updating this constant.
#
# The values themselves matter separately: Render's free tier is a 512MB hard
# ceiling (OOM-killed, not throttled), and DuckDB's buffer manager is
# otherwise unbounded. Override via DUCKDB_MEMORY_LIMIT / DUCKDB_THREADS on a
# host with more headroom.
DUCKDB_CONFIG: dict[str, object] = {
    "memory_limit": _str("DUCKDB_MEMORY_LIMIT", "256MB"),
    "threads": _int("DUCKDB_THREADS", 2),
}

# --- API --------------------------------------------------------------------
API_PORT: int = _int("API_PORT", 3001)
# CORS_ORIGINS env var: comma-separated origins, or "*" to allow any origin
# (needed when the frontend is opened from a dynamic host like a StackBlitz/
# WebContainer preview URL, which can't be allowlisted in advance). Defaults
# to the local-dev origins so nothing changes for local V1-style usage.
_cors_env = _str("CORS_ORIGINS", "")
if _cors_env == "*":
    CORS_ORIGINS: list[str] = ["*"]
elif _cors_env:
    CORS_ORIGINS = [o.strip() for o in _cors_env.split(",") if o.strip()]
else:
    CORS_ORIGINS = [
        "http://localhost:3000", "http://127.0.0.1:3000",
        "http://localhost:3002", "http://127.0.0.1:3002",
    ]

# --- Context budget ----------------------------------------------------------
MAX_CONTEXT_TOKENS: int = _int("MAX_CONTEXT_TOKENS", 6000)
# Truncation priority when over budget (kept first -> dropped last):
CONTEXT_PRIORITY: list[str] = ["schema_context", "glossary_terms", "semantic_docs", "past_queries"]

# --- Semantic cache ----------------------------------------------------------
CACHE_SIMILARITY_THRESHOLD: float = _float("CACHE_SIMILARITY_THRESHOLD", 0.92)
CACHE_TTL_HOURS: int = _int("CACHE_TTL_HOURS", 24)

# --- SQL guardrails ----------------------------------------------------------
SQL_ROW_LIMIT: int = 50
SQL_FORBIDDEN_KEYWORDS: tuple[str, ...] = (
    "insert", "update", "delete", "drop", "alter", "truncate", "create",
    "merge", "call", "copy", "grant", "revoke", "attach", "detach",
    "install", "load", "export", "import", "pragma", "set", "vacuum",
)

# --- Roles (mirrors the live V1 app) -----------------------------------------
ROLE_PROMPTS: dict[str, str] = {
    "Executive Leadership": (
        "Answer at portfolio level with cross-product aggregates. Focus on premium, "
        "persistency, lapse exposure, and growth trends across the whole Singapore book."
    ),
    "Agency Manager": (
        "Focus on agent productivity, lapse exposure, and conversion by region/territory. "
        "Surface which agents or branches need coaching or intervention."
    ),
    "Campaign Manager": (
        "Focus on campaign ROI, funnel metrics (targets -> responses -> conversions), "
        "response rates, and conversion premium by channel."
    ),
    "Sales Director": (
        "Focus on team targets and attainment, top producers (MDRT-level), rising stars, "
        "and product-line premium concentration."
    ),
    "Insurance Agent": (
        "Answer for an individual agent's own book of business: their customers, policies, "
        "renewal/lapse risks, and prioritized next-best-actions."
    ),
    "Claims Manager": (
        "Focus on claims volumes and severity, fraud indicators, assessments, and claim "
        "ratios by product."
    ),
    "Data Analyst": (
        "Unrestricted schema access. Answer with technical precision: exact tables, columns, "
        "and reproducible SQL."
    ),
}
ROLES: list[dict[str, str]] = [{"role": k, "description": v} for k, v in ROLE_PROMPTS.items()]


def require_api_key() -> str:
    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY is not configured — set it in the project-root .env")
    return GEMINI_API_KEY
