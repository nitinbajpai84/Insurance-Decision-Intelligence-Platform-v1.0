from __future__ import annotations

import argparse
import os
import socket
import sys
from urllib.parse import urlparse

import requests
from dotenv import load_dotenv
from psycopg.conninfo import conninfo_to_dict


REQUIRED = {
    "SUPABASE_PROJECT_URL",
    "SUPABASE_URL",
    "SUPABASE_DB_URL",
    "EMBEDDING_PROVIDER",
    "EMBEDDING_DIMENSIONS",
    "GEMINI_API_KEY",
    "GEMINI_EMBEDDING_MODEL",
    "LLM_PROVIDER",
    "GEMINI_MODEL_SQL",
    "GEMINI_MODEL_FAST",
    "TEXT2SQL_PROVIDER",
    "TEXT2SQL_MODEL",
}


def has_placeholder(value: str | None) -> bool:
    if not value:
        return True
    lowered = value.lower()
    return any(token in lowered for token in ["[your-password]", "your-compatible-gateway", "your_key", "your-key"])


def check_url(name: str, value: str | None, errors: list[str]) -> None:
    if not value:
        errors.append(f"{name} is empty")
        return
    parsed = urlparse(value)
    if not parsed.scheme or not parsed.netloc:
        errors.append(f"{name} is not a valid URL: {value}")


def check_db_url(value: str | None, warnings: list[str], errors: list[str]) -> None:
    if not value:
        errors.append("SUPABASE_DB_URL is empty")
        return
    parse_value = value.replace("[YOUR-PASSWORD]", "PASSWORD_PLACEHOLDER")
    parsed = urlparse(parse_value)
    if parsed.scheme not in {"postgresql", "postgres"}:
        errors.append("SUPABASE_DB_URL must start with postgresql://")
    if not parsed.hostname:
        errors.append("SUPABASE_DB_URL is missing host")
    if parsed.netloc.count("@") > 1:
        errors.append(
            "SUPABASE_DB_URL has more than one '@'. Your password likely contains an unencoded '@'. "
            "Encode it as %40 and remove placeholder brackets."
        )
    if "[" in parsed.netloc or "]" in parsed.netloc:
        errors.append("SUPABASE_DB_URL still contains square brackets. Remove placeholder brackets around the password.")
    if parsed.hostname and not parsed.hostname.endswith(".supabase.co"):
        warnings.append(f"Parsed DB host is {parsed.hostname}; expected a Supabase host ending in .supabase.co.")
    if has_placeholder(value):
        warnings.append("SUPABASE_DB_URL still contains [YOUR-PASSWORD]. Replace it before running DB jobs.")
    try:
        parsed_conninfo = conninfo_to_dict(value)
        libpq_host = parsed_conninfo.get("host", "")
        if "@" in libpq_host:
            errors.append(
                "SUPABASE_DB_URL appears to contain an unencoded '@' in the password. "
                "URL-encode the password, e.g. @ becomes %40."
            )
    except Exception as exc:
        errors.append(f"SUPABASE_DB_URL could not be parsed by psycopg/libpq: {exc}")


def test_gemini(api_key: str | None, model: str) -> tuple[bool, str]:
    if not api_key:
        return False, "GEMINI_API_KEY is empty"
    try:
        from google import genai

        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(model=model, contents="Return ok.")
        if getattr(response, "text", ""):
            return True, "Gemini generation reachable"
        return False, "Gemini returned an empty response"
    except Exception as exc:
        return False, f"Gemini not reachable: {type(exc).__name__}: {exc}"


def test_db_dns(db_url: str | None) -> tuple[bool, str]:
    if not db_url:
        return False, "SUPABASE_DB_URL is empty"
    parse_value = db_url.replace("[YOUR-PASSWORD]", "PASSWORD_PLACEHOLDER")
    host = urlparse(parse_value).hostname
    if not host:
        return False, "SUPABASE_DB_URL has no host"
    try:
        addresses = socket.getaddrinfo(host, 5432, type=socket.SOCK_STREAM)
        resolved = sorted({item[4][0] for item in addresses})
        return True, f"DB DNS resolved {host} -> {', '.join(resolved[:4])}"
    except Exception as exc:
        return False, f"DB DNS failed for {host}: {exc}"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Smoke test local .env configuration.")
    parser.add_argument("--env-file", default=".env")
    parser.add_argument("--check-gemini", action="store_true")
    parser.add_argument("--check-db-dns", action="store_true", help="Deprecated; DB DNS is checked by default.")
    parser.add_argument("--skip-db-dns", action="store_true", help="Skip database DNS resolution check.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    load_dotenv(args.env_file, override=True)

    errors: list[str] = []
    warnings: list[str] = []

    missing = sorted(name for name in REQUIRED if not os.getenv(name))
    if missing:
        errors.append(f"Missing required variables: {', '.join(missing)}")

    check_url("SUPABASE_PROJECT_URL", os.getenv("SUPABASE_PROJECT_URL"), errors)
    check_url("SUPABASE_URL", os.getenv("SUPABASE_URL"), errors)
    check_db_url(os.getenv("SUPABASE_DB_URL"), warnings, errors)

    embedding_provider = os.getenv("EMBEDDING_PROVIDER", "").lower()
    if embedding_provider not in {"gemini", "openai", "compatible", "local"}:
        errors.append("EMBEDDING_PROVIDER must be one of: gemini, openai, compatible, local")
    if embedding_provider == "gemini" and os.getenv("EMBEDDING_DIMENSIONS") != "768":
        warnings.append("EMBEDDING_PROVIDER=gemini is configured for this MVP with EMBEDDING_DIMENSIONS=768.")
    if embedding_provider == "openai" and not os.getenv("OPENAI_API_KEY"):
        warnings.append("EMBEDDING_PROVIDER=openai but OPENAI_API_KEY is empty. Embedding jobs will fail until set.")
    if embedding_provider == "ollama" and os.getenv("EMBEDDING_DIMENSIONS") != "768":
        warnings.append("EMBEDDING_PROVIDER=ollama usually requires EMBEDDING_DIMENSIONS=768 for nomic-embed-text.")

    text_provider = os.getenv("TEXT2SQL_PROVIDER", "").lower()
    if text_provider not in {"openai", "compatible", "mock", "gemini"}:
        errors.append("TEXT2SQL_PROVIDER must be one of: openai, compatible, mock, gemini")
    llm_provider = os.getenv("LLM_PROVIDER", "").lower()
    if llm_provider != "gemini":
        errors.append("LLM_PROVIDER must be gemini for this Gemini-only MVP configuration.")
    if text_provider == "compatible" and os.getenv("TEXT2SQL_BASE_URL"):
        check_url("TEXT2SQL_BASE_URL", os.getenv("TEXT2SQL_BASE_URL"), errors)

    if args.check_gemini:
        ok, message = test_gemini(os.getenv("GEMINI_API_KEY"), os.getenv("GEMINI_MODEL_FAST", "gemini-2.5-flash"))
        if ok:
            warnings.append(message)
        else:
            errors.append(message)
    if args.check_db_dns or not args.skip_db_dns:
        ok, message = test_db_dns(os.getenv("SUPABASE_DB_URL"))
        (warnings if not ok else warnings).append(message)

    print("ENV SMOKE TEST")
    print(f"- env file: {args.env_file}")
    print(f"- Supabase URL: {os.getenv('SUPABASE_URL')}")
    db_url_for_parse = os.getenv("SUPABASE_DB_URL", "").replace("[YOUR-PASSWORD]", "PASSWORD_PLACEHOLDER")
    print(f"- DB host: {urlparse(db_url_for_parse).hostname}")
    print(f"- embedding provider: {embedding_provider}")
    print(f"- embedding dimensions: {os.getenv('EMBEDDING_DIMENSIONS')}")
    print(f"- text provider: {text_provider}")
    print(f"- LLM provider: {llm_provider}")
    print(f"- text model: {os.getenv('TEXT2SQL_MODEL')}")

    for warning in warnings:
        print(f"WARNING: {warning}")
    for error in errors:
        print(f"ERROR: {error}", file=sys.stderr)

    if errors:
        return 1
    print("ENV SMOKE TEST PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
