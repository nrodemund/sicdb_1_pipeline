from __future__ import annotations

from psycopg import AsyncConnection


class PreExecutionCheckError(RuntimeError):
    """Raised when a required pre-execution database check fails."""


async def run(conn: AsyncConnection) -> None:
    """Validate database prerequisites before the ETL pipeline starts."""
    await _assert_table_exists(conn, "person")


async def _assert_table_exists(conn: AsyncConnection, table_name: str) -> None:
    row = await (await conn.execute(
        "SELECT to_regclass(%s) AS table_name",
        (f"public.{table_name}",),
    )).fetchone()
    if row is None or row["table_name"] is None:
        raise PreExecutionCheckError(f"Required table '{table_name}' does not exist.")
