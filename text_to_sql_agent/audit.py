from __future__ import annotations

from typing import Any


def create_audit_log(
    conn,
    *,
    question: str,
    semantic_document_ids: list[str],
) -> str | None:
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                insert into public.query_audit_log (
                  question,
                  retrieved_semantic_document_ids,
                  execution_status,
                  safety_decision
                )
                values (%s, %s::uuid[], 'started', 'pending')
                returning query_audit_log_id::text
                """,
                (question, semantic_document_ids),
            )
            row = cur.fetchone()
        conn.commit()
        return row["query_audit_log_id"] if row else None
    except Exception as exc:
        conn.rollback()
        print(f"Audit insert failed: {exc}")
        return None


def update_audit_log(
    conn,
    *,
    audit_id: str | None,
    generated_sql: str | None,
    execution_status: str,
    safety_decision: str,
    error_message: str | None = None,
    row_count: int | None = None,
    duration_ms: int | None = None,
) -> None:
    if not audit_id:
        return
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                update public.query_audit_log
                set generated_sql = %s,
                    execution_status = %s,
                    safety_decision = %s,
                    error_message = %s,
                    row_count = %s,
                    duration_ms = %s,
                    updated_at = now()
                where query_audit_log_id = %s::uuid
                """,
                (generated_sql, execution_status, safety_decision, error_message, row_count, duration_ms, audit_id),
            )
        conn.commit()
    except Exception as exc:
        conn.rollback()
        print(f"Audit update failed: {exc}")


def json_safe_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result = []
    for row in rows:
        result.append({key: str(value) if not isinstance(value, (str, int, float, bool, type(None))) else value for key, value in row.items()})
    return result
