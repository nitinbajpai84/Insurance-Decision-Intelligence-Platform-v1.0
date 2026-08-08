#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from typing import Any

import psycopg
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from psycopg.rows import dict_row
from pydantic import BaseModel, Field

from context_retriever_service import ContextRetriever


class CopilotContextRequest(BaseModel):
    role_code: str = Field(min_length=1)
    question: str = Field(min_length=1)
    match_count: int = Field(default=8, ge=1, le=20)


def get_db_url(env_file: str = ".env") -> str:
    load_dotenv(env_file)
    db_url = os.getenv("SUPABASE_DB_URL")
    if not db_url:
        raise RuntimeError("Missing SUPABASE_DB_URL in .env.")
    return db_url


def connect(db_url: str | None = None):
    return psycopg.connect(db_url or get_db_url(), row_factory=dict_row, connect_timeout=30)


def json_ready(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: json_ready(item) for key, item in value.items()}
    if isinstance(value, list):
        return [json_ready(item) for item in value]
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


def fetch_roles() -> list[dict[str, Any]]:
    with connect() as conn, conn.cursor() as cur:
        cur.execute(
            """
            select role_code, role_name, role_category, description
            from public.role_definitions
            where active_flag = true
            order by display_order, role_name
            """
        )
        return [json_ready(row) for row in cur.fetchall()]


def fetch_role_profile(role_code: str) -> dict[str, Any]:
    with connect() as conn, conn.cursor() as cur:
        cur.execute(
            """
            select *
            from public.v_role_intelligence_profile
            where role_code = %s
            """,
            (role_code,),
        )
        row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail=f"Role not found: {role_code}")
    return json_ready(dict(row))


def build_role_context(request: CopilotContextRequest) -> dict[str, Any]:
    profile = fetch_role_profile(request.role_code)
    enriched_question = "\n".join(
        [
            f"Role: {profile['role_name']}",
            f"Objectives: {', '.join(profile.get('primary_objectives') or [])}",
            f"Recommended models: {', '.join(profile.get('recommended_ml_models') or [])}",
            f"Question: {request.question}",
        ]
    )
    retrieved_context = ContextRetriever().retrieve(enriched_question, match_count=request.match_count)
    return {
        "role_profile": profile,
        "question": request.question,
        "retrieved_context": retrieved_context,
        "prompt_contract": {
            "role_name": profile["role_name"],
            "primary_objectives": profile["primary_objectives"],
            "data_access_scope": profile["data_access_scope"],
            "recommended_ml_models": profile["recommended_ml_models"],
            "kpis": profile["kpis"],
            "action_templates": profile["action_templates"],
        },
    }


app = FastAPI(title="Insurance Role Intelligence Service", version="1.0.0")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/roles")
def api_roles() -> list[dict[str, Any]]:
    return fetch_roles()


@app.get("/api/roles/{role_code}/profile")
def api_role_profile(role_code: str) -> dict[str, Any]:
    return fetch_role_profile(role_code)


@app.post("/api/copilot/context")
def api_copilot_context(request: CopilotContextRequest) -> dict[str, Any]:
    return build_role_context(request)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Role intelligence service helper.")
    parser.add_argument("--role-code", help="Print a role profile.")
    parser.add_argument("--question", help="Print role-aware copilot context for a question.")
    parser.add_argument("--match-count", type=int, default=8)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.role_code and args.question:
        payload = build_role_context(
            CopilotContextRequest(role_code=args.role_code, question=args.question, match_count=args.match_count)
        )
    elif args.role_code:
        payload = fetch_role_profile(args.role_code)
    else:
        payload = fetch_roles()
    print(json.dumps(payload, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

