from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from copilot_orchestration.models import CopilotIntent


@dataclass
class ResultValidationOutput:
    answer_status: str
    does_result_answer_question: bool
    result_quality_score: float
    reason: str
    missing_data_points: list[str] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)
    can_generate_business_insight: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "answer_status": self.answer_status,
            "validation_status": self.answer_status,
            "does_result_answer_question": self.does_result_answer_question,
            "result_quality_score": self.result_quality_score,
            "reason": self.reason,
            "missing_data_points": self.missing_data_points,
            "limitations": self.limitations,
            "can_generate_business_insight": self.can_generate_business_insight,
            "publish_allowed": self.can_generate_business_insight,
        }


def validate_result_relevance(
    *,
    question: str,
    role_code: str | None,
    intent: CopilotIntent,
    generated_sql: str | None,
    execution_status: str,
    row_count: int,
    result_preview: list[dict[str, Any]],
    retrieved_context: dict[str, Any] | None,
    missing_requirements: list[str] | None = None,
) -> ResultValidationOutput:
    if execution_status != "executed":
        return ResultValidationOutput(
            answer_status="NOT_SUPPORTED",
            does_result_answer_question=False,
            result_quality_score=0.0,
            reason="SQL was not executed successfully.",
            missing_data_points=missing_requirements or [],
            limitations=["Business insight is blocked because SQL execution did not succeed."],
            can_generate_business_insight=False,
        )
    if not generated_sql:
        return ResultValidationOutput(
            answer_status="NOT_SUPPORTED",
            does_result_answer_question=False,
            result_quality_score=0.0,
            reason="No validated SQL was available.",
            missing_data_points=missing_requirements or ["validated SQL"],
            limitations=["Business insight is blocked because there is no validated SQL."],
            can_generate_business_insight=False,
        )
    if row_count == 0:
        return ResultValidationOutput(
            answer_status="PARTIAL",
            does_result_answer_question=False,
            result_quality_score=0.35,
            reason="SQL executed successfully but returned no rows for the current data scope.",
            missing_data_points=["matching rows for the selected question, role, or time window"],
            limitations=["The current data does not contain rows matching the generated query."],
            can_generate_business_insight=True,
        )

    q = question.lower()
    columns = {column.lower() for row in result_preview[:10] for column in row.keys()}
    limitations: list[str] = []
    score = 0.78
    status = "VALIDATED"

    if intent == CopilotIntent.RECOMMENDATION and not any(
        token in columns for token in {"recommended_action", "priority_score", "customer_id", "agent_id"}
    ):
        status = "PARTIAL"
        score = 0.55
        limitations.append("Recommendation question returned data, but not a complete next-best-action shape.")
    if "campaign" in q and not any(token in columns for token in {"campaign_name", "campaign_id", "conversions", "policy_count"}):
        status = "PARTIAL"
        score = min(score, 0.55)
        limitations.append("Campaign question returned data, but campaign identifiers or conversion metrics were limited.")
    if ("agent" in q or "coaching" in q) and not any(token in columns for token in {"agent_name", "agent_id", "agent_number"}):
        status = "PARTIAL"
        score = min(score, 0.58)
        limitations.append("Agent question returned data, but agent identifiers were limited.")
    if "lapse" in q and not any(token in columns for token in {"lapse_score", "lapse_risk", "premium_at_risk", "lapsed_policy_count"}):
        status = "PARTIAL"
        score = min(score, 0.6)
        limitations.append("Lapse question returned data, but explicit lapse-risk fields were limited.")

    if missing_requirements:
        status = "PARTIAL"
        score = min(score, 0.62)
        limitations.extend(missing_requirements)

    return ResultValidationOutput(
        answer_status=status,
        does_result_answer_question=status == "VALIDATED",
        result_quality_score=score,
        reason="SQL executed and returned a relevant result preview." if status == "VALIDATED" else "SQL executed, but result relevance is partial.",
        missing_data_points=missing_requirements or [],
        limitations=list(dict.fromkeys(limitations)),
        can_generate_business_insight=True,
    )
