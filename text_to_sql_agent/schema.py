from __future__ import annotations

from collections import defaultdict


def fetch_schema_metadata(conn, *, schemas: set[str], allowed_tables: set[str] | None = None) -> str:
    with conn.cursor() as cur:
        cur.execute(
            """
            select
              table_schema,
              table_name,
              column_name,
              data_type,
              udt_name,
              is_nullable
            from information_schema.columns
            where table_schema = any(%s)
              and table_name not like 'pg_%%'
            order by table_schema, table_name, ordinal_position
            """,
            (list(schemas),),
        )
        rows = cur.fetchall()

    grouped: dict[tuple[str, str], list[str]] = defaultdict(list)
    for row in rows:
        full_table_name = f"{row['table_schema']}.{row['table_name']}"
        if allowed_tables and full_table_name not in allowed_tables:
            continue
        dtype = row["data_type"]
        if dtype == "USER-DEFINED":
            dtype = row["udt_name"]
        nullable = "nullable" if row["is_nullable"] == "YES" else "not null"
        grouped[(row["table_schema"], row["table_name"])].append(f"{row['column_name']} {dtype} {nullable}")

    lines = []
    for (schema_name, table_name), columns in grouped.items():
        lines.append(f"Table {schema_name}.{table_name}:")
        for column in columns:
            lines.append(f"  - {column}")
    return "\n".join(lines)
