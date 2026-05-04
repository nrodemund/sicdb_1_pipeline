from __future__ import annotations
import asyncio

from psycopg import AsyncConnection

from sicdb_1_pipeline.runtime.progress import CliProgressReporter
from sicdb_1_pipeline.runtime.status import EtlStatusStore


async def exec(
    conn: AsyncConnection,
    source_db: str,
    target_db: str,
    status: EtlStatusStore,
    progress: CliProgressReporter,
) -> None:
    """Populate the target person table from source_db.

    Implementation intentionally left empty until the person ETL mapping is defined.
    """
    
    await progress.init_progress(
        title="Importing people",
        module="person",
        description="Reading source rows",
        overall_progress="...",
        progress=-1,
        progress_max=5000,
        detail="Opening source cursor",
    )
    
    await progress.end_progress()
    await progress.info("Table person updated.", source_db=source_db, target_db=target_db)
