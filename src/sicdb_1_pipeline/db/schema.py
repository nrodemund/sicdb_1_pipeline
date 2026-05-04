from __future__ import annotations

from pathlib import Path

from psycopg import Connection


ETL_VALUES_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS etl_values (
    identifier TEXT PRIMARY KEY,
    data TEXT NOT NULL,
    updated TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
"""


def ensure_etl_values_table(conn: Connection) -> None:
    conn.execute(ETL_VALUES_TABLE_SQL)


def execute_ddl_folder(conn: Connection, ddl_folder: Path) -> list[Path]:
    if not ddl_folder.exists():
        return []

    sql_files = sorted(path for path in ddl_folder.iterdir() if path.is_file() and path.suffix.lower() == ".sql")
    for sql_file in sql_files:
        sql_text = sql_file.read_text(encoding="utf-8")
        print(f"Executing DDL from {sql_file}...")
        if sql_text.strip():
            conn.execute(sql_text)
    return sql_files
