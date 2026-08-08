from __future__ import annotations

import re
from typing import Any

try:
    import sqlglot
    from sqlglot import exp
except Exception:  # pragma: no cover - fallback is used when dependency is missing
    sqlglot = None
    exp = None


MODEL_CATALOG: dict[str, dict[str, str]] = {
    "policy_lapse_risk": {
        "model_name": "policy_lapse_risk",
        "model_type": "binary_classification",
        "entity_type": "policy",
        "score_interpretation": "Higher score means higher probability of policy lapse.",
        "source_table": "model_scores",
    },
    "propensity_to_buy": {
        "model_name": "propensity_to_buy",
        "model_type": "binary_classification",
        "entity_type": "customer",
        "score_interpretation": "Higher score means higher likelihood to buy or respond to a product offer.",
        "source_table": "model_scores",
    },
    "churn_risk": {
        "model_name": "churn_risk",
        "model_type": "binary_classification",
        "entity_type": "customer",
        "score_interpretation": "Higher score means higher probability of customer churn.",
        "source_table": "model_scores",
    },
    "customer_lifetime_value": {
        "model_name": "customer_lifetime_value",
        "model_type": "regression",
        "entity_type": "customer",
        "score_interpretation": "Higher value means higher estimated future customer value.",
        "source_table": "model_scores",
    },
    "campaign_response": {
        "model_name": "campaign_response",
        "model_type": "binary_classification",
        "entity_type": "customer_campaign",
        "score_interpretation": "Higher score means higher likelihood to respond to a campaign.",
        "source_table": "model_scores",
    },
    "fraud_risk": {
        "model_name": "fraud_risk",
        "model_type": "binary_classification",
        "entity_type": "claim",
        "score_interpretation": "Higher score means higher fraud-review priority.",
        "source_table": "model_scores",
    },
    "next_best_product": {
        "model_name": "next_best_product",
        "model_type": "ranking",
        "entity_type": "customer",
        "score_interpretation": "Recommended product with highest next-best-product fit.",
        "source_table": "model_predictions",
    },
    "agent_performance": {
        "model_name": "agent_performance",
        "model_type": "forecasting",
        "entity_type": "agent",
        "score_interpretation": "Higher score means stronger expected agent productivity.",
        "source_table": "model_scores",
    },
    "next_best_action": {
        "model_name": "next_best_action",
        "model_type": "rules_plus_model_decisioning",
        "entity_type": "customer",
        "score_interpretation": "Higher priority score means the action should be worked sooner.",
        "source_table": "next_best_actions",
    },
}


COLUMN_DESCRIPTIONS: dict[str, str] = {
    "annual_premium": "Annual premium amount for the policy.",
    "policy_status": "Current lifecycle status of the policy.",
    "policy_id": "Unique policy identifier.",
    "product_id": "Product identifier used to join policies and products.",
    "product_name": "Human-readable insurance product name.",
    "line_of_business": "Insurance product line such as health, wealth, protection, or savings.",
    "campaign_name": "Human-readable campaign name.",
    "campaign_id": "Campaign identifier.",
    "campaign_target_id": "Targeted customer record within a campaign.",
    "campaign_response_id": "Customer response record for a campaign target.",
    "conversion_flag": "Indicates whether a response converted to a policy or sale.",
    "conversion_premium": "Premium attributed to a converted campaign response.",
    "channel": "Campaign or customer contact channel.",
    "agent_id": "Agent identifier.",
    "agent_number": "Business-facing agent code.",
    "territory_code": "Agent branch or territory code.",
    "metric_month": "Monthly snapshot period for MAPA productivity metrics.",
    "contacts_count": "Number of customer contacts recorded for the agent.",
    "quotes_count": "Number of quotes created by the agent.",
    "applications_count": "Number of applications submitted by the agent.",
    "policies_bound_count": "Number of policies bound by the agent.",
    "new_business_premium": "New business premium produced by the agent.",
    "lapsed_policy_count": "Count of policies lapsed in the metric period.",
    "retained_policy_count": "Count of policies retained in the metric period.",
    "claim_id": "Claim identifier.",
    "claim_number": "Business-facing claim number.",
    "claim_status": "Current claim lifecycle status.",
    "incurred_amount": "Paid plus reserved claim cost.",
    "paid_amount": "Claim amount already paid.",
    "reserve_amount": "Claim amount reserved but not yet paid.",
    "indicator_score": "Fraud indicator score or severity measure.",
    "score_value": "Generic model score value.",
    "probability": "Probability output from a model score.",
    "score_band": "Model score band such as LOW, MEDIUM, HIGH, or VERY_HIGH.",
    "priority_score": "Priority ranking score for a recommended action.",
    "recommended_action": "Next-best-action recommendation text.",
}


def extract_related_columns(sql: str) -> list[dict[str, str]]:
    if not sql.strip():
        return []
    if sqlglot is None or exp is None:
        return fallback_column(sql)
    try:
        tree = sqlglot.parse_one(sql, read="postgres")
    except Exception:
        return fallback_column(sql)

    alias_map: dict[str, str] = {}
    table_names: list[str] = []
    for table in tree.find_all(exp.Table):
        table_name = table.name
        if not table_name:
            continue
        table_names.append(table_name)
        alias_map[table.alias_or_name] = table_name
        alias_map[table_name] = table_name

    single_table = table_names[0] if len(set(table_names)) == 1 else ""
    seen: set[tuple[str, str, str]] = set()
    columns: list[dict[str, str]] = []
    for column in tree.find_all(exp.Column):
        column_name = column.name
        if not column_name or column_name == "*":
            continue
        table_name = alias_map.get(column.table or "", column.table or single_table or "unknown")
        usage = classify_usage(column)
        key = (table_name, column_name, usage)
        if key in seen:
            continue
        seen.add(key)
        columns.append(
            {
                "table": table_name,
                "column": column_name,
                "usage": usage,
                "business_description": COLUMN_DESCRIPTIONS.get(column_name, f"{column_name.replace('_', ' ').title()} used by the generated SQL."),
            }
        )
    concrete = [item for item in columns if item["table"] != "unknown"]
    return (concrete or columns)[:80] or fallback_column(sql)


def classify_usage(column: Any) -> str:
    node = column
    usage = "selected"
    while getattr(node, "parent", None) is not None:
        node = node.parent
        if isinstance(node, exp.AggFunc):
            return "aggregated"
        if isinstance(node, (exp.Where, exp.Having)):
            return "filtered"
        if isinstance(node, exp.Join):
            return "joined"
        if isinstance(node, exp.Group):
            return "grouped"
        if isinstance(node, exp.Order):
            return "ordered"
    return usage


def fallback_column(sql: str) -> list[dict[str, str]]:
    table_match = re.search(r"\bfrom\s+(?:public\.)?([a-zA-Z_][\w]*)", sql, re.IGNORECASE)
    return [
        {
            "table": table_match.group(1) if table_match else "unknown",
            "column": "unknown",
            "usage": "unknown",
            "business_description": "Column extraction failed. See generated SQL.",
        }
    ]


def detect_models_used(
    *,
    question: str,
    sql: str,
    related_context: list[dict[str, Any]],
    raw_models: Any,
) -> list[dict[str, str]]:
    q = question.lower()
    sql_lower = sql.lower()
    names: dict[str, str] = {}

    if "model_scores" in sql_lower:
        for key, terms in {
            "policy_lapse_risk": ["lapse", "premium at risk", "renewal"],
            "propensity_to_buy": ["propensity", "buy", "cross-sell", "likely to buy"],
            "churn_risk": ["churn"],
            "customer_lifetime_value": ["clv", "lifetime value"],
            "campaign_response": ["campaign", "response"],
            "fraud_risk": ["fraud"],
            "agent_performance": ["agent", "mapa", "coaching", "performance"],
        }.items():
            if any(term in q for term in terms):
                names[key] = "sql"
    if "model_predictions" in sql_lower:
        names["next_best_product"] = "sql"
    if "next_best_actions" in sql_lower:
        names["next_best_action"] = "sql"

    for item in normalise_model_names(raw_models):
        if item in MODEL_CATALOG:
            names.setdefault(item, "context")

    for doc in related_context:
        for item in normalise_model_names(doc.get("related_models")):
            if item in MODEL_CATALOG:
                names.setdefault(item, "context")

    for key, terms in {
        "policy_lapse_risk": ["lapse risk", "likely to lapse", "lapse", "revenue risk", "risks to revenue", "premium at risk"],
        "propensity_to_buy": ["propensity", "cross-sell", "buy", "declining in new sales", "declining sales", "new sales"],
        "churn_risk": ["churn", "revenue risk", "risks to revenue"],
        "customer_lifetime_value": ["clv", "lifetime value", "revenue risk", "risks to revenue"],
        "campaign_response": ["campaign response", "responded", "campaign"],
        "fraud_risk": ["fraud"],
        "next_best_product": ["next best product"],
        "agent_performance": ["agent performance", "mapa", "coaching", "declining in new sales", "declining sales", "new sales"],
    }.items():
        if any(term in q for term in terms):
            names.setdefault(key, "intent")

    result: list[dict[str, str]] = []
    for model_name, used_in in names.items():
        entry = dict(MODEL_CATALOG[model_name])
        entry["used_in"] = used_in
        result.append(entry)
    return result


def normalise_model_names(value: Any) -> list[str]:
    if not value:
        return []
    if isinstance(value, str):
        values = [value]
    elif isinstance(value, list):
        values = [str(item.get("model_name") if isinstance(item, dict) else item) for item in value]
    else:
        return []
    aliases = {
        "lapse_risk": "policy_lapse_risk",
        "policy_lapse": "policy_lapse_risk",
        "policy_lapse_prediction": "policy_lapse_risk",
        "propensity": "propensity_to_buy",
        "fraud": "fraud_risk",
        "nba": "next_best_action",
    }
    names = []
    for value in values:
        key = value.strip().lower().replace(" ", "_")
        names.append(aliases.get(key, key))
    return names


def technical_warning_flags(payload: dict[str, Any]) -> dict[str, Any]:
    provider = payload.get("provider") or {}
    debug = payload.get("debug") or {}
    errors = " ".join(str(debug.get(key) or "") for key in ["generation_error", "insight_error", "context_error", "role_error"])
    billing_depleted = "prepayment credits are depleted" in errors.lower() or "billing" in errors.lower()
    quota = billing_depleted or "RESOURCE_EXHAUSTED" in errors or "quota" in errors.lower()
    fallback = bool(provider.get("fallback_used")) or any(key.startswith("fallback_") for key in (payload.get("timings") or {}))
    warnings: list[str] = []
    if billing_depleted:
        warnings.append("Gemini billing/prepayment credits are depleted, so deterministic SQL and fallback insight generation were used.")
    elif quota:
        warnings.append("Gemini quota was exhausted, so deterministic SQL and fallback insight generation were used.")
    elif fallback:
        warnings.append("Fallback SQL or insight generation was used for this answer.")
    if "timeout" in errors.lower():
        warnings.append("Provider timeout occurred during generation or validation.")
    return {
        "technical_warnings": list(dict.fromkeys(warnings)),
        "fallback_used": fallback,
        "gemini_available": not quota and bool(provider.get("provider_used") or "gemini"),
        "gemini_quota_exhausted": quota,
        "gemini_billing_depleted": billing_depleted,
    }
