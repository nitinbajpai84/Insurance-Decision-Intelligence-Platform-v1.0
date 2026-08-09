"""Robust DuckDB connect for the graph/feedback subsystem.

DuckDB caches one database *instance* per file per process, keyed by access
mode. The V2 backend mixes read_only readers (data_products, execution_agent —
which must stay read-only for untrusted-SQL safety) with read_write writers
(feedback engine, tracer). When a read_only instance from a previous request is
still cached, a later read_write open raises:

    ConnectionException: Can't open a connection to same database file with a
    different configuration than existing connections

Once the stale connection is garbage-collected the instance is released. So on
that specific error we force a gc pass and retry briefly. This keeps the
feedback subsystem reliable without forcing every reader to read_write.
"""
from __future__ import annotations

import gc
import time

import duckdb

_CONFIG_ERR = "different configuration"


def robust_connect(path: str, read_only: bool, retries: int = 6, delay: float = 0.15):
    # Lazy + defensive import: robust_connect is also used by standalone
    # graph-building scripts invoked directly (python graph/build_graph.py
    # etc.), which don't put the project root on sys.path themselves.
    import sys
    from pathlib import Path as _Path

    project_root = _Path(__file__).resolve().parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    from backend_v2.config import DUCKDB_CONFIG

    last: Exception | None = None
    for attempt in range(retries):
        try:
            return duckdb.connect(path, read_only=read_only, config=DUCKDB_CONFIG)
        except duckdb.ConnectionException as exc:
            last = exc
            if _CONFIG_ERR in str(exc) and attempt < retries - 1:
                gc.collect()
                time.sleep(delay)
                continue
            raise
    if last:
        raise last
    raise RuntimeError("robust_connect: exhausted retries")
