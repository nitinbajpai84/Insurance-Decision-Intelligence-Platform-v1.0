from __future__ import annotations

from fastapi import FastAPI
from pydantic import BaseModel, Field

from copilot_orchestration.classifier import classify_intent
from copilot_orchestration.intents import INTENT_DEFINITIONS
from copilot_orchestration.models import IntentClassification, OrchestrationPlan, OrchestrationRequest
from copilot_orchestration.router import build_orchestration_plan


class ClassificationRequest(BaseModel):
    question: str = Field(min_length=3, max_length=2000)


app = FastAPI(title="Insurance Copilot Orchestration Service", version="1.0.0")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "insurance-copilot-orchestration"}


@app.get("/intents")
def list_intents() -> dict:
    return {intent.value: definition.model_dump(mode="json") for intent, definition in INTENT_DEFINITIONS.items()}


@app.post("/classify-intent", response_model=IntentClassification)
def api_classify_intent(request: ClassificationRequest) -> IntentClassification:
    return classify_intent(request.question)


@app.post("/orchestrate", response_model=OrchestrationPlan)
def api_orchestrate(request: OrchestrationRequest) -> OrchestrationPlan:
    return build_orchestration_plan(request)

