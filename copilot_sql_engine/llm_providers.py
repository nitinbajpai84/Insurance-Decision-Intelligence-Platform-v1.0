from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

import psycopg
from dotenv import load_dotenv


class LLMProviderError(RuntimeError):
    pass


@dataclass(frozen=True)
class LLMResponse:
    text: str
    provider: str
    model: str
    task_type: str
    latency_ms: int
    fallback_used: bool = False


class LLMProvider:
    provider_name = "base"

    def generate(self, prompt: str, task_type: str = "general", temperature: float = 0.1) -> LLMResponse:
        raise NotImplementedError

    def model_for_task(self, task_type: str) -> str:
        raise NotImplementedError


def _float_env(name: str, default: float) -> float:
    value = os.getenv(name)
    return default if value in {None, ""} else float(value)


def estimate_tokens(text: str) -> int:
    return max(1, int(len(text) / 4)) if text else 0


def classify_gemini_error(message: str) -> str:
    lowered = message.lower()
    if "prepayment credits are depleted" in lowered or "billing" in lowered:
        return "billing_or_prepayment_exhausted"
    if "resource_exhausted" in lowered or "quota" in lowered or "rate limit" in lowered:
        return "quota_or_rate_limit"
    if "api key" in lowered or "permission" in lowered or "unauthenticated" in lowered or "forbidden" in lowered:
        return "authentication_or_permission"
    if "timeout" in lowered or "timed out" in lowered:
        return "timeout"
    if "unavailable" in lowered or "503" in lowered:
        return "provider_unavailable"
    return "provider_error"


def gemini_error_action(error_category: str) -> str:
    if error_category == "billing_or_prepayment_exhausted":
        return "Add or renew Gemini API billing/prepayment credits in Google AI Studio, then rerun the smoke test."
    if error_category == "quota_or_rate_limit":
        return "Wait for the quota window to reset, reduce request volume, or increase Gemini API quota."
    if error_category == "authentication_or_permission":
        return "Check that GEMINI_API_KEY is a valid Google AI Studio key with Gemini API access."
    if error_category == "timeout":
        return "Retry later or increase LLM_TIMEOUT_SECONDS if the network is slow."
    if error_category == "provider_unavailable":
        return "Retry later or temporarily use deterministic fallback responses for the demo."
    return "Inspect the Gemini error message and provider status."


class GeminiProvider(LLMProvider):
    provider_name = "gemini"

    def __init__(self) -> None:
        load_dotenv(".env")
        self.api_key = os.getenv("GEMINI_API_KEY", "").strip()
        if not self.api_key:
            raise LLMProviderError("GEMINI_API_KEY is not configured")
        self.sql_model = os.getenv("GEMINI_MODEL_SQL", "gemini-2.5-flash").strip()
        self.fast_model = os.getenv("GEMINI_MODEL_FAST", "gemini-2.5-flash").strip()
        self.timeout_seconds = _float_env("LLM_TIMEOUT_SECONDS", 120.0)

    def model_for_task(self, task_type: str) -> str:
        if task_type in {"sql_generation", "recommendation"}:
            return self.sql_model
        return self.fast_model

    def generate(self, prompt: str, task_type: str = "general", temperature: float = 0.1) -> LLMResponse:
        start = time.perf_counter()
        model = self.model_for_task(task_type)
        try:
            from google import genai
            from google.genai import types

            client = genai.Client(
                api_key=self.api_key,
                http_options=types.HttpOptions(timeout=int(self.timeout_seconds * 1000)),
            )
            response = client.models.generate_content(
                model=model,
                contents=prompt,
                config=types.GenerateContentConfig(temperature=temperature),
            )
            text = clean_text(getattr(response, "text", "") or "")
            latency_ms = int((time.perf_counter() - start) * 1000)
            log_llm_request(
                provider=self.provider_name,
                model=model,
                task_type=task_type,
                latency_ms=latency_ms,
                prompt=prompt,
                response_text=text,
                success=True,
                timeout=False,
                error_message=None,
            )
            return LLMResponse(text=text, provider=self.provider_name, model=model, task_type=task_type, latency_ms=latency_ms)
        except Exception as exc:
            latency_ms = int((time.perf_counter() - start) * 1000)
            timeout_flag = "timeout" in type(exc).__name__.lower() or "timed out" in str(exc).lower()
            log_llm_request(
                provider=self.provider_name,
                model=model,
                task_type=task_type,
                latency_ms=latency_ms,
                prompt=prompt,
                response_text="",
                success=False,
                timeout=timeout_flag,
                error_message=f"{type(exc).__name__}: {exc}",
            )
            raise LLMProviderError(f"Gemini generation failed: {type(exc).__name__}: {exc}") from exc
        finally:
            close = getattr(locals().get("client", None), "close", None)
            if callable(close):
                close()


def get_llm_provider(task_type: str = "general") -> LLMProvider:
    load_dotenv(".env")
    configured = os.getenv("LLM_PROVIDER", "").strip().lower()
    provider_name = configured or "gemini"
    if provider_name == "gemini":
        return GeminiProvider()
    if provider_name in {"mock", "deterministic"}:
        raise LLMProviderError("Mock provider is handled by the SQL engine fallback templates")
    raise LLMProviderError(f"Unsupported LLM_PROVIDER: {provider_name}")


def clean_text(text: str) -> str:
    return text.strip()


def log_llm_request(
    *,
    provider: str,
    model: str,
    task_type: str,
    latency_ms: int,
    prompt: str,
    response_text: str,
    success: bool,
    timeout: bool,
    error_message: str | None,
) -> None:
    db_url = os.getenv("SUPABASE_DB_URL", "").strip()
    if not db_url:
        return
    try:
        with psycopg.connect(db_url, connect_timeout=10) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    create table if not exists public.llm_request_log (
                      request_id uuid primary key,
                      provider varchar,
                      model varchar,
                      task_type varchar,
                      latency_ms int,
                      prompt_tokens_estimate int,
                      response_tokens_estimate int,
                      success_flag boolean,
                      timeout_flag boolean,
                      error_message text,
                      created_at timestamp with time zone default now()
                    )
                    """
                )
                cur.execute(
                    """
                    insert into public.llm_request_log (
                      request_id,
                      provider,
                      model,
                      task_type,
                      latency_ms,
                      prompt_tokens_estimate,
                      response_tokens_estimate,
                      success_flag,
                      timeout_flag,
                      error_message
                    )
                    values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        str(uuid4()),
                        provider,
                        model,
                        task_type,
                        latency_ms,
                        estimate_tokens(prompt),
                        estimate_tokens(response_text),
                        success,
                        timeout,
                        error_message[:2000] if error_message else None,
                    ),
                )
    except Exception:
        return


def provider_health() -> dict[str, Any]:
    load_dotenv(".env")
    active = os.getenv("LLM_PROVIDER", "").strip().lower() or "gemini"
    timeout_seconds = _float_env("LLM_TIMEOUT_SECONDS", 120.0)
    gemini_available = False
    gemini_quota_exhausted = False
    last_error_type = ""
    last_error_message = ""
    error_category = ""
    recommended_action = ""
    latency_ms = 0
    start = time.perf_counter()
    api_key_present = bool(os.getenv("GEMINI_API_KEY"))
    if api_key_present:
        try:
            GeminiProvider().generate("Return the word ok.", task_type="health", temperature=0.0)
            gemini_available = True
        except Exception as exc:
            gemini_available = False
            last_error_type = type(exc).__name__
            last_error_message = str(exc)[:500]
            error_category = classify_gemini_error(str(exc))
            recommended_action = gemini_error_action(error_category)
            gemini_quota_exhausted = error_category in {"billing_or_prepayment_exhausted", "quota_or_rate_limit"}
    latency_ms = int((time.perf_counter() - start) * 1000)
    return {
        "active_provider": active,
        "gemini_api_key_present": api_key_present,
        "gemini_available": gemini_available,
        "gemini_quota_exhausted": gemini_quota_exhausted,
        "gemini_model_fast": os.getenv("GEMINI_MODEL_FAST", "gemini-2.5-flash"),
        "gemini_model_sql": os.getenv("GEMINI_MODEL_SQL", "gemini-2.5-flash"),
        "ollama_available": False,
        "fallback_available": True,
        "last_error_type": last_error_type,
        "last_error_message": last_error_message,
        "error_category": error_category,
        "recommended_action": recommended_action,
        "latency_ms": latency_ms,
        "models": {
            "intent": os.getenv("GEMINI_MODEL_FAST", "gemini-2.5-flash"),
            "sql_generation": os.getenv("GEMINI_MODEL_SQL", "gemini-2.5-flash"),
            "explanation": os.getenv("GEMINI_MODEL_FAST", "gemini-2.5-flash"),
            "embedding": os.getenv("GEMINI_EMBEDDING_MODEL", "gemini-embedding-001"),
        },
        "timeout_seconds": timeout_seconds,
        "latency_test_ms": latency_ms,
    }


def response_preview(text: str, limit: int = 300) -> str:
    normalized = " ".join(text.split())
    return normalized[:limit]


def dumps_json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, default=str)
