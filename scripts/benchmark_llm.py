from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from copilot_sql_engine.llm_providers import GeminiProvider, LLMProvider, response_preview


PROMPTS = {
    "intent": "Classify intent for: Which customers should I call this week? Return only the intent name.",
    "sql_generation": "Generate a PostgreSQL SELECT to find top campaigns by conversion rate. Return concise SQL only.",
    "explanation": "Explain this result: campaign A conversion_rate=0.12, campaign B conversion_rate=0.04.",
    "recommendation": "Explain why an agent should call a high CLV customer with high lapse risk.",
}


def run_one(provider: LLMProvider, task_type: str, prompt: str) -> dict:
    try:
        response = provider.generate(prompt, task_type=task_type, temperature=0.1)
        return {
            "provider": response.provider,
            "model": response.model,
            "task_type": task_type,
            "latency_ms": response.latency_ms,
            "success": True,
            "timeout": False,
            "response_length": len(response.text),
            "response_preview": response_preview(response.text, 140),
        }
    except Exception as exc:
        return {
            "provider": provider.provider_name,
            "model": provider.model_for_task(task_type),
            "task_type": task_type,
            "latency_ms": None,
            "success": False,
            "timeout": "timeout" in type(exc).__name__.lower() or "timed out" in str(exc).lower(),
            "response_length": 0,
            "response_preview": f"{type(exc).__name__}: {exc}"[:140],
        }


def main() -> None:
    load_dotenv(".env")
    providers: list[LLMProvider] = []
    try:
        providers.append(GeminiProvider())
    except Exception as exc:
        print(f"Skipping GeminiProvider: {type(exc).__name__}: {exc}")

    rows = [run_one(provider, task_type, prompt) for provider in providers for task_type, prompt in PROMPTS.items()]

    print("\nprovider | model | task_type | latency_ms | success | timeout | preview")
    print("-" * 110)
    for row in rows:
        print(
            f"{row['provider']} | {row['model']} | {row['task_type']} | {row['latency_ms']} | "
            f"{row['success']} | {row['timeout']} | {row['response_preview']}"
        )

    Path("benchmark_results.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
    with Path("benchmark_results.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()) if rows else [])
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    main()
