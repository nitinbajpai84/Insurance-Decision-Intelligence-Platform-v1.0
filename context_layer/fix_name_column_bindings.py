"""
Idempotent fix: 7 of 31 metric_bindings referenced a canonical_view that has a
display_name/campaign_name column, but allowed_columns never listed it -- so
any question naming an entity by name (not ID) had no sanctioned column to
filter on, and the SQL agent hallucinated one instead (e.g. `agents.agent_name`,
which does not exist -- names live on parties.display_name / the *_360 views).

Applied directly to the live DB during the 2026-08-12 data-layer audit;
this script exists so the fix survives a rebuild-from-schema and isn't lost
to a one-off interactive session. Safe to rerun: it only appends a column
if missing, never removes.

Usage: venv\\Scripts\\python.exe context_layer\\fix_name_column_bindings.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from graph.db_util import robust_connect
from backend_v2.config import DUCKDB_PATH

# metric_id -> name column(s) to guarantee are present in allowed_columns,
# qualified against that binding's own canonical_view.
FIXES: dict[str, list[str]] = {
    "metric::campaign_conversion": ["campaign_name"],
    "metric::clv": ["display_name", "advisor_name"],
    "metric::agent_target_achievement": ["display_name"],
    "metric::persistency_25m": ["display_name"],
    "metric::campaign_response_rate": ["campaign_name"],
    "metric::campaign_roi": ["campaign_name"],
    "metric::agent_persistency": ["display_name"],
}


def main() -> None:
    con = robust_connect(DUCKDB_PATH, read_only=False)
    changed = 0
    try:
        for mid, new_cols in FIXES.items():
            row = con.execute(
                "select canonical_view, allowed_columns from metric_bindings where metric_id = ?", [mid]
            ).fetchone()
            if not row:
                print(f"[skip] {mid} not found")
                continue
            view, cols_json = row
            cols = json.loads(cols_json) if cols_json else []
            added = []
            for nc in new_cols:
                qualified = f"{view}.{nc}"
                if qualified not in cols:
                    cols.append(qualified)
                    added.append(qualified)
            if added:
                con.execute("update metric_bindings set allowed_columns = ? where metric_id = ?",
                           [json.dumps(cols), mid])
                changed += 1
                print(f"[fixed] {mid}: +{added}")
            else:
                print(f"[ok] {mid}: already has name column(s)")
        con.commit()
    finally:
        con.close()
    print(f"\n{changed} binding(s) updated.")


if __name__ == "__main__":
    main()
