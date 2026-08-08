from __future__ import annotations

import json
import re
from abc import ABC, abstractmethod
from typing import Any

from openai import OpenAI

from copilot_orchestration.models import CopilotIntent
from copilot_sql_engine.llm_providers import dumps_json, get_llm_provider
from copilot_sql_engine.models import BusinessInsight, GeneratedRecommendation, SqlGenerationResult
from copilot_sql_engine.prompts import INSIGHT_SYSTEM_PROMPT, SQL_SYSTEM_PROMPT, build_sql_prompt_payload
from copilot_sql_engine.settings import SqlEngineSettings


class SqlProvider(ABC):
    @abstractmethod
    def generate_sql(
        self,
        *,
        question: str,
        intent: CopilotIntent,
        role_context: dict | None,
        retrieved_context: dict | None,
        schema_metadata: str,
        row_limit: int,
    ) -> SqlGenerationResult:
        raise NotImplementedError

    @abstractmethod
    def generate_insight(
        self,
        *,
        question: str,
        intent: CopilotIntent,
        sql: str,
        rows: list[dict[str, Any]],
        retrieved_context: dict | None,
    ) -> tuple[BusinessInsight, list[GeneratedRecommendation]]:
        raise NotImplementedError


class OpenAICompatibleSqlProvider(SqlProvider):
    def __init__(self, settings: SqlEngineSettings) -> None:
        kwargs: dict[str, Any] = {
            "api_key": settings.text_api_key,
            "timeout": settings.text_timeout_seconds,
            "max_retries": 0,
        }
        if settings.text_provider == "compatible" and settings.text_base_url:
            kwargs["base_url"] = settings.text_base_url
        self.client = OpenAI(**kwargs)
        self.model = settings.text_model
        self.temperature = settings.text_temperature

    def generate_sql(
        self,
        *,
        question: str,
        intent: CopilotIntent,
        role_context: dict | None,
        retrieved_context: dict | None,
        schema_metadata: str,
        row_limit: int,
    ) -> SqlGenerationResult:
        if should_use_curated_sql_template(question, intent):
            template_result = MockSqlProvider().generate_sql(
                question=question,
                intent=intent,
                role_context=role_context,
                retrieved_context=retrieved_context,
                schema_metadata=schema_metadata,
                row_limit=row_limit,
            )
            template_result.generation_explanation = (
                template_result.generation_explanation
                + " Provider=curated_template; model=validated_sql_template; fallback_used=false; latency_ms=0."
            )
            return template_result
        payload = build_sql_prompt_payload(
            question=question,
            intent=intent,
            role_context=role_context,
            retrieved_context=retrieved_context,
            schema_metadata=schema_metadata,
            row_limit=row_limit,
        )
        response = self.client.chat.completions.create(
            model=self.model,
            temperature=self.temperature,
            messages=[
                {"role": "system", "content": SQL_SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False, default=str)},
            ],
            response_format={"type": "json_object"},
        )
        data = json.loads(response.choices[0].message.content or "{}")
        return SqlGenerationResult(
            sql=clean_sql(str(data.get("sql", ""))),
            generation_explanation=str(data.get("explanation", "")),
            referenced_tables_expected=list(data.get("tables_used") or data.get("referenced_tables_expected") or []),
            columns_used=list(data.get("columns_used") or []),
            metrics_used=list(data.get("metrics_used") or []),
            models_used=list(data.get("models_used") or []),
            assumptions=list(data.get("assumptions") or []),
            confidence_score=float(data.get("confidence_score") or 0.65),
        )

    def generate_insight(
        self,
        *,
        question: str,
        intent: CopilotIntent,
        sql: str,
        rows: list[dict[str, Any]],
        retrieved_context: dict | None,
    ) -> tuple[BusinessInsight, list[GeneratedRecommendation]]:
        payload = {
            "question": question,
            "intent": intent.value,
            "sql": sql,
            "row_count": len(rows),
            "sample_rows": rows[:25],
            "retrieved_context": retrieved_context,
        }
        response = self.client.chat.completions.create(
            model=self.model,
            temperature=self.temperature,
            messages=[
                {"role": "system", "content": INSIGHT_SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False, default=str)},
            ],
            response_format={"type": "json_object"},
        )
        data = json.loads(response.choices[0].message.content or "{}")
        insight = BusinessInsight(
            summary=str(data.get("summary") or "Query executed successfully."),
            key_observations=[str(item) for item in data.get("key_observations") or []],
            caveats=[str(item) for item in data.get("caveats") or []],
        )
        recommendations = [
            GeneratedRecommendation(
                recommendation=str(item.get("recommendation", "")),
                reason=str(item.get("reason", "")),
                priority_score=float(item.get("priority_score") or 0.5),
                source="llm",
            )
            for item in data.get("recommendations") or []
            if isinstance(item, dict) and item.get("recommendation")
        ]
        return insight, recommendations


class LLMSqlProvider(SqlProvider):
    def __init__(self, settings: SqlEngineSettings) -> None:
        self.settings = settings

    def generate_sql(
        self,
        *,
        question: str,
        intent: CopilotIntent,
        role_context: dict | None,
        retrieved_context: dict | None,
        schema_metadata: str,
        row_limit: int,
    ) -> SqlGenerationResult:
        if should_use_curated_sql_template(question, intent):
            template_result = MockSqlProvider().generate_sql(
                question=question,
                intent=intent,
                role_context=role_context,
                retrieved_context=retrieved_context,
                schema_metadata=schema_metadata,
                row_limit=row_limit,
            )
            template_result.generation_explanation = (
                template_result.generation_explanation
                + " Provider=curated_template; model=validated_sql_template; fallback_used=false; latency_ms=0."
            )
            return template_result
        payload = build_sql_prompt_payload(
            question=question,
            intent=intent,
            role_context=role_context,
            retrieved_context=retrieved_context,
            schema_metadata=schema_metadata,
            row_limit=row_limit,
        )
        prompt = f"{SQL_SYSTEM_PROMPT}\n\nINPUT_JSON:\n{dumps_json(payload)}"
        response = get_llm_provider("sql_generation").generate(
            prompt,
            task_type="sql_generation",
            temperature=self.settings.text_temperature,
        )
        data = parse_json_object(response.text)
        return SqlGenerationResult(
            sql=clean_sql(str(data.get("sql", ""))),
            generation_explanation=(
                str(data.get("explanation", ""))
                + f" Provider={response.provider}; model={response.model}; fallback_used={response.fallback_used}; latency_ms={response.latency_ms}."
            ).strip(),
            referenced_tables_expected=list(data.get("tables_used") or data.get("referenced_tables_expected") or []),
            columns_used=list(data.get("columns_used") or []),
            metrics_used=list(data.get("metrics_used") or []),
            models_used=list(data.get("models_used") or []),
            assumptions=list(data.get("assumptions") or []),
            confidence_score=float(data.get("confidence_score") or 0.65),
        )

    def generate_insight(
        self,
        *,
        question: str,
        intent: CopilotIntent,
        sql: str,
        rows: list[dict[str, Any]],
        retrieved_context: dict | None,
    ) -> tuple[BusinessInsight, list[GeneratedRecommendation]]:
        payload = {
            "question": question,
            "intent": intent.value,
            "sql": sql,
            "row_count": len(rows),
            "sample_rows": rows[:25],
            "retrieved_context": retrieved_context,
        }
        prompt = f"{INSIGHT_SYSTEM_PROMPT}\n\nINPUT_JSON:\n{dumps_json(payload)}"
        response = get_llm_provider("explanation").generate(
            prompt,
            task_type="explanation",
            temperature=self.settings.text_temperature,
        )
        data = parse_json_object(response.text)
        insight = BusinessInsight(
            summary=str(data.get("summary") or "Query executed successfully."),
            key_observations=[str(item) for item in data.get("key_observations") or []],
            caveats=[str(item) for item in data.get("caveats") or []],
        )
        recommendations = [
            GeneratedRecommendation(
                recommendation=str(item.get("recommendation", "")),
                reason=str(item.get("reason", "")),
                priority_score=float(item.get("priority_score") or 0.5),
                source=response.provider,
            )
            for item in data.get("recommendations") or []
            if isinstance(item, dict) and item.get("recommendation")
        ]
        return insight, recommendations


class MockSqlProvider(SqlProvider):
    def generate_sql(
        self,
        *,
        question: str,
        intent: CopilotIntent,
        role_context: dict | None,
        retrieved_context: dict | None,
        schema_metadata: str,
        row_limit: int,
    ) -> SqlGenerationResult:
        q = question.lower()
        if is_claims_question(q):
            if "fraud" in q or "manual" in q or "review" in q:
                sql = """
                select
                  cl.claim_id,
                  cl.claim_number,
                  cl.claim_status,
                  cl.loss_cause,
                  cl.incurred_amount,
                  cl.paid_amount,
                  cl.reserve_amount,
                  cfi.indicator_type,
                  cfi.severity,
                  cfi.indicator_score as fraud_indicator_score,
                  cfi.resolved_flag,
                  prod.product_name,
                  prod.line_of_business
                from public.claim_fraud_indicators cfi
                join public.claims cl on cl.claim_id = cfi.claim_id
                left join public.policies p on p.policy_id = cl.policy_id
                left join public.products prod on prod.product_id = p.product_id
                where coalesce(cfi.resolved_flag, false) = false
                order by cfi.indicator_score desc nulls last, cl.incurred_amount desc nulls last
                """
                explanation = "Ranks unresolved claim fraud indicators for manual review."
            elif "region" in q or "growth" in q:
                sql = """
                select
                  coalesce(a.territory_code, 'Unassigned') as branch_or_territory,
                  date_trunc('month', cl.report_date)::date as report_month,
                  count(cl.claim_id) as claim_count,
                  sum(cl.incurred_amount) as incurred_amount,
                  avg(cl.incurred_amount) as avg_incurred_amount
                from public.claims cl
                left join public.agents a on a.agent_id = cl.assigned_agent_id
                group by coalesce(a.territory_code, 'Unassigned'), date_trunc('month', cl.report_date)::date
                order by incurred_amount desc nulls last, claim_count desc
                """
                explanation = "Summarizes claims by agent territory and report month to spot unusual exposure."
            else:
                sql = """
                with claims_by_product as (
                  select
                    p.product_id,
                    count(cl.claim_id) as claim_count,
                    sum(cl.paid_amount) as paid_amount,
                    sum(cl.reserve_amount) as reserve_amount,
                    sum(cl.incurred_amount) as incurred_amount
                  from public.claims cl
                  join public.policies p on p.policy_id = cl.policy_id
                  group by p.product_id
                ),
                premium_by_product as (
                  select
                    product_id,
                    count(policy_id) as policy_count,
                    sum(annual_premium) as annual_premium
                  from public.policies
                  group by product_id
                )
                select
                  prod.product_name,
                  prod.line_of_business,
                  coalesce(pb.policy_count, 0) as policy_count,
                  coalesce(cb.claim_count, 0) as claim_count,
                  coalesce(cb.paid_amount, 0) as paid_amount,
                  coalesce(cb.reserve_amount, 0) as reserve_amount,
                  coalesce(cb.incurred_amount, 0) as incurred_amount,
                  coalesce(pb.annual_premium, 0) as annual_premium,
                  coalesce(cb.incurred_amount, 0)::numeric / nullif(pb.annual_premium, 0) as claims_ratio
                from public.products prod
                left join claims_by_product cb on cb.product_id = prod.product_id
                left join premium_by_product pb on pb.product_id = prod.product_id
                where coalesce(cb.claim_count, 0) > 0
                order by claims_ratio desc nulls last, incurred_amount desc nulls last
                """
                explanation = "Ranks product claim performance by incurred claims ratio and claims exposure."
        elif is_agent_performance_question(q):
            if "premium at risk" in q or ("highest premium" in q and "risk" in q):
                sql = """
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
                """
                explanation = "Ranks agents by active policy premium exposed to lapse-risk signals."
            elif "branch" in q and "lapse" in q:
                sql = """
                select
                  coalesce(a.territory_code, 'Unassigned') as branch_or_territory,
                  count(p.policy_id) filter (where p.policy_status = 'lapsed') as lapsed_policies,
                  count(p.policy_id) as total_policies,
                  count(p.policy_id) filter (where p.policy_status = 'lapsed')::numeric / nullif(count(p.policy_id), 0) as lapse_rate,
                  sum(p.annual_premium) filter (where p.policy_status = 'lapsed') as lapsed_annual_premium
                from public.policies p
                join public.agents a on a.agent_id = p.agent_id
                group by coalesce(a.territory_code, 'Unassigned')
                order by lapsed_annual_premium desc nulls last, lapse_rate desc nulls last
                """
                explanation = "Ranks branches or territories by lapsed premium exposure and lapse rate."
            elif "changed" in q or "movement" in q or "territor" in q or "improved" in q:
                sql = """
                with before_after as (
                  select
                    a.agent_id,
                    a.agent_number,
                    coalesce(pt.display_name, a.agent_number) as agent_name,
                    m.movement_type,
                    m.from_territory_code,
                    m.to_territory_code,
                    m.effective_date,
                    sum(am.new_business_premium) filter (where am.metric_month < date_trunc('month', m.effective_date)::date) as premium_before_move,
                    sum(am.new_business_premium) filter (where am.metric_month >= date_trunc('month', m.effective_date)::date) as premium_after_move,
                    sum(am.policies_bound_count) filter (where am.metric_month < date_trunc('month', m.effective_date)::date) as policies_before_move,
                    sum(am.policies_bound_count) filter (where am.metric_month >= date_trunc('month', m.effective_date)::date) as policies_after_move
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
                order by premium_lift desc nulls last, premium_after_move desc nulls last
                """
                explanation = "Compares agent new-business premium before and after movement or territory changes."
            else:
                sql = """
                with monthly as (
                  select
                    a.agent_id,
                    a.agent_number,
                    coalesce(pt.display_name, a.agent_number) as agent_name,
                    a.territory_code as branch_or_territory,
                    am.metric_month,
                    coalesce(am.contacts_count, 0) as contacts_count,
                    coalesce(am.quotes_count, 0) as quotes_count,
                    coalesce(am.applications_count, 0) as applications_count,
                    coalesce(am.policies_bound_count, 0) as policies_bound_count,
                    coalesce(am.new_business_premium, 0) as new_business_premium,
                    coalesce(am.lapsed_policy_count, 0) as lapsed_policy_count,
                    coalesce(am.retained_policy_count, 0) as retained_policy_count,
                    row_number() over (partition by a.agent_id order by am.metric_month desc) as recency_rank
                  from public.agent_mapa_metrics am
                  join public.agents a on a.agent_id = am.agent_id
                  left join public.parties pt on pt.party_id = a.party_id
                ),
                agent_rollup as (
                  select
                    agent_id,
                    agent_number,
                    agent_name,
                    branch_or_territory,
                    sum(contacts_count) filter (where recency_rank <= 3) as recent_contacts,
                    sum(quotes_count) filter (where recency_rank <= 3) as recent_quotes,
                    sum(applications_count) filter (where recency_rank <= 3) as recent_applications,
                    sum(policies_bound_count) filter (where recency_rank <= 3) as recent_policies_bound,
                    sum(new_business_premium) filter (where recency_rank <= 3) as recent_new_business_premium,
                    sum(contacts_count + quotes_count + applications_count + policies_bound_count) filter (where recency_rank between 4 and 6) as prior_mapa_activity,
                    sum(contacts_count + quotes_count + applications_count + policies_bound_count) filter (where recency_rank <= 3) as recent_mapa_activity,
                    sum(lapsed_policy_count) filter (where recency_rank <= 3) as recent_lapsed_policies,
                    sum(retained_policy_count) filter (where recency_rank <= 3) as recent_retained_policies
                  from monthly
                  where recency_rank <= 6
                  group by agent_id, agent_number, agent_name, branch_or_territory
                )
                select
                  agent_id,
                  agent_number,
                  agent_name,
                  branch_or_territory,
                  recent_contacts,
                  recent_quotes,
                  recent_applications,
                  recent_policies_bound,
                  recent_new_business_premium,
                  recent_mapa_activity,
                  prior_mapa_activity,
                  recent_mapa_activity - coalesce(prior_mapa_activity, 0) as mapa_activity_change,
                  recent_lapsed_policies,
                  recent_retained_policies,
                  case
                    when coalesce(recent_mapa_activity, 0) = 0 then 'No recent MAPA activity'
                    when recent_mapa_activity < coalesce(prior_mapa_activity, 0) * 0.75 then 'MAPA activity declined more than 25%'
                    when coalesce(recent_policies_bound, 0) = 0 then 'No recent policy conversion'
                    when coalesce(recent_applications, 0) > 0 and recent_policies_bound::numeric / nullif(recent_applications, 0) < 0.25 then 'Low application-to-policy conversion'
                    else 'Monitor productivity'
                  end as coaching_reason
                from agent_rollup
                order by
                  case
                    when coalesce(recent_mapa_activity, 0) = 0 then 1
                    when recent_mapa_activity < coalesce(prior_mapa_activity, 0) * 0.75 then 2
                    when coalesce(recent_policies_bound, 0) = 0 then 3
                    else 4
                  end,
                  mapa_activity_change asc nulls first,
                  recent_new_business_premium asc nulls first
                """
                explanation = "Ranks agents needing coaching using recent MAPA activity, conversion, lapse, and premium productivity."
        elif intent == CopilotIntent.RECOMMENDATION or "call" in q:
            sql = """
            select
              customer_id,
              agent_id,
              coalesce(action_type, 'Review next best action') as recommended_action,
              product_id as recommended_product_id,
              priority_score,
              business_reason,
              action_reason as suggested_message,
              due_date as expiry_date,
              confidence_score
            from public.next_best_actions
            where coalesce(action_status, 'open') not in ('completed', 'cancelled')
            order by priority_score desc nulls last, due_date asc nulls last
            """
            explanation = "Uses persisted next-best-action rows for fast advisor prioritization."
        elif intent == CopilotIntent.KPI_LOOKUP and "lapse" in q:
            sql = """
            select
              count(*) filter (where policy_status = 'lapsed') as lapsed_policies,
              count(*) as total_policies,
              count(*) filter (where policy_status = 'lapsed')::numeric / nullif(count(*), 0) as lapse_rate
            from public.policies
            """
            explanation = "Calculates current lapse rate from policy status."
        elif is_policy_lapse_prediction_question(q):
            sql = """
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
              p.policy_id,
              p.policy_number,
              p.policy_status,
              p.effective_date,
              p.annual_premium,
              c.customer_id,
              coalesce(cp.display_name, c.customer_number) as customer_name,
              a.agent_id,
              a.agent_number,
              coalesce(ap.display_name, a.agent_number) as agent_name,
              coalesce(ls.lapse_score, 0) as lapse_score,
              coalesce(ls.score_band, 'UNSCORED') as score_band,
              case
                when coalesce(ls.score_band, '') in ('HIGH', 'VERY_HIGH') or coalesce(ls.lapse_score, 0) >= 0.60 then 'Model lapse signal is high'
                when p.policy_status = 'lapsed' then 'Policy is already lapsed'
                else 'Ranked by premium exposure and available lapse signal'
              end as lapse_reason,
              case
                when coalesce(ls.score_band, '') in ('HIGH', 'VERY_HIGH') or coalesce(ls.lapse_score, 0) >= 0.60 then 'Retention call within 7 days'
                else 'Review renewal and payment history'
              end as recommended_action
            from public.policies p
            join public.customers c on c.customer_id = p.customer_id
            left join public.parties cp on cp.party_id = c.party_id
            left join public.agents a on a.agent_id = p.agent_id
            left join public.parties ap on ap.party_id = a.party_id
            left join latest_lapse_scores ls on ls.policy_id = p.policy_id
            where p.policy_status in ('active', 'in_force', 'issued', 'lapsed')
            order by
              coalesce(ls.lapse_score, 0) desc,
              case when p.policy_status = 'lapsed' then 1 else 2 end,
              p.annual_premium desc nulls last
            """
            explanation = "Ranks policies and responsible agents by latest lapse-risk score and premium exposure."
        elif is_revenue_risk_question(q):
            sql = """
            with latest_lapse_scores as (
              select distinct on (entity_id)
                entity_id as policy_id,
                coalesce(probability, score_value, 0) as lapse_score,
                score_band
              from public.model_scores
              where model_name in ('policy_lapse', 'policy_lapse_prediction', 'lapse_risk')
                and entity_type in ('policy', 'policies')
              order by entity_id, score_ts desc nulls last, created_at desc
            ),
            policy_risk as (
              select
                p.policy_id,
                p.policy_number,
                p.policy_status,
                p.annual_premium,
                coalesce(ls.lapse_score, 0) as lapse_score,
                coalesce(ls.score_band, 'UNSCORED') as score_band,
                case
                  when p.policy_status = 'lapsed' then 'Lapsed premium already lost'
                  when coalesce(ls.score_band, '') = 'VERY_HIGH' or coalesce(ls.lapse_score, 0) >= 0.80 then 'Very high lapse risk premium'
                  when coalesce(ls.score_band, '') = 'HIGH' or coalesce(ls.lapse_score, 0) >= 0.60 then 'High lapse risk premium'
                  when coalesce(ls.lapse_score, 0) >= 0.40 then 'Medium lapse risk premium'
                  else 'Active premium watch'
                end as revenue_risk_area
              from public.policies p
              left join latest_lapse_scores ls on ls.policy_id = p.policy_id
            )
            select
              revenue_risk_area,
              count(policy_id) as policy_count,
              sum(annual_premium) as premium_exposure,
              avg(lapse_score) as avg_lapse_score,
              count(policy_id) filter (where score_band in ('HIGH', 'VERY_HIGH')) as high_risk_policy_count
            from policy_risk
            group by revenue_risk_area
            order by
              case
                when revenue_risk_area = 'Lapsed premium already lost' then 1
                when revenue_risk_area = 'Very high lapse risk premium' then 2
                when revenue_risk_area = 'High lapse risk premium' then 3
                when revenue_risk_area = 'Medium lapse risk premium' then 4
                else 5
              end,
              premium_exposure desc nulls last
            """
            explanation = "Summarizes revenue risk by current policy status and latest lapse-risk model score."
        elif is_product_sales_question(q):
            sql = """
            with anchor as (
              select max(effective_date)::date as max_effective_date
              from public.policies
            ),
            sales as (
              select
                prod.product_id,
                prod.product_name,
                prod.line_of_business,
                count(p.policy_id) filter (
                  where p.effective_date >= a.max_effective_date - interval '180 days'
                ) as current_period_policies,
                count(p.policy_id) filter (
                  where p.effective_date < a.max_effective_date - interval '180 days'
                    and p.effective_date >= a.max_effective_date - interval '360 days'
                ) as prior_period_policies,
                sum(p.annual_premium) filter (
                  where p.effective_date >= a.max_effective_date - interval '180 days'
                ) as current_period_premium,
                sum(p.annual_premium) filter (
                  where p.effective_date < a.max_effective_date - interval '180 days'
                    and p.effective_date >= a.max_effective_date - interval '360 days'
                ) as prior_period_premium
              from public.products prod
              cross join anchor a
              left join public.policies p on p.product_id = prod.product_id
              group by prod.product_id, prod.product_name, prod.line_of_business
            )
            select
              product_id,
              product_name,
              line_of_business,
              coalesce(current_period_policies, 0) as current_period_policies,
              coalesce(prior_period_policies, 0) as prior_period_policies,
              coalesce(current_period_policies, 0) - coalesce(prior_period_policies, 0) as policy_growth_delta,
              coalesce(current_period_premium, 0) as current_period_premium,
              coalesce(prior_period_premium, 0) as prior_period_premium,
              coalesce(current_period_premium, 0) - coalesce(prior_period_premium, 0) as premium_growth_delta
            from sales
            where coalesce(current_period_policies, 0) + coalesce(prior_period_policies, 0) > 0
            order by policy_growth_delta asc, premium_growth_delta asc nulls first, prior_period_policies desc
            """
            explanation = "Compares recent product sales against the prior period using the latest available policy effective date."
        elif "campaign" in q:
            if is_underperforming_campaign_question(q):
                sql = """
                select
                  c.campaign_name,
                  c.channel,
                  count(distinct ct.campaign_target_id) as targets,
                  count(distinct cr.campaign_response_id) as responses,
                  count(distinct cr.campaign_response_id) filter (where cr.conversion_flag) as conversions,
                  count(distinct cr.campaign_response_id)::numeric / nullif(count(distinct ct.campaign_target_id), 0) as response_rate,
                  count(distinct cr.campaign_response_id) filter (where cr.conversion_flag)::numeric / nullif(count(distinct ct.campaign_target_id), 0) as conversion_rate,
                  sum(coalesce(cr.conversion_premium, 0)) as conversion_premium
                from public.campaigns c
                left join public.campaign_targets ct on ct.campaign_id = c.campaign_id
                left join public.campaign_responses cr on cr.campaign_target_id = ct.campaign_target_id
                group by c.campaign_name, c.channel
                having count(distinct ct.campaign_target_id) > 0
                order by conversion_rate asc nulls first, conversions asc, conversion_premium asc nulls first, targets desc
                """
                explanation = "Ranks underperforming campaigns by low conversion rate, low conversions, and low converted premium."
            elif ("channel" in q or "medium" in q) and any(term in q for term in ["conversion", "response", "performance"]):
                sql = """
                select
                  c.channel,
                  count(distinct c.campaign_id) as campaign_count,
                  count(distinct ct.campaign_target_id) as targets,
                  count(distinct cr.campaign_response_id) as responses,
                  count(distinct cr.campaign_response_id) filter (where cr.conversion_flag) as conversions,
                  count(distinct cr.campaign_response_id)::numeric / nullif(count(distinct ct.campaign_target_id), 0) as response_rate,
                  count(distinct cr.campaign_response_id) filter (where cr.conversion_flag)::numeric / nullif(count(distinct ct.campaign_target_id), 0) as conversion_rate,
                  sum(coalesce(cr.conversion_premium, 0)) as conversion_premium
                from public.campaigns c
                left join public.campaign_targets ct on ct.campaign_id = c.campaign_id
                left join public.campaign_responses cr on cr.campaign_target_id = ct.campaign_target_id
                group by c.channel
                having count(distinct ct.campaign_target_id) > 0
                order by conversion_rate desc nulls last, conversion_premium desc nulls last
                """
                explanation = "Aggregates campaign response and policy conversion performance by channel."
            else:
                sql = """
                select
                  c.campaign_name,
                  c.channel,
                  count(distinct ct.campaign_target_id) as targets,
                  count(distinct cr.campaign_response_id) as responses,
                  count(distinct cr.campaign_response_id) filter (where cr.conversion_flag) as conversions,
                  count(distinct cr.campaign_response_id) filter (where cr.conversion_flag)::numeric / nullif(count(distinct ct.campaign_target_id), 0) as conversion_rate,
                  sum(coalesce(cr.conversion_premium, 0)) as conversion_premium
                from public.campaigns c
                left join public.campaign_targets ct on ct.campaign_id = c.campaign_id
                left join public.campaign_responses cr on cr.campaign_target_id = ct.campaign_target_id
                group by c.campaign_name, c.channel
                order by conversion_premium desc nulls last, conversion_rate desc nulls last
                """
                explanation = "Ranks campaigns by conversion premium and conversion rate."
        elif "singapore" in q:
            sql = """
            select
              p.policy_number,
              p.policy_status,
              p.effective_date,
              p.annual_premium,
              prod.product_name,
              prod.line_of_business,
              a.country_code
            from public.policies p
            join public.products prod on prod.product_id = p.product_id
            join public.customers c on c.customer_id = p.customer_id
            join public.addresses a on a.party_id = c.party_id and a.is_current = true
            where upper(a.country_code) in ('SG', 'SGP')
               or lower(a.city) like '%singapore%'
            order by p.effective_date desc
            """
            explanation = "Finds policies linked to current customer addresses in Singapore."
        else:
            sql = """
            select
              prod.line_of_business,
              count(*) as policy_count,
              sum(p.annual_premium) as annual_premium
            from public.policies p
            join public.products prod on prod.product_id = p.product_id
            group by prod.line_of_business
            order by annual_premium desc
            """
            explanation = "Summarizes policies and premium by line of business."

        return SqlGenerationResult(
            sql=clean_sql(sql),
            generation_explanation=explanation,
            referenced_tables_expected=[],
            confidence_score=0.72,
        )

    def generate_insight(
        self,
        *,
        question: str,
        intent: CopilotIntent,
        sql: str,
        rows: list[dict[str, Any]],
        retrieved_context: dict | None,
    ) -> tuple[BusinessInsight, list[GeneratedRecommendation]]:
        if not rows:
            return (
                BusinessInsight(
                    summary="The query executed successfully but returned no rows for the requested filters.",
                    key_observations=[],
                    caveats=["Check whether the requested geography, role scope, or date window exists in the synthetic data."],
                ),
                [],
            )
        first = rows[0]
        observations = [f"Returned {len(rows)} row(s)."]
        if "campaign_name" in first:
            observations.append(f"Top campaign in the result is {first.get('campaign_name')}.")
        if "recommended_action" in first:
            observations.append(f"Highest priority action is {first.get('recommended_action')}.")
        if "lapse_rate" in first:
            observations.append(f"Current lapse rate is {first.get('lapse_rate')}.")
        recommendations = build_deterministic_recommendations(intent, rows)
        return (
            BusinessInsight(
                summary="The result highlights the strongest insurance business signal for the question.",
                key_observations=observations,
                caveats=["This MVP uses synthetic data and should be validated before production decisions."],
            ),
            recommendations,
        )


def build_deterministic_recommendations(intent: CopilotIntent, rows: list[dict[str, Any]]) -> list[GeneratedRecommendation]:
    if not rows:
        return []
    first = rows[0]
    if intent == CopilotIntent.RECOMMENDATION and "recommended_action" in first:
        return [
            GeneratedRecommendation(
                recommendation=str(first.get("recommended_action")),
                reason=str(first.get("business_reason") or "Top ranked next-best-action by priority."),
                priority_score=float(first.get("priority_score") or first.get("confidence_score") or 0.7),
            )
        ]
    if intent == CopilotIntent.CAMPAIGN_360 or "campaign_name" in first:
        return [
            GeneratedRecommendation(
                recommendation="Prioritize follow-up for the strongest campaign responders.",
                reason="Campaign performance output includes conversion and premium signals.",
                priority_score=0.7,
            )
        ]
    if intent == CopilotIntent.KPI_LOOKUP:
        return [
            GeneratedRecommendation(
                recommendation="Monitor KPI trend and drill into segments if the value is outside target.",
                reason="KPI lookup should lead to segment diagnostics when performance is adverse.",
                priority_score=0.6,
            )
        ]
    return [
        GeneratedRecommendation(
            recommendation="Review the top result and drill into the related customer, product, agent, or campaign segment.",
            reason="The query result is ranked by the primary business metric.",
            priority_score=0.5,
        )
    ]


def build_sql_provider(settings: SqlEngineSettings) -> SqlProvider:
    if settings.text_provider == "mock":
        return MockSqlProvider()
    if settings.text_provider == "openai":
        return OpenAICompatibleSqlProvider(settings)
    if settings.text_provider == "compatible" and not settings.llm_provider:
        return OpenAICompatibleSqlProvider(settings)
    if settings.text_provider == "gemini":
        return LLMSqlProvider(settings)
    if settings.llm_provider in {"gemini", "ollama"}:
        return LLMSqlProvider(settings)
    return OpenAICompatibleSqlProvider(settings)


def should_use_curated_sql_template(question: str, intent: CopilotIntent) -> bool:
    q = question.lower()
    if is_agent_performance_question(q):
        return True
    if is_claims_question(q):
        return True
    if intent == CopilotIntent.RECOMMENDATION or "call" in q:
        return True
    if intent == CopilotIntent.KPI_LOOKUP and "lapse" in q:
        return True
    if is_policy_lapse_prediction_question(q):
        return True
    if is_revenue_risk_question(q):
        return True
    if is_product_sales_question(q):
        return True
    if "campaign" in q:
        return True
    if "singapore" in q:
        return True
    return False


def is_underperforming_campaign_question(question: str) -> bool:
    negative_terms = [
        "bad",
        "poor",
        "worst",
        "underperform",
        "under-performing",
        "low conversion",
        "poor conversion",
        "not converting",
        "least effective",
        "weak",
        "suppress",
        "stop",
        "drop",
    ]
    return "campaign" in question and any(term in question for term in negative_terms)


def is_agent_performance_question(question: str) -> bool:
    agent_terms = ["agent", "agents", "agency", "branch", "territory", "mapa", "coaching", "coach"]
    performance_terms = [
        "coaching",
        "coach",
        "premium at risk",
        "highest premium",
        "branch",
        "lapse exposure",
        "changed",
        "movement",
        "territory",
        "improved",
        "declining",
        "productivity",
        "performance",
        "mapa",
    ]
    return any(term in question for term in agent_terms) and any(term in question for term in performance_terms)


def is_claims_question(question: str) -> bool:
    return any(term in question for term in ["claim", "claims", "fraud", "loss ratio", "loss", "incurred"])


def is_product_sales_question(question: str) -> bool:
    return (
        "product" in question
        and any(term in question for term in ["declining", "decline", "new sales", "sales", "new business", "growth"])
    )


def is_revenue_risk_question(question: str) -> bool:
    return "risk" in question and "revenue" in question


def is_policy_lapse_prediction_question(question: str) -> bool:
    return "lapse" in question and any(term in question for term in ["likely", "next 90", "risk", "at risk"])


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
