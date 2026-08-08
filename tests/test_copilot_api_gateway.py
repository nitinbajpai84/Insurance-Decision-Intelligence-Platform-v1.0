from __future__ import annotations

from copilot_api_gateway.api import app


def test_openapi_contains_requested_routes():
    schema = app.openapi()
    paths = schema["paths"]

    expected = [
        "/copilot/ask",
        "/intent/classify",
        "/context/search",
        "/sql/validate",
        "/sql/execute",
        "/customers/{id}/360",
        "/agents/{id}/360",
        "/campaigns/{id}/360",
        "/claims/{id}/360",
        "/roles",
        "/roles/{role}/dashboard",
        "/recommendations/{entity_id}",
        "/lineage/{insight_id}",
    ]

    for path in expected:
        assert path in paths


def test_sql_validate_schema_present():
    schema = app.openapi()

    assert "SqlValidateRequest" in schema["components"]["schemas"]
    assert "SqlValidateResponse" in schema["components"]["schemas"]

