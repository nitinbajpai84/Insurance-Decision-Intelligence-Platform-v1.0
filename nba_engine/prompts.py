from __future__ import annotations

NBA_EXPLANATION_SYSTEM_PROMPT = """You are an insurance CRM decisioning copilot.
Explain next-best-action recommendations using only the supplied customer facts,
model scores, business rules, and retrieved semantic context. Do not invent
policy details, product eligibility, or regulatory claims. Keep the explanation
short, operational, and suitable for an agent desktop."""

NBA_EXPLANATION_USER_TEMPLATE = """Customer decision:
{decision_json}

Retrieved business context:
{context_json}

Write:
1. A concise business_reason.
2. A customer-safe suggested_message.
3. Any caveat if the recommendation is suppressed or agent capacity is constrained.
Return JSON with keys: business_reason, suggested_message."""


def build_explanation_prompt(decision_json: str, context_json: str) -> str:
    return NBA_EXPLANATION_USER_TEMPLATE.format(
        decision_json=decision_json,
        context_json=context_json,
    )

