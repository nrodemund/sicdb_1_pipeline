from typing import Any, Mapping, Sequence

from psycopg import AsyncConnection
from psycopg.rows import dict_row
from psycopg.sql import SQL, Identifier, Placeholder


async def upsert_row(
    conn: AsyncConnection,
    table_name: str,
    row: Mapping[str, Any],
) -> dict[str, Any] | None:
    """
    Insert or update a single row in PostgreSQL using psycopg 3.

    Assumptions:
    - `row` is an ordered mapping, such as a normal Python 3.7+ dict
    - the first key in `row` is the primary key or unique column
    - `table_name` is a single trusted table name, not schema-qualified

    Returns the inserted/updated row as a dict.
    """

    if not row:
        raise ValueError("row cannot be empty")

    columns = list(row.keys())
    conflict_column = columns[0]
    update_columns = columns[1:]

    insert_columns_sql = SQL(", ").join(Identifier(col) for col in columns)
    placeholders_sql = SQL(", ").join(Placeholder() for _ in columns)

    if update_columns:
        update_clause = SQL(", ").join(
            SQL("{} = EXCLUDED.{}").format(
                Identifier(col),
                Identifier(col),
            )
            for col in update_columns
        )

        conflict_action = SQL("DO UPDATE SET {}").format(update_clause)
    else:
        conflict_action = SQL("DO NOTHING")

    query = SQL("""
        INSERT INTO {} ({})
        VALUES ({})
        ON CONFLICT ({})
        {}
        RETURNING *;
    """).format(
        Identifier(table_name),
        insert_columns_sql,
        placeholders_sql,
        Identifier(conflict_column),
        conflict_action,
    )



    try:
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(query, list(row.values()))
            return await cur.fetchone()
    except Exception as e:
        await conn.rollback()
        print("FAILED TABLE:", table_name)
        print("FAILED ROW:", row)
        print("ERROR:", repr(e))
        raise
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(query, list(row.values()))
            return await cur.fetchone()
    


# Note: for a unknown reason this "long-query-string" method is faster than executemany. TODO: investigate further and consider replacing upsert_row with a batch version that uses this method.
async def upsert_rows(
    conn: AsyncConnection,
    table_name: str,
    rows: Sequence[Mapping[str, Any]],
    *,
    chunk_size: int = 1_000,
) -> list[dict[str, Any]]:
    """
    Efficiently upsert many rows into PostgreSQL using psycopg 3.

    Assumptions:
    - every row has the same keys, in the same order
    - the first key is the primary key or unique conflict column
    - `table_name` is a single trusted table name, not schema-qualified

    Returns inserted/updated rows as dicts.
    """

    if not rows:
        return []

    columns = list(rows[0].keys())
    conflict_column = columns[0]
    update_columns = columns[1:]

    for row in rows:
        if list(row.keys()) != columns:
            raise ValueError("All rows must have the same columns in the same order")

    insert_columns_sql = SQL(", ").join(Identifier(col) for col in columns)

    if update_columns:
        update_clause = SQL(", ").join(
            SQL("{} = EXCLUDED.{}").format(
                Identifier(col),
                Identifier(col),
            )
            for col in update_columns
        )

        conflict_action = SQL("DO UPDATE SET {}").format(update_clause)
    else:
        conflict_action = SQL("DO NOTHING")

    results: list[dict[str, Any]] = []

    async with conn.transaction():
        for start in range(0, len(rows), chunk_size):
            chunk = rows[start:start + chunk_size]

            row_placeholders = SQL(", ").join(
                SQL("(") + SQL(", ").join(Placeholder() for _ in columns) + SQL(")")
                for _ in chunk
            )

            values: list[Any] = [
                row[col]
                for row in chunk
                for col in columns
            ]

            query = SQL("""
                INSERT INTO {} ({})
                VALUES {}
                ON CONFLICT ({})
                {}
                RETURNING *;
            """).format(
                Identifier(table_name),
                insert_columns_sql,
                row_placeholders,
                Identifier(conflict_column),
                conflict_action,
            )

            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(query, values)
                batch_result = await cur.fetchall()
                results.extend(batch_result)

    return results