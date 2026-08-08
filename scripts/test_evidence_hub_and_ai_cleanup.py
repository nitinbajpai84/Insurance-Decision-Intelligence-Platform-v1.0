from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

import requests


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_JSON = ROOT / "evidence_hub_cleanup_results.json"
DEFAULT_OUTPUT_MD = ROOT / "evidence_hub_cleanup_report.md"


TEST_QUESTIONS = [
    ("Executive Leadership", "What are the top risks to revenue this month?"),
    ("Insurance Agent", "Which customers are likely to lapse in the next 90 days?"),
    ("Campaign Manager", "Which campaign generated the highest policy conversion?"),
    ("Data Analyst", "Show SQL for lapse risk by product."),
    ("Sales Director", "Which products are declining in new sales?"),
]

TECHNICAL_TERMS = ("gemini", "quota", "fallback", "ollama", "provider timeout", "llm validation")


def get_json(url: str, timeout: int) -> dict[str, Any]:
    response = requests.get(url, timeout=timeout)
    response.raise_for_status()
    return response.json()


def post_json(url: str, payload: dict[str, Any], timeout: int) -> dict[str, Any]:
    response = requests.post(url, json=payload, timeout=timeout)
    response.raise_for_status()
    return response.json()


def add_result(results: list[dict[str, Any]], name: str, passed: bool, detail: str = "", payload: Any = None) -> None:
    results.append(
        {
            "check": name,
            "status": "PASS" if passed else "FAIL",
            "detail": detail,
            "payload": payload,
        }
    )


def has_real_columns(columns: Any) -> bool:
    if not isinstance(columns, list) or not columns:
        return False
    for item in columns:
        if not isinstance(item, dict):
            return False
        table = str(item.get("table") or "")
        column = str(item.get("column") or "")
        description = str(item.get("business_description") or "")
        if not table or not column:
            return False
        if "See generated SQL projection and joins" in description:
            return False
    return True


def business_limitations_are_clean(limitations: Any) -> bool:
    text = " ".join(str(item).lower() for item in limitations or [])
    return not any(term in text for term in TECHNICAL_TERMS)


def models_are_structured(models: Any) -> bool:
    if models in (None, []):
        return True
    if not isinstance(models, list):
        return False
    return all(isinstance(item, dict) and item.get("model_name") for item in models)


def response_uses_model_for_model_question(question: str, response: dict[str, Any]) -> bool:
    q = question.lower()
    if not any(token in q for token in ("lapse", "risk", "campaign", "declining", "revenue")):
        return True
    return bool(response.get("models_used"))


def write_outputs(results: list[dict[str, Any]], output_json: Path, output_md: Path) -> None:
    summary = {
        "generated_at_epoch": int(time.time()),
        "pass_count": sum(1 for item in results if item["status"] == "PASS"),
        "fail_count": sum(1 for item in results if item["status"] == "FAIL"),
        "results": results,
    }
    output_json.write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")

    lines = [
        "# Evidence Hub and AI Intelligence Cleanup Report",
        "",
        f"- Passed: {summary['pass_count']}",
        f"- Failed: {summary['fail_count']}",
        "",
        "| Check | Status | Detail |",
        "|---|---:|---|",
    ]
    for item in results:
        detail = str(item.get("detail") or "").replace("|", "\\|").replace("\n", " ")
        lines.append(f"| {item['check']} | {item['status']} | {detail} |")
    output_md.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke test AI Intelligence cleanup and Insight Evidence Hub.")
    parser.add_argument("--backend-url", default="http://127.0.0.1:8071")
    parser.add_argument("--frontend-url", default="http://127.0.0.1:3000")
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--output-json", type=Path, default=DEFAULT_OUTPUT_JSON)
    parser.add_argument("--output-md", type=Path, default=DEFAULT_OUTPUT_MD)
    args = parser.parse_args()

    backend = args.backend_url.rstrip("/")
    frontend = args.frontend_url.rstrip("/")
    results: list[dict[str, Any]] = []
    latest_insight_id = ""

    try:
        health = get_json(f"{backend}/health/llm", args.timeout)
        add_result(results, "GET /health/llm", True, f"active_provider={health.get('active_provider')}", health)
    except Exception as exc:
        add_result(results, "GET /health/llm", False, str(exc))

    for route in ("/ai-intelligence", "/insight-evidence-hub"):
        try:
            response = requests.get(f"{frontend}{route}", timeout=args.timeout)
            add_result(results, f"frontend route {route}", response.status_code == 200, f"status={response.status_code}")
        except Exception as exc:
            add_result(results, f"frontend route {route}", False, str(exc))

    source = (ROOT / "frontend" / "app" / "page.tsx").read_text(encoding="utf-8")
    add_result(results, "old duplicate state removed", "intelligenceV10" not in source and 'key: "models"' not in source)
    add_result(results, "old Model Insights UI label removed", 'title="Model Insights"' not in source and 'label: "Model Insights"' not in source)

    for role, question in TEST_QUESTIONS:
        check_prefix = f"AI question: {role} / {question}"
        try:
            response = post_json(f"{backend}/ai-insight-v11/ask", {"role": role, "question": question}, args.timeout)
            latest_insight_id = str(response.get("insight_id") or latest_insight_id)
            add_result(results, f"{check_prefix} returns insight_id", bool(response.get("insight_id")), f"insight_id={response.get('insight_id')}")
            add_result(results, f"{check_prefix} business limitations exclude technical warnings", business_limitations_are_clean(response.get("business_data_limitations")), str(response.get("business_data_limitations") or []))
            add_result(results, f"{check_prefix} related columns are structured", has_real_columns(response.get("related_columns")), json.dumps((response.get("related_columns") or [])[:3], default=str))
            add_result(results, f"{check_prefix} models used are structured", models_are_structured(response.get("models_used")), json.dumps(response.get("models_used") or [], default=str)[:500])
            add_result(results, f"{check_prefix} model intent detection", response_uses_model_for_model_question(question, response), json.dumps(response.get("models_used") or [], default=str)[:500])
            if response.get("technical_warnings"):
                joined_business = " ".join(response.get("business_data_limitations") or []).lower()
                joined_technical = " ".join(response.get("technical_warnings") or []).lower()
                add_result(results, f"{check_prefix} Gemini/fallback warning split", "gemini" not in joined_business and ("gemini" in joined_technical or "fallback" in joined_technical), str(response.get("technical_warnings")))
        except Exception as exc:
            add_result(results, check_prefix, False, str(exc))

    if latest_insight_id:
        try:
            evidence = get_json(f"{backend}/debug/latest-insight-evidence?insight_id={latest_insight_id}", args.timeout)
            add_result(results, "GET /debug/latest-insight-evidence by insight_id", evidence.get("insight_id") == latest_insight_id, f"insight_id={evidence.get('insight_id')}")
            add_result(results, "Evidence Hub payload has related tables", bool(evidence.get("related_tables")), json.dumps((evidence.get("related_tables") or [])[:2], default=str))
            add_result(results, "Evidence Hub payload has related columns", has_real_columns(evidence.get("related_columns")), json.dumps((evidence.get("related_columns") or [])[:3], default=str))
            add_result(results, "Evidence Hub payload has SQL evidence", bool((evidence.get("sql_evidence") or {}).get("generated_sql")), "")
            add_result(results, "Evidence Hub payload has technical diagnostics", bool(evidence.get("technical_diagnostics")), json.dumps(evidence.get("technical_diagnostics") or {}, default=str)[:500])
        except Exception as exc:
            add_result(results, "GET /debug/latest-insight-evidence by insight_id", False, str(exc))
    else:
        add_result(results, "GET /debug/latest-insight-evidence by insight_id", False, "No insight_id generated by previous checks.")

    write_outputs(results, args.output_json, args.output_md)
    failures = [item for item in results if item["status"] == "FAIL"]
    print(f"Wrote {args.output_json}")
    print(f"Wrote {args.output_md}")
    print(f"PASS={len(results) - len(failures)} FAIL={len(failures)}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
