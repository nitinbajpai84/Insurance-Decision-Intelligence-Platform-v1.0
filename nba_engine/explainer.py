from __future__ import annotations

import json
from typing import Any

from dotenv import load_dotenv

from copilot_sql_engine.llm_providers import get_llm_provider
from nba_engine.models import NextBestActionDecision
from nba_engine.prompts import NBA_EXPLANATION_SYSTEM_PROMPT, build_explanation_prompt


def _json_default(value: Any) -> str:
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _decision_dict(decision: NextBestActionDecision) -> dict[str, Any]:
    if hasattr(decision, "model_dump"):
        return decision.model_dump(mode="json")
    return json.loads(decision.json())


class LLMExplanationLayer:
    def __init__(self, env_file: str = ".env", enable_llm: bool = False) -> None:
        load_dotenv(env_file)
        self.enable_llm = enable_llm

    def explain(self, decision: NextBestActionDecision, context_used: list[dict[str, Any]]) -> NextBestActionDecision:
        updated = decision.model_copy(deep=True) if hasattr(decision, "model_copy") else decision.copy(deep=True)
        updated.context_used = context_used
        if not self.enable_llm:
            return self._deterministic_explanation(updated, context_used)
        try:
            return self._llm_explanation(updated, context_used)
        except Exception:
            return self._deterministic_explanation(updated, context_used)

    def _deterministic_explanation(
        self,
        decision: NextBestActionDecision,
        context_used: list[dict[str, Any]],
    ) -> NextBestActionDecision:
        context_titles = [item.get("title") for item in context_used[:3] if item.get("title")]
        if context_titles:
            decision.business_reason = f"{decision.business_reason} Context referenced: {', '.join(context_titles)}."
        return decision

    def _llm_explanation(
        self,
        decision: NextBestActionDecision,
        context_used: list[dict[str, Any]],
    ) -> NextBestActionDecision:
        prompt = (
            f"{NBA_EXPLANATION_SYSTEM_PROMPT}\n\n"
            + build_explanation_prompt(
                decision_json=json.dumps(_decision_dict(decision), default=_json_default),
                context_json=json.dumps(context_used, default=_json_default),
            )
        )
        response = get_llm_provider("recommendation").generate(prompt, task_type="recommendation", temperature=0.0)
        parsed = json.loads(response.text)
        if parsed.get("business_reason"):
            decision.business_reason = str(parsed["business_reason"])
        if parsed.get("suggested_message"):
            decision.suggested_message = str(parsed["suggested_message"])
        return decision
