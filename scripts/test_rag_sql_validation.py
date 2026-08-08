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
        "Which customers have high CLV and high churn risk?",
        "Which renewal customers need a retention conversation?",
    ],
    "Agency Manager": [
        "Which agents need coaching this month?",
        "Which agents have the highest premium at risk?",
        "Which branch has the highest lapse exposure?",
        "Which agents changed territories and improved sales?",
        "Which agents show declining productivity?",
    ],
    "Campaign Manager": [
        "Which campaign generated the highest policy conversion?",
        "Which customer segments responded best to recent campaigns?",
        "Which campaign has engagement but poor conversion?",
        "What is campaign conversion rate by channel?",
        "What are the bad campaigns?",
    ],
    "Claims Manager": [
        "Which products have the highest claims ratio?",
        "Which claims have high fraud risk?",
        "Which regions show unusual claims growth?",
        "Which claims need manual fraud review?",
        "What is claims exposure by product?",
    ],
    "Sales Director": [
        "Which products are declining in new sales?",
        "Where is the largest cross-sell opportunity?",
        "Which regions are underperforming against target?",
        "Which products are declining in the market?",
        "What product line has the largest premium concentration?",
    ],
    "Executive Leadership": [
        "What are the top risks to revenue this month?",
        "What hidden trends should leadership focus on?",
        "What are the top three growth opportunities?",
        "What is our current lapse rate?",
        "Which business area needs immediate management attention?",
    ],
    "Data Analyst": [
        "Show SQL for lapse risk by product.",
        "Show campaign conversion rate by channel.",
        "Show customers with high CLV and high churn risk.",
        "Show policies sold in Singapore.",
        "Show internal premium by line of business.",
    ],
}


def post_json(url: str, payload: dict[str, Any], timeout: int) -> tuple[int, dict[str, Any] | None, str | None]:
    body = json.dumps(payload).encode("utf-8")
    req = urlrequest.Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urlrequest.urlopen(req, timeout=timeout) as response:
            return response.status, json.loads(response.read().decode("utf-8")), None
    except HTTPError as exc:
        return exc.code, None, exc.read().decode("utf-8", errors="replace")
    except (URLError, TimeoutError) as exc:
        return 0, None, str(exc)


def assess(status_code: int, payload: dict[str, Any] | None, error: str | None) -> tuple[str, list[str]]:
    failures: list[str] = []
    if status_code != 200:
        failures.append(f"http_status={status_code}")
    if error:
        failures.append(error[:180])
    if not payload:
        return "FAIL", failures

    validation = payload.get("result_validation") or {}
    validation_status = str(validation.get("validation_status") or "").upper()
    if not payload.get("related_context"):
        failures.append("context_not_returned")
    if not payload.get("generated_sql"):
        failures.append("sql_not_generated")
    if payload.get("sql_validation_status") != "allowed_select_or_with":
        failures.append(f"sql_validation={payload.get('sql_validation_status')}")
    if payload.get("sql_execution_status") != "executed":
        failures.append(f"sql_execution={payload.get('sql_execution_status')}")
    if validation_status not in {"PASS", "PARTIAL", "FAIL"}:
        failures.append("result_validation_missing")
    if validation_status in {"PASS", "PARTIAL"}:
        if not payload.get("answer_summary"):
            failures.append("final_answer_missing")
        if not payload.get("key_data_points"):
            failures.append("key_data_points_missing")
        if payload.get("recommendations"):
            for recommendation in payload["recommendations"]:
                if not recommendation.get("data_points_used"):
                    failures.append("recommendation_without_data_points")
                    break
    if validation_status == "FAIL" and payload.get("recommendations"):
        failures.append("unsupported_recommendations_published")

    if failures:
        return "FAIL", failures
    if validation_status == "FAIL":
        return "BLOCKED", []
    return validation_status or "PASS", []


def write_outputs(rows: list[dict[str, Any]], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "rag_sql_validation_results.json").write_text(json.dumps(rows, indent=2, default=str), encoding="utf-8")

    fieldnames = [
        "status",
        "role",
        "question",
        "validation_status",
        "row_count",
        "confidence_score",
        "generated_sql",
        "key_data_points",
        "missing_data",
        "final_insight",
        "failures",
    ]
    with (output_dir / "rag_sql_validation_results.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})

    pass_count = sum(1 for row in rows if row["status"] == "PASS")
    partial_count = sum(1 for row in rows if row["status"] == "PARTIAL")
    blocked_count = sum(1 for row in rows if row["status"] == "BLOCKED")
    fail_count = sum(1 for row in rows if row["status"] == "FAIL")
    lines = [
        "# RAG SQL Validation Regression Report",
        "",
        f"- Total tests: {len(rows)}",
        f"- Pass: {pass_count}",
        f"- Partial: {partial_count}",
        f"- Blocked unsupported: {blocked_count}",
        f"- Fail: {fail_count}",
        f"- Generated at: {time.strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "| Status | Role | Question | Rows | Validation | Key Data Points |",
        "|---|---|---|---:|---|---|",
    ]
    for row in rows:
        question = str(row["question"]).replace("|", "\\|")
        key_points = str(row.get("key_data_points", "")).replace("|", "\\|")[:240]
        lines.append(f"| {row['status']} | {row['role']} | {question} | {row.get('row_count', 0)} | {row.get('validation_status', '')} | {key_points} |")
    (output_dir / "rag_sql_validation_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Regression-test AI Insight RAG SQL validation and grounded answer quality.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8071")
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--output-dir", default=".")
    args = parser.parse_args()

    endpoint = args.base_url.rstrip("/") + "/ai-insight-v11/ask"
    results: list[dict[str, Any]] = []
    for role, questions in QUESTIONS_BY_ROLE.items():
        for question in questions:
            started = time.perf_counter()
            status_code, payload, error = post_json(endpoint, {"role": role, "question": question}, timeout=args.timeout)
            elapsed_ms = int((time.perf_counter() - started) * 1000)
            status, failures = assess(status_code, payload, error)
            payload = payload or {}
            validation = payload.get("result_validation") or {}
            key_points = payload.get("key_data_points") or []
            row = {
                "status": status,
                "role": role,
                "question": question,
                "validation_status": validation.get("validation_status", ""),
                "row_count": payload.get("row_count", 0),
                "confidence_score": payload.get("confidence_score", ""),
                "generated_sql": payload.get("generated_sql", ""),
                "key_data_points": "; ".join(f"{item.get('metric')}: {item.get('value')}" for item in key_points if isinstance(item, dict)),
                "missing_data": "; ".join(payload.get("missing_data_points") or validation.get("missing_data_points") or []),
                "final_insight": payload.get("answer_summary", ""),
                "latency_ms": payload.get("latency_ms", elapsed_ms),
                "failures": "; ".join(failures),
            }
            results.append(row)
            print(f"{status}: {role} - {question} ({row['validation_status']}, {row['row_count']} rows)")

    write_outputs(results, Path(args.output_dir))
    return 0 if all(row["status"] in {"PASS", "PARTIAL", "BLOCKED"} for row in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
