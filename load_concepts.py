#!/usr/bin/env python3
"""
Load large OMOP vocabulary concept files into PostgreSQL.

Requires:
    pip install "psycopg[binary]"

Usage:
    python load_concepts.py /path/to/vocabulary/files

Expected files:
    CONCEPT_CLASS.csv
    CONCEPT.csv
    CONCEPT_ANCESTOR.csv
    CONCEPT_RELATIONSHIP.csv
    CONCEPT_SYNONYM.csv
"""

import asyncio
import argparse
from pathlib import Path

from psycopg import AsyncConnection
import sys


DB_NAME = "sicdb_1"

# "default connection, default pass"
# Adjust user/password if your local defaults differ.
CONNINFO = f"dbname={DB_NAME} user=postgres password=postgres host=localhost port=5432"


LOAD_ORDER = [
    {
        "file": "CONCEPT_CLASS.csv",
        "table": "concept_class",
        "columns": [
            "concept_class_id",
            "concept_class_name",
            "concept_class_concept_id",
        ],
    },
    {
        "file": "CONCEPT.csv",
        "table": "concept",
        "columns": [
            "concept_id",
            "concept_name",
            "domain_id",
            "vocabulary_id",
            "concept_class_id",
            "standard_concept",
            "concept_code",
            "valid_start_date",
            "valid_end_date",
            "invalid_reason",
        ],
    },
    {
        "file": "CONCEPT_ANCESTOR.csv",
        "table": "concept_ancestor",
        "columns": [
            "ancestor_concept_id",
            "descendant_concept_id",
            "min_levels_of_separation",
            "max_levels_of_separation",
        ],
    },
    {
        "file": "CONCEPT_RELATIONSHIP.csv",
        "table": "concept_relationship",
        "columns": [
            "concept_id_1",
            "concept_id_2",
            "relationship_id",
            "valid_start_date",
            "valid_end_date",
            "invalid_reason",
        ],
    },
    {
        "file": "CONCEPT_SYNONYM.csv",
        "table": "concept_synonym",
        "columns": [
            "concept_id",
            "concept_synonym_name",
            "language_concept_id",
        ],
    },
]


def copy_sql(table: str, columns: list[str]) -> str:
    cols = ", ".join(columns)

    return f"""
        COPY {table} ({cols})
        FROM STDIN
        WITH (
            FORMAT csv,
            HEADER true,
            DELIMITER E'\\t',
            QUOTE E'\\b',
            NULL ''
        )
    """


async def truncate_tables(conn: AsyncConnection) -> None:
    """
    Truncate in dependency-safe order.
    RESTART IDENTITY is harmless if there are no sequences.
    CASCADE handles FK dependencies between vocabulary tables.
    """
    tables = ", ".join(item["table"] for item in reversed(LOAD_ORDER))

    async with conn.cursor() as cur:
        await cur.execute(f"TRUNCATE TABLE {tables} RESTART IDENTITY CASCADE;")


async def load_file(conn: AsyncConnection, file_path: Path, table: str, columns: list[str]) -> None:
    if not file_path.exists():
        raise FileNotFoundError(f"Missing file: {file_path}")

    print(f"Loading {file_path.name} -> {table}")

    sql = copy_sql(table, columns)

    async with conn.cursor() as cur:
        async with cur.copy(sql) as copy:
            with file_path.open("rb") as f:
                while True:
                    chunk = f.read(1024 * 1024 * 8)  # 8 MB chunks
                    if not chunk:
                        break
                    await copy.write(chunk)

    print(f"Finished {file_path.name}")


async def defer_constraints(conn: AsyncConnection) -> None:
    """
    Works only for constraints declared DEFERRABLE.
    Safe to call even if none are deferrable.
    """
    async with conn.cursor() as cur:
        await cur.execute("SET CONSTRAINTS ALL DEFERRED;")


async def load_all(folder: Path, truncate_first: bool) -> None:
    async with await AsyncConnection.connect(CONNINFO) as conn:
        async with conn.transaction():
            await defer_constraints(conn)

            if truncate_first:
                print("Truncating target tables")
                await truncate_tables(conn)

            for item in LOAD_ORDER:
                await load_file(
                    conn=conn,
                    file_path=folder / item["file"],
                    table=item["table"],
                    columns=item["columns"],
                )

            # Forces deferred constraints to be checked before COMMIT.
            async with conn.cursor() as cur:
                await cur.execute("SET CONSTRAINTS ALL IMMEDIATE;")

    print("All files loaded successfully")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "folder",
        type=Path,
        help="Folder containing CONCEPT*.csv files",
    )
    parser.add_argument(
        "--no-truncate",
        action="store_true",
        help="Do not truncate target tables before loading",
    )

    args = parser.parse_args()

    asyncio.run(load_all(
        folder=args.folder,
        truncate_first=not args.no_truncate,
    ))


if __name__ == "__main__":
    print("Starting concept loading")
    if sys.platform.startswith("win"):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    main()