from __future__ import annotations

import json
from datetime import datetime, timezone

from sicdb_1_pipeline.config import AppConfig
from sicdb_1_pipeline.db.admin import ensure_database
from sicdb_1_pipeline.db.connection import connect_database
from sicdb_1_pipeline.db.schema import ensure_etl_values_table, execute_ddl_folder


def run_init(config: AppConfig, reset: bool = False) -> int:
    ensure_database(config, reset=reset)

    with connect_database(config) as conn:
        ddl_files = execute_ddl_folder(conn, config.ddl_folder)
        ensure_etl_values_table(conn)
        conn.execute(
            """
            INSERT INTO etl_values (identifier, data, updated)
            VALUES (%s, %s, NOW())
            ON CONFLICT (identifier)
            DO UPDATE SET data = EXCLUDED.data, updated = NOW()
            """,
            (
                "database.initialized",
                json.dumps(
                    {
                        "initialized": True,
                        "reset": reset,
                        "ddl_files": [path.name for path in ddl_files],
                        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                    },
                    indent=2,
                ),
            ),
        )
        conn.commit()

    print(f"Initialized database '{config.database.default_name}'.")
    if ddl_files:
        print("Executed DDL files:")
        for path in ddl_files:
            print(f"  - {path.name}")
    else:
        print("No DDL files found.")
    return 0
