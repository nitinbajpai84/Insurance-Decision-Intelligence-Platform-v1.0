from __future__ import annotations

from fastapi import FastAPI

from copilot_sql_engine.engine import run_sql_engine
from copilot_sql_engine.models import SqlEngineRequest, SqlEngineResponse


app = FastAPI(title="Insurance Decision Intelligence LLM-to-SQL Engine", version="1.0.0")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "insurance-llm-to-sql-engine"}


@app.post("/copilot/query", response_model=SqlEngineResponse)
def copilot_query(request: SqlEngineRequest) -> SqlEngineResponse:
    return run_sql_engine(request)

