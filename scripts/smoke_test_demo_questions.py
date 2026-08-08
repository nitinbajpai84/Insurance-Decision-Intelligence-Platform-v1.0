from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from uuid import uuid4

import psycopg
from dotenv import load_dotenv
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from copilot_sql_engine.engine import run_sql_engine
from copilot_sql_engine.models import SqlEngineRequest
from scripts.build_actual_schema_catalog import create_snapshot


DDL = """
create extension if not exists pgcrypto;

create table if not exists public.cld_demo_question_catalog (
  demo_question_id uuid primary key,
  role text not null,
  question text not null,
  intent text,
  business_domain text,
  required_tables jsonb not null default '[]'::jsonb,
  required_columns jsonb not null default '[]'::jsonb,
  required_models jsonb not null default '[]'::jsonb,
  validated_sql text,
  expected_output_shape jsonb not null default '{}'::jsonb,
  is_validated boolean not null default false,
  last_validated_at timestamp with time zone,
  validation_status text,
  created_at timestamp with time zone not null default now(),
  updated_at timestamp with time zone not null default now()
);

create unique index if not exists idx_cld_demo_question_catalog_role_question
  on public.cld_demo_question_catalog(role, question);
"""


DEMO_QUESTIONS = [
    ("Insurance Agent", "Which customers should I contact first this week?", "RECOMMENDATION", "Customer"),
    ("Insurance Agent", "Which customers are likely to lapse in the next 90 days?", "ANALYTICS", "Policy"),
    ("Insurance Agent", "Which product should I cross-sell to my high propensity customers?", "RECOMMENDATION", "Customer"),
    ("Insurance Agent", "Which customers have high CLV and high churn risk?", "ANALYTICS", "Customer"),
    ("Insurance Agent", "Which customers have missed payments and active policies?", "ANALYTICS", "Policy"),
    ("Agency Manager", "Which agents need coaching this month?", "ANALYTICS", "Agent"),
    ("Agency Manager", "Which agents have the highest premium at risk?", "ANALYTICS", "Agent"),
    ("Agency Manager", "Which branch has the highest lapse exposure?", "ANALYTICS", "Policy"),
    ("Agency Manager", "Which agents have declining MAPA productivity?", "ANALYTICS", "Agent"),
    ("Agency Manager", "Which agents changed territories and improved sales?", "ANALYTICS", "Agent"),
    ("Campaign Manager", "Which campaign generated the highest policy conversion?", "ANALYTICS", "Campaign"),
    ("Campaign Manager", "Which customer segment responded best to recent campaigns?", "ANALYTICS", "Campaign"),
    ("Campaign Manager", "Which campaign has engagement but poor conversion?", "ANALYTICS", "Campaign"),
    ("Campaign Manager", "Which channel has the best response rate?", "ANALYTICS", "Campaign"),
    ("Campaign Manager", "Which campaigns should be suppressed due to low response?", "ANALYTICS", "Campaign"),
    ("Claims Manager", "Which products have the highest claims ratio?", "ANALYTICS", "Claims"),
    ("Claims Manager", "Which claims have high fraud risk?", "ANALYTICS", "Claims"),
    ("Claims Manager", "Which regions show unusual claims growth?", "ANALYTICS", "Claims"),
    ("Claims Manager", "Which claim causes drive the highest incurred amount?", "ANALYTICS", "Claims"),
    ("Sales Director", "Which products are declining in new sales?", "ANALYTICS", "Sales"),
    ("Sales Director", "Where is the largest cross-sell opportunity?", "ANALYTICS", "Customer"),
    ("Sales Director", "Which regions are underperforming against target?", "ANALYTICS", "Agent"),
    ("Sales Director", "Which agent clusters are rising stars?", "ANALYTICS", "Agent"),
    ("Executive Leadership", "What are the top risks to revenue this month?", "KPI_LOOKUP", "Executive"),
    ("Executive Leadership", "What hidden trends should leadership focus on?", "ANALYTICS", "Executive"),
    ("Executive Leadership", "What are the top three growth opportunities?", "ANALYTICS", "Executive"),
    ("Executive Leadership", "What is policy persistency by product?", "KPI_LOOKUP", "Policy"),
    ("Data Analyst", "Show SQL for lapse risk by product.", "ANALYTICS", "Policy"),
    ("Data Analyst", "Show campaign conversion rate by channel.", "ANALYTICS", "Campaign"),
    ("Data Analyst", "Show customers with high CLV and high churn risk.", "ANALYTICS", "Customer"),
]


def connect(database_url: str):
    return psycopg.connect(database_url, row_factory=dict_row, connect_timeout=30)


def seed_catalog(database_url: str) -> int:
    with connect(database_url) as conn:
        with conn.cursor() as cur:
            cur.execute(DDL)
            for role, question, intent, domain in DEMO_QUESTIONS:
                cur.execute(
                    """
                    insert into public.cld_demo_question_catalog (
                      demo_question_id, role, question, intent, business_domain,
                      expected_output_shape, created_at, updated_at
                    ) values (%s, %s, %s, %s, %s, '{}'::jsonb, now(), now())
                    on conflict (role, question) do update
                    set intent = excluded.intent,
                        business_domain = excluded.business_domain,
                        updated_at = now()
                    """,
                    (str(uuid4()), role, question, intent, domain),
                )
        conn.commit()
    return len(DEMO_QUESTIONS)


def role_code(role: str) -> str:
    return role.lower().replace(" ", "_")


def smoke(database_url: str, *, limit: int | None, rebuild_schema: bool) -> list[dict[str, object]]:
    if rebuild_schema:
        create_snapshot(database_url, ["public"])
    seed_catalog(database_url)
    with connect(database_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select demo_question_id, role, question, intent, business_domain
                from public.cld_demo_question_catalog
                order by role, question
                limit %s
                """,
                (limit or 1000,),
            )
            questions = cur.fetchall()

    results: list[dict[str, object]] = []
    for row in questions:
        started = perf_counter()
        failure_reason = ""
        try:
            response = run_sql_engine(
                SqlEngineRequest(
                    question=row["question"],
                    role_code=role_code(row["role"]),
                    business_domain=row["business_domain"],
                    include_context=True,
                    include_debug=True,
                    row_limit=25,
                    execute_sql=True,
                )
            )
            validation_status = response.strict_sql_validation.get("validation_status")
            if not validation_status and response.validation:
                validation_status = response.validation.safety_decision
            validation_status = validation_status or "missing"
            repair_status = (response.sql_repair or {}).get("repair_status", "not_attempted")
            execution_status = response.execution.execution_status
            answer_status = response.answer_status
            passed = validation_status in {"VALIDATED", "SQL_REPAIRED"} and execution_status == "executed" and answer_status in {"VALIDATED", "PARTIAL"}
            failure_reason = "" if passed else "; ".join(response.strict_sql_validation.get("errors") or response.business_insight.caveats or [])
            generated_sql = response.sql or ""
            row_count = response.execution.row_count
        except Exception as exc:
            validation_status = "error"
            repair_status = "not_attempted"
            execution_status = "error"
            answer_status = "NOT_SUPPORTED"
            generated_sql = ""
            row_count = 0
            passed = False
            failure_reason = f"{type(exc).__name__}: {exc}"
        latency_ms = int((perf_counter() - started) * 1000)
        result = {
            "role": row["role"],
            "question": row["question"],
            "generated_sql": generated_sql,
            "validation_status": validation_status,
            "repair_status": repair_status,
            "execution_status": execution_status,
            "row_count": row_count,
            "answer_status": answer_status,
            "latency_ms": latency_ms,
            "pass_fail": "PASS" if passed else "FAIL",
            "failure_reason": failure_reason,
        }
        results.append(result)
        with connect(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    update public.cld_demo_question_catalog
                    set validated_sql = %s,
                        is_validated = %s,
                        last_validated_at = %s,
                        validation_status = %s,
                        updated_at = now()
                    where demo_question_id = %s
                    """,
                    (
                        generated_sql,
                        passed,
                        datetime.now(timezone.utc),
                        validation_status if passed else failure_reason[:500],
                        row["demo_question_id"],
                    ),
                )
            conn.commit()
    return results


def write_outputs(results: list[dict[str, object]]) -> None:
    Path("demo_question_smoke_results.json").write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")
    with Path("demo_question_smoke_results.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(results[0].keys()) if results else ["status"])
        writer.writeheader()
        writer.writerows(results)
    passed = sum(1 for row in results if row["pass_fail"] == "PASS")
    lines = [
        "# Demo Question Smoke Report",
        "",
        f"- Generated at: {datetime.now(timezone.utc).isoformat()}",
        f"- Questions tested: {len(results)}",
        f"- Passed: {passed}",
        f"- Failed: {len(results) - passed}",
        "",
        "| Role | Question | Validation | Execution | Rows | Answer | Result | Failure Reason |",
        "|---|---|---|---|---:|---|---|---|",
    ]
    for row in results:
        lines.append(
            f"| {row['role']} | {row['question']} | {row['validation_status']} | {row['execution_status']} | {row['row_count']} | {row['answer_status']} | {row['pass_fail']} | {str(row['failure_reason']).replace('|', '/')} |"
        )
    Path("demo_question_smoke_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke test validated client-demo questions.")
    parser.add_argument("--env-file", default=".env")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--rebuild-schema", action="store_true")
    args = parser.parse_args()
    load_dotenv(args.env_file, override=True)
    results = smoke(os.environ["SUPABASE_DB_URL"], limit=args.limit, rebuild_schema=args.rebuild_schema)
    write_outputs(results)
    print(json.dumps({"tested": len(results), "passed": sum(1 for row in results if row["pass_fail"] == "PASS")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
