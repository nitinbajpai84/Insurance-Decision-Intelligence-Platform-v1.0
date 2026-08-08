"""Governed feedback engine for the ontology graph (Prompt 13).

Behavioural contract:
  * Lightweight signals (edge confirm/reject, node confirm/reject, answer thumbs)
    are AUTO-APPLIED — they nudge edge weights or cache hygiene immediately and
    are logged (status='auto_applied').
  * Structural signals (node edit, missing relationship, proposed edge) are
    NEVER silently applied — they enter the review queue (status='pending_review')
    and only take effect after apply_review(approve).
  * Every change is audited (agent_reasoning_log) and reversible (old values are
    logged: edge_weight_log for weights, the audit trail for definitions).
"""
from __future__ import annotations

import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import duckdb

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

DB_PATH = str(PROJECT_ROOT / "database" / "insurance_v2.duckdb")
SCHEMA_FILE = SCRIPT_DIR / "feedback_schema.sql"

WEIGHT_CONFIRM_STEP = 0.1
WEIGHT_REJECT_STEP = 0.3
WEIGHT_MAX = 2.0
WEIGHT_MIN = 0.0


def _connect() -> duckdb.DuckDBPyConnection:
    from graph.db_util import robust_connect
    return robust_connect(DB_PATH, read_only=False)


def ensure_feedback_schema(con: duckdb.DuckDBPyConnection | None = None) -> None:
    own = con is None
    con = con or _connect()
    try:
        con.execute(SCHEMA_FILE.read_text(encoding="utf-8"))
        con.commit()
    finally:
        if own:
            con.close()


def _audit(con, action: str, summary: str, query_id: str | None = None) -> None:
    """Best-effort audit row into agent_reasoning_log (never raises)."""
    try:
        con.execute(
            "insert into agent_reasoning_log "
            "(query_id, agent_name, input_summary, output_summary, duration_ms, tokens_used, cache_hit, created_at) "
            "values (?,?,?,?,?,?,?,?)",
            [query_id or f"feedback-{uuid.uuid4()}", "feedback_engine", action,
             summary[:1000], 0, 0, False, datetime.now()],
        )
    except Exception as exc:  # pragma: no cover
        print(f"[feedback] audit warn: {exc}", file=sys.stderr)


# ---------------------------------------------------------------------------
# Edge weight adjustment (shared)
# ---------------------------------------------------------------------------
def _adjust_edge_weight(con, edge_id: str, delta: float, reason: str) -> dict[str, Any] | None:
    row = con.execute("select coalesce(weight,1.0), status from graph_edges where edge_id = ?",
                      [edge_id]).fetchone()
    if not row:
        return None
    old_w = float(row[0])
    new_w = max(WEIGHT_MIN, min(WEIGHT_MAX, round(old_w + delta, 4)))
    new_status = "inactive" if new_w <= WEIGHT_MIN else ("active" if row[1] != "pending_review" else row[1])
    con.execute("update graph_edges set weight = ?, status = ? where edge_id = ?",
                [new_w, new_status, edge_id])
    con.execute("insert into edge_weight_log (edge_id, old_weight, new_weight, reason) values (?,?,?,?)",
                [edge_id, old_w, new_w, reason])
    return {"edge_id": edge_id, "old_weight": old_w, "new_weight": new_w, "status": new_status}


# ---------------------------------------------------------------------------
# Node feedback
# ---------------------------------------------------------------------------
def record_node_feedback(node_id: str, feedback_type: str, rating: int | None = None,
                         comment: str | None = None, proposed_change: dict | None = None,
                         user: str = "console.user", user_role: str = "Data Analyst") -> dict[str, Any]:
    con = _connect()
    try:
        ensure_feedback_schema(con)
        fid = str(uuid.uuid4())
        structural = feedback_type in ("edit", "missing")
        status = "pending_review" if structural else "auto_applied"
        con.execute(
            "insert into graph_feedback (feedback_id, target_type, target_id, feedback_type, rating, comment, "
            "proposed_change, user_id, user_role, status) values (?,?,?,?,?,?,?,?,?,?)",
            [fid, "node", node_id, feedback_type, rating, comment,
             json.dumps(proposed_change) if proposed_change else None, user, user_role, status],
        )
        adjustments: list[dict] = []
        if not structural:
            # confirm/reject → nudge weights of edges touching this node
            delta = WEIGHT_CONFIRM_STEP if feedback_type == "confirm" else -WEIGHT_REJECT_STEP
            edges = con.execute(
                "select edge_id from graph_edges where (src_node_id = ? or dst_node_id = ?) "
                "and coalesce(status,'active') <> 'pending_review'", [node_id, node_id]
            ).fetchall()
            for (eid,) in edges:
                adj = _adjust_edge_weight(con, eid, delta, "feedback")
                if adj:
                    adjustments.append(adj)
        con.commit()
        _audit(con, f"node_feedback:{feedback_type}",
               f"node={node_id} status={status} edges_adjusted={len(adjustments)} by={user}")
        con.commit()
        return {"feedback_id": fid, "status": status, "structural": structural,
                "edges_adjusted": len(adjustments), "adjustments": adjustments}
    finally:
        con.close()


# ---------------------------------------------------------------------------
# Edge feedback
# ---------------------------------------------------------------------------
def record_edge_feedback(edge_id: str, feedback_type: str, rating: int | None = None,
                         user: str = "console.user", user_role: str = "Data Analyst") -> dict[str, Any]:
    con = _connect()
    try:
        ensure_feedback_schema(con)
        delta = WEIGHT_CONFIRM_STEP if feedback_type == "confirm" else -WEIGHT_REJECT_STEP
        adj = _adjust_edge_weight(con, edge_id, delta, "feedback")
        if adj is None:
            con.close()
            return {"error": "edge_not_found", "edge_id": edge_id}
        fid = str(uuid.uuid4())
        con.execute(
            "insert into graph_feedback (feedback_id, target_type, target_id, feedback_type, rating, "
            "user_id, user_role, status) values (?,?,?,?,?,?,?,?)",
            [fid, "edge", edge_id, feedback_type, rating, user, user_role, "auto_applied"],
        )
        con.commit()
        _audit(con, f"edge_feedback:{feedback_type}",
               f"edge={edge_id} {adj['old_weight']}->{adj['new_weight']} status={adj['status']} by={user}")
        con.commit()
        return {"feedback_id": fid, "status": "auto_applied", **adj}
    finally:
        con.close()


# ---------------------------------------------------------------------------
# Rule feedback (confirm keeps active; reject -> needs_review => excluded from retrieval)
# ---------------------------------------------------------------------------
def record_rule_feedback(rule_id: str, feedback_type: str, rating: int | None = None,
                         user: str = "console.user", user_role: str = "Data Analyst") -> dict[str, Any]:
    con = _connect()
    try:
        ensure_feedback_schema(con)
        new_status = "active" if feedback_type == "confirm" else "needs_review"
        con.execute("update decision_rules set status = ? where rule_id = ?", [new_status, rule_id])
        fid = str(uuid.uuid4())
        con.execute(
            "insert into graph_feedback (feedback_id, target_type, target_id, feedback_type, rating, "
            "user_id, user_role, status) values (?,?,?,?,?,?,?,?)",
            [fid, "rule", rule_id, feedback_type, rating, user, user_role, "auto_applied"],
        )
        con.commit()
        _audit(con, f"rule_feedback:{feedback_type}", f"rule={rule_id} -> {new_status} by={user}")
        con.commit()
        return {"feedback_id": fid, "status": "auto_applied", "rule_status": new_status}
    finally:
        con.close()


# ---------------------------------------------------------------------------
# Answer feedback → semantic-cache hygiene
# ---------------------------------------------------------------------------
def record_answer_feedback(query_id: str, thumbs: str, comment: str | None = None,
                           rating: int | None = None, role: str | None = None) -> dict[str, Any]:
    con = _connect()
    try:
        ensure_feedback_schema(con)
        # resolve the question text from the reasoning trace
        q = con.execute(
            "select input_summary from agent_reasoning_log where query_id = ? and agent_name = 'context_agent' limit 1",
            [query_id]).fetchone()
        question = q[0] if q else None
        applied = False
        detail = ""
        if question:
            try:
                applied, detail = _apply_cache_change(question, thumbs)
            except Exception as exc:  # pragma: no cover
                detail = f"cache change failed: {type(exc).__name__}: {exc}"
        af_id = str(uuid.uuid4())
        con.execute(
            "insert into answer_feedback (af_id, query_id, question, role, rating, thumbs, comment, applied_to_cache) "
            "values (?,?,?,?,?,?,?,?)",
            [af_id, query_id, question, role, rating, thumbs, comment, applied],
        )
        con.commit()
        _audit(con, f"answer_feedback:{thumbs}", f"query={query_id} applied_to_cache={applied} {detail}", query_id)
        con.commit()
        return {"af_id": af_id, "thumbs": thumbs, "applied_to_cache": applied, "detail": detail}
    finally:
        con.close()


def _apply_cache_change(question: str, thumbs: str) -> tuple[bool, str]:
    """down → delete the Q&A from insurance_query_history; up → flag confidence boost."""
    import lancedb
    from embeddings.vector_search import LANCEDB_PATH

    db = lancedb.connect(LANCEDB_PATH)
    tbl = db.open_table("insurance_query_history")
    safe_q = question.replace("'", "''")
    if thumbs == "down":
        tbl.delete(f"question = '{safe_q}'")
        return True, "removed from semantic cache"
    # up → boost: re-write rows with a confidence flag in metadata (best-effort)
    rows = tbl.search().where(f"question = '{safe_q}'").limit(5).to_list()
    if not rows:
        return False, "no cache entry to boost"
    tbl.delete(f"question = '{safe_q}'")
    for r in rows:
        try:
            meta = json.loads(r.get("metadata") or "{}")
        except Exception:
            meta = {}
        meta["confidence_boost"] = True
        r["metadata"] = json.dumps(meta)
        r["confidence_score"] = min(1.0, float(r.get("confidence_score") or 0.7) + 0.1)
    tbl.add(rows)
    return True, "confidence boosted on cached entry"


# ---------------------------------------------------------------------------
# Propose a missing edge (structural → review)
# ---------------------------------------------------------------------------
def propose_edge(src: str, dst: str, edge_type: str, user: str = "console.user",
                 user_role: str = "Data Analyst", comment: str | None = None) -> dict[str, Any]:
    con = _connect()
    try:
        ensure_feedback_schema(con)
        # endpoints must exist as vertices
        for nid in (src, dst):
            if not con.execute("select 1 from graph_nodes_all where node_id = ?", [nid]).fetchone():
                con.close()
                return {"error": "node_not_found", "node_id": nid}
        edge_id = str(uuid.uuid4())
        src_type = con.execute("select node_type from graph_nodes_all where node_id = ?", [src]).fetchone()[0]
        dst_type = con.execute("select node_type from graph_nodes_all where node_id = ?", [dst]).fetchone()[0]
        con.execute(
            "insert into graph_edges (edge_id, src_node_id, src_node_type, dst_node_id, dst_node_type, "
            "edge_type, weight, status) values (?,?,?,?,?,?,?,?)",
            [edge_id, src, src_type, dst, dst_type, edge_type, 1.0, "pending_review"],
        )
        fid = str(uuid.uuid4())
        con.execute(
            "insert into graph_feedback (feedback_id, target_type, target_id, feedback_type, proposed_change, "
            "comment, user_id, user_role, status) values (?,?,?,?,?,?,?,?,?)",
            [fid, "edge", edge_id, "missing",
             json.dumps({"src": src, "dst": dst, "edge_type": edge_type}), comment, user, user_role, "pending_review"],
        )
        con.commit()
        _audit(con, "propose_edge", f"{src} -{edge_type}-> {dst} edge={edge_id} (pending_review) by={user}")
        con.commit()
        return {"feedback_id": fid, "edge_id": edge_id, "status": "pending_review",
                "src": src, "dst": dst, "edge_type": edge_type}
    finally:
        con.close()


# ---------------------------------------------------------------------------
# Review queue + apply
# ---------------------------------------------------------------------------
def get_review_queue() -> list[dict[str, Any]]:
    con = _connect()
    try:
        ensure_feedback_schema(con)
        rows = con.execute(
            "select feedback_id, target_type, target_id, feedback_type, comment, proposed_change, "
            "user_id, user_role, created_at from graph_feedback where status = 'pending_review' "
            "order by created_at desc"
        ).fetchall()
        out = []
        for r in rows:
            item = {"feedback_id": r[0], "target_type": r[1], "target_id": r[2], "feedback_type": r[3],
                    "comment": r[4], "proposed_change": json.loads(r[5]) if r[5] else None,
                    "user_id": r[6], "user_role": r[7],
                    "created_at": r[8].isoformat() if hasattr(r[8], "isoformat") else r[8]}
            # enrich with the node/edge label
            if r[1] == "node":
                nm = con.execute("select name, definition from concept_nodes where node_id = ?", [r[2]]).fetchone()
                if nm:
                    item["target_name"] = nm[0]
                    item["current_definition"] = nm[1]
            out.append(item)
        return out
    finally:
        con.close()


def apply_review(feedback_id: str, decision: str, reviewer: str = "reviewer") -> dict[str, Any]:
    con = _connect()
    try:
        ensure_feedback_schema(con)
        fb = con.execute(
            "select target_type, target_id, feedback_type, proposed_change, status from graph_feedback "
            "where feedback_id = ?", [feedback_id]).fetchone()
        if not fb:
            con.close()
            return {"error": "feedback_not_found", "feedback_id": feedback_id}
        target_type, target_id, feedback_type, proposed_raw, status = fb
        if status != "pending_review":
            con.close()
            return {"error": "not_pending", "current_status": status}
        proposed = json.loads(proposed_raw) if proposed_raw else {}
        now = datetime.now()

        if decision not in ("approve", "approved", "reject", "rejected"):
            con.close()
            return {"error": "bad_decision", "decision": decision}
        approving = decision in ("approve", "approved")

        result: dict[str, Any] = {"feedback_id": feedback_id, "decision": "approved" if approving else "rejected"}

        if not approving:
            con.execute(
                "update graph_feedback set status='rejected', reviewed_by=?, reviewed_at=? where feedback_id=?",
                [reviewer, now, feedback_id])
            con.commit()
            _audit(con, "review:reject", f"feedback={feedback_id} target={target_type}:{target_id} by={reviewer}")
            con.commit()
            return result

        # ---- approve paths ----
        if target_type == "node" and feedback_type == "edit":
            field = proposed.get("field", "definition")
            new_value = proposed.get("value") or proposed.get("definition") or proposed.get(field)
            old = con.execute(f"select {field} from concept_nodes where node_id = ?", [target_id]).fetchone()
            old_value = old[0] if old else None
            con.execute(f"update concept_nodes set {field} = ?, updated_at = ? where node_id = ?",
                        [new_value, now, target_id])
            reembedded, embed_detail = _reembed_node(con, target_id)
            result.update({"action": "node_edited", "field": field, "old_value": old_value,
                           "new_value": new_value, "reembedded": reembedded, "embed_detail": embed_detail})
            _audit(con, "review:approve_edit",
                   f"node={target_id} {field}: '{str(old_value)[:80]}' -> '{str(new_value)[:80]}' reembedded={reembedded} by={reviewer}")

        elif target_type == "edge" and feedback_type == "missing":
            con.execute("update graph_edges set status='active' where edge_id = ?", [target_id])
            result.update({"action": "edge_activated", "edge_id": target_id})
            _audit(con, "review:approve_edge", f"edge={target_id} activated by={reviewer}")

        elif target_type == "node" and feedback_type == "missing":
            src = proposed.get("src", target_id)
            dst = proposed.get("dst")
            etype = proposed.get("edge_type", "informs")
            new_edge = str(uuid.uuid4())
            con.execute(
                "insert into graph_edges (edge_id, src_node_id, src_node_type, dst_node_id, dst_node_type, "
                "edge_type, weight, status) select ?, ?, n1.node_type, ?, n2.node_type, ?, 1.0, 'active' "
                "from graph_nodes_all n1, graph_nodes_all n2 where n1.node_id=? and n2.node_id=?",
                [new_edge, src, dst, etype, src, dst])
            result.update({"action": "edge_created", "edge_id": new_edge, "src": src, "dst": dst, "edge_type": etype})
            _audit(con, "review:approve_missing_edge", f"{src} -{etype}-> {dst} edge={new_edge} by={reviewer}")

        con.execute(
            "update graph_feedback set status='approved', reviewed_by=?, reviewed_at=? where feedback_id=?",
            [reviewer, now, feedback_id])
        con.commit()
        _audit(con, "review:committed", f"feedback={feedback_id}")
        con.commit()
        return result
    finally:
        con.close()


def _reembed_node(con, node_id: str) -> tuple[bool, str]:
    """Re-embed an edited concept node into insurance_glossary_vectors (best-effort)."""
    try:
        import lancedb
        from embeddings.vector_search import LANCEDB_PATH, embed_text

        row = con.execute(
            "select name, definition, coalesce(subject_area,''), coalesce(formula,'') "
            "from concept_nodes where node_id = ?", [node_id]).fetchone()
        if not row:
            return False, "node not found"
        name, definition, area, formula = row
        text = f"{name} | {definition} | domain={area}; formula={formula}"
        vector = embed_text(text)
        db = lancedb.connect(LANCEDB_PATH)
        tbl = db.open_table("insurance_glossary_vectors")
        tbl.delete(f"record_id = '{str(node_id).replace(chr(39), chr(39)*2)}'")
        tbl.add([{
            "id": str(uuid.uuid4()), "term": name, "definition": definition,
            "business_context": f"domain={area}; formula={formula}", "subject_area": area,
            "source_table": "concept_nodes", "record_id": str(node_id), "text_chunk": text,
            "metadata": json.dumps({"reembedded_from": "graph_feedback"}), "vector": vector,
        }])
        return True, "re-embedded into insurance_glossary_vectors"
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"


# ---------------------------------------------------------------------------
# Adaptation log (transparency)
# ---------------------------------------------------------------------------
def adaptation_log(limit: int = 50) -> list[dict[str, Any]]:
    con = _connect()
    try:
        ensure_feedback_schema(con)
        items: list[dict[str, Any]] = []
        for r in con.execute(
            "select edge_id, old_weight, new_weight, reason, changed_at from edge_weight_log "
            "order by changed_at desc limit ?", [limit]).fetchall():
            items.append({"kind": "edge_weight", "edge_id": r[0], "old_weight": r[1], "new_weight": r[2],
                          "reason": r[3], "at": r[4].isoformat() if hasattr(r[4], "isoformat") else r[4]})
        for r in con.execute(
            "select feedback_id, target_type, target_id, feedback_type, status, reviewed_by, "
            "coalesce(reviewed_at, created_at) from graph_feedback where status in ('auto_applied','approved') "
            "order by coalesce(reviewed_at, created_at) desc limit ?", [limit]).fetchall():
            items.append({"kind": "feedback", "feedback_id": r[0], "target_type": r[1], "target_id": r[2],
                          "feedback_type": r[3], "status": r[4], "by": r[5],
                          "at": r[6].isoformat() if hasattr(r[6], "isoformat") else r[6]})
        for r in con.execute(
            "select af_id, query_id, thumbs, applied_to_cache, created_at from answer_feedback "
            "where applied_to_cache order by created_at desc limit ?", [limit]).fetchall():
            items.append({"kind": "cache", "af_id": r[0], "query_id": r[1], "thumbs": r[2],
                          "applied_to_cache": r[3], "at": r[4].isoformat() if hasattr(r[4], "isoformat") else r[4]})
        items.sort(key=lambda x: str(x.get("at") or ""), reverse=True)
        return items[:limit]
    finally:
        con.close()


def node_detail(node_id: str) -> dict[str, Any]:
    con = _connect()
    try:
        ensure_feedback_schema(con)
        n = con.execute(
            "select node_id, node_type, name, definition, formula, default_grain, subject_area, owner_role, "
            "source_glossary_id, updated_at from concept_nodes where node_id = ?", [node_id]).fetchone()
        if not n:
            # maybe a hydrated entity node
            e = con.execute("select node_id, node_type, name, subject_area from graph_nodes_all where node_id = ?",
                            [node_id]).fetchone()
            if not e:
                return {"error": "node_not_found", "node_id": node_id}
            base = {"node_id": e[0], "node_type": e[1], "name": e[2], "subject_area": e[3],
                    "definition": None, "formula": None, "owner_role": None, "updated_at": None}
        else:
            base = {"node_id": n[0], "node_type": n[1], "name": n[2], "definition": n[3], "formula": n[4],
                    "default_grain": n[5], "subject_area": n[6], "owner_role": n[7],
                    "source_glossary_id": n[8],
                    "updated_at": n[9].isoformat() if hasattr(n[9], "isoformat") else n[9]}
        # source tables/columns = defined_by edges to column:: nodes
        srcs = con.execute(
            "select dst_node_id from graph_edges where src_node_id = ? and edge_type = 'defined_by'",
            [node_id]).fetchall()
        base["source_columns"] = [s[0].replace("column::", "") for s in srcs]
        # connected edges
        edges = con.execute(
            "select edge_id, src_node_id, dst_node_id, edge_type, coalesce(weight,1.0), coalesce(status,'active') "
            "from graph_edges where (src_node_id = ? or dst_node_id = ?) and coalesce(status,'active') <> 'inactive' "
            "order by coalesce(weight,1.0) desc limit 60", [node_id, node_id]).fetchall()
        names = {}
        ids = {e[1] for e in edges} | {e[2] for e in edges}
        if ids:
            ph = ",".join("?" * len(ids))
            for nid, nm in con.execute(f"select node_id, name from graph_nodes_all where node_id in ({ph})",
                                       list(ids)).fetchall():
                names[nid] = nm
        base["connected_edges"] = [
            {"edge_id": e[0], "src": e[1], "src_name": names.get(e[1], e[1]),
             "dst": e[2], "dst_name": names.get(e[2], e[2]), "edge_type": e[3],
             "weight": e[4], "status": e[5], "direction": "out" if e[1] == node_id else "in"}
            for e in edges]
        # feedback history
        fb = con.execute(
            "select feedback_type, rating, comment, status, user_id, created_at from graph_feedback "
            "where target_type='node' and target_id = ? order by created_at desc limit 20", [node_id]).fetchall()
        base["feedback_history"] = [
            {"feedback_type": f[0], "rating": f[1], "comment": f[2], "status": f[3], "user_id": f[4],
             "created_at": f[5].isoformat() if hasattr(f[5], "isoformat") else f[5]} for f in fb]
        # health = avg rating
        h = con.execute(
            "select avg(rating) from graph_feedback where target_type='node' and target_id=? and rating is not null",
            [node_id]).fetchone()
        base["health"] = round(float(h[0]), 2) if h and h[0] is not None else None
        base["last_adapted"] = base.get("updated_at")
        return base
    finally:
        con.close()


def node_health_map() -> dict[str, float]:
    """avg rating per node_id (for the model viz 'health' field)."""
    con = _connect()
    try:
        ensure_feedback_schema(con)
        rows = con.execute(
            "select target_id, avg(rating) from graph_feedback where target_type='node' and rating is not null "
            "group by target_id").fetchall()
        return {r[0]: round(float(r[1]), 2) for r in rows if r[1] is not None}
    finally:
        con.close()


if __name__ == "__main__":
    ensure_feedback_schema()
    print("feedback schema ensured.")
