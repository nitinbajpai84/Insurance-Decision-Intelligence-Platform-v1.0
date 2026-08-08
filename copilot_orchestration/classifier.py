from __future__ import annotations

import re
from collections import Counter

from copilot_orchestration.models import CopilotIntent, IntentClassification


SIGNALS: dict[CopilotIntent, list[str]] = {
    CopilotIntent.RECOMMENDATION: [
        "should i call",
        "should i contact",
        "who should",
        "which customers should",
        "recommend",
        "next best",
        "next-best",
        "action",
        "call this week",
        "priority",
        "follow up",
    ],
    CopilotIntent.EXPLANATION: [
        "why",
        "explain",
        "reason",
        "drivers",
        "at high risk",
        "high lapse risk",
        "high churn risk",
        "what caused",
    ],
    CopilotIntent.KPI_LOOKUP: [
        "current",
        "kpi",
        "rate",
        "ratio",
        "persistency",
        "lapse rate",
        "claim ratio",
        "conversion rate",
        "what is our",
        "how many",
    ],
    CopilotIntent.CUSTOMER_360: [
        "customer 360",
        "customer profile",
        "customer summary",
        "this customer",
        "customer details",
        "customer view",
    ],
    CopilotIntent.AGENT_360: [
        "agent 360",
        "agent profile",
        "agent summary",
        "mapa",
        "agent productivity",
        "agent performance",
        "territory",
    ],
    CopilotIntent.CAMPAIGN_360: [
        "campaign 360",
        "campaign profile",
        "campaign summary",
        "campaigns",
        "campaign",
        "responders",
        "audience",
    ],
    CopilotIntent.CLAIMS_360: [
        "claims 360",
        "claim 360",
        "claim profile",
        "claim summary",
        "claims",
        "claim",
        "fraud",
        "loss",
    ],
    CopilotIntent.ANALYTICS: [
        "which",
        "show me",
        "compare",
        "trend",
        "performed best",
        "best",
        "sold",
        "in singapore",
        "by product",
        "by segment",
    ],
}


ENTITY_OVERRIDES: list[tuple[CopilotIntent, list[str]]] = [
    (CopilotIntent.CUSTOMER_360, ["customer 360", "customer profile", "customer summary"]),
    (CopilotIntent.AGENT_360, ["agent 360", "agent profile", "agent summary"]),
    (CopilotIntent.CAMPAIGN_360, ["campaign 360", "campaign profile", "campaign summary"]),
    (CopilotIntent.CLAIMS_360, ["claims 360", "claim 360", "claim profile", "claim summary"]),
]


def normalize_question(question: str) -> str:
    lowered = question.lower()
    return re.sub(r"\s+", " ", lowered).strip()


def classify_intent(question: str) -> IntentClassification:
    q = normalize_question(question)

    for intent, phrases in ENTITY_OVERRIDES:
        matched = [phrase for phrase in phrases if phrase in q]
        if matched:
            return IntentClassification(
                intent=intent,
                confidence_score=0.95,
                rationale=f"Explicit entity 360 signal matched: {matched[0]}",
                matched_signals=matched,
                fallback_intent=CopilotIntent.ANALYTICS,
            )

    if q.startswith("why ") or q.startswith("explain ") or " why " in q:
        matched = [phrase for phrase in SIGNALS[CopilotIntent.EXPLANATION] if phrase in q]
        return IntentClassification(
            intent=CopilotIntent.EXPLANATION,
            confidence_score=0.90,
            rationale="Question asks for reasons or drivers.",
            matched_signals=matched or ["why/explain"],
            fallback_intent=CopilotIntent.ANALYTICS,
        )

    if "should" in q and any(token in q for token in ["call", "contact", "follow", "recommend", "action"]):
        matched = [phrase for phrase in SIGNALS[CopilotIntent.RECOMMENDATION] if phrase in q]
        return IntentClassification(
            intent=CopilotIntent.RECOMMENDATION,
            confidence_score=0.88,
            rationale="Question asks for prioritized operational action.",
            matched_signals=matched or ["should + action"],
            fallback_intent=CopilotIntent.ANALYTICS,
        )

    scores = Counter()
    matches: dict[CopilotIntent, list[str]] = {}
    for intent, phrases in SIGNALS.items():
        found = [phrase for phrase in phrases if phrase in q]
        if found:
            scores[intent] += len(found)
            matches[intent] = found

    if "campaign" in q and any(word in q for word in ["performance", "performed", "conversion", "response", "funnel"]):
        scores[CopilotIntent.CAMPAIGN_360] += 2
    if "claim" in q and any(word in q for word in ["fraud", "ratio", "severity", "paid", "reserve"]):
        scores[CopilotIntent.CLAIMS_360] += 2
    if "agent" in q and any(word in q for word in ["mapa", "performance", "productivity", "territory"]):
        scores[CopilotIntent.AGENT_360] += 2
    if any(kpi in q for kpi in ["lapse rate", "claim ratio", "conversion rate", "persistency rate"]):
        scores[CopilotIntent.KPI_LOOKUP] += 3

    if not scores:
        return IntentClassification(
            intent=CopilotIntent.ANALYTICS,
            confidence_score=0.55,
            rationale="No strong intent signal found; defaulting to analytics.",
            matched_signals=[],
        )

    intent, score = scores.most_common(1)[0]
    if intent in {CopilotIntent.CAMPAIGN_360, CopilotIntent.CLAIMS_360, CopilotIntent.AGENT_360} and "show me" in q:
        fallback = CopilotIntent.ANALYTICS
    else:
        fallback = CopilotIntent.ANALYTICS if intent != CopilotIntent.ANALYTICS else None

    confidence = min(0.90, 0.55 + (score * 0.10))
    return IntentClassification(
        intent=intent,
        confidence_score=round(confidence, 3),
        rationale=f"Matched {score} intent signal(s) for {intent}.",
        matched_signals=matches.get(intent, []),
        fallback_intent=fallback,
    )

