from __future__ import annotations

import os
from time import perf_counter
from typing import Any

from pydantic import BaseModel, Field

from ai_evidence_utils import detect_models_used, extract_related_columns, technical_warning_flags
from copilot_api_gateway.db import connect
from copilot_sql_engine.engine import run_sql_engine
from copilot_sql_engine.models import SqlEngineRequest


class AiInsightV11Request(BaseModel):
    role: str = Field(default="Executive Leadership", min_length=2, max_length=100)
    question: str = Field(min_length=3, max_length=2000)


class AiInsightV11Response(BaseModel):
    insight_id: str | None = None
    role: str
    question: str
    answer_summary: str
    key_data_points: list[dict[str, Any]] = Field(default_factory=list)
    insights: list[dict[str, Any]]
    recommendations: list[dict[str, Any]]
    result_validation: dict[str, Any] = Field(default_factory=dict)
    answer_status: str = "PENDING"
    strict_sql_validation: dict[str, Any] = Field(default_factory=dict)
    sql_repair: dict[str, Any] | None = None
    lifecycle: list[dict[str, Any]] = Field(default_factory=list)
    actual_tables_allowed: list[str] = Field(default_factory=list)
    actual_columns_allowed: list[str] = Field(default_factory=list)
    suggested_follow_up_questions: list[str] = Field(default_factory=list)
    generated_sql: str
    sql_validation_status: str
    sql_execution_status: str
    row_count: int
    result_preview: list[dict[str, Any]]
    related_tables: list[str]
    related_columns: list[dict[str, Any]]
    related_context: list[dict[str, Any]]
    models_used: list[dict[str, Any]]
    business_data_limitations: list[str] = Field(default_factory=list)
    context_limitations: list[str] = Field(default_factory=list)
    model_limitations: list[str] = Field(default_factory=list)
    technical_warnings: list[str] = Field(default_factory=list)
    missing_data_points: list[str]
    assumptions: list[str]
    limitations: list[str]
    confidence_score: float
    latency_ms: int
    provider_used: str
    model_used: str
    fallback_used: bool = False
    gemini_available: bool = True
    gemini_quota_exhausted: bool = False
    evidence_summary: dict[str, Any] = Field(default_factory=dict)


def ask_ai_insight_v11(request: AiInsightV11Request) -> AiInsightV11Response:
    started = perf_counter()
    role_code = normalize_role(request.role)
    engine_response = run_sql_engine(
        SqlEngineRequest(
            question=request.question,
            role_code=role_code,
            include_context=True,
            include_debug=True,
            row_limit=25,
            execute_sql=True,
        )
    )
    payload = engine_response.model_dump(mode="json")
    execution = payload.get("execution") or {}
    validation = payload.get("validation") or {}
    insight = payload.get("business_insight") or {}
    sql_metadata = payload.get("sql_metadata") or {}
    provider = payload.get("provider") or {}
    explainability = payload.get("explainability") or {}
    debug = payload.get("debug") or {}
    strict_sql_validation = payload.get("strict_sql_validation") or {}
    engine_result_validation = payload.get("result_validation") or {}
    sql_repair = payload.get("sql_repair")
    context_docs = flatten_related_context(payload.get("retrieved_context"))
    missing, business_data_limitations = infer_missing_data(request.question, payload)
    provider_used, model_used = provider_metadata(provider, debug)
    assumptions = list(sql_metadata.get("assumptions") or [])
    if missing and not assumptions:
        assumptions.append("I can partially answer this using the current internal insurance data.")
    rows = (execution.get("rows") or [])[:10]
    related_tables = list(sql_metadata.get("tables_used") or explainability.get("source_tables") or [])
    generated_sql = payload.get("sql") or ""
    related_columns = extract_related_columns(generated_sql)
    models_used = detect_models_used(
        question=request.question,
        sql=generated_sql,
        related_context=context_docs,
        raw_models=sql_metadata.get("models_used") or explainability.get("ml_models_used") or [],
    )
    if not context_docs:
        context_docs = fallback_semantic_context_documents(
            question=request.question,
            related_tables=related_tables,
            models_used=models_used,
        )
    context_limitations = infer_context_limitations(payload, context_docs)
    model_limitations = infer_model_limitations(request.question, models_used, related_tables)
    technical = technical_warning_flags(payload)
    key_data_points = extract_key_data_points(request.question, rows, related_tables)
    result_validation = validate_result_support(
        question=request.question,
        rows=rows,
        related_tables=related_tables,
        key_data_points=key_data_points,
        missing_data_points=missing,
        limitations=business_data_limitations + context_limitations + model_limitations,
    )
    if engine_result_validation.get("answer_status") == "NOT_SUPPORTED":
        result_validation = {
            **result_validation,
            **engine_result_validation,
            "validation_status": "NOT_SUPPORTED",
            "publish_allowed": False,
            "issues": dedupe(
                list(result_validation.get("issues") or [])
                + list(engine_result_validation.get("limitations") or [])
                + list(strict_sql_validation.get("errors") or [])
            ),
        }
    elif engine_result_validation:
        result_validation = {
            **result_validation,
            "engine_answer_status": engine_result_validation.get("answer_status"),
            "engine_result_quality_score": engine_result_validation.get("result_quality_score"),
        }
    if result_validation["validation_status"] == "FAIL":
        business_data_limitations = dedupe(business_data_limitations + result_validation["issues"])
    elif result_validation["validation_status"] == "PARTIAL":
        business_data_limitations = dedupe(business_data_limitations + result_validation["issues"])
    legacy_limitations = dedupe(business_data_limitations + context_limitations + model_limitations)

    return AiInsightV11Response(
        role=request.role,
        question=request.question,
        answer_summary=human_answer_summary(
            role=request.role,
            question=request.question,
            rows=rows,
            key_data_points=key_data_points,
            missing=missing,
            validation=result_validation,
        ),
        key_data_points=key_data_points,
        insights=build_human_insights(
            question=request.question,
            rows=rows,
            key_data_points=key_data_points,
            confidence=float(payload.get("confidence_score") or 0.0),
            validation=result_validation,
        ),
        recommendations=build_supported_recommendations(
            question=request.question,
            rows=rows,
            key_data_points=key_data_points,
            recommendations=payload.get("recommendations") or [],
            missing=missing,
            validation=result_validation,
        ),
        result_validation=result_validation,
        answer_status=str(payload.get("answer_status") or result_validation.get("validation_status") or "PENDING"),
        strict_sql_validation=strict_sql_validation,
        sql_repair=sql_repair,
        lifecycle=payload.get("lifecycle") or [],
        actual_tables_allowed=list(payload.get("actual_tables_allowed") or []),
        actual_columns_allowed=list(payload.get("actual_columns_allowed") or []),
        suggested_follow_up_questions=suggest_follow_ups(request.role, request.question, related_tables, result_validation),
        generated_sql=payload.get("sql") or "",
        sql_validation_status=strict_sql_validation.get("validation_status") or validation.get("safety_decision") or sql_metadata.get("validation_status") or "not_validated",
        sql_execution_status=execution.get("execution_status") or "not_executed",
        row_count=int(execution.get("row_count") or 0),
        result_preview=rows,
        related_tables=related_tables,
        related_columns=related_columns,
        related_context=context_docs,
        models_used=models_used,
        business_data_limitations=business_data_limitations,
        context_limitations=context_limitations,
        model_limitations=model_limitations,
        technical_warnings=technical["technical_warnings"],
        missing_data_points=missing,
        assumptions=assumptions,
        limitations=legacy_limitations,
        confidence_score=float(payload.get("confidence_score") or 0.0),
        latency_ms=int((perf_counter() - started) * 1000),
        provider_used=provider_used,
        model_used=model_used,
        fallback_used=bool(technical["fallback_used"]),
        gemini_available=bool(technical["gemini_available"]),
        gemini_quota_exhausted=bool(technical["gemini_quota_exhausted"]),
        evidence_summary={
            "tables_count": len(related_tables),
            "columns_count": len(related_columns),
            "context_count": len(context_docs),
            "models_count": len(models_used),
            "facts_count": len(key_data_points),
        },
    )


def normalize_role(role: str) -> str:
    return role.strip().lower().replace(" ", "_")


def answer_summary(summary: str | None, missing: list[str]) -> str:
    if missing:
        return f"I can partially answer this using the current data. {summary or 'The available internal data was queried and summarized.'}"
    return summary or "The available internal data was queried and summarized."


def human_answer_summary(
    *,
    role: str,
    question: str,
    rows: list[dict[str, Any]],
    key_data_points: list[dict[str, Any]],
    missing: list[str],
    validation: dict[str, Any],
) -> str:
    status = validation.get("validation_status")
    if status == "FAIL":
        return (
            "I cannot publish a supported insurance insight for this question from the current SQL result. "
            f"The main gap is: {', '.join(missing or validation.get('issues') or ['insufficient supporting rows'])}."
        )
    if not rows:
        return "The query ran safely, but no matching rows were returned for the selected scope."

    q = question.lower()
    first = rows[0]
    qualifier = "I can partially answer this using the current data. " if status == "PARTIAL" or missing else ""
    audience = role.replace("_", " ").strip()

    if "channel" in first and "conversion_rate" in first and "campaign_name" not in first:
        channel = str(first.get("channel") or "unknown channel")
        premium = money(first.get("conversion_premium"))
        conversions = count_text(first.get("conversions"))
        rate = pct(first.get("conversion_rate"))
        response_rate = pct(first.get("response_rate")) if "response_rate" in first else "not available"
        return (
            f"{qualifier}For {audience}, {channel} is the strongest campaign channel in the returned result. "
            f"It delivered {conversions} policy conversions, {premium} converted premium, a {rate} policy conversion rate, "
            f"and a {response_rate} response rate across {count_text(first.get('campaign_count'))} campaigns."
        )
    if "channel" in first and "conversion_rate" in first and "campaign_name" not in first:
        points.extend(
            [
                {"metric": "Top campaign channel", "value": str(first.get("channel")), "comparison": f"Aggregated across {count_text(first.get('campaign_count'))} campaigns", "source": source},
                {"metric": "Policy conversion rate", "value": pct(first.get("conversion_rate")), "comparison": f"{count_text(first.get('conversions'))} conversions from {count_text(first.get('targets'))} targets", "source": "campaign response conversion flag"},
                {"metric": "Response rate", "value": pct(first.get("response_rate")), "comparison": f"{count_text(first.get('responses'))} responses", "source": "campaign_responses and campaign_targets"},
                {"metric": "Converted premium", "value": money(first.get("conversion_premium")), "comparison": "Aggregated converted premium by channel", "source": "campaign_responses.conversion_premium"},
            ]
        )
    elif "campaign_name" in first:
        top = str(first.get("campaign_name"))
        channel = str(first.get("channel") or "unknown channel")
        premium = money(first.get("conversion_premium"))
        conversions = count_text(first.get("conversions"))
        rate = pct(first.get("conversion_rate"))
        if is_underperforming_campaign_question(q):
            response_rate = pct(first.get("response_rate")) if "response_rate" in first else "not available"
            return (
                f"{qualifier}For {audience}, the weakest campaign in the current result is {top} through {channel}. "
                f"It produced only {conversions} policy conversions, {premium} in converted premium, and a {rate} policy conversion rate. "
                f"The response rate is {response_rate}, so this should be reviewed as an underperforming campaign cohort rather than a growth campaign."
            )
        return (
            f"{qualifier}For {audience}, the strongest campaign result is {top} through {channel}. "
            f"It generated {premium} in converted premium from {conversions} conversions, with a policy conversion rate of {rate}. "
            "This is a campaign effectiveness view grounded in campaign target, response, and conversion records."
        )
    if "recommended_action" in first:
        action = str(first.get("recommended_action") or "review next best action")
        priority = pct(first.get("priority_score"))
        reason = str(first.get("business_reason") or first.get("suggested_message") or "ranked by next-best-action priority")
        return (
            f"{qualifier}The highest priority action is to {action.lower()}. "
            f"The top record has a priority score of {priority}. The supporting business reason is: {reason}."
        )
    if "agent_name" in first or "agent_number" in first or "branch_or_territory" in first:
        agent = str(first.get("agent_name") or first.get("agent_number") or first.get("branch_or_territory"))
        if "coaching_reason" in first:
            return (
                f"{qualifier}For {audience}, the top coaching candidate is {agent}. "
                f"The reason is {first.get('coaching_reason')}. Recent MAPA activity is {count_text(first.get('recent_mapa_activity'))}, "
                f"down by {count_text(abs(to_float(first.get('mapa_activity_change'))))} activities versus the prior period, with "
                f"{count_text(first.get('recent_policies_bound'))} recent policies bound and {money(first.get('recent_new_business_premium'))} new business premium."
            )
        if "premium_at_risk" in first:
            return (
                f"{qualifier}For {audience}, {agent} has the highest visible premium at risk in the result, with "
                f"{money(first.get('premium_at_risk'))} active annual premium across {count_text(first.get('policies_at_risk'))} policies. "
                f"The average lapse score is {pct(first.get('avg_lapse_score'))}, so this should be treated as a retention and coaching priority."
            )
        if "lapse_rate" in first and "branch_or_territory" in first:
            return (
                f"{qualifier}For {audience}, {first.get('branch_or_territory')} has the highest branch lapse exposure in the result, "
                f"with {money(first.get('lapsed_annual_premium'))} lapsed annual premium and a {pct(first.get('lapse_rate'))} lapse rate."
            )
        if "premium_lift" in first:
            return (
                f"{qualifier}For {audience}, {agent} shows the strongest post-movement improvement in the result. "
                f"Premium moved from {money(first.get('premium_before_move'))} before the move to {money(first.get('premium_after_move'))} after the move, "
                f"a lift of {money(first.get('premium_lift'))}."
            )
    if "claims_ratio" in first or "fraud_indicator_score" in first or ("claim_count" in first and ("claim" in q or "fraud" in q)):
        if "fraud_indicator_score" in first:
            return (
                f"{qualifier}For {audience}, claim {first.get('claim_number')} is the highest unresolved fraud-review item in the result. "
                f"It has a fraud indicator score of {pct(first.get('fraud_indicator_score'))}, severity {first.get('severity')}, "
                f"and incurred amount of {money(first.get('incurred_amount'))}."
            )
        if "claims_ratio" in first:
            return (
                f"{qualifier}For {audience}, {first.get('product_name')} has the highest claims pressure in the result. "
                f"The claims ratio is {pct(first.get('claims_ratio'))}, based on {money(first.get('incurred_amount'))} incurred claims "
                f"against {money(first.get('annual_premium'))} annual premium."
            )
        return (
            f"{qualifier}For {audience}, {first.get('branch_or_territory')} is the highest claims exposure row in the preview, "
            f"with {count_text(first.get('claim_count'))} claims and {money(first.get('incurred_amount'))} incurred amount in {first.get('report_month')}."
        )
    if "lapse_rate" in first:
        return (
            f"{qualifier}The current book lapse rate is {pct(first.get('lapse_rate'))}, based on "
            f"{count_text(first.get('lapsed_policies'))} lapsed policies out of {count_text(first.get('total_policies'))} total policies."
        )
    if "policy_number" in first:
        total_premium = sum_number(row.get("annual_premium") for row in rows)
        return (
            f"{qualifier}The Singapore policy view returned {len(rows)} recent policies in the preview, "
            f"with previewed annual premium of {money(total_premium)}. The first policy is {first.get('policy_number')} "
            f"for {first.get('product_name')} with annual premium {money(first.get('annual_premium'))}."
        )
    if "line_of_business" in first:
        top = str(first.get("line_of_business"))
        premium = money(first.get("annual_premium"))
        policies = count_text(first.get("policy_count"))
        if "market" in q:
            return (
                f"{qualifier}The platform does not contain external market share or competitor sales data. "
                f"Using internal policy and premium data instead, {top} is the largest visible line of business with "
                f"{policies} policies and {premium} annual premium in the result preview."
            )
        return (
            f"{qualifier}{top} is the largest visible line of business in the SQL result, with "
            f"{policies} policies and {premium} annual premium. This is an internal portfolio view, not an external market view."
        )

    if key_data_points:
        main = key_data_points[0]
        return f"{qualifier}The SQL result supports a directional answer: {main['metric']} is {main['value']} from {main['source']}."
    return f"{qualifier}The SQL ran successfully and returned {len(rows)} preview rows, but the result needs a more specific metric to form a stronger insurance insight."


def validate_result_support(
    *,
    question: str,
    rows: list[dict[str, Any]],
    related_tables: list[str],
    key_data_points: list[dict[str, Any]],
    missing_data_points: list[str],
    limitations: list[str],
) -> dict[str, Any]:
    q = question.lower()
    issues: list[str] = []
    unsupported: list[str] = []
    if not rows:
        return {
            "validation_status": "FAIL",
            "does_answer_question": False,
            "result_quality_score": 0.0,
            "issues": ["No SQL rows were returned for the requested business question."],
            "missing_data_points": missing_data_points or ["Matching source rows"],
            "unsupported_claims": ["No business conclusion can be supported without result rows."],
            "repair_required": False,
            "publish_allowed": False,
            "user_message_if_partial_or_fail": "No supported answer can be published for the current filters.",
        }

    first = rows[0]
    expected_shape = True
    if "campaign" in q and "campaign_name" not in first and not ("channel" in first and "conversion_rate" in first):
        expected_shape = False
        issues.append("Campaign question did not return campaign-level fields.")
    if "lapse rate" in q and "lapse_rate" not in first:
        expected_shape = False
        issues.append("Lapse-rate question did not return lapse numerator, denominator, and rate.")
    if "singapore" in q and "country_code" not in first:
        expected_shape = False
        issues.append("Singapore question did not return geography evidence.")
    if any(token in q for token in ["claim", "fraud"]) and not any("claim" in key or "fraud" in key for key in first):
        expected_shape = False
        issues.append("Claims or fraud question returned an internal portfolio proxy rather than claim-level evidence.")
    if any(token in q for token in ["agent", "mapa", "coaching", "branch"]) and not any("agent" in key or "mapa" in key or "branch" in key for key in first):
        expected_shape = False
        issues.append("Agent performance question returned a portfolio proxy rather than agent-level productivity evidence.")
    if any(token in q for token in ["market", "competitor"]):
        expected_shape = False
        issues.append("External market or competitor data is not available in the current database.")
    if any(token in q for token in ["propensity", "cross-sell", "clv", "churn"]) and not any(
        token in key for key in first for token in ["score", "clv", "customer", "recommended"]
    ):
        expected_shape = False
        issues.append("Model-score or customer-level evidence is limited for this question.")

    if not expected_shape and "line_of_business" in first and any(token in q for token in ["agent", "mapa", "coaching", "branch", "claim", "fraud", "customer", "propensity", "cross-sell", "clv", "churn"]):
        return {
            "validation_status": "FAIL",
            "does_answer_question": False,
            "result_quality_score": 0.0,
            "issues": dedupe(issues + ["The SQL result is a generic product-line portfolio proxy and must not be used to answer this question."]),
            "missing_data_points": missing_data_points,
            "unsupported_claims": ["Blocked a misleading portfolio answer for a role-specific business question."],
            "repair_required": True,
            "publish_allowed": False,
            "user_message_if_partial_or_fail": "The generated SQL did not match the question. No insight was published.",
            "tables_checked": related_tables,
        }

    status = "PASS" if expected_shape and key_data_points else "PARTIAL"
    if not key_data_points:
        issues.append("The result returned rows but no numeric business metric could be extracted.")
    if limitations:
        issues.extend(limitations)
    if status == "PARTIAL":
        unsupported.append("Do not claim a complete answer beyond the displayed SQL result and available internal data.")

    return {
        "validation_status": status,
        "does_answer_question": status == "PASS",
        "result_quality_score": 0.9 if status == "PASS" else 0.58,
        "issues": dedupe(issues),
        "missing_data_points": missing_data_points,
        "unsupported_claims": unsupported,
        "repair_required": False,
        "publish_allowed": True,
        "user_message_if_partial_or_fail": "This is a partial answer grounded in the available SQL result." if status == "PARTIAL" else "",
        "tables_checked": related_tables,
    }


def extract_key_data_points(question: str, rows: list[dict[str, Any]], related_tables: list[str]) -> list[dict[str, Any]]:
    if not rows:
        return []
    first = rows[0]
    source = ", ".join(related_tables[:3]) or "SQL result preview"
    points: list[dict[str, Any]] = []
    if "channel" in first and "conversion_rate" in first and "campaign_name" not in first:
        points.extend(
            [
                {"metric": "Top campaign channel", "value": str(first.get("channel")), "comparison": f"Aggregated across {count_text(first.get('campaign_count'))} campaigns", "source": source},
                {"metric": "Policy conversion rate", "value": pct(first.get("conversion_rate")), "comparison": f"{count_text(first.get('conversions'))} conversions from {count_text(first.get('targets'))} targets", "source": "campaign response conversion flag"},
                {"metric": "Response rate", "value": pct(first.get("response_rate")), "comparison": f"{count_text(first.get('responses'))} responses", "source": "campaign_responses and campaign_targets"},
                {"metric": "Converted premium", "value": money(first.get("conversion_premium")), "comparison": "Aggregated converted premium by channel", "source": "campaign_responses.conversion_premium"},
            ]
        )
    elif "campaign_name" in first:
        underperforming = is_underperforming_campaign_question(question.lower())
        points.extend(
            [
                {"metric": "Weakest campaign" if underperforming else "Top campaign", "value": str(first.get("campaign_name")), "comparison": f"Ranked first among {len(rows)} previewed campaign rows", "source": source},
                {"metric": "Converted premium", "value": money(first.get("conversion_premium")), "comparison": "Sorted by low converted premium and conversion rate" if underperforming else "Sorted by converted premium descending", "source": "campaign_responses.conversion_premium"},
                {"metric": "Policy conversions", "value": count_text(first.get("conversions")), "comparison": f"{count_text(first.get('responses'))} responses from {count_text(first.get('targets'))} targets", "source": "campaign_targets and campaign_responses"},
                {"metric": "Policy conversion rate", "value": pct(first.get("conversion_rate")), "comparison": f"Channel: {first.get('channel')}", "source": "campaign response conversion flag"},
            ]
        )
        if "response_rate" in first:
            points.append({"metric": "Response rate", "value": pct(first.get("response_rate")), "comparison": "Responses divided by targets", "source": "campaign_responses and campaign_targets"})
    elif "recommended_action" in first:
        points.extend(
            [
                {"metric": "Recommended action", "value": str(first.get("recommended_action")), "comparison": "Highest ranked open action in result", "source": "next_best_actions.recommended_action"},
                {"metric": "Priority score", "value": pct(first.get("priority_score")), "comparison": "Sorted by priority score", "source": "next_best_actions.priority_score"},
                {"metric": "Confidence score", "value": pct(first.get("confidence_score")), "comparison": "Model or rule confidence for action", "source": "next_best_actions.confidence_score"},
            ]
        )
    elif "lapse_rate" in first:
        points.extend(
            [
                {"metric": "Lapse rate", "value": pct(first.get("lapse_rate")), "comparison": f"{count_text(first.get('lapsed_policies'))} lapsed out of {count_text(first.get('total_policies'))} policies", "source": "policies.policy_status"},
                {"metric": "Lapsed policies", "value": count_text(first.get("lapsed_policies")), "comparison": "Current policy-status count", "source": "policies"},
                {"metric": "Total policies", "value": count_text(first.get("total_policies")), "comparison": "Current policy book count", "source": "policies"},
            ]
        )
    elif "claims_ratio" in first or "fraud_indicator_score" in first or ("claim_count" in first and any("claim" in key for key in first)):
        if "fraud_indicator_score" in first:
            points.extend(
                [
                    {"metric": "Claim for review", "value": str(first.get("claim_number")), "comparison": f"Severity: {first.get('severity')}", "source": "claim_fraud_indicators"},
                    {"metric": "Fraud indicator score", "value": pct(first.get("fraud_indicator_score")), "comparison": str(first.get("indicator_type")), "source": "claim_fraud_indicators.indicator_score"},
                    {"metric": "Incurred amount", "value": money(first.get("incurred_amount")), "comparison": f"Status: {first.get('claim_status')}", "source": "claims.incurred_amount"},
                ]
            )
        elif "claims_ratio" in first:
            points.extend(
                [
                    {"metric": "Product", "value": str(first.get("product_name")), "comparison": str(first.get("line_of_business")), "source": source},
                    {"metric": "Claims ratio", "value": pct(first.get("claims_ratio")), "comparison": f"{count_text(first.get('claim_count'))} claims", "source": "claims.incurred_amount / policies.annual_premium"},
                    {"metric": "Incurred amount", "value": money(first.get("incurred_amount")), "comparison": f"Annual premium: {money(first.get('annual_premium'))}", "source": "claims and policies"},
                ]
            )
        else:
            points.extend(
                [
                    {"metric": "Branch or territory", "value": str(first.get("branch_or_territory")), "comparison": f"Report month: {first.get('report_month')}", "source": source},
                    {"metric": "Claim count", "value": count_text(first.get("claim_count")), "comparison": "Claims reported in month", "source": "claims.claim_id"},
                    {"metric": "Incurred amount", "value": money(first.get("incurred_amount")), "comparison": f"Average incurred: {money(first.get('avg_incurred_amount'))}", "source": "claims.incurred_amount"},
                ]
            )
    elif "agent_name" in first or "agent_number" in first or "branch_or_territory" in first:
        if "coaching_reason" in first:
            points.extend(
                [
                    {"metric": "Agent needing coaching", "value": str(first.get("agent_name") or first.get("agent_number")), "comparison": str(first.get("coaching_reason")), "source": source},
                    {"metric": "Recent MAPA activity", "value": count_text(first.get("recent_mapa_activity")), "comparison": f"Prior activity: {count_text(first.get('prior_mapa_activity'))}", "source": "agent_mapa_metrics"},
                    {"metric": "MAPA activity change", "value": count_text(first.get("mapa_activity_change")), "comparison": "Recent 3 months minus prior 3 months", "source": "agent_mapa_metrics"},
                    {"metric": "Recent new business premium", "value": money(first.get("recent_new_business_premium")), "comparison": f"{count_text(first.get('recent_policies_bound'))} recent policies bound", "source": "agent_mapa_metrics"},
                ]
            )
        elif "premium_at_risk" in first:
            points.extend(
                [
                    {"metric": "Agent", "value": str(first.get("agent_name") or first.get("agent_number")), "comparison": f"Territory: {first.get('branch_or_territory')}", "source": source},
                    {"metric": "Premium at risk", "value": money(first.get("premium_at_risk")), "comparison": f"{count_text(first.get('policies_at_risk'))} policies at risk", "source": "policies.annual_premium"},
                    {"metric": "Average lapse score", "value": pct(first.get("avg_lapse_score")), "comparison": f"{count_text(first.get('high_risk_policy_count'))} high-risk policies", "source": "model_scores"},
                ]
            )
        elif "lapsed_annual_premium" in first:
            points.extend(
                [
                    {"metric": "Branch or territory", "value": str(first.get("branch_or_territory")), "comparison": "Ranked by lapsed premium exposure", "source": source},
                    {"metric": "Lapsed annual premium", "value": money(first.get("lapsed_annual_premium")), "comparison": f"{count_text(first.get('lapsed_policies'))} lapsed policies", "source": "policies"},
                    {"metric": "Lapse rate", "value": pct(first.get("lapse_rate")), "comparison": f"{count_text(first.get('total_policies'))} total policies", "source": "policies.policy_status"},
                ]
            )
        elif "premium_lift" in first:
            points.extend(
                [
                    {"metric": "Agent with movement", "value": str(first.get("agent_name") or first.get("agent_number")), "comparison": f"{first.get('from_territory_code')} to {first.get('to_territory_code')}", "source": "agent_movements"},
                    {"metric": "Premium lift", "value": money(first.get("premium_lift")), "comparison": f"Before {money(first.get('premium_before_move'))}, after {money(first.get('premium_after_move'))}", "source": "agent_mapa_metrics"},
                    {"metric": "Policies after move", "value": count_text(first.get("policies_after_move")), "comparison": f"Before move: {count_text(first.get('policies_before_move'))}", "source": "agent_mapa_metrics"},
                ]
            )
    elif "policy_number" in first:
        points.extend(
            [
                {"metric": "Previewed policies", "value": count_text(len(rows)), "comparison": "First 10 rows from SQL result", "source": source},
                {"metric": "Previewed annual premium", "value": money(sum_number(row.get("annual_premium") for row in rows)), "comparison": "Sum of previewed annual premiums", "source": "policies.annual_premium"},
                {"metric": "First product", "value": str(first.get("product_name")), "comparison": f"Policy {first.get('policy_number')}", "source": "products.product_name"},
            ]
        )
    elif "line_of_business" in first:
        points.extend(
            [
                {"metric": "Top line of business", "value": str(first.get("line_of_business")), "comparison": f"Ranked first among {len(rows)} preview rows", "source": "products.line_of_business"},
                {"metric": "Policy count", "value": count_text(first.get("policy_count")), "comparison": "Policies grouped by line of business", "source": "policies.policy_id"},
                {"metric": "Annual premium", "value": money(first.get("annual_premium")), "comparison": "Sum of annual premium for line of business", "source": "policies.annual_premium"},
            ]
        )
    else:
        for key, value in first.items():
            if len(points) >= 4:
                break
            if is_number_like(value):
                points.append({"metric": key.replace("_", " ").title(), "value": compact_number(value), "comparison": "Top row value", "source": source})
    return points[:6]


def build_human_insights(
    *,
    question: str,
    rows: list[dict[str, Any]],
    key_data_points: list[dict[str, Any]],
    confidence: float,
    validation: dict[str, Any],
) -> list[dict[str, Any]]:
    if validation.get("validation_status") == "FAIL":
        return []
    if not rows:
        return []
    first = rows[0]
    points = [point["value"] for point in key_data_points[:3]]
    data_refs = [f"{point['metric']}: {point['value']}" for point in key_data_points[:4]]
    insights: list[dict[str, Any]] = []

    if "channel" in first and "conversion_rate" in first and "campaign_name" not in first:
        insights.append(
            {
                "title": "Campaign channel performance is measurable",
                "description": (
                    f"{first.get('channel')} leads the returned channel view with a {pct(first.get('conversion_rate'))} policy conversion rate, "
                    f"{count_text(first.get('conversions'))} conversions, and {money(first.get('conversion_premium'))} converted premium."
                ),
                "data_points_used": data_refs,
                "business_impact": "Channel budget allocation, follow-up capacity, and campaign design",
                "confidence_score": confidence,
            }
        )
        if len(rows) > 1:
            second = rows[1]
            insights.append(
                {
                    "title": "Compare the leading channel against the next channel",
                    "description": (
                        f"The next channel is {second.get('channel')} with a {pct(second.get('conversion_rate'))} conversion rate and "
                        f"{money(second.get('conversion_premium'))} converted premium."
                    ),
                    "data_points_used": [f"Top channel: {first.get('channel')}", f"Second channel: {second.get('channel')}"],
                    "business_impact": "Separates channel signal from individual campaign-wave noise",
                    "confidence_score": max(0.0, confidence - 0.04),
                }
            )
    elif "campaign_name" in first:
        underperforming = is_underperforming_campaign_question(question.lower())
        if underperforming:
            insights.append(
                {
                    "title": "Campaign underperformance is visible in conversion output",
                    "description": (
                        f"{first.get('campaign_name')} appears weakest in the preview with {count_text(first.get('conversions'))} conversions, "
                        f"{money(first.get('conversion_premium'))} converted premium, and a {pct(first.get('conversion_rate'))} conversion rate."
                    ),
                    "data_points_used": data_refs,
                    "business_impact": "Campaign suppression, message redesign, and lead follow-up triage",
                    "confidence_score": confidence,
                }
            )
            if len(rows) > 1:
                second = rows[1]
                insights.append(
                    {
                        "title": "Use the second weak campaign as a benchmark",
                        "description": (
                            f"The next weak row is {second.get('campaign_name')} with {count_text(second.get('conversions'))} conversions "
                            f"and {money(second.get('conversion_premium'))} converted premium. Comparing these rows helps decide whether the issue is offer, channel, or audience."
                        ),
                        "data_points_used": [f"Weakest row: {first.get('campaign_name')}", f"Next weak row: {second.get('campaign_name')}"],
                        "business_impact": "Campaign remediation and budget reallocation",
                        "confidence_score": max(0.0, confidence - 0.04),
                    }
                )
            return insights[:5]
        insights.append(
            {
                "title": "Campaign conversion is concentrated in a clear winning offer",
                "description": (
                    f"{first.get('campaign_name')} is leading the preview with {money(first.get('conversion_premium'))} converted premium, "
                    f"{count_text(first.get('conversions'))} conversions, and a {pct(first.get('conversion_rate'))} conversion rate."
                ),
                "data_points_used": data_refs,
                "business_impact": "Campaign ROI, lead prioritization, and agent follow-up planning",
                "confidence_score": confidence,
            }
        )
        if len(rows) > 1:
            second = rows[1]
            insights.append(
                {
                    "title": "The top campaign should be compared with the next best wave",
                    "description": (
                        f"The second preview row is {second.get('campaign_name')} with {money(second.get('conversion_premium'))} converted premium. "
                        "This gives campaign managers a practical benchmark before shifting budget or follow-up capacity."
                    ),
                    "data_points_used": [f"Top row: {points[0] if points else first.get('campaign_name')}", f"Second row premium: {money(second.get('conversion_premium'))}"],
                    "business_impact": "Budget allocation and response-to-policy conversion discipline",
                    "confidence_score": max(0.0, confidence - 0.04),
                }
            )
    elif "recommended_action" in first:
        insights.append(
            {
                "title": "The action queue has a measurable priority leader",
                "description": (
                    f"The top next action is {first.get('recommended_action')} with priority {pct(first.get('priority_score'))}. "
                    f"The reason captured in the database is: {first.get('business_reason') or first.get('suggested_message') or 'not supplied'}."
                ),
                "data_points_used": data_refs,
                "business_impact": "Agent focus, retention handling, and cross-sell execution",
                "confidence_score": confidence,
            }
        )
    elif "lapse_rate" in first:
        insights.append(
            {
                "title": "Book lapse can be quantified directly from policy status",
                "description": (
                    f"The SQL result shows {count_text(first.get('lapsed_policies'))} lapsed policies out of "
                    f"{count_text(first.get('total_policies'))}, giving a current lapse rate of {pct(first.get('lapse_rate'))}."
                ),
                "data_points_used": data_refs,
                "business_impact": "Persistency, premium protection, and retention workload sizing",
                "confidence_score": confidence,
            }
        )
    elif "agent_name" in first or "agent_number" in first or "branch_or_territory" in first:
        agent = str(first.get("agent_name") or first.get("agent_number") or first.get("branch_or_territory"))
        if "coaching_reason" in first:
            insights.append(
                {
                    "title": "Coaching priority is grounded in MAPA and conversion evidence",
                    "description": (
                        f"{agent} is the top coaching candidate because {first.get('coaching_reason')}. "
                        f"Recent MAPA activity is {count_text(first.get('recent_mapa_activity'))} versus {count_text(first.get('prior_mapa_activity'))} in the prior period, "
                        f"with {count_text(first.get('recent_policies_bound'))} policies bound."
                    ),
                    "data_points_used": data_refs,
                    "business_impact": "Distribution productivity and manager coaching focus",
                    "confidence_score": confidence,
                }
            )
        elif "premium_at_risk" in first:
            insights.append(
                {
                    "title": "Premium-at-risk is concentrated by agent",
                    "description": (
                        f"{agent} has {money(first.get('premium_at_risk'))} active annual premium at risk across "
                        f"{count_text(first.get('policies_at_risk'))} policies, with an average lapse score of {pct(first.get('avg_lapse_score'))}."
                    ),
                    "data_points_used": data_refs,
                    "business_impact": "Retention workload and agent prioritization",
                    "confidence_score": confidence,
                }
            )
        elif "lapsed_annual_premium" in first:
            insights.append(
                {
                    "title": "Branch lapse exposure is measurable",
                    "description": (
                        f"{first.get('branch_or_territory')} has {money(first.get('lapsed_annual_premium'))} lapsed annual premium "
                        f"and a {pct(first.get('lapse_rate'))} lapse rate in the returned policy book."
                    ),
                    "data_points_used": data_refs,
                    "business_impact": "Branch-level persistency management",
                    "confidence_score": confidence,
                }
            )
        elif "premium_lift" in first:
            insights.append(
                {
                    "title": "Agent movement impact can be compared before and after transfer",
                    "description": (
                        f"{agent} shows {money(first.get('premium_lift'))} premium lift after movement, "
                        f"from {money(first.get('premium_before_move'))} before to {money(first.get('premium_after_move'))} after."
                    ),
                    "data_points_used": data_refs,
                    "business_impact": "Territory design and talent mobility decisions",
                    "confidence_score": confidence,
                }
            )
    elif "claims_ratio" in first or "fraud_indicator_score" in first or ("claim_count" in first and any("claim" in key for key in first)):
        if "fraud_indicator_score" in first:
            insights.append(
                {
                    "title": "Fraud review is backed by unresolved indicator evidence",
                    "description": (
                        f"Claim {first.get('claim_number')} has the highest unresolved fraud indicator score at {pct(first.get('fraud_indicator_score'))}, "
                        f"with {money(first.get('incurred_amount'))} incurred amount."
                    ),
                    "data_points_used": data_refs,
                    "business_impact": "Claims leakage control and manual review prioritization",
                    "confidence_score": confidence,
                }
            )
        elif "claims_ratio" in first:
            insights.append(
                {
                    "title": "Product claims pressure is visible in incurred-to-premium ratio",
                    "description": (
                        f"{first.get('product_name')} has a {pct(first.get('claims_ratio'))} claims ratio, "
                        f"with {money(first.get('incurred_amount'))} incurred claims against {money(first.get('annual_premium'))} annual premium."
                    ),
                    "data_points_used": data_refs,
                    "business_impact": "Claims cost, product profitability, and underwriting review",
                    "confidence_score": confidence,
                }
            )
        else:
            insights.append(
                {
                    "title": "Claims exposure can be monitored by territory and month",
                    "description": (
                        f"{first.get('branch_or_territory')} has {count_text(first.get('claim_count'))} claims and "
                        f"{money(first.get('incurred_amount'))} incurred amount for {first.get('report_month')}."
                    ),
                    "data_points_used": data_refs,
                    "business_impact": "Regional claims monitoring and operational triage",
                    "confidence_score": confidence,
                }
            )
    elif "line_of_business" in first:
        insights.append(
            {
                "title": "Internal portfolio concentration is visible by product line",
                "description": (
                    f"{first.get('line_of_business')} leads the returned portfolio view with {count_text(first.get('policy_count'))} policies "
                    f"and {money(first.get('annual_premium'))} annual premium."
                ),
                "data_points_used": data_refs,
                "business_impact": "Product mix, growth focus, and premium concentration",
                "confidence_score": confidence,
            }
        )
    else:
        insights.append(
            {
                "title": "SQL result contains usable business evidence",
                "description": f"The result returned {len(rows)} preview rows. Key extracted data points are: {', '.join(data_refs[:3])}.",
                "data_points_used": data_refs,
                "business_impact": "Analyst review and follow-up segmentation",
                "confidence_score": confidence,
            }
        )

    if validation.get("validation_status") == "PARTIAL":
        insights.append(
            {
                "title": "Answer is partial and should not be over-read",
                "description": "The result is useful as an internal directional view, but the validation layer found gaps for the exact question.",
                "data_points_used": validation.get("issues", [])[:3],
                "business_impact": "Prevents unsupported recommendations and keeps the decision audit trail honest",
                "confidence_score": min(confidence, 0.62),
            }
        )
    return insights[:5]


def build_supported_recommendations(
    *,
    question: str,
    rows: list[dict[str, Any]],
    key_data_points: list[dict[str, Any]],
    recommendations: list[dict[str, Any]],
    missing: list[str],
    validation: dict[str, Any],
) -> list[dict[str, Any]]:
    if validation.get("validation_status") == "FAIL":
        return []
    first = rows[0] if rows else {}
    data_refs = [f"{point['metric']}: {point['value']}" for point in key_data_points[:4]]

    if "channel" in first and "conversion_rate" in first and "campaign_name" not in first:
        return [
            {
                "title": "Prioritize the strongest campaign channel",
                "recommended_action": f"Use {first.get('channel')} as the primary follow-up channel for similar campaign audiences.",
                "rationale": f"The channel shows a {pct(first.get('conversion_rate'))} policy conversion rate and {money(first.get('conversion_premium'))} converted premium.",
                "data_points_used": data_refs,
                "expected_impact": "Improve campaign conversion by aligning follow-up capacity to the best-performing medium.",
                "confidence_score": 0.8 if validation.get("validation_status") == "PASS" else 0.58,
            }
        ]
    if "campaign_name" in first:
        if is_underperforming_campaign_question(question.lower()):
            return [
                {
                    "title": "Diagnose or suppress the weakest campaign cohort",
                    "recommended_action": f"Review {first.get('campaign_name')} before adding more budget or follow-up capacity.",
                    "rationale": f"The campaign shows only {count_text(first.get('conversions'))} conversions, {money(first.get('conversion_premium'))} converted premium, and a {pct(first.get('conversion_rate'))} conversion rate.",
                    "data_points_used": data_refs,
                    "expected_impact": "Reduce wasted campaign spend and redirect effort toward better converting cohorts.",
                    "confidence_score": 0.8 if validation.get("validation_status") == "PASS" else 0.58,
                }
            ]
        return [
            {
                "title": "Act on the highest converting campaign cohort",
                "recommended_action": f"Prioritize follow-up for responders from {first.get('campaign_name')} through {first.get('channel')}.",
                "rationale": f"The top campaign generated {money(first.get('conversion_premium'))} converted premium and {count_text(first.get('conversions'))} policy conversions.",
                "data_points_used": data_refs,
                "expected_impact": "Improve policy conversion while the campaign signal is fresh.",
                "confidence_score": 0.82 if validation.get("validation_status") == "PASS" else 0.6,
            }
        ]
    if "recommended_action" in first:
        return [
            {
                "title": "Work the top ranked customer action first",
                "recommended_action": str(first.get("recommended_action")),
                "rationale": str(first.get("business_reason") or first.get("suggested_message") or "The action is ranked highest by priority score."),
                "data_points_used": data_refs,
                "expected_impact": "Improve agent productivity by focusing on the highest value or highest risk action.",
                "confidence_score": to_float(first.get("confidence_score"), 0.72),
            }
        ]
    if "lapse_rate" in first:
        return [
            {
                "title": "Use lapse rate as a retention workload trigger",
                "recommended_action": "Drill into high-premium policies and missed-payment cohorts before launching retention calls.",
                "rationale": f"The current lapse rate is {pct(first.get('lapse_rate'))} across {count_text(first.get('total_policies'))} policies.",
                "data_points_used": data_refs,
                "expected_impact": "Protect renewal premium and reduce preventable lapses.",
                "confidence_score": 0.78 if validation.get("validation_status") == "PASS" else 0.58,
            }
        ]
    if "agent_name" in first or "agent_number" in first or "branch_or_territory" in first:
        agent = str(first.get("agent_name") or first.get("agent_number") or first.get("branch_or_territory"))
        if "coaching_reason" in first:
            return [
                {
                    "title": "Schedule targeted coaching",
                    "recommended_action": f"Coach {agent} on the specific productivity gap: {first.get('coaching_reason')}.",
                    "rationale": f"Recent MAPA activity is {count_text(first.get('recent_mapa_activity'))} versus {count_text(first.get('prior_mapa_activity'))} in the prior period.",
                    "data_points_used": data_refs,
                    "expected_impact": "Improve meeting-to-application and application-to-policy conversion.",
                    "confidence_score": 0.78 if validation.get("validation_status") == "PASS" else 0.58,
                }
            ]
        if "premium_at_risk" in first:
            return [
                {
                    "title": "Prioritize retention support for the agent book",
                    "recommended_action": f"Ask the manager to review {agent}'s highest-premium policies at risk.",
                    "rationale": f"The agent has {money(first.get('premium_at_risk'))} premium at risk across {count_text(first.get('policies_at_risk'))} active policies.",
                    "data_points_used": data_refs,
                    "expected_impact": "Protect renewal premium and reduce preventable lapse.",
                    "confidence_score": 0.76 if validation.get("validation_status") == "PASS" else 0.58,
                }
            ]
        if "lapsed_annual_premium" in first:
            return [
                {
                    "title": "Focus branch persistency review",
                    "recommended_action": f"Review lapse drivers in {first.get('branch_or_territory')} with agency managers.",
                    "rationale": f"The branch has {money(first.get('lapsed_annual_premium'))} lapsed annual premium and a {pct(first.get('lapse_rate'))} lapse rate.",
                    "data_points_used": data_refs,
                    "expected_impact": "Improve branch persistency and retention action planning.",
                    "confidence_score": 0.74,
                }
            ]
        if "premium_lift" in first:
            return [
                {
                    "title": "Replicate successful movement patterns",
                    "recommended_action": f"Review why {agent}'s movement produced premium lift and apply lessons to territory planning.",
                    "rationale": f"Premium increased by {money(first.get('premium_lift'))} after movement.",
                    "data_points_used": data_refs,
                    "expected_impact": "Improve territory design and agent deployment decisions.",
                    "confidence_score": 0.72,
                }
            ]
    if "claims_ratio" in first or "fraud_indicator_score" in first or ("claim_count" in first and any("claim" in key for key in first)):
        if "fraud_indicator_score" in first:
            return [
                {
                    "title": "Send high-risk claim for manual review",
                    "recommended_action": f"Review claim {first.get('claim_number')} before final settlement action.",
                    "rationale": f"The unresolved fraud indicator score is {pct(first.get('fraud_indicator_score'))} with {money(first.get('incurred_amount'))} incurred amount.",
                    "data_points_used": data_refs,
                    "expected_impact": "Improve claims governance and reduce leakage.",
                    "confidence_score": 0.78,
                }
            ]
        if "claims_ratio" in first:
            return [
                {
                    "title": "Review product claims economics",
                    "recommended_action": f"Ask claims and product teams to review {first.get('product_name')} claim drivers.",
                    "rationale": f"The product shows a {pct(first.get('claims_ratio'))} claims ratio and {money(first.get('incurred_amount'))} incurred amount.",
                    "data_points_used": data_refs,
                    "expected_impact": "Identify underwriting, pricing, or claims handling actions.",
                    "confidence_score": 0.74,
                }
            ]
        return [
            {
                "title": "Investigate territory claims concentration",
                "recommended_action": f"Review claims drivers for {first.get('branch_or_territory')} in {first.get('report_month')}.",
                "rationale": f"The territory shows {count_text(first.get('claim_count'))} claims and {money(first.get('incurred_amount'))} incurred amount.",
                "data_points_used": data_refs,
                "expected_impact": "Prioritize regional claims monitoring and operational support.",
                "confidence_score": 0.72,
            }
        ]
    if "line_of_business" in first and validation.get("validation_status") != "FAIL":
        return [
            {
                "title": "Use this as an internal portfolio diagnostic",
                "recommended_action": f"Review {first.get('line_of_business')} premium concentration and compare it with lapse, campaign, and new-business trends.",
                "rationale": f"The returned internal view shows {money(first.get('annual_premium'))} annual premium and {count_text(first.get('policy_count'))} policies.",
                "data_points_used": data_refs,
                "expected_impact": "Clarifies whether the business issue is product mix, persistency, or campaign demand.",
                "confidence_score": 0.62,
            }
        ]

    supported = [
        {
            "title": str(item.get("recommendation") or "Review generated insight"),
            "recommended_action": str(item.get("recommendation") or "Review generated insight"),
            "rationale": str(item.get("reason") or "Recommendation generated from the SQL result and retrieved context."),
            "data_points_used": data_refs,
            "expected_impact": "Improve decision quality using SQL-backed evidence.",
            "confidence_score": float(item.get("priority_score") or 0.6),
        }
        for item in recommendations[:3]
    ]
    if missing:
        supported.append(
            {
                "title": "Improve data coverage before a high-stakes decision",
                "recommended_action": "Add or refresh the missing data points shown in the limitations panel.",
                "rationale": "The validation layer found a data gap, so recommendations should be treated as directional.",
                "data_points_used": missing,
                "expected_impact": "Higher confidence and stronger auditability.",
                "confidence_score": 0.52,
            }
        )
    return supported


def suggest_follow_ups(role: str, question: str, related_tables: list[str], validation: dict[str, Any]) -> list[str]:
    q = question.lower()
    if "campaign" in q:
        if is_underperforming_campaign_question(q):
            return [
                "Which low-performing campaign has high engagement but poor conversion?",
                "Which customer segment is dragging down this campaign?",
                "Should this campaign be suppressed, redesigned, or reassigned to agents?",
            ]
        return [
            "Which customer segments converted best within this campaign?",
            "Which agents followed up fastest after campaign response?",
            "What is campaign conversion premium by product and channel?",
        ]
    if "lapse" in q:
        return [
            "Which products have the highest premium at risk from lapse?",
            "Which customers with missed payments need retention calls this week?",
            "What is lapse risk by tenure and premium band?",
        ]
    if "agent" in q or "mapa" in q:
        return [
            "Which agents have declining MAPA but high customer potential?",
            "Which peer cluster should this agent be compared with?",
            "Which agents need coaching by product line?",
        ]
    if validation.get("validation_status") == "PARTIAL":
        return [
            "Which additional data would make this answer complete?",
            f"Show the same question limited to tables {', '.join(related_tables[:3])}.",
            "What SQL evidence supports the current partial answer?",
        ]
    return [
        f"What should a {role} do next based on this result?",
        "Which customer, policy, product, or agent segment explains this result?",
        "Show the same result as a monthly trend.",
    ]


def build_insights(insight: dict[str, Any], execution: dict[str, Any], confidence: float) -> list[dict[str, Any]]:
    observations = insight.get("key_observations") or []
    rows = execution.get("rows") or []
    if not observations and rows:
        observations = [f"The query returned {len(rows)} rows from live Supabase data."]
    if not observations:
        observations = ["The query completed, but no strong row-level signal was returned for the selected question."]
    return [
        {
            "title": f"Insight {index + 1}",
            "description": str(item),
            "business_impact": impact_from_observation(str(item)),
            "confidence_score": confidence,
        }
        for index, item in enumerate(observations[:5])
    ]


def build_recommendations(recommendations: list[dict[str, Any]], missing: list[str]) -> list[dict[str, Any]]:
    rows = [
        {
            "title": str(item.get("recommendation") or "Review generated insight"),
            "recommended_action": str(item.get("recommendation") or "Review generated insight"),
            "rationale": str(item.get("reason") or "Recommendation generated from the SQL result and retrieved context."),
            "expected_impact": "Improve decision quality using SQL-backed evidence.",
            "confidence_score": float(item.get("priority_score") or 0.6),
        }
        for item in recommendations[:5]
    ]
    if missing:
        rows.append(
            {
                "title": "Improve data coverage",
                "recommended_action": "Add missing data points before using this answer for production decisions.",
                "rationale": "The platform can answer partially, but the missing data limits confidence.",
                "expected_impact": "Higher confidence and more complete business interpretation.",
                "confidence_score": 0.55,
            }
        )
    return rows or [
        {
            "title": "Review result preview",
            "recommended_action": "Use the SQL result preview to decide the next drill-down.",
            "rationale": "No prescriptive recommendation was returned by the current result.",
            "expected_impact": "Focus follow-up analysis on the highest signal rows.",
            "confidence_score": 0.6,
        }
    ]


def flatten_related_context(context: Any) -> list[dict[str, Any]]:
    docs: list[dict[str, Any]] = []
    if not isinstance(context, dict):
        return docs
    for bucket in ["business_context", "schema_context", "metric_context", "model_context", "sql_examples"]:
        values = context.get(bucket)
        if not isinstance(values, list):
            continue
        for item in values:
            if not isinstance(item, dict):
                continue
            score = item.get("score")
            relevance = score.get("hybrid") if isinstance(score, dict) else item.get("score")
            docs.append(
                {
                    "title": item.get("title") or item.get("document_type") or "Context document",
                    "document_type": item.get("document_type") or bucket,
                    "business_domain": item.get("business_domain"),
                    "relevance_score": float(relevance or 0.0),
                    "related_tables": item.get("related_tables") or [],
                    "related_models": item.get("related_models") or [],
                    "related_metrics": item.get("related_metrics") or [],
                    "reason_retrieved": reason_for_context_item(item, bucket),
                    "content": item.get("content") or item.get("snippet") or item.get("business_definition") or "",
                }
            )
    return docs[:10]


def reason_for_context_item(item: dict[str, Any], bucket: str) -> str:
    title = str(item.get("title") or item.get("document_type") or "context")
    if bucket == "model_context" or item.get("related_models"):
        return f"Retrieved because the question or SQL may need model interpretation for {title}."
    if bucket == "metric_context" or item.get("related_metrics"):
        return f"Retrieved because the answer uses metric definitions connected to {title}."
    if item.get("related_tables"):
        return f"Retrieved because it describes tables used by the generated SQL."
    return f"Retrieved as {bucket.replace('_', ' ')} for the user question."


def fallback_semantic_context_documents(
    *,
    question: str,
    related_tables: list[str],
    models_used: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    keywords = semantic_fallback_keywords(question, related_tables, models_used)
    if not keywords:
        return []
    searchable = "lower(coalesce(title, '') || ' ' || coalesce(document_type, '') || ' ' || coalesce(business_domain, '') || ' ' || coalesce(content, ''))"
    clauses = " or ".join([f"{searchable} like %s" for _ in keywords])
    params = [f"%{keyword.lower()}%" for keyword in keywords]
    try:
        with connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    select
                      title,
                      document_type,
                      business_domain,
                      content,
                      related_tables,
                      related_models,
                      related_metrics
                    from public.semantic_documents
                    where coalesce(active_flag, true) = true
                      and ({clauses})
                    order by
                      case
                        when lower(coalesce(title, '')) like %s then 0
                        when lower(coalesce(content, '')) like %s then 1
                        else 2
                      end,
                      updated_at desc nulls last,
                      created_at desc nulls last
                    limit 5
                    """,
                    params + [f"%{keywords[0].lower()}%", f"%{keywords[0].lower()}%"],
                )
                rows = cur.fetchall()
    except Exception:
        return []

    docs: list[dict[str, Any]] = []
    for row in rows:
        docs.append(
            {
                "title": row.get("title") or "Semantic context",
                "document_type": row.get("document_type") or "semantic_document",
                "business_domain": row.get("business_domain"),
                "relevance_score": 0.55,
                "related_tables": context_value_to_list(row.get("related_tables")),
                "related_models": context_value_to_list(row.get("related_models")),
                "related_metrics": context_value_to_list(row.get("related_metrics")),
                "reason_retrieved": "Retrieved by keyword fallback because pgvector context retrieval returned no displayable document.",
                "content": row.get("content") or "",
            }
        )
    return docs


def semantic_fallback_keywords(question: str, related_tables: list[str], models_used: list[dict[str, Any]]) -> list[str]:
    q = question.lower()
    keywords: list[str] = []
    intent_map = {
        "agent": ["agent performance", "mapa", "coaching"],
        "coaching": ["agent performance", "mapa", "coaching"],
        "mapa": ["mapa", "agent performance"],
        "lapse": ["policy lapse", "lapse risk"],
        "campaign": ["campaign conversion", "campaign response"],
        "claims": ["claims ratio", "fraud indicators"],
        "fraud": ["fraud indicators"],
        "churn": ["churn risk"],
        "propensity": ["propensity to buy"],
        "next best": ["next best product", "next best action"],
        "clv": ["customer lifetime value"],
        "lifetime value": ["customer lifetime value"],
    }
    for token, values in intent_map.items():
        if token in q:
            keywords.extend(values)
    for table in related_tables:
        table_name = str(table).split(".")[-1].replace("_", " ")
        if table_name:
            keywords.append(table_name)
    for model in models_used:
        model_name = str(model.get("model_name") or "").replace("_", " ")
        if model_name:
            keywords.append(model_name)
    return dedupe(keywords)[:8]


def context_value_to_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if item][:10]
    if isinstance(value, tuple):
        return [str(item) for item in value if item][:10]
    if isinstance(value, dict):
        return [str(key) for key in value.keys()][:10]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def normalise_columns(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value][:20]
    if isinstance(value, dict):
        return [f"{table}.{column}" for table, columns in value.items() for column in (columns if isinstance(columns, list) else [columns])][:20]
    return []


def infer_missing_data(question: str, payload: dict[str, Any]) -> tuple[list[str], list[str]]:
    q = question.lower()
    missing: list[str] = []
    limitations: list[str] = []
    if "market" in q or "competitor" in q:
        missing.append("External market share or competitor sales data")
        limitations.append("The current platform contains internal sales, policy, campaign, claims, lapse, and model-score data, not external market benchmarks.")
    if "declining" in q and "market" in q:
        limitations.append("Product decline can be estimated from internal new-policy and premium trends only.")
    if (payload.get("execution") or {}).get("row_count", 0) == 0:
        missing.append("Rows matching the selected role, time window, or filter")
        limitations.append("The SQL was generated and executed, but returned no rows for the current data scope.")
    return dedupe(missing), dedupe(limitations)


def infer_context_limitations(payload: dict[str, Any], context_docs: list[dict[str, Any]]) -> list[str]:
    if not payload.get("retrieved_context") and context_docs:
        return ["pgvector semantic retrieval did not return displayable context; keyword fallback selected semantic documents."]
    if not payload.get("retrieved_context"):
        return ["Relevant semantic context from pgvector was not available for this request."]
    if not context_docs:
        return ["Context retrieval ran, but no semantic context documents were selected for display."]
    return []


def infer_model_limitations(question: str, models_used: list[dict[str, Any]], related_tables: list[str]) -> list[str]:
    q = question.lower()
    model_terms = ["model", "score", "risk", "propensity", "churn", "clv", "fraud", "next best", "lapse"]
    if models_used:
        return []
    if any(term in q for term in model_terms) or any(table.endswith("model_scores") or table.endswith("model_predictions") for table in related_tables):
        return ["No model score was required or available for the generated SQL answer."]
    return []


def provider_metadata(provider: dict[str, Any], debug: dict[str, Any]) -> tuple[str, str]:
    provider_used = str(provider.get("provider_used") or "").strip()
    model_used = str(provider.get("model_used") or "").strip()
    if provider_used and provider_used != "configured" and model_used and model_used != "configured":
        return provider_used, model_used

    configured_provider = os.getenv("LLM_PROVIDER", "gemini").strip() or "gemini"
    configured_model = os.getenv("GEMINI_MODEL_SQL", os.getenv("TEXT2SQL_MODEL", "gemini-2.5-flash-lite")).strip()
    generation_error = str(debug.get("generation_error") or "")
    insight_error = str(debug.get("insight_error") or "")
    combined_error = f"{generation_error} {insight_error}".lower()
    if "prepayment credits are depleted" in combined_error or "billing" in combined_error:
        return f"{configured_provider} (billing fallback)", f"{configured_model} + deterministic fallback"
    if "RESOURCE_EXHAUSTED" in generation_error or "RESOURCE_EXHAUSTED" in insight_error:
        return f"{configured_provider} (quota fallback)", f"{configured_model} + deterministic fallback"
    return configured_provider, configured_model


def is_underperforming_campaign_question(question: str) -> bool:
    negative_terms = [
        "bad",
        "poor",
        "worst",
        "underperform",
        "under-performing",
        "low conversion",
        "poor conversion",
        "not converting",
        "least effective",
        "weak",
        "suppress",
        "stop",
        "drop",
    ]
    return "campaign" in question and any(term in question for term in negative_terms)


def to_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def is_number_like(value: Any) -> bool:
    try:
        float(value)
        return value not in {None, ""}
    except (TypeError, ValueError):
        return False


def sum_number(values: Any) -> float:
    return sum(to_float(value) for value in values)


def count_text(value: Any) -> str:
    number = to_float(value)
    return f"{int(round(number)):,}"


def compact_number(value: Any) -> str:
    number = to_float(value)
    if abs(number) >= 1_000_000:
        return f"{number / 1_000_000:.1f}M"
    if abs(number) >= 1_000:
        return f"{number / 1_000:.1f}K"
    if number.is_integer():
        return f"{int(number):,}"
    return f"{number:.4f}"


def money(value: Any) -> str:
    number = to_float(value)
    if abs(number) >= 1_000_000:
        return f"S${number / 1_000_000:.2f}M"
    if abs(number) >= 1_000:
        return f"S${number / 1_000:.1f}K"
    return f"S${number:,.0f}"


def pct(value: Any) -> str:
    number = to_float(value)
    if number <= 1:
        number *= 100
    return f"{number:.1f}%"


def impact_from_observation(observation: str) -> str:
    lower = observation.lower()
    if "lapse" in lower or "risk" in lower:
        return "Retention and premium protection"
    if "campaign" in lower or "conversion" in lower:
        return "Campaign ROI and lead conversion"
    if "agent" in lower or "mapa" in lower:
        return "Distribution productivity"
    if "claim" in lower:
        return "Claims cost and fraud monitoring"
    return "Business prioritization"


def dedupe(values: list[str]) -> list[str]:
    return list(dict.fromkeys([value for value in values if value]))
