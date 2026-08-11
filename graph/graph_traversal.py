"""Graph traversal over the V2 ontology graph.

Primary engine: DuckPGQ SQL/PGQ (registered PROPERTY GRAPH `insurance_graph`).
Every traversal has a recursive-SQL fallback so the module works even when the
DuckPGQ extension cannot load.

All functions open a short-lived read-only connection unless a connection is
passed in.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Iterable

import duckdb

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
DB_PATH = str(PROJECT_ROOT / "database" / "insurance_v2.duckdb")


def _connect(read_only: bool = True) -> duckdb.DuckDBPyConnection:
    from graph.db_util import robust_connect
    con = robust_connect(DB_PATH, read_only=read_only)
    try:
        con.execute("LOAD duckpgq;")
    except Exception:
        try:
            con.execute("INSTALL duckpgq FROM community; LOAD duckpgq;")
        except Exception:
            pass  # fallback paths do not need the extension
    return con


def _quote_list(ids: Iterable[str]) -> str:
    return ",".join("'" + str(i).replace("'", "''") + "'" for i in ids)


# ---------------------------------------------------------------------------
# get_subgraph — N-hop neighbourhood around entry nodes
# ---------------------------------------------------------------------------
def get_subgraph(entry_node_ids: list[str], hops: int = 2,
                 con: duckdb.DuckDBPyConnection | None = None) -> dict[str, Any]:
    """Return {nodes, edges, entry_nodes, hops, engine} for the undirected
    N-hop neighbourhood around the entry nodes."""
    if not entry_node_ids:
        return {"nodes": [], "edges": [], "entry_nodes": [], "hops": hops, "engine": "none"}

    own = con is None
    con = con or _connect()
    try:
        edges, engine = _subgraph_edges(con, entry_node_ids, hops)
        node_ids = set(entry_node_ids)
        for e in edges:
            node_ids.add(e["src"])
            node_ids.add(e["dst"])
        nodes = []
        if node_ids:
            rows = con.execute(
                f"select node_id, node_type, name, subject_area from graph_nodes_all "
                f"where node_id in ({_quote_list(node_ids)})"
            ).fetchall()
            nodes = [{"id": r[0], "type": r[1], "name": r[2], "subject_area": r[3]} for r in rows]
        return {"nodes": nodes, "edges": edges, "entry_nodes": entry_node_ids,
                "hops": hops, "engine": engine}
    finally:
        if own:
            con.close()


def _subgraph_edges(con, entry_node_ids: list[str], hops: int):
    """Try DuckPGQ variable-length MATCH; fall back to recursive SQL."""
    frontier = set(entry_node_ids)
    seen_edges: dict[str, dict] = {}
    try:
        # DuckPGQ: expand hop-by-hop (1..hops) so we can collect intermediate edges.
        for _h in range(hops):
            if not frontier:
                break
            # Adaptation loop (Prompt 13): rank by edge weight DESC and exclude
            # inactive (weight 0 / status inactive) and not-yet-approved
            # (pending_review) edges, so feedback steers what context surfaces.
            rows = con.execute(f"""
                select e.edge_id, e.src_node_id, e.dst_node_id, e.edge_type, coalesce(e.weight, 1.0) as w
                from graph_edges e
                where (e.src_node_id in ({_quote_list(frontier)})
                    or e.dst_node_id in ({_quote_list(frontier)}))
                  and coalesce(e.status, 'active') = 'active'
                  and coalesce(e.weight, 1.0) > 0
                order by w desc
            """).fetchall()
            new_nodes: set[str] = set()
            for eid, src, dst, etype, w in rows:
                if eid not in seen_edges:
                    seen_edges[eid] = {"id": eid, "src": src, "dst": dst,
                                       "type": etype, "weight": w}
                    new_nodes.add(src)
                    new_nodes.add(dst)
            frontier = new_nodes - frontier
        return list(seen_edges.values()), "sql-bfs"
    except Exception:
        # last-ditch recursive CTE (single statement)
        rows = con.execute(f"""
            with recursive reach(node_id, depth) as (
                select unnest([{_quote_list(entry_node_ids)}]), 0
                union
                select case when e.src_node_id = r.node_id then e.dst_node_id else e.src_node_id end, r.depth + 1
                from reach r
                join graph_edges e on e.src_node_id = r.node_id or e.dst_node_id = r.node_id
                where r.depth < {int(hops)}
            )
            select distinct e.edge_id, e.src_node_id, e.dst_node_id, e.edge_type, coalesce(e.weight,1.0) as w
            from graph_edges e
            where e.src_node_id in (select node_id from reach)
              and e.dst_node_id in (select node_id from reach)
              and coalesce(e.status,'active') = 'active'
              and coalesce(e.weight,1.0) > 0
            order by w desc
        """).fetchall()
        return ([{"id": r[0], "src": r[1], "dst": r[2], "type": r[3], "weight": r[4]} for r in rows],
                "recursive-sql")


# ---------------------------------------------------------------------------
# find_decision_paths — decision_rules reachable within N hops of entities
# ---------------------------------------------------------------------------
def find_decision_paths(question_entities: list[str], hops: int = 3,
                        con: duckdb.DuckDBPyConnection | None = None) -> list[dict[str, Any]]:
    if not question_entities:
        return []
    own = con is None
    con = con or _connect()
    try:
        sub = get_subgraph(question_entities, hops=hops, con=con)
        reachable = {n["id"] for n in sub["nodes"]}
        rule_node_ids = [nid for nid in reachable if str(nid).startswith("rule::")]
        # also include rules whose considered metrics are in the subgraph
        metric_ids = {nid for nid in reachable if str(nid).startswith("metric::")}
        results: list[dict[str, Any]] = []
        rules = con.execute(
            "select rule_id, name, condition_text, action_text, assigned_role, priority, status, "
            # threshold_json carries the GOVERNED numbers (e.g. lapse_risk 0.70).
            # Without it downstream, the insight LLM invents its own cut-offs.
            "threshold_json "
            "from decision_rules "
            # Only status='active' governs answers. This used to be an allowlist-by-
            # exclusion (only 'needs_review'/'rejected' were withheld), which meant
            # newly captured 'draft' rules -- never reviewed by anyone -- silently
            # applied as if governing. NULL status is treated as active for rows
            # seeded before the status column existed.
            "where coalesce(status, 'active') = 'active'"
        ).fetchall()
        adj = _adjacency(sub["edges"])
        for rid, name, cond, action, role_, prio, status, thresholds in rules:
            rnode = f"rule::{rid}"
            considered = {e["dst"] for e in sub["edges"] if e["src"] == rnode}
            direct = rnode in rule_node_ids
            via_metric = bool(considered & metric_ids)
            if not (direct or via_metric):
                continue
            path = _explain_path(question_entities, rnode, adj) if direct else None
            if isinstance(thresholds, str):
                try:
                    thresholds = json.loads(thresholds)
                except (ValueError, TypeError):
                    thresholds = {}
            results.append({
                "rule_id": rid, "name": name, "condition_text": cond, "action_text": action,
                "assigned_role": role_, "priority": prio, "status": status,
                "threshold_json": thresholds or {},
                "reached_via": "direct" if direct else "shared_metric",
                "considered_metrics": sorted(considered & metric_ids),
                "path": path,
            })
        results.sort(key=lambda r: (r["priority"] or 99))
        return results
    finally:
        if own:
            con.close()


def _adjacency(edges: list[dict]) -> dict[str, list[tuple[str, str]]]:
    adj: dict[str, list[tuple[str, str]]] = {}
    for e in edges:
        adj.setdefault(e["src"], []).append((e["dst"], e["type"]))
        adj.setdefault(e["dst"], []).append((e["src"], e["type"]))
    return adj


def _explain_path(starts: list[str], target: str, adj: dict[str, list[tuple[str, str]]]) -> list[str] | None:
    """BFS shortest path from any start to target, rendered as readable steps."""
    from collections import deque
    starts_in = [s for s in starts if s in adj] or starts
    q = deque((s, [s]) for s in starts_in)
    visited = set(starts_in)
    while q:
        node, path = q.popleft()
        if node == target:
            return path
        for nbr, etype in adj.get(node, []):
            if nbr not in visited:
                visited.add(nbr)
                q.append((nbr, path + [f"-{etype}->", nbr]))
    return None


# ---------------------------------------------------------------------------
# cross_domain_scan — nodes bridging 2+ subject areas
# ---------------------------------------------------------------------------
def cross_domain_scan(min_areas: int = 2, limit: int = 50,
                      con: duckdb.DuckDBPyConnection | None = None) -> list[dict[str, Any]]:
    """Find concept nodes whose neighbours span 2+ subject areas — the
    'new combined decision' discovery pattern."""
    own = con is None
    con = con or _connect()
    try:
        rows = con.execute(f"""
            with neighbours as (
                select e.src_node_id as node_id, nd.subject_area as area
                from graph_edges e
                join graph_nodes_all ns on ns.node_id = e.src_node_id
                join graph_nodes_all nd on nd.node_id = e.dst_node_id
                where ns.node_type in ('metric','process','decision','term','entity_class')
                union all
                select e.dst_node_id as node_id, ns.subject_area as area
                from graph_edges e
                join graph_nodes_all ns on ns.node_id = e.src_node_id
                join graph_nodes_all nd on nd.node_id = e.dst_node_id
                where nd.node_type in ('metric','process','decision','term','entity_class')
            )
            select n.node_id, an.node_type, an.name,
                   count(distinct n.area) as area_count,
                   string_agg(distinct n.area, ', ') as areas
            from neighbours n
            join graph_nodes_all an on an.node_id = n.node_id
            where n.area is not null
            group by 1,2,3
            having count(distinct n.area) >= {int(min_areas)}
            order by area_count desc, n.node_id
            limit {int(limit)}
        """).fetchall()
        return [{"node_id": r[0], "node_type": r[1], "name": r[2],
                 "area_count": r[3], "areas": r[4]} for r in rows]
    finally:
        if own:
            con.close()


# ---------------------------------------------------------------------------
# to_networkx
# ---------------------------------------------------------------------------
def to_networkx(con: duckdb.DuckDBPyConnection | None = None):
    """Load graph_edges into a NetworkX DiGraph (node attrs from graph_nodes_all)."""
    import networkx as nx

    own = con is None
    con = con or _connect()
    try:
        g = nx.DiGraph()
        for nid, ntype, name, area in con.execute(
            "select node_id, node_type, name, subject_area from graph_nodes_all"
        ).fetchall():
            g.add_node(nid, type=ntype, name=name, subject_area=area)
        for src, dst, etype, w in con.execute(
            "select src_node_id, dst_node_id, edge_type, weight from graph_edges"
        ).fetchall():
            g.add_edge(src, dst, type=etype, weight=w)
        return g
    finally:
        if own:
            con.close()


# ---------------------------------------------------------------------------
# export_graph_json — for a frontend force-directed view
# ---------------------------------------------------------------------------
def export_graph_json(subgraph: dict[str, Any]) -> dict[str, Any]:
    nodes = [
        {"id": n["id"], "label": n.get("name") or n["id"], "type": n.get("type"),
         "group": n.get("subject_area") or n.get("type")}
        for n in subgraph.get("nodes", [])
    ]
    links = [
        {"source": e["src"], "target": e["dst"], "type": e["type"]}
        for e in subgraph.get("edges", [])
    ]
    return {"nodes": nodes, "links": links}


if __name__ == "__main__":
    entity = sys.argv[1] if len(sys.argv) > 1 else None
    con = _connect()
    if not entity:
        entity = con.execute("select customer_id from customers limit 1").fetchone()[0]
    print(f"Subgraph for {entity} (2 hops):")
    sg = get_subgraph([entity], hops=2, con=con)
    print(f"  engine={sg['engine']} nodes={len(sg['nodes'])} edges={len(sg['edges'])}")
    print("Decision paths:")
    for p in find_decision_paths([entity], con=con):
        print(f"  [{p['priority']}] {p['name']} ({p['reached_via']}) -> {p['action_text']}")
    print("Cross-domain discoveries (top 5):")
    for d in cross_domain_scan(con=con)[:5]:
        print(f"  {d['name']} spans {d['area_count']} areas: {d['areas']}")
    con.close()
