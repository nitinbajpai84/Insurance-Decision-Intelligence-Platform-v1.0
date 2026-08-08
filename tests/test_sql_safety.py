import pytest

from text_to_sql_agent.sql_safety import SqlSafetyError, validate_select_sql


def test_allows_simple_select():
    result = validate_select_sql(
        "select policy_id, annual_premium from public.policies",
        allowed_schemas={"public"},
        row_limit=100,
    )
    assert result.sql.startswith("select * from (")
    assert result.sql.endswith("limit 100")
    assert "public.policies" in result.referenced_tables


@pytest.mark.parametrize(
    "sql",
    [
        "delete from public.policies",
        "update public.policies set annual_premium = 0",
        "insert into public.products(product_code) values ('X')",
        "drop table public.claims",
        "alter table public.claims add column bad text",
        "select * from public.policies; select * from public.claims",
    ],
)
def test_blocks_non_readonly_sql(sql):
    with pytest.raises(SqlSafetyError):
        validate_select_sql(sql, allowed_schemas={"public"}, row_limit=100)


def test_blocks_disallowed_schema():
    with pytest.raises(SqlSafetyError):
        validate_select_sql("select * from auth.users", allowed_schemas={"public"}, row_limit=100)


def test_blocks_keyword_inside_cte_mutation():
    with pytest.raises(SqlSafetyError):
        validate_select_sql(
            "with x as (delete from public.policies returning *) select * from x",
            allowed_schemas={"public"},
            row_limit=100,
        )
