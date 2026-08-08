from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
DOCS_DIR = ROOT / "docs" / "demo"
RESULTS_PATH = DOCS_DIR / "demo_readiness_results.json"
REPORT_PATH = DOCS_DIR / "demo_readiness_report.md"
CATALOG_PATH = DOCS_DIR / "validated-demo-question-catalog.md"


FRONTEND_ROUTES = [
    ("/", "Home"),
    ("/?view=customer", "Know Your Customer"),
    ("/?view=agent", "Know Your Agent"),
    ("/?view=campaign", "Campaign Effectiveness"),
    ("/?view=agent-performance", "Agent Performance Tracking"),
    ("/?view=lapse-risk", "Policy Lapse Risk"),
    ("/ai-intelligence", "AI Intelligence"),
    ("/insight-evidence-hub", "Insight Evidence Hub"),
]


DEMO_QUESTIONS = [
    ("Agency Manager", "Which agents have the highest premium at risk?"),
    ("Agency Manager", "Which agents need coaching this month?"),
    ("Campaign Manager", "Which campaign generated the highest policy conversion?"),
    ("Campaign Manager", "Which customer segment responded best to health campaigns?"),
    ("Sales Director", "Which products are declining in new sales?"),
    ("Insurance Agent", "Which policies are likely to lapse in the next 90 days?"),
    ("Insurance Agent", "Which customers should agents contact this week?"),
    ("Executive Leadership", "What are the top risks to revenue this month?"),
    ("Executive Leadership", "What are the top growth opportunities?"),
    ("Data Analyst", "Show campaign conversion rate by channel."),
]


def env(name: str, default: str) -> str:
    return os.environ.get(name, default).rstrip("/")


def request_json(method: str, url: str, payload: dict[str, Any] | None = None, timeout: int = 120) -> tuple[int, Any, str]:
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = Request(url, data=data, headers=headers, method=method)
    try:
        with urlopen(req, timeout=timeout) as response:
            raw = response.read().decode("utf-8", errors="replace")
            content_type = response.headers.get("Content-Type", "")
            if "json" in content_type:
                return response.status, json.loads(raw), raw
            return response.status, None, raw
    except HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            return exc.code, json.loads(raw), raw
        except json.JSONDecodeError:
            return exc.code, None, raw
    except URLError as exc:
        return 0, None, str(exc.reason)
    except TimeoutError as exc:
        return 0, None, str(exc)


def add_result(results: list[dict[str, Any]], area: str, name: str, status: str, details: str, **extra: Any) -> None:
    results.append(
        {
            "area": area,
            "name": name,
            "status": status,
            "details": details,
            **extra,
        }
    )


def test_frontend(frontend_url: str, results: list[dict[str, Any]]) -> None:
    for route, title in FRONTEND_ROUTES:
        status, _, raw = request_json("GET", f"{frontend_url}{route}", timeout=30)
        ok = status == 200 and "Application error" not in raw and "Runtime TypeError" not in raw
        has_brand = "Insurance Decision Intelligence Platform" in raw or "Insurance Intelligence Product" in raw
        add_result(
            results,
            "frontend_route",
            title,
            "PASS" if ok and has_brand else "FAIL",
            f"HTTP {status}; route={route}; brand_present={has_brand}",
        )


def test_backend(api_url: str, results: list[dict[str, Any]]) -> None:
    endpoints = [
        ("/health", "backend health"),
        ("/health/llm", "llm health"),
        ("/debug/sql-context-health", "sql context health"),
        ("/debug/latest-insight-evidence", "latest insight evidence"),
    ]
    for path, name in endpoints:
        status, payload, raw = request_json("GET", f"{api_url}{path}", timeout=60)
        ok = status == 200
        details = raw[:300].replace("\n", " ")
        if path == "/health/llm" and isinstance(payload, dict):
            details = f"provider={payload.get('active_provider')}; gemini_available={payload.get('gemini_available')}; quota_exhausted={payload.get('gemini_quota_exhausted')}"
        add_result(results, "backend_endpoint", name, "PASS" if ok else "FAIL", details)


def test_sql_safety(api_url: str, results: list[dict[str, Any]]) -> None:
    payload = {
        "sql": "drop table public.customers",
        "row_limit": 25,
    }
    status, body, raw = request_json("POST", f"{api_url}/sql/validate", payload, timeout=30)
    text = json.dumps(body or {}, default=str).lower() + raw.lower()
    blocked = status in {200, 400, 422} and ("drop" in text or "blocked" in text or "not allowed" in text or "unsafe" in text)
    add_result(
        results,
        "sql_safety",
        "blocks destructive SQL",
        "PASS" if blocked else "FAIL",
        f"HTTP {status}; response={raw[:250].replace(chr(10), ' ')}",
    )


def test_ai_questions(api_url: str, results: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    catalog: list[dict[str, Any]] = []
    for role, question in DEMO_QUESTIONS[:limit]:
        status, payload, raw = request_json(
            "POST",
            f"{api_url}/ai-insight-v11/ask",
            {"role": role, "question": question},
            timeout=180,
        )
        if isinstance(payload, dict):
            validation = str(payload.get("sql_validation_status") or payload.get("answer_status") or "")
            execution = str(payload.get("sql_execution_status") or "")
            row_count = int(payload.get("row_count") or 0)
            answer_status = str(payload.get("answer_status") or "")
            sql = str(payload.get("generated_sql") or "")
            unsupported = answer_status.upper() in {"NOT_SUPPORTED", "FAIL"} or "not supported" in str(payload.get("answer_summary", "")).lower()
            ready = (
                status == 200
                and validation.upper() in {"VALIDATED", "SQL_REPAIRED", "ALLOWED"}
                and execution.lower() in {"executed", "success"}
                and row_count > 0
                and not unsupported
                and "public." in sql
            )
            details = f"validation={validation}; execution={execution}; rows={row_count}; answer={answer_status}"
            catalog.append(
                {
                    "role": role,
                    "question": question,
                    "demo_ready": ready,
                    "validation_status": validation,
                    "execution_status": execution,
                    "row_count": row_count,
                    "answer_status": answer_status,
                    "sql_preview": sql[:500],
                    "fallback_used": bool(payload.get("fallback_used")),
                    "provider_used": payload.get("provider_used"),
                    "model_used": payload.get("model_used"),
                    "unsupported_reason": "" if ready else "; ".join(str(x) for x in payload.get("missing_data_points", [])[:3]),
                }
            )
        else:
            ready = False
            details = f"HTTP {status}; response={raw[:250].replace(chr(10), ' ')}"
            catalog.append(
                {
                    "role": role,
                    "question": question,
                    "demo_ready": False,
                    "validation_status": "error",
                    "execution_status": "error",
                    "row_count": 0,
                    "answer_status": "error",
                    "sql_preview": "",
                    "fallback_used": False,
                    "provider_used": "",
                    "model_used": "",
                    "unsupported_reason": details,
                }
            )
        add_result(results, "ai_question", f"{role}: {question}", "PASS" if ready else "FAIL", details)
    return catalog


def write_report(results: list[dict[str, Any]], catalog: list[dict[str, Any]], frontend_url: str, api_url: str) -> None:
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    generated_at = datetime.now(timezone.utc).isoformat()
    RESULTS_PATH.write_text(
        json.dumps(
            {
                "generated_at": generated_at,
                "frontend_url": frontend_url,
                "api_url": api_url,
                "results": results,
                "question_catalog": catalog,
            },
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )

    passed = sum(1 for item in results if item["status"] == "PASS")
    lines = [
        "# Demo Readiness Report",
        "",
        f"- Generated at: {generated_at}",
        f"- Frontend URL: `{frontend_url}`",
        f"- API URL: `{api_url}`",
        f"- Checks passed: {passed}/{len(results)}",
        "",
        "## Check Results",
        "",
        "| Area | Name | Status | Details |",
        "|---|---|---|---|",
    ]
    for item in results:
        details = str(item["details"]).replace("|", "/").replace("\n", " ")
        lines.append(f"| {item['area']} | {item['name']} | {item['status']} | {details} |")
    lines.extend(
        [
            "",
            "## Demo Question Catalog",
            "",
            "| Role | Question | Demo Ready | Validation | Execution | Rows | Provider |",
            "|---|---|---|---|---|---:|---|",
        ]
    )
    for item in catalog:
        lines.append(
            f"| {item['role']} | {item['question']} | {'YES' if item['demo_ready'] else 'NO'} | {item['validation_status']} | {item['execution_status']} | {item['row_count']} | {item['provider_used']} / {item['model_used']} |"
        )
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")

    catalog_lines = [
        "# Validated Demo Question Catalog",
        "",
        f"- Generated at: {generated_at}",
        "- Only use questions marked `YES` during a client recording.",
        "",
        "| Role | Question | Demo Ready | Row Count | Notes |",
        "|---|---|---|---:|---|",
    ]
    for item in catalog:
        notes = item["unsupported_reason"] if not item["demo_ready"] else f"{item['validation_status']} / {item['execution_status']}"
        catalog_lines.append(f"| {item['role']} | {item['question']} | {'YES' if item['demo_ready'] else 'NO'} | {item['row_count']} | {str(notes).replace('|', '/')} |")
    CATALOG_PATH.write_text("\n".join(catalog_lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run client-demo readiness checks.")
    parser.add_argument("--frontend-url", default=env("FRONTEND_URL", "http://127.0.0.1:3000"))
    parser.add_argument("--api-url", default=env("API_URL", "http://127.0.0.1:8071"))
    parser.add_argument("--ai-limit", type=int, default=10)
    args = parser.parse_args()

    results: list[dict[str, Any]] = []
    test_frontend(args.frontend_url, results)
    test_backend(args.api_url, results)
    test_sql_safety(args.api_url, results)
    catalog = test_ai_questions(args.api_url, results, max(0, min(args.ai_limit, len(DEMO_QUESTIONS))))
    write_report(results, catalog, args.frontend_url, args.api_url)

    passed = sum(1 for item in results if item["status"] == "PASS")
    print(json.dumps({"passed": passed, "total": len(results), "report": str(REPORT_PATH)}, indent=2))
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())

