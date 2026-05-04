from __future__ import annotations

import json
from typing import Any

from sicdb_1_pipeline.config import AppConfig
from sicdb_1_pipeline.db.admin import database_exists
from sicdb_1_pipeline.db.connection import connect_database


def run_check(config: AppConfig) -> int:
    if not database_exists(config):
        print(f"Database '{config.database.default_name}' does not exist. Status: empty/not initialized.")
        return 2

    with connect_database(config) as conn:
        etl_table_exists = _table_exists(conn, "etl_values")
        if not etl_table_exists:
            print(
                f"Database '{config.database.default_name}' exists, but etl_values is missing. "
                "Status: empty/not initialized."
            )
            return 2

        initialized = _fetch_value(conn, "database.initialized")
        etl_status = _fetch_value(conn, "etl.status")

    if initialized is None:
        print(
            f"Database '{config.database.default_name}' has etl_values, but no initialization marker. "
            "Status: not initialized."
        )
        return 2

    parsed_status = _parse_json(etl_status["data"]) if etl_status else None
    if parsed_status and parsed_status.get("finished") is True:
        print("Database structure exists. ETL status: finished.")
        return 0

    print("Database structure exists. ETL status: not finished.")
    if parsed_status:
        print(f"Current ETL state: {parsed_status.get('state', 'unknown')}")
        if parsed_status.get("message"):
            print(f"Message: {parsed_status['message']}")
    else:
        print("No ETL status row found yet.")
    return 1


def _table_exists(conn: Any, table_name: str) -> bool:
    result = conn.execute("SELECT to_regclass(%s) AS table_name", (f"public.{table_name}",)).fetchone()
    return result is not None and result["table_name"] is not None


def _fetch_value(conn: Any, identifier: str) -> dict[str, Any] | None:
    return conn.execute(
        "SELECT identifier, data, updated FROM etl_values WHERE identifier = %s",
        (identifier,),
    ).fetchone()


def _parse_json(raw: str) -> dict[str, Any] | None:
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        return {"state": "unknown", "message": raw, "finished": False}
    return value if isinstance(value, dict) else None
