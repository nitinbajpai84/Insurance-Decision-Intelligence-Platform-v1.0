"""
Orchestrator — master controller replacing V1's sequential 6-step pipeline.

Architecture:
  Step 1: context_agent.get_context()       <- runs FIRST (all agents need it)
          cache_hit? -> skip straight to the answer (no SQL, no execution)
  Step 2+3 (PARALLEL, asyncio.gather):
          - sql_agent.generate_sql()
          - supplemental schema pre-load (extra table/column candidates for repair)
  Step 4: execution_agent.execute_and_validate()
  Step 5: insight_agent.generate_insight()  <- STREAMS tokens immediately

Every step is traced to DuckDB agent_reasoning_log via observability.tracer.

Two entry points:
  - stream_pipeline(...)  -> async generator of SSE-ready event dicts
  - run_pipeline(...)     -> consumes the stream, returns the final PipelineResult dict
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from time import perf_counter
from typing import Any, AsyncGenerator

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend_v2.agents import context_agent, execution_agent, insight_agent, sql_agent
from backend_v2.agents.models import ContextResult, ExecutionResult, SQLResult
from backend_v2.config import ALLOW_UNGOVERNED_FALLBACK, USE_GRAPH_GROUNDED_SQL
from backend_v2.observability import tracer
from embeddings.vector_search import search_schema


def _build_result(
    *,
    query_id: str,
    question: str,
    role: str,
    context: ContextResult,
    sql_result: SQLResult,
    exec_result: ExecutionResult,
    insight_meta: dict[str, Any],
    answer_summary: str,
    step_latencies: dict[str, int],
    total_latency_ms: int,
) -> dict[str, Any]:
    """PipelineResult — V1-compatible shape plus V2 fields."""
    executed = exec_result.execution_status == "executed"
    return {
        "query_id": query_id,
        "question": question,
        "role": role,
        # --- V1-compatible fields ---
        "context_retrieved": bool(
            context.schema_context or context.glossary_terms or context.semantic_docs
        ),
        "sql_generated": bool(sql_result.sql),
        "sql_validated": sql_result.validation_status == "validated",
        "sql_executed": executed,
        "result_validated": executed and not exec_result.suspicious_zero_rows,
        "insight_generated": bool(answer_summary),
        "answer_summary": answer_summary,
        "sql_generated_text": exec_result.repair_sql or sql_result.sql,
        "validation": {
            "status": sql_result.validation_status,
            "errors": sql_result.validation_errors,
        },
        "execution": exec_result.to_dict(),
        "row_count": exec_result.row_count,
        "explain_passed": exec_result.explain_passed,
        "repair_status": "REPAIRED" if exec_result.repaired else ("NOT_NEEDED" if executed else "NOT_REPAIRED"),
        "answer_status": (
            "CACHED" if context.cache_hit
            else "VALIDATED" if executed and exec_result.row_count > 0
            else "PARTIAL" if executed
            else "NOT_SUPPORTED"
        ),
        "actual_tables": sql_result.tables_used,
        "actual_columns": sql_result.columns_used,
        "top_context": {
            "schema": context.schema_context[:5],
            "glossary": context.glossary_terms[:5],
            "docs": context.semantic_docs[:3],
        },
        "models_used": insight_meta.get("models_used", []),
        "business_data_limitations": insight_meta.get("business_limitations", ""),
        "result_preview": exec_result.rows[:10],
        "key_data_points": insight_meta.get("key_data_points", []),
        # --- NEW V2 fields ---
        "cache_hit": context.cache_hit,
        "cache_similarity": context.cache_similarity,
        "parallel_execution": True,
        "total_latency_ms": total_latency_ms,
        "step_latencies": step_latencies,
        "agent_trace_id": query_id,
        "recommended_action": insight_meta.get("recommended_action", ""),
        "confidence_score": insight_meta.get("confidence_score", 0.0),
        "streaming": True,
    }


async def stream_pipeline(
    question: str, role: str, query_id: str
) -> AsyncGenerator[dict[str, Any], None]:
    """Yields SSE-ready event dicts; the last event has step='complete'."""
    total_started = perf_counter()
    step_latencies: dict[str, int] = {}

    # ---- Step 1: context (runs first — everything depends on it) -----------
    context = await context_agent.get_context(question, role)
    step_latencies["context_ms"] = context.assembly_time_ms
    tracer.log_step(
        query_id, "context_agent", question,
        f"schema={len(context.schema_context)} glossary={len(context.glossary_terms)} "
        f"docs={len(context.semantic_docs)} cache_hit={context.cache_hit}",
        context.assembly_time_ms,
        tokens_used=context.total_tokens_estimate,
        cache_hit=context.cache_hit,
    )
    yield {"step": "context_retrieved", "status": "done",
           "time_ms": context.assembly_time_ms, "cache_hit": context.cache_hit,
           "tokens": context.total_tokens_estimate}

    # ---- Cache hit: skip SQL + execution entirely ---------------------------
    if context.cache_hit and context.cached_answer:
        answer = context.cached_answer
        tracer.log_step(query_id, "semantic_cache", question, answer[:200], 0, cache_hit=True)
        yield {"step": "cache_hit", "status": "done", "similarity": context.cache_similarity}
        # stream the cached answer in word groups so the UI behaves identically
        words = answer.split()
        for i in range(0, len(words), 8):
            yield {"step": "insight_token", "token": " ".join(words[i:i + 8]) + " "}
        total_ms = int((perf_counter() - total_started) * 1000)
        result = _build_result(
            query_id=query_id, question=question, role=role, context=context,
            sql_result=SQLResult(validation_status="skipped_cache"),
            exec_result=ExecutionResult(execution_status="skipped_cache"),
            insight_meta={"models_used": ["semantic_cache"],
                          "business_limitations": "Served from semantic cache.",
                          "recommended_action": "", "confidence_score": context.cache_similarity},
            answer_summary=answer, step_latencies=step_latencies, total_latency_ms=total_ms,
        )
        yield {"step": "complete", "query_id": query_id, "metadata": result}
        return

    # ---- Step 2: SQL generation (graph-grounded behind flag) ----------------
    started = perf_counter()
    grounding = None  # GroundedSQLResult evidence when the grounded agent is used
    ungoverned = False  # set when we fall back to the legacy free-SQL agent
    if USE_GRAPH_GROUNDED_SQL:
        from backend_v2.agents import graph_sql_agent
        try:
            grounding = await graph_sql_agent.generate_grounded_sql(question, role, execute=False)
        except Exception as exc:
            grounding = None
            sql_result = SQLResult(validation_status="blocked",
                                   validation_errors=[f"graph_sql_agent failed: {type(exc).__name__}: {exc}"])
        if grounding is not None and grounding.unsupported and ALLOW_UNGOVERNED_FALLBACK:
            # flag on: fall back to the legacy free-SQL agent, label as ungoverned
            tracer.log_step(query_id, "graph_sql_agent", question,
                            "unsupported -> ungoverned fallback (legacy sql_agent)", grounding.generation_time_ms)
            grounding = None
            ungoverned = True
        elif grounding is not None and grounding.unsupported:
            # GUARDRAIL: no sanctioned metric -> explain transparently, run NO SQL.
            gen_ms = grounding.generation_time_ms
            step_latencies["sql_generation_ms"] = gen_ms
            tracer.log_step(query_id, "graph_sql_agent", question,
                            f"unsupported_question suggested={grounding.suggested_metrics}", gen_ms)
            yield {"step": "sql_generated", "sql": "", "status": "unsupported",
                   "validation_status": "unsupported", "time_ms": gen_ms}
            words = grounding.note.split()
            for i in range(0, len(words), 8):
                yield {"step": "insight_token", "token": " ".join(words[i:i + 8]) + " "}
            total_ms = int((perf_counter() - total_started) * 1000)
            result = _build_result(
                query_id=query_id, question=question, role=role, context=context,
                sql_result=SQLResult(validation_status="unsupported"),
                exec_result=ExecutionResult(execution_status="skipped_unsupported"),
                insight_meta={"models_used": ["graph_sql_agent"],
                              "business_limitations": "No sanctioned metric matched the question.",
                              "recommended_action": "", "confidence_score": 0.0},
                answer_summary=grounding.note, step_latencies=step_latencies, total_latency_ms=total_ms,
            )
            result["grounding"] = grounding.to_evidence()
            result["answer_status"] = "UNSUPPORTED"
            yield {"step": "complete", "query_id": query_id, "metadata": result}
            return
        if grounding is not None:
            sql_result = grounding.to_sql_result()
            step_latencies["sql_generation_ms"] = grounding.generation_time_ms
            tracer.log_step(
                query_id, "graph_sql_agent", question,
                f"metrics={grounding.metrics_used} bindings={grounding.binding_ids} "
                f"validated={grounding.validation.get('ok')} repaired={grounding.validation.get('repaired')} "
                f"rules={[r.get('name') for r in grounding.applicable_rules][:3]}",
                grounding.generation_time_ms,
            )
            yield {"step": "sql_generated", "sql": sql_result.sql, "status": "done",
                   "validation_status": sql_result.validation_status,
                   "time_ms": grounding.generation_time_ms}
    if grounding is None:
        # ---- legacy free-form path (Prompt 6) — Steps 2+3 in PARALLEL --------
        sql_task = sql_agent.generate_sql(question, role, context)
        preload_task = search_schema(question, top_k=20)  # extra candidates for repair
        sql_result, preload = await asyncio.gather(sql_task, preload_task, return_exceptions=True)
        if isinstance(sql_result, Exception):
            sql_result = SQLResult(validation_status="blocked",
                                   validation_errors=[f"{type(sql_result).__name__}: {sql_result}"])
        if not isinstance(preload, Exception) and preload:
            known = {(s.get("table"), s.get("column")) for s in context.schema_context}
            for item in preload:
                key = (item.get("table_name"), item.get("column_name"))
                if key not in known:
                    context.schema_context.append({
                        "table": item.get("table_name"), "column": item.get("column_name"),
                        "description": item.get("business_description"), "score": item.get("score"),
                    })
        step_latencies["sql_generation_ms"] = sql_result.generation_time_ms or int((perf_counter() - started) * 1000)
        tracer.log_step(
            query_id, "sql_agent", question,
            f"status={sql_result.validation_status} tables={sql_result.tables_used}",
            step_latencies["sql_generation_ms"],
        )
        yield {"step": "sql_generated", "sql": sql_result.sql, "status": "done",
               "validation_status": sql_result.validation_status,
               "time_ms": step_latencies["sql_generation_ms"]}

    # ---- Step 4: execute + validate -----------------------------------------
    exec_result = await execution_agent.execute_and_validate(sql_result.sql, context)
    step_latencies["execution_ms"] = exec_result.execution_time_ms
    tracer.log_step(
        query_id, "execution_agent", sql_result.sql[:200],
        f"status={exec_result.execution_status} rows={exec_result.row_count} repaired={exec_result.repaired}",
        exec_result.execution_time_ms,
    )
    yield {"step": "sql_executed", "status": exec_result.execution_status,
           "row_count": exec_result.row_count, "repaired": exec_result.repaired,
           "time_ms": exec_result.execution_time_ms}

    # ---- Step 5: insight — streams immediately ------------------------------
    insight = await insight_agent.generate_insight(
        question, role, context, sql_result, exec_result,
        applicable_rules=grounding.applicable_rules if grounding is not None else None,
    )
    answer_parts: list[str] = []
    if insight.insight_stream is not None:
        async for token in insight.insight_stream:
            answer_parts.append(token)
            yield {"step": "insight_token", "token": token}
    answer_summary = "".join(answer_parts).strip()
    step_latencies["insight_ms"] = insight.generation_time_ms
    tracer.log_step(
        query_id, "insight_agent", question, answer_summary[:200],
        insight.generation_time_ms, tokens_used=len(answer_summary) // 4,
    )

    total_ms = int((perf_counter() - total_started) * 1000)
    result = _build_result(
        query_id=query_id, question=question, role=role, context=context,
        sql_result=sql_result, exec_result=exec_result,
        insight_meta=insight.metadata(), answer_summary=answer_summary,
        step_latencies=step_latencies, total_latency_ms=total_ms,
    )
    if grounding is not None:
        # Evidence Hub: which metric/binding/view/rules grounded this answer.
        result["grounding"] = grounding.to_evidence()
        result["governed"] = True
    else:
        result["governed"] = not ungoverned
        if ungoverned:
            result["ungoverned"] = True
            result["ungoverned_label"] = "Ungoverned answer — not validated against the semantic model"
    yield {"step": "complete", "query_id": query_id, "metadata": result}


async def run_pipeline(question: str, role: str, query_id: str) -> dict[str, Any]:
    """Non-streaming entry point: drains stream_pipeline and returns PipelineResult."""
    final: dict[str, Any] = {}
    async for event in stream_pipeline(question, role, query_id):
        if event.get("step") == "complete":
            final = event["metadata"]
    return final
