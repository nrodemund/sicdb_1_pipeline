from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
import sys
import traceback
from psycopg import AsyncConnection

from sicdb_1_pipeline.config import AppConfig
from sicdb_1_pipeline.db.connection import connect_database_async
from sicdb_1_pipeline.db.schema import ETL_VALUES_TABLE_SQL
from sicdb_1_pipeline.pipeline import person
from sicdb_1_pipeline.pipeline import drug
from sicdb_1_pipeline.runtime.progress import CliProgressReporter
from sicdb_1_pipeline.runtime.status import EtlStatusStore
from sicdb_1_pipeline.unittests import unittest_preexecution
from sicdb_1_pipeline.shared.shared import SharedObjects

PipelineActionFn = Callable[[AsyncConnection, str, str, EtlStatusStore, CliProgressReporter], Awaitable[None]]


@dataclass(frozen=True)
class PipelineAction:
    name: str
    execute: PipelineActionFn
    version: str = "0.0.0"


PIPELINE_ACTIONS: tuple[PipelineAction, ...] = (
    PipelineAction(name="person", execute=person.exec, version=person.MODULE_VERSION),
    PipelineAction(name="drug", execute=drug.exec, version=drug.MODULE_VERSION),
)


def run_execute(config: AppConfig) -> int:
    """Start or continue the ETL pipeline through the async execution pathway."""
    return asyncio.run(_run_execute_async(config))


async def _run_execute_async(config: AppConfig) -> int:
    progress = CliProgressReporter()
    target_db = config.database.default_name
    source_db = config.database.source_db
    active_action: str | None = None

    async with (
        connect_database_async(config, target_db) as target_conn,
        connect_database_async(config, source_db) as source_conn,
        ):
        await target_conn.execute(ETL_VALUES_TABLE_SQL)
        await target_conn.commit()

        status = EtlStatusStore(target_conn)
        await status.load()

        try:
            await progress.info("Running pre-execution checks.")
            await unittest_preexecution.run(target_conn)
            await progress.success("Pre-execution checks passed.")
            shared = SharedObjects(source_conn, config.mapping_file_source, progress)
            await shared.load_mapping_file()
            await shared.load_d_references()
            await shared.load_cases()
            await progress.success("Shared data loaded successfully.")    

            for action in PIPELINE_ACTIONS:

                previous_status = await status.get_action_status(action.name)
                if previous_status.get("completed") and previous_status.get("version") == action.version:
                    await progress.info(f"Skipping action {action.name} as it is already completed.")
                    continue



                active_action = action.name
                await progress.start_action(action.name)
                await status.mark_action_started(action.name)
                await action.execute(source_conn, target_conn, shared, status, progress)
                await progress.finish_action(action.name)
                active_action = None

            await status.mark_finished()
            await progress.success("ETL pipeline finished successfully.")
            return 0
        except Exception as exc:
            await progress.stop_heartbeat()
            await status.mark_failed(active_action, exc)
            await progress.error("ETL pipeline failed.", error=exc)
            # Print error and stacktrace to stderr for visibility in CLI and logs

            traceback.print_exc(file=sys.stderr)
            

            return 1
