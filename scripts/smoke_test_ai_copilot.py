from __future__ import annotations

import argparse
import csv
import json
import time
from dataclasses import dataclass
from pathlib import Path
import sys
from typing import Any
from uuid import uuid4

import requests

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from insight_snapshot_service import save_insight_snapshot


QUESTIONS_BY_ROLE: dict[str, list[str]] = {
    "insurance_agent": [
        "Which customers should I contact first today?",
        "Which of my customers are most likely to lapse in the next 90 days?",
        "Which customers have high propensity to buy health products?",
        "Which customer has high value but low recent engagement?",
        "What is the next best product for my top priority customers?",
    ],
    "agency_manager": [
        "Which agents need coaching this month?",
        "Which agents have declining MAPA activity?",
        "Which agents have the highest premium at risk?",
        "Which branch has the highest lapse exposure?",
        "Which agents are converting leads below the team average?",
    ],
    "campaign_manager": [
        "Which campaigns generated the highest policy conversion?",
        "Which customer segment responded best to health campaigns?",
        "Which campaign has high engagement but low conversion?",
        "Which campaign should receive more budget?",
        "Which leads from recent campaigns should be prioritized?",
    ],
    "claims_manager": [
        "Which products have increasing claim ratios?",
        "Which claims have high fraud risk?",
        "Which regions show unusual claims growth?",
        "Which customers have repeated claims and high lapse risk?",
        "Which claim types are driving the highest payout?",
    ],
    "sales_director": [
        "Which regions are underperforming against target?",
        "Which products are declining in new sales?",
        "Which agents have high activity but low conversion?",
        "Where is the largest cross-sell opportunity?",
        "Which customer segments are driving premium growth?",
    ],
    "executive_leadership": [
        "What are the top risks to revenue this month?",
        "What hidden trends should concern leadership?",
        "Which products are declining in the market?",
        "What is the total premium at risk from likely lapses?",
        "What are the top three growth opportunities?",
    ],
    "data_analyst": [
        "Show the SQL for lapse risk by product.",
        "Show campaign conversion rate by channel.",
        "Show agent MAPA trend by month.",
        "Show customers with high CLV and high churn risk.",
        "Show policies with missed payments and high lapse score.",
    ],
}


@dataclass
class SmokeResult:
    role: str
    question: str
    passed: bool
    status: str
    latency_ms: int
    row_count: int
    generated_sql: str
    confidence_score: float
    error: str
    snapshot_saved: bool


def main() -> None:
    parser = argparse.ArgumentParser(description="Smoke test role-aware AI Intelligence text-to-SQL flow.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8071")
    parser.add_argument("--output-dir", default=".")
    parser.add_argument("--row-limit", type=int, default=25)
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--legacy-route", action="store_true", help="Use /copilot/ask instead of /intelligence/ask.")
    args = parser.parse_args()

    endpoint = f"{args.base_url.rstrip('/')}/{'copilot/ask' if args.legacy_route else 'intelligence/ask'}"
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    test_run_id = uuid4()
    results: list[SmokeResult] = []

    for role, questions in QUESTIONS_BY_ROLE.items():
        for question in questions:
            started = time.perf_counter()
            payload = {
                "question": question,
                "role_code": role,
                "include_context": True,
                "include_debug": True,
                "row_limit": args.row_limit,
                "execute_sql": True,
            }
            response_json: dict[str, Any] | None = None
            error = ""
            try:
                response = requests.post(endpoint, json=payload, timeout=args.timeout)
                response.raise_for_status()
                response_json = response.json()
            except Exception as exc:
                error = f"{type(exc).__name__}: {exc}"
            latency_ms = int((time.perf_counter() - started) * 1000)
            snapshot_saved = False
            if response_json:
                try:
                    save_insight_snapshot(
                        question=question,
                        role=role,
                        response=response_json,
                        test_run_id=test_run_id,
                        error_message=error or None,
                    )
                    snapshot_saved = True
                except Exception as exc:
                    error = f"{error}; snapshot_save_failed={type(exc).__name__}: {exc}".strip("; ")
            execution = (response_json or {}).get("execution") or {}
            validation = (response_json or {}).get("validation") or {}
            sql = (response_json or {}).get("sql") or ""
            row_count = int(execution.get("row_count") or 0)
            passed = bool(
                response_json
                and (response_json.get("role_code") == role)
                and sql
                and validation
                and execution.get("execution_status") == "executed"
                and (response_json.get("business_insight") or {}).get("summary")
                and (response_json.get("explainability") or {}).get("source_tables") is not None
                and snapshot_saved
            )
            results.append(
                SmokeResult(
                    role=role,
                    question=question,
                    passed=passed,
                    status=str(execution.get("execution_status") or "failed"),
                    latency_ms=latency_ms,
                    row_count=row_count,
                    generated_sql=sql,
                    confidence_score=float((response_json or {}).get("confidence_score") or 0),
                    error=error,
                    snapshot_saved=snapshot_saved,
                )
            )

    write_outputs(output_dir, test_run_id, results)
    failed = [result for result in results if not result.passed]
    print_summary(test_run_id, results)
    if failed:
        raise SystemExit(1)


def write_outputs(output_dir: Path, test_run_id, results: list[SmokeResult]) -> None:
    rows = [result.__dict__ for result in results]
    (output_dir / "smoke_test_results.json").write_text(
        json.dumps({"test_run_id": str(test_run_id), "results": rows}, indent=2),
        encoding="utf-8",
    )
    with (output_dir / "smoke_test_results.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    passed = sum(1 for result in results if result.passed)
    failed = len(results) - passed
    report = [
        "# AI Intelligence Smoke Test Report",
        "",
        f"- Test run id: `{test_run_id}`",
        f"- Total questions: {len(results)}",
        f"- Passed: {passed}",
        f"- Failed: {failed}",
        f"- Average latency ms: {round(sum(result.latency_ms for result in results) / max(len(results), 1), 1)}",
        "",
        "| Role | Question | Status | Rows | Latency ms | Snapshot |",
        "|---|---|---:|---:|---:|---|",
    ]
    for result in results:
        report.append(
            f"| {result.role} | {result.question.replace('|', '/')} | {'PASS' if result.passed else 'FAIL'} | {result.row_count} | {result.latency_ms} | {result.snapshot_saved} |"
        )
    failures = [result for result in results if not result.passed]
    if failures:
        report.extend(["", "## Failures", ""])
        for result in failures:
            report.append(f"- `{result.role}` / {result.question}: {result.error or result.status}")
    (output_dir / "smoke_test_report.md").write_text("\n".join(report), encoding="utf-8")


def print_summary(test_run_id, results: list[SmokeResult]) -> None:
    print(f"test_run_id={test_run_id}")
    for result in results:
        state = "PASS" if result.passed else "FAIL"
        print(f"{state:4} | {result.role:22} | rows={result.row_count:4} | latency={result.latency_ms:6} ms | {result.question}")


if __name__ == "__main__":
    main()
