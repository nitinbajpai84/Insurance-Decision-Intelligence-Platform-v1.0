"""Refresh and validate ML feature tables in Supabase Postgres.

The SQL views in 006_ml_feature_engineering_views.sql define leakage-safe
feature logic. This script materializes those views into physical feature
tables created by 007_ml_feature_tables.sql, then runs data quality checks.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import psycopg
from dotenv import load_dotenv
from psycopg import sql
from psycopg.rows import dict_row


FEATURE_TABLES: dict[str, str] = {
    "propensity_to_buy_features": "v_propensity_to_buy_features",
    "next_best_product_features": "v_next_best_product_features",
    "customer_churn_features": "v_customer_churn_features",
    "policy_lapse_features": "v_policy_lapse_features",
    "agent_performance_features": "v_agent_performance_features",
    "next_best_customer_features": "v_next_best_customer_features",
    "lead_conversion_features": "v_lead_conversion_features",
    "agent_attrition_features": "v_agent_attrition_features",
    "claim_prediction_features": "v_claim_prediction_features",
    "fraud_detection_features": "v_fraud_detection_features",
    "customer_lifetime_value_features": "v_customer_lifetime_value_features",
    "campaign_response_features": "v_campaign_response_features",
}

REQUIRED_COLUMNS = (
    "entity_id",
    "snapshot_date",
    "target_label",
    "training_window_start",
    "training_window_end",
    "prediction_window_start",
    "prediction_window_end",
)

CLASSIFICATION_TABLES = {
    "propensity_to_buy_features",
    "next_best_product_features",
    "customer_churn_features",
    "policy_lapse_features",
    "agent_performance_features",
    "next_best_customer_features",
    "lead_conversion_features",
    "agent_attrition_features",
    "claim_prediction_features",
    "fraud_detection_features",
    "campaign_response_features",
}

NUMERIC_TYPES = {
    "smallint",
    "integer",
    "bigint",
    "decimal",
    "numeric",
    "real",
    "double precision",
}


@dataclass
class CheckResult:
    name: str
    status: str
    details: dict[str, Any]


def connect(db_url: str, statement_timeout_ms: int) -> psycopg.Connection:
    conn = psycopg.connect(db_url, row_factory=dict_row, connect_timeout=30)
    with conn.cursor() as cur:
        cur.execute("set statement_timeout = %s", (statement_timeout_ms,))
    return conn


def selected_tables(selection: str) -> list[str]:
    if selection == "all":
        return list(FEATURE_TABLES)
    if selection not in FEATURE_TABLES:
        valid = ", ".join(["all", *FEATURE_TABLES.keys()])
        raise ValueError(f"Unknown feature table '{selection}'. Valid values: {valid}")
    return [selection]


def qualified(name: str) -> sql.Composed:
    if name not in FEATURE_TABLES and name not in FEATURE_TABLES.values():
        raise ValueError(f"Unsafe relation name: {name}")
    return sql.SQL("{}.{}").format(sql.Identifier("public"), sql.Identifier(name))


def refresh_table(conn: psycopg.Connection, table_name: str, dry_run: bool) -> dict[str, Any]:
    view_name = FEATURE_TABLES[table_name]
    started = time.perf_counter()

    statements = [
        sql.SQL("truncate table {}").format(qualified(table_name)),
        sql.SQL("insert into {} select * from {}").format(qualified(table_name), qualified(view_name)),
        sql.SQL("analyze {}").format(qualified(table_name)),
    ]

    if dry_run:
        return {
            "table": table_name,
            "source_view": view_name,
            "status": "dry_run",
            "elapsed_seconds": 0,
        }

    try:
        with conn.cursor() as cur:
            for statement in statements:
                cur.execute(statement)
        conn.commit()
    except Exception:
        conn.rollback()
        raise

    row_count = get_row_count(conn, table_name)
    return {
        "table": table_name,
        "source_view": view_name,
        "status": "refreshed",
        "row_count": row_count,
        "elapsed_seconds": round(time.perf_counter() - started, 2),
    }


def get_row_count(conn: psycopg.Connection, table_name: str) -> int:
    with conn.cursor() as cur:
        cur.execute(sql.SQL("select count(*) as row_count from {}").format(qualified(table_name)))
        return int(cur.fetchone()["row_count"])


def get_columns(conn: psycopg.Connection, table_name: str) -> list[dict[str, Any]]:
    with conn.cursor() as cur:
        cur.execute(
            """
            select column_name, data_type
            from information_schema.columns
            where table_schema = 'public'
              and table_name = %s
            order by ordinal_position
            """,
            (table_name,),
        )
        return list(cur.fetchall())


def check_row_count(conn: psycopg.Connection, table_name: str) -> CheckResult:
    row_count = get_row_count(conn, table_name)
    return CheckResult(
        name="row_count",
        status="pass" if row_count > 0 else "fail",
        details={"row_count": row_count},
    )


def check_required_nulls(conn: psycopg.Connection, table_name: str) -> CheckResult:
    columns = {row["column_name"] for row in get_columns(conn, table_name)}
    missing = [column for column in REQUIRED_COLUMNS if column not in columns]
    if missing:
        return CheckResult("required_nulls", "fail", {"missing_columns": missing})

    projections = [
        sql.SQL("sum(case when {} is null then 1 else 0 end) as {}").format(
            sql.Identifier(column),
            sql.Identifier(f"{column}_nulls"),
        )
        for column in REQUIRED_COLUMNS
    ]

    with conn.cursor() as cur:
        cur.execute(
            sql.SQL("select {} from {}").format(
                sql.SQL(", ").join(projections),
                qualified(table_name),
            )
        )
        nulls = dict(cur.fetchone())

    total_nulls = sum(int(value or 0) for value in nulls.values())
    return CheckResult(
        name="required_nulls",
        status="pass" if total_nulls == 0 else "fail",
        details=nulls,
    )


def check_window_integrity(conn: psycopg.Connection, table_name: str) -> CheckResult:
    with conn.cursor() as cur:
        cur.execute(
            sql.SQL(
                """
                select
                  count(*) filter (
                    where training_window_start > training_window_end
                       or training_window_end > snapshot_date
                       or prediction_window_start < snapshot_date
                       or prediction_window_end <= prediction_window_start
                  ) as bad_window_rows
                from {}
                """
            ).format(qualified(table_name))
        )
        bad_window_rows = int(cur.fetchone()["bad_window_rows"])

    return CheckResult(
        name="window_integrity",
        status="pass" if bad_window_rows == 0 else "fail",
        details={"bad_window_rows": bad_window_rows},
    )


def check_target_distribution(conn: psycopg.Connection, table_name: str) -> CheckResult:
    with conn.cursor() as cur:
        cur.execute(
            sql.SQL(
                """
                select
                  count(*) as row_count,
                  count(target_label) as non_null_targets,
                  count(distinct target_label) as distinct_targets,
                  min(target_label) as min_target,
                  max(target_label) as max_target,
                  avg(target_label::numeric) as avg_target
                from {}
                """
            ).format(qualified(table_name))
        )
        details = dict(cur.fetchone())

    distinct_targets = int(details["distinct_targets"] or 0)
    status = "pass"
    if table_name in CLASSIFICATION_TABLES and distinct_targets < 2:
        status = "warn"
    if int(details["non_null_targets"] or 0) == 0:
        status = "fail"

    for key, value in details.items():
        if hasattr(value, "__float__"):
            details[key] = float(value)

    return CheckResult(name="target_distribution", status=status, details=details)


def check_feature_null_distribution(conn: psycopg.Connection, table_name: str) -> CheckResult:
    columns = [
        row["column_name"]
        for row in get_columns(conn, table_name)
        if row["data_type"] in NUMERIC_TYPES and row["column_name"] != "target_label"
    ][:20]

    if not columns:
        return CheckResult("feature_null_distribution", "warn", {"message": "No numeric feature columns found"})

    row_count = max(get_row_count(conn, table_name), 1)
    projections = [
        sql.SQL("sum(case when {} is null then 1 else 0 end) as {}").format(
            sql.Identifier(column),
            sql.Identifier(column),
        )
        for column in columns
    ]

    with conn.cursor() as cur:
        cur.execute(
            sql.SQL("select {} from {}").format(
                sql.SQL(", ").join(projections),
                qualified(table_name),
            )
        )
        null_counts = dict(cur.fetchone())

    null_rates = {
        column: round(float(null_counts[column] or 0) / row_count, 4)
        for column in columns
    }
    high_null_features = {
        column: rate for column, rate in null_rates.items() if rate > 0.5
    }

    return CheckResult(
        name="feature_null_distribution",
        status="warn" if high_null_features else "pass",
        details={
            "checked_numeric_features": columns,
            "null_rates": null_rates,
            "high_null_features": high_null_features,
        },
    )


def check_numeric_distribution(conn: psycopg.Connection, table_name: str) -> CheckResult:
    columns = [
        row["column_name"]
        for row in get_columns(conn, table_name)
        if row["data_type"] in NUMERIC_TYPES and row["column_name"] != "target_label"
    ][:12]

    if not columns:
        return CheckResult("numeric_distribution", "warn", {"message": "No numeric feature columns found"})

    projections = []
    for column in columns:
        ident = sql.Identifier(column)
        projections.extend(
            [
                sql.SQL("min({}) as {}").format(ident, sql.Identifier(f"{column}_min")),
                sql.SQL("max({}) as {}").format(ident, sql.Identifier(f"{column}_max")),
                sql.SQL("avg({}::numeric) as {}").format(ident, sql.Identifier(f"{column}_avg")),
            ]
        )

    with conn.cursor() as cur:
        cur.execute(
            sql.SQL("select {} from {}").format(
                sql.SQL(", ").join(projections),
                qualified(table_name),
            )
        )
        details = dict(cur.fetchone())

    normalized: dict[str, Any] = {}
    for key, value in details.items():
        normalized[key] = float(value) if hasattr(value, "__float__") else value

    constant_features = []
    for column in columns:
        if normalized.get(f"{column}_min") == normalized.get(f"{column}_max"):
            constant_features.append(column)

    return CheckResult(
        name="numeric_distribution",
        status="warn" if constant_features else "pass",
        details={"checked_numeric_features": columns, "constant_features": constant_features, **normalized},
    )


def run_quality_checks(conn: psycopg.Connection, table_name: str) -> dict[str, Any]:
    checks = [
        check_row_count(conn, table_name),
        check_required_nulls(conn, table_name),
        check_window_integrity(conn, table_name),
        check_target_distribution(conn, table_name),
        check_feature_null_distribution(conn, table_name),
        check_numeric_distribution(conn, table_name),
    ]
    statuses = [check.status for check in checks]
    overall = "fail" if "fail" in statuses else "warn" if "warn" in statuses else "pass"
    return {
        "table": table_name,
        "overall_status": overall,
        "checks": [
            {"name": check.name, "status": check.status, "details": check.details}
            for check in checks
        ],
    }


def write_report(path: Path, report: dict[str, Any]) -> None:
    path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Refresh insurance ML feature tables.")
    parser.add_argument(
        "--feature",
        default="all",
        help="Feature table to refresh, or 'all'.",
    )
    parser.add_argument(
        "--env-file",
        default=".env",
        help="Path to .env file containing SUPABASE_DB_URL.",
    )
    parser.add_argument(
        "--report",
        default="ml_feature_quality_report.json",
        help="Path for the JSON quality report.",
    )
    parser.add_argument(
        "--statement-timeout-ms",
        type=int,
        default=900000,
        help="Postgres statement timeout in milliseconds.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Show selected tables without refreshing.")
    parser.add_argument("--skip-checks", action="store_true", help="Refresh tables without running checks.")
    parser.add_argument("--validate-only", action="store_true", help="Run checks without refreshing.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    load_dotenv(args.env_file)
    db_url = os.getenv("SUPABASE_DB_URL")
    if not db_url:
        print("Missing SUPABASE_DB_URL in environment or .env file.", file=sys.stderr)
        return 2

    try:
        tables = selected_tables(args.feature)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    report: dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "selected_tables": tables,
        "refresh_results": [],
        "quality_results": [],
    }

    with connect(db_url, args.statement_timeout_ms) as conn:
        for table_name in tables:
            if args.validate_only:
                print(f"Validating {table_name}")
            else:
                print(f"Refreshing {table_name}")
                refresh_result = refresh_table(conn, table_name, args.dry_run)
                report["refresh_results"].append(refresh_result)

            if not args.skip_checks and not args.dry_run:
                quality_result = run_quality_checks(conn, table_name)
                report["quality_results"].append(quality_result)
                print(f"  quality: {quality_result['overall_status']}")

    write_report(Path(args.report), report)

    failed = [
        result["table"]
        for result in report["quality_results"]
        if result["overall_status"] == "fail"
    ]
    if failed:
        print(f"Quality checks failed for: {', '.join(failed)}", file=sys.stderr)
        return 1

    print(f"Wrote quality report to {args.report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
