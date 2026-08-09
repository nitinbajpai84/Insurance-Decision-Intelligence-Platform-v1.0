"""
Tracer — every agent call is recorded in DuckDB agent_reasoning_log,
correlated by query_id. Powers the V2 Insight Evidence Hub.
"""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import duckdb

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend_v2.config import DUCKDB_CONFIG, DUCKDB_PATH


def log_step(
    query_id: str,
    agent_name: str,
    input_summary: str,
    output_summary: str,
    duration_ms: int,
    tokens_used: int = 0,
    cache_hit: bool = False,
) -> None:
    """Insert one reasoning step. Never raises — tracing must not break the pipeline."""
    try:
        conn = duckdb.connect(DUCKDB_PATH, read_only=False, config=DUCKDB_CONFIG)
        try:
            conn.execute(
                "INSERT INTO agent_reasoning_log "
                "(query_id, agent_name, input_summary, output_summary, duration_ms, tokens_used, cache_hit, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                [query_id, agent_name, input_summary[:1000], output_summary[:1000],
                 int(duration_ms), int(tokens_used), bool(cache_hit), datetime.now()],
            )
        finally:
            conn.close()
    except Exception as exc:  # pragma: no cover — observability is best-effort
        print(f"[tracer] WARN could not log step ({agent_name}): {exc}", file=sys.stderr)


_COLUMNS = ["id", "query_id", "agent_name", "input_summary", "output_summary",
            "duration_ms", "tokens_used", "cache_hit", "created_at"]


def _rows_to_dicts(rows: list[tuple]) -> list[dict[str, Any]]:
    out = []
    for row in rows:
        item = dict(zip(_COLUMNS, row))
        if item.get("created_at") is not None and hasattr(item["created_at"], "isoformat"):
            item["created_at"] = item["created_at"].isoformat()
        out.append(item)
    return out


def get_trace(query_id: str) -> list[dict[str, Any]]:
    """Full reasoning chain for one query — Insight Evidence Hub detail view."""
    try:
        conn = duckdb.connect(DUCKDB_PATH, read_only=True, config=DUCKDB_CONFIG)
    except Exception as exc:
        print(f"[tracer] WARN cannot open DB for get_trace: {exc}", file=sys.stderr)
        return []
    try:
        rows = conn.execute(
            f"SELECT {', '.join(_COLUMNS)} FROM agent_reasoning_log WHERE query_id = ? ORDER BY id",
            [query_id],
        ).fetchall()
    finally:
        conn.close()
    return _rows_to_dicts(rows)


def get_recent_traces(limit: int = 20) -> list[dict[str, Any]]:
    """Last N distinct queries with summaries — Evidence Hub history view."""
    try:
        conn = duckdb.connect(DUCKDB_PATH, read_only=True, config=DUCKDB_CONFIG)
    except Exception as exc:
        print(f"[tracer] WARN cannot open DB for get_recent_traces: {exc}", file=sys.stderr)
        return []
    try:
        rows = conn.execute(
            """
            SELECT query_id,
                   min(created_at) AS started_at,
                   max(created_at) AS finished_at,
                   sum(duration_ms) AS total_duration_ms,
                   sum(tokens_used) AS total_tokens,
                   bool_or(cache_hit) AS any_cache_hit,
                   count(*) AS steps,
                   max(CASE WHEN agent_name = 'context_agent' THEN input_summary END) AS question
            FROM agent_reasoning_log
            GROUP BY query_id
            ORDER BY max(created_at) DESC
            LIMIT ?
            """,
            [int(limit)],
        ).fetchall()
    finally:
        conn.close()
    out = []
    for r in rows:
        out.append({
            "query_id": r[0],
            "started_at": r[1].isoformat() if hasattr(r[1], "isoformat") else r[1],
            "finished_at": r[2].isoformat() if hasattr(r[2], "isoformat") else r[2],
            "total_duration_ms": r[3],
            "total_tokens": r[4],
            "any_cache_hit": r[5],
            "steps": r[6],
            "question": r[7],
        })
    return out


def cache_hit_rate_24h() -> float:
    """Share of queries in the last 24h that hit the semantic cache."""
    try:
        conn = duckdb.connect(DUCKDB_PATH, read_only=True, config=DUCKDB_CONFIG)
    except Exception:
        return 0.0
    try:
        row = conn.execute(
            """
            SELECT coalesce(avg(CASE WHEN hit THEN 1.0 ELSE 0.0 END), 0.0) FROM (
              SELECT query_id, bool_or(cache_hit) AS hit
              FROM agent_reasoning_log
              WHERE created_at >= now() - INTERVAL 24 HOUR
              GROUP BY query_id
            )
            """
        ).fetchone()
        return round(float(row[0] or 0.0), 4)
    except Exception:
        return 0.0
    finally:
        conn.close()
