from __future__ import annotations

from contextlib import asynccontextmanager, contextmanager
from typing import AsyncIterator, Iterator

import psycopg
from psycopg import AsyncConnection, Connection
from psycopg.rows import dict_row

from sicdb_1_pipeline.config import AppConfig


class DatabaseConnectionError(RuntimeError):
    """Raised when PostgreSQL cannot be reached."""


def _connection_kwargs(config: AppConfig, database_name: str | None = None) -> dict[str, object]:
    db = config.database
    return {
        "dbname": database_name or db.default_name,
        "user": db.user,
        "password": db.password,
        "host": db.host,
        "port": db.port,
        "sslmode": db.sslmode,
        "row_factory": dict_row,
    }


@contextmanager
def connect_database(
    config: AppConfig,
    database_name: str | None = None,
    autocommit: bool = False,
) -> Iterator[Connection]:
    """Connect to PostgreSQL using only the connection settings in config.json.

    All CLI commands should use this function rather than connecting directly.
    The PostgreSQL server must already be running and reachable.
    """
    target_db = database_name or config.database.default_name
    try:
        with psycopg.connect(**_connection_kwargs(config, target_db)) as conn:
            conn.autocommit = autocommit
            yield conn
    except psycopg.Error as exc:
        raise DatabaseConnectionError(
            f"Could not connect to PostgreSQL database '{target_db}' at "
            f"{config.database.host}:{config.database.port}: {exc}"
        ) from exc


@asynccontextmanager
async def connect_database_async(
    config: AppConfig,
    database_name: str | None = None,
    autocommit: bool = False,
) -> AsyncIterator[AsyncConnection]:
    """Asynchronously connect to PostgreSQL using config.json connection settings."""
    target_db = database_name or config.database.default_name
    try:
        async with await psycopg.AsyncConnection.connect(**_connection_kwargs(config, target_db)) as conn:
            await conn.set_autocommit(autocommit)
            yield conn
    except psycopg.Error as exc:
        raise DatabaseConnectionError(
            f"Could not connect to PostgreSQL database '{target_db}' at "
            f"{config.database.host}:{config.database.port}: {exc}"
        ) from exc


@contextmanager
def connect_maintenance_database(config: AppConfig, autocommit: bool = True) -> Iterator[Connection]:
    """Connect to the maintenance database used for CREATE/DROP DATABASE."""
    with connect_database(config, config.database.maintenance_database, autocommit=autocommit) as conn:
        yield conn
