"""GraphRAG context retrieval = LanceDB vector recall + DuckPGQ graph traversal.

Standalone module (does NOT modify backend_v2/agents/context_agent.py). The
orchestrator can import get_graph_context and run it as an extra parallel
branch alongside the existing 4-way vector context.

Flow:
  1. vector search (embeddings.vector_search.search_all) -> top concept hits
  2. map hits -> ontology node_ids -> get_subgraph(hops=2)   (concept-level
     entry nodes keep the neighbourhood small; entity fan-out is avoided)
  3. find_decision_paths for any decision_rules in the subgraph
  4. return a structured GraphContext (compact triples + applicable rules)
"""
from __future__ import annotations

import asyncio
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from graph import graph_traversal as gt  # noqa: E402

MAX_TRIPLES = 40


@dataclass
class GraphContext:
    entry_nodes: list[dict[str, Any]] = field(default_factory=list)
    subgraph_summary: list[str] = field(default_factory=list)   # compact triples
    applicable_rules: list[dict[str, Any]] = field(default_factory=list)
    traversal_path: list[str] | None = None
    engine: str = "none"
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "entry_nodes": self.entry_nodes,
            "subgraph_summary": self.subgraph_summary,
            "applicable_rules": self.applicable_rules,
            "traversal_path": self.traversal_path,
            "engine": self.engine,
            "errors": self.errors,
        }


def _slug(term: str) -> str:
    return term.lower().strip().replace(" ", "_").replace("(", "").replace(")", "")


def _map_hits_to_nodes(con, vector_results: dict[str, Any], question: str) -> list[str]:
    """Resolve vector hits + question keywords to concept node_ids that exist."""
    candidates: set[str] = set()
    for g in vector_results.get("glossary", []) or []:
        if g.get("term"):
            candidates.add(f"term::{_slug(g['term'])}")
    for s in vector_results.get("schema", []) or []:
        t, c = s.get("table_name"), s.get("column_name")
        if t and c:
            candidates.add(f"column::{t}.{c}")
    # metric keyword hints straight from the question
    ql = question.lower()
    for metric in ["lapse_rate", "lapse_risk", "persistency", "premium_at_risk",
                   "campaign_conversion", "propensity_to_buy", "clv",
                   "agent_target_achievement"]:
        if metric.replace("_", " ") in ql or metric in ql:
            candidates.add(f"metric::{metric}")
    if not candidates:
        return []
    rows = con.execute(
        f"select node_id from graph_nodes_all where node_id in ({gt._quote_list(candidates)})"
    ).fetchall()
    return [r[0] for r in rows]


def _compact_triples(con, subgraph: dict[str, Any]) -> list[str]:
    names = {n["id"]: (n.get("name") or n["id"]) for n in subgraph.get("nodes", [])}
    triples: list[str] = []
    # prefer edges among concept/decision/metric/process nodes (most meaningful)
    concept_types = {"term", "metric", "process", "decision", "entity_class"}
    typed = {n["id"]: n.get("type") for n in subgraph.get("nodes", [])}
    ranked = sorted(
        subgraph.get("edges", []),
        key=lambda e: 0 if (typed.get(e["src"]) in concept_types and typed.get(e["dst"]) in concept_types) else 1,
    )
    for e in ranked[:MAX_TRIPLES]:
        src = names.get(e["src"], e["src"])
        dst = names.get(e["dst"], e["dst"])
        w = f" ({round(e['weight'], 3)})" if isinstance(e.get("weight"), (int, float)) else ""
        triples.append(f"{src} -{e['type']}-> {dst}{w}")
    return triples


def _sync_graph_context(question: str, role: str, vector_results: dict[str, Any]) -> GraphContext:
    ctx = GraphContext()
    con = gt._connect()
    try:
        entry_ids = _map_hits_to_nodes(con, vector_results, question)
        if not entry_ids:
            ctx.errors.append("no concept nodes matched the question")
            return ctx
        rows = con.execute(
            f"select node_id, node_type, name, subject_area from graph_nodes_all "
            f"where node_id in ({gt._quote_list(entry_ids)})"
        ).fetchall()
        ctx.entry_nodes = [{"id": r[0], "type": r[1], "name": r[2], "subject_area": r[3]} for r in rows]

        sub = gt.get_subgraph(entry_ids, hops=2, con=con)
        ctx.engine = sub["engine"]
        ctx.subgraph_summary = _compact_triples(con, sub)

        rules = gt.find_decision_paths(entry_ids, hops=3, con=con)
        ctx.applicable_rules = [
            {"name": r["name"], "condition_text": r["condition_text"],
             "action_text": r["action_text"], "assigned_role": r["assigned_role"],
             "priority": r["priority"], "reached_via": r["reached_via"]}
            for r in rules
        ]
        if rules and rules[0].get("path"):
            ctx.traversal_path = rules[0]["path"]
        return ctx
    except Exception as exc:  # pragma: no cover
        ctx.errors.append(f"{type(exc).__name__}: {exc}")
        return ctx
    finally:
        con.close()


async def get_graph_context(question: str, role: str) -> GraphContext:
    """Async GraphRAG entry point. Runs the (sync) vector search + DuckDB
    traversal in worker threads so it can be gathered alongside other agents."""
    try:
        from embeddings.vector_search import search_all
        vector_results = await search_all(question, role, top_k=5)
    except Exception as exc:
        vector_results = {}
        # continue with keyword-only mapping
        ctx = await asyncio.to_thread(_sync_graph_context, question, role, vector_results)
        ctx.errors.append(f"vector_search unavailable: {type(exc).__name__}")
        return ctx
    return await asyncio.to_thread(_sync_graph_context, question, role, vector_results)


if __name__ == "__main__":
    q = sys.argv[1] if len(sys.argv) > 1 else "Which policies have high lapse risk and big premium at risk?"
    out = asyncio.run(get_graph_context(q, "Agency Manager"))
    print("QUESTION:", q)
    print("ENGINE:", out.engine)
    print("ENTRY NODES:", [n["name"] for n in out.entry_nodes])
    print("\nSUBGRAPH TRIPLES:")
    for t in out.subgraph_summary[:15]:
        print("  ", t)
    print("\nAPPLICABLE RULES:")
    for r in out.applicable_rules:
        print(f"   [{r['priority']}] {r['name']} -> {r['action_text']} ({r['assigned_role']})")
    if out.traversal_path:
        print("\nTRAVERSAL PATH:", " ".join(out.traversal_path))
    if out.errors:
        print("\nERRORS:", out.errors)
