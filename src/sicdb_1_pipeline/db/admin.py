from __future__ import annotations

from psycopg import sql

from sicdb_1_pipeline.config import AppConfig
from sicdb_1_pipeline.db.connection import connect_maintenance_database


def database_exists(config: AppConfig, database_name: str | None = None) -> bool:
    db_name = database_name or config.database.default_name
    with connect_maintenance_database(config) as conn:
        result = conn.execute(
            "SELECT 1 FROM pg_database WHERE datname = %s",
            (db_name,),
        ).fetchone()
    return result is not None


def create_database(config: AppConfig, database_name: str | None = None) -> None:
    db_name = database_name or config.database.default_name
    with connect_maintenance_database(config) as conn:
        conn.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(db_name)))


def drop_database(config: AppConfig, database_name: str | None = None) -> None:
    db_name = database_name or config.database.default_name
    with connect_maintenance_database(config) as conn:
        conn.execute(
            "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = %s AND pid <> pg_backend_pid()",
            (db_name,),
        )
        conn.execute(sql.SQL("DROP DATABASE IF EXISTS {}").format(sql.Identifier(db_name)))


def ensure_database(config: AppConfig, reset: bool = False) -> None:
    if reset:
        drop_database(config)
        create_database(config)
        return

    if not database_exists(config):
        create_database(config)
