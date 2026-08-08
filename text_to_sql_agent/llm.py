from __future__ import annotations

import json
import re
from abc import ABC, abstractmethod
from typing import Any

from openai import OpenAI

from copilot_sql_engine.llm_providers import dumps_json, get_llm_provider
from .models import SemanticContextItem
from .settings import AgentSettings


SYSTEM_PROMPT = """You are an enterprise insurance analytics SQL assistant.
Generate safe PostgreSQL SELECT queries only.
Rules:
- Return JSON only with keys: sql, explanation.
- SQL must be a single read-only SELECT statement.
- Do not generate INSERT, UPDATE, DELETE, DROP, ALTER, TRUNCATE, CREATE, MERGE, CALL, COPY, DO, GRANT, REVOKE, or SET.
- Use only the schemas and tables shown in the schema metadata.
- Prefer explicit joins and qualified table aliases.
- Use nullif for division.
- Aggregate before joining facts at different grains, especially claims and premiums.
- Do not include a semicolon.
- Include a limit only if the user asks for raw rows; aggregates do not need an explicit limit.
"""


class SqlGeneration(ABC):
    @abstractmethod
    def generate_sql(
        self,
        *,
        question: str,
        semantic_context: list[SemanticContextItem],
        schema_metadata: str,
        row_limit: int,
    ) -> tuple[str, str]:
        raise NotImplementedError

    @abstractmethod
    def explain_results(
        self,
        *,
        question: str,
        sql: str,
        rows: list[dict[str, Any]],
        semantic_context: list[SemanticContextItem],
    ) -> str:
        raise NotImplementedError


class OpenAITextToSqlProvider(SqlGeneration):
    def __init__(self, *, api_key: str, model: str, base_url: str | None, temperature: float) -> None:
        kwargs: dict[str, Any] = {"api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url
        self.client = OpenAI(**kwargs)
        self.model = model
        self.temperature = temperature

    def generate_sql(
        self,
        *,
        question: str,
        semantic_context: list[SemanticContextItem],
        schema_metadata: str,
        row_limit: int,
    ) -> tuple[str, str]:
        payload = {
            "question": question,
            "row_limit": row_limit,
            "semantic_context": [item.model_dump() for item in semantic_context],
            "schema_metadata": schema_metadata,
        }
        response = self.client.chat.completions.create(
            model=self.model,
            temperature=self.temperature,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
            ],
            response_format={"type": "json_object"},
        )
        content = response.choices[0].message.content or "{}"
        data = json.loads(content)
        return clean_sql(data.get("sql", "")), str(data.get("explanation", ""))

    def explain_results(
        self,
        *,
        question: str,
        sql: str,
        rows: list[dict[str, Any]],
        semantic_context: list[SemanticContextItem],
    ) -> str:
        sample_rows = rows[:20]
        prompt = {
            "question": question,
            "sql": sql,
            "row_count": len(rows),
            "sample_rows": sample_rows,
            "semantic_context_titles": [item.title for item in semantic_context],
        }
        response = self.client.chat.completions.create(
            model=self.model,
            temperature=self.temperature,
            messages=[
                {
                    "role": "system",
                    "content": "Explain insurance analytics query results in concise business language. Mention caveats if the sample is empty.",
                },
                {"role": "user", "content": json.dumps(prompt, ensure_ascii=False, default=str)},
            ],
        )
        return response.choices[0].message.content or "Query executed successfully."


class MockTextToSqlProvider(SqlGeneration):
    """Deterministic provider for tests and local smoke checks without an LLM key."""

    def generate_sql(
        self,
        *,
        question: str,
        semantic_context: list[SemanticContextItem],
        schema_metadata: str,
        row_limit: int,
    ) -> tuple[str, str]:
        q = question.lower()
        if "loss ratio" in q:
            return (
                """
                with claim_agg as (
                  select p.product_id, sum(c.paid_amount + c.reserve_amount) as incurred_amount
                  from public.claims c
                  join public.policies p on p.policy_id = c.policy_id
                  group by p.product_id
                ),
                premium_agg as (
                  select p.product_id, sum(pr.earned_premium_amount) as earned_premium
                  from public.premiums pr
                  join public.policies p on p.policy_id = pr.policy_id
                  group by p.product_id
                )
                select prod.line_of_business,
                       sum(coalesce(claim_agg.incurred_amount, 0)) / nullif(sum(coalesce(premium_agg.earned_premium, 0)), 0) as loss_ratio
                from public.products prod
                left join claim_agg on claim_agg.product_id = prod.product_id
                left join premium_agg on premium_agg.product_id = prod.product_id
                group by prod.line_of_business
                order by loss_ratio desc nulls last
                """,
                "Calculates incurred claims divided by earned premium by line of business.",
            )
        if "campaign" in q:
            return (
                """
                select c.campaign_name,
                       c.channel,
                       count(*) filter (where cr.conversion_flag) as conversions,
                       count(*) as responses,
                       count(*) filter (where cr.conversion_flag)::numeric / nullif(count(*), 0) as conversion_rate,
                       sum(coalesce(cr.conversion_premium, 0)) as conversion_premium
                from public.campaigns c
                join public.campaign_responses cr on cr.campaign_id = c.campaign_id
                group by c.campaign_name, c.channel
                order by conversion_premium desc
                """,
                "Ranks campaigns by conversion premium and conversion rate.",
            )
        return (
            """
            select prod.line_of_business,
                   count(*) as policy_count,
                   sum(p.annual_premium) as annual_premium
            from public.policies p
            join public.products prod on prod.product_id = p.product_id
            group by prod.line_of_business
            order by annual_premium desc
            """,
            "Summarizes policies and annual premium by line of business.",
        )

    def explain_results(
        self,
        *,
        question: str,
        sql: str,
        rows: list[dict[str, Any]],
        semantic_context: list[SemanticContextItem],
    ) -> str:
        if not rows:
            return "The query ran successfully but returned no rows for the requested filters."
        return f"The query returned {len(rows)} rows. Review the top rows for the strongest business signal."


class ProviderBackedTextToSqlProvider(SqlGeneration):
    def __init__(self, *, temperature: float) -> None:
        self.temperature = temperature

    def generate_sql(
        self,
        *,
        question: str,
        semantic_context: list[SemanticContextItem],
        schema_metadata: str,
        row_limit: int,
    ) -> tuple[str, str]:
        payload = {
            "question": question,
            "row_limit": row_limit,
            "semantic_context": [item.model_dump() for item in semantic_context],
            "schema_metadata": schema_metadata,
        }
        prompt = f"{SYSTEM_PROMPT}\n\nINPUT_JSON:\n{dumps_json(payload)}"
        response = get_llm_provider("sql_generation").generate(prompt, task_type="sql_generation", temperature=self.temperature)
        data = parse_json_object(response.text)
        return clean_sql(str(data.get("sql", ""))), str(data.get("explanation", ""))

    def explain_results(
        self,
        *,
        question: str,
        sql: str,
        rows: list[dict[str, Any]],
        semantic_context: list[SemanticContextItem],
    ) -> str:
        payload = {
            "question": question,
            "sql": sql,
            "row_count": len(rows),
            "sample_rows": rows[:20],
            "semantic_context_titles": [item.title for item in semantic_context],
        }
        prompt = "Explain insurance analytics query results in concise business language.\n\n" + dumps_json(payload)
        response = get_llm_provider("explanation").generate(prompt, task_type="explanation", temperature=self.temperature)
        return response.text or "Query executed successfully."


def build_text_provider(settings: AgentSettings) -> SqlGeneration:
    if settings.text_provider == "mock":
        return MockTextToSqlProvider()
    if settings.text_provider == "compatible" and settings.text_api_key == "ollama":
        return ProviderBackedTextToSqlProvider(temperature=settings.text_temperature)
    if not settings.text_api_key:
        raise ValueError("TEXT2SQL_API_KEY or OPENAI_API_KEY is required for this text provider")
    return OpenAITextToSqlProvider(
        api_key=settings.text_api_key,
        model=settings.text_model,
        base_url=settings.text_base_url if settings.text_provider == "compatible" else None,
        temperature=settings.text_temperature,
    )


def clean_sql(sql: str) -> str:
    sql = sql.strip()
    sql = re.sub(r"^```(?:sql)?", "", sql, flags=re.IGNORECASE).strip()
    sql = re.sub(r"```$", "", sql).strip()
    return sql.rstrip(";").strip()


def parse_json_object(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?", "", cleaned, flags=re.IGNORECASE).strip()
    cleaned = re.sub(r"```$", "", cleaned).strip()
    try:
        value = json.loads(cleaned)
        return value if isinstance(value, dict) else {}
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
        if not match:
            return {}
        value = json.loads(match.group(0))
        return value if isinstance(value, dict) else {}
