from __future__ import annotations

import pytest

from copilot_orchestration.models import CopilotIntent
from copilot_sql_engine.engine import calculate_confidence, run_sql_engine
from copilot_sql_engine.models import SqlGenerationResult, SqlEngineRequest
from copilot_sql_engine.executor import escape_literal_percent_signs
from copilot_sql_engine.generator import MockSqlProvider
from copilot_sql_engine.safety import SqlValidationError, validate_sql
from text_to_sql_agent.schema import fetch_schema_metadata


def test_validate_allows_select():
    result = validate_sql(
        "select campaign_name from public.campaigns",
        allowed_schemas={"public"},
        row_limit=100,
    )

    assert "public.campaigns" in result.referenced_tables
    assert result.sql.startswith("select * from (")
    assert result.sql.endswith("limit 100")


def test_validate_allows_with_select():
    result = validate_sql(
        """
        with x as (
          select campaign_id from public.campaigns
        )
        select count(*) as campaign_count from x
        """,
        allowed_schemas={"public"},
        row_limit=50,
    )

    assert "public.campaigns" in result.referenced_tables


@pytest.mark.parametrize(
    "sql",
    [
        "insert into public.campaigns(campaign_name) values ('x')",
        "update public.customers set lifecycle_stage = 'active'",
        "delete from public.policies",
        "drop table public.claims",
        "alter table public.customers add column x text",
        "truncate table public.model_scores",
    ],
)
def test_validate_blocks_mutation(sql):
    with pytest.raises(SqlValidationError):
        validate_sql(sql, allowed_schemas={"public"}, row_limit=100)


def test_mock_provider_generates_recommendation_sql():
    provider = MockSqlProvider()
    result = provider.generate_sql(
        question="Which customers should I call this week?",
        intent=CopilotIntent.RECOMMENDATION,
        role_context=None,
        retrieved_context=None,
        schema_metadata="",
        row_limit=100,
    )

    assert "public.next_best_actions" in result.sql
    assert result.confidence_score > 0


def test_confidence_drops_on_failed_execution():
    class Execution:
        execution_status = "failed"
        row_count = 0

    confidence = calculate_confidence(
        classification_confidence=0.9,
        generation_confidence=0.8,
        has_context=True,
        execution=Execution(),
    )

    assert confidence < 0.6


def test_executor_escapes_literal_percent_signs_for_psycopg():
    sql = "select * from public.addresses where lower(city) like '%singapore%'"

    escaped = escape_literal_percent_signs(sql)

    assert "%%singapore%%" in escaped


def test_schema_metadata_query_escapes_pg_prefix_like_pattern():
    class Cursor:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def execute(self, query, params):
            self.query = query
            self.params = params

        def fetchall(self):
            return []

    class Conn:
        def __init__(self):
            self.cursor_obj = Cursor()

        def cursor(self):
            return self.cursor_obj

    conn = Conn()

    fetch_schema_metadata(conn, schemas={"public"})

    assert "pg_%%" in conn.cursor_obj.query


def test_engine_falls_back_when_llm_returns_empty_sql(monkeypatch):
    class EmptyProvider:
        def generate_sql(self, **kwargs):
            return SqlGenerationResult(sql="", generation_explanation="empty", confidence_score=0.1)

        def generate_insight(self, **kwargs):
            raise AssertionError("insight should not be called when execution is disabled")

    class Conn:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def cursor(self):
            return self

        def execute(self, query, params=None):
            self.query = query

        def fetchall(self):
            return []

    monkeypatch.setattr("copilot_sql_engine.engine.build_sql_provider", lambda settings: EmptyProvider())
    monkeypatch.setattr("copilot_sql_engine.engine.connect", lambda database_url: Conn())
    monkeypatch.setattr("copilot_sql_engine.engine.fetch_schema_metadata", lambda conn, schemas: "Table public.policies:")
    monkeypatch.setattr("copilot_sql_engine.engine.ContextRetriever", lambda: None)

    response = run_sql_engine(
        SqlEngineRequest(
            question="What is our current lapse rate?",
            include_context=False,
            include_debug=True,
            execute_sql=False,
        )
    )

    assert response.sql
    assert "public.policies" in response.sql
    assert response.debug["generation_error"] == "ValueError: LLM returned empty SQL"
