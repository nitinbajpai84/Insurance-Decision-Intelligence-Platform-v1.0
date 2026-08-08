from __future__ import annotations

import argparse
import csv
import json
import time
from pathlib import Path
from typing import Any
from urllib import request as urlrequest
from urllib.error import HTTPError, URLError


QUESTIONS_BY_ROLE: dict[str, list[str]] = {
    "Insurance Agent": [
        "Which customers should I contact first this week?",
        "Which customers are likely to lapse in the next 90 days?",
        "Which product should I cross-sell to my high propensity customers?",
    ],
    "Agency Manager": [
        "Which agents need coaching this month?",
        "Which agents have the highest premium at risk?",
        "Which branch has the highest lapse exposure?",
    ],
    "Campaign Manager": [
        "Which campaign generated the highest policy conversion?",
        "Which customer segments responded best to recent campaigns?",
        "Which campaign has engagement but poor conversion?",
    ],
    "Claims Manager": [
        "Which products have the highest claims ratio?",
        "Which claims have high fraud risk?",
        "Which regions show unusual claims growth?",
    ],
    "Sales Director": [
        "Which products are declining in new sales?",
        "Where is the largest cross-sell opportunity?",
        "Which regions are underperforming against target?",
    ],
    "Executive Leadership": [
        "What are the top risks to revenue this month?",
        "What hidden trends should leadership focus on?",
        "What are the top three growth opportunities?",
    ],
    "Data Analyst": [
        "Show SQL for lapse risk by product.",
        "Show campaign conversion rate by channel.",
        "Show customers with high CLV and high churn risk.",
    ],
}


def post_json(url: str, payload: dict[str, Any], timeout: int) -> tuple[int, dict[str, Any] | None, str | None]:
    data = json.dumps(payload).encode("utf-8")
    req = urlrequest.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlrequest.urlopen(req, timeout=timeout) as response:
            body = response.read().decode("utf-8")
            return response.status, json.loads(body), None
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        return exc.code, None, body
    except URLError as exc:
        return 0, None, str(exc.reason)
    except TimeoutError:
        return 0, None, "Request timed out"


def evaluate_result(status_code: int, payload: dict[str, Any] | None, error: str | None) -> tuple[str, list[str]]:
    failures: list[str] = []
    if status_code != 200:
        failures.append(f"http_status={status_code}")
    if error:
        failures.append(error[:180])
    if not payload:
        return "FAIL", failures
    if not payload.get("generated_sql"):
        failures.append("missing_generated_sql")
    if str(payload.get("sql_validation_status", "")).lower() not in {"allowed_select_or_with", "sample"}:
        failures.append(f"validation={payload.get('sql_validation_status')}")
    if str(payload.get("sql_execution_status", "")).lower() not in {"executed", "sample"}:
        failures.append(f"execution={payload.get('sql_execution_status')}")
    if not payload.get("answer_summary"):
        failures.append("missing_answer_summary")
    if payload.get("confidence_score") is None:
        failures.append("missing_confidence")
    return ("PASS" if not failures else "FAIL"), failures


def write_outputs(results: list[dict[str, Any]], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "ai_insight_v11_smoke_results.json"
    csv_path = output_dir / "ai_insight_v11_smoke_results.csv"
    report_path = output_dir / "ai_insight_v11_smoke_report.md"

    json_path.write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")

    fieldnames = [
        "status",
        "role",
        "question",
        "sql_validation_status",
        "sql_execution_status",
        "row_count",
        "confidence_score",
        "latency_ms",
        "provider_used",
        "model_used",
        "generated_sql",
        "answer_summary",
        "missing_data_points",
        "failures",
    ]
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in results:
            writer.writerow({key: row.get(key, "") for key in fieldnames})

    passed = sum(1 for row in results if row["status"] == "PASS")
    failed = len(results) - passed
    lines = [
        "# AI Insight v1.1 Smoke Test Report",
        "",
        f"- Total tests: {len(results)}",
        f"- Passed: {passed}",
        f"- Failed: {failed}",
        f"- Generated at: {time.strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "| Status | Role | Question | Rows | Confidence | Provider | Model |",
        "|---|---|---|---:|---:|---|---|",
    ]
    for row in results:
        question = str(row["question"]).replace("|", "\\|")
        lines.append(
            f"| {row['status']} | {row['role']} | {question} | {row.get('row_count', 0)} | "
            f"{row.get('confidence_score', '')} | {row.get('provider_used', '')} | {row.get('model_used', '')} |"
        )
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke test the AI Insight v1.1 endpoint.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8071", help="FastAPI base URL")
    parser.add_argument("--timeout", type=int, default=90, help="Per-request timeout in seconds")
    parser.add_argument("--output-dir", default=".", help="Folder for JSON, CSV, and Markdown outputs")
    args = parser.parse_args()

    endpoint = args.base_url.rstrip("/") + "/ai-insight-v11/ask"
    results: list[dict[str, Any]] = []

    for role, questions in QUESTIONS_BY_ROLE.items():
        for question in questions:
            started = time.perf_counter()
            status_code, payload, error = post_json(endpoint, {"role": role, "question": question}, timeout=args.timeout)
            elapsed_ms = int((time.perf_counter() - started) * 1000)
            status, failures = evaluate_result(status_code, payload, error)
            payload = payload or {}
            row = {
                "status": status,
                "role": role,
                "question": question,
                "generated_sql": payload.get("generated_sql", ""),
                "sql_validation_status": payload.get("sql_validation_status", ""),
                "sql_execution_status": payload.get("sql_execution_status", ""),
                "row_count": payload.get("row_count", 0),
                "answer_summary": payload.get("answer_summary", ""),
                "confidence_score": payload.get("confidence_score", ""),
                "missing_data_points": "; ".join(payload.get("missing_data_points") or []),
                "latency_ms": payload.get("latency_ms", elapsed_ms),
                "provider_used": payload.get("provider_used", ""),
                "model_used": payload.get("model_used", ""),
                "failures": "; ".join(failures),
            }
            results.append(row)
            print(f"{status}: {role} - {question} ({row['row_count']} rows, {row['latency_ms']} ms)")

    write_outputs(results, Path(args.output_dir))
    return 0 if all(row["status"] == "PASS" for row in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
