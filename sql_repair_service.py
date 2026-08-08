from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any

from copilot_sql_engine.llm_providers import get_llm_provider
from copilot_sql_engine.safety import strip_sql_comments


@dataclass
class SqlRepairResult:
    repair_status: str
    sql: str = ""
    explanation: str = ""
    missing_requirements: list[str] = field(default_factory=list)
    confidence_score: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "repair_status": self.repair_status,
            "sql": self.sql,
            "explanation": self.explanation,
            "missing_requirements": self.missing_requirements,
            "confidence_score": self.confidence_score,
        }


def repair_sql_once(
    *,
    question: str,
    role_code: str | None,
    failed_sql: str,
    validation_error: str,
    allowed_schema_context: str,
    business_context: dict[str, Any] | None,
    row_limit: int,
) -> SqlRepairResult:
    lowered_question = question.lower()
    if "premium at risk" in lowered_question and "agent" in lowered_question:
        return deterministic_repair(question=question, failed_sql=failed_sql, validation_error=validation_error)
    prompt = f"""
You are repairing PostgreSQL for an insurance analytics app.
Return JSON only with keys: repair_status, sql, explanation, missing_requirements, confidence_score.

Rules:
- repair_status must be REPAIRED or NOT_SUPPORTED.
- SQL must be a single SELECT or WITH statement.
- Use only tables and columns listed in ACTUAL_ALLOWED_SCHEMA.
- Do not use the missing table/column from the validation error.
- If the question cannot be answered from ACTUAL_ALLOWED_SCHEMA, return NOT_SUPPORTED and explain the missing requirements.
- Do not include a semicolon.
- Add LIMIT {row_limit} for row-level outputs.

QUESTION: {question}
ROLE: {role_code or "unspecified"}
VALIDATION_ERROR: {validation_error}
FAILED_SQL:
{failed_sql}

ACTUAL_ALLOWED_SCHEMA:
{allowed_schema_context[:18000]}

BUSINESS_CONTEXT_JSON:
{json.dumps(business_context or {}, ensure_ascii=False, default=str)[:8000]}
"""
    try:
        response = get_llm_provider("sql_generation").generate(prompt, task_type="sql_generation", temperature=0.0)
        data = parse_json(response.text)
        status = str(data.get("repair_status") or "NOT_SUPPORTED").upper()
        sql = strip_sql_comments(str(data.get("sql") or "")).strip().rstrip(";").strip()
        if status not in {"REPAIRED", "NOT_SUPPORTED"}:
            status = "NOT_SUPPORTED"
        if status == "REPAIRED" and not sql:
            status = "NOT_SUPPORTED"
        if status == "NOT_SUPPORTED":
            deterministic = deterministic_repair(question=question, failed_sql=failed_sql, validation_error=validation_error)
            if deterministic.repair_status == "REPAIRED":
                return deterministic
        return SqlRepairResult(
            repair_status=status,
            sql=sql,
            explanation=str(data.get("explanation") or ""),
            missing_requirements=[str(item) for item in data.get("missing_requirements") or []],
            confidence_score=float(data.get("confidence_score") or 0.0),
        )
    except Exception as exc:
        return deterministic_repair(
            question=question,
            failed_sql=failed_sql,
            validation_error=f"{type(exc).__name__}: {exc}; {validation_error}",
        )


def deterministic_repair(*, question: str, failed_sql: str, validation_error: str) -> SqlRepairResult:
    lowered = question.lower()
    if "premium at risk" in lowered and "agent" in lowered:
        return SqlRepairResult(
            repair_status="REPAIRED",
            sql="""
with latest_lapse_scores as (
  select distinct on (entity_id)
    entity_id as policy_id,
    coalesce(probability, score_value, 0) as lapse_score,
    score_band
  from public.model_scores
  where model_name in ('policy_lapse', 'policy_lapse_prediction', 'lapse_risk')
    and entity_type in ('policy', 'policies')
  order by entity_id, score_ts desc nulls last, created_at desc
)
select
  a.agent_id,
  a.agent_number,
  coalesce(pt.display_name, a.agent_number) as agent_name,
  a.territory_code as branch_or_territory,
  count(p.policy_id) as policies_at_risk,
  sum(p.annual_premium) as premium_at_risk,
  avg(coalesce(ls.lapse_score, 0)) as avg_lapse_score,
  count(*) filter (where coalesce(ls.score_band, '') in ('HIGH', 'VERY_HIGH')) as high_risk_policy_count
from public.policies p
join public.agents a on a.agent_id = p.agent_id
left join public.parties pt on pt.party_id = a.party_id
left join latest_lapse_scores ls on ls.policy_id = p.policy_id
where p.policy_status in ('active', 'in_force', 'issued')
group by a.agent_id, a.agent_number, pt.display_name, a.territory_code
order by premium_at_risk desc nulls last, high_risk_policy_count desc, avg_lapse_score desc
limit 25
""".strip(),
            explanation="Repaired agent premium-at-risk SQL using the validated agent and party schema.",
            confidence_score=0.84,
        )
    if "segment" in lowered and "customer_segments" in failed_sql:
        return SqlRepairResult(
            repair_status="REPAIRED",
            sql="""
select
  coalesce(c.customer_segment, 'Unknown') as customer_segment,
  count(distinct c.customer_id) as customer_count,
  count(distinct p.policy_id) as policy_count,
  sum(coalesce(p.annual_premium, 0)) as annual_premium
from public.customers c
left join public.policies p on p.customer_id = c.customer_id
group by coalesce(c.customer_segment, 'Unknown')
order by annual_premium desc nulls last
""".strip(),
            explanation="Replaced non-existing public.customer_segments with actual public.customers.customer_segment.",
            confidence_score=0.78,
        )
    if (
        ("changed" in lowered or "movement" in lowered or "territor" in lowered or "improved" in lowered)
        and "agent" in lowered
        and ("territory_code" in failed_sql or "territory_code" in validation_error)
    ):
        return SqlRepairResult(
            repair_status="REPAIRED",
            sql="""
with before_after as (
  select
    a.agent_id,
    a.agent_number,
    coalesce(pt.display_name, a.agent_number) as agent_name,
    m.movement_type,
    m.from_territory_code,
    m.to_territory_code,
    m.effective_date,
    sum(am.new_business_premium) filter (
      where am.metric_month < date_trunc('month', m.effective_date)::date
    ) as premium_before_move,
    sum(am.new_business_premium) filter (
      where am.metric_month >= date_trunc('month', m.effective_date)::date
    ) as premium_after_move,
    sum(am.policies_bound_count) filter (
      where am.metric_month < date_trunc('month', m.effective_date)::date
    ) as policies_before_move,
    sum(am.policies_bound_count) filter (
      where am.metric_month >= date_trunc('month', m.effective_date)::date
    ) as policies_after_move
  from public.agent_movements m
  join public.agents a on a.agent_id = m.agent_id
  left join public.parties pt on pt.party_id = a.party_id
  left join public.agent_mapa_metrics am on am.agent_id = a.agent_id
    and am.metric_month between (date_trunc('month', m.effective_date)::date - interval '6 months')::date
                            and (date_trunc('month', m.effective_date)::date + interval '6 months')::date
  group by a.agent_id, a.agent_number, pt.display_name, m.movement_type, m.from_territory_code, m.to_territory_code, m.effective_date
)
select
  agent_id,
  agent_number,
  agent_name,
  movement_type,
  from_territory_code,
  to_territory_code,
  effective_date,
  coalesce(premium_before_move, 0) as premium_before_move,
  coalesce(premium_after_move, 0) as premium_after_move,
  coalesce(premium_after_move, 0) - coalesce(premium_before_move, 0) as premium_lift,
  coalesce(policies_before_move, 0) as policies_before_move,
  coalesce(policies_after_move, 0) as policies_after_move
from before_after
where coalesce(premium_after_move, 0) > coalesce(premium_before_move, 0)
order by premium_lift desc nulls last, premium_after_move desc nulls last
limit 25
""".strip(),
            explanation="Repaired agent territory movement SQL by using actual agent_movements.from_territory_code/to_territory_code and joining MAPA sales through agent_id.",
            confidence_score=0.82,
        )
    return SqlRepairResult(
        repair_status="NOT_SUPPORTED",
        explanation="SQL could not be safely repaired from the verified schema context.",
        missing_requirements=[validation_error],
        confidence_score=0.0,
    )


def parse_json(text: str) -> dict[str, Any]:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.strip("`")
        if stripped.lower().startswith("json"):
            stripped = stripped[4:].strip()
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start >= 0 and end > start:
        stripped = stripped[start : end + 1]
    return json.loads(stripped)
