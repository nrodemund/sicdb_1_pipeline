from __future__ import annotations
import asyncio

from psycopg import AsyncConnection

from sicdb_1_pipeline.runtime.progress import CliProgressReporter
from sicdb_1_pipeline.runtime.status import EtlStatusStore
from sicdb_1_pipeline.shared.shared import SharedObjects
from sicdb_1_pipeline.db.util import upsert_row

MODULE_VERSION = "0.1.0"

async def exec(
    source_db: AsyncConnection,
    target_db: AsyncConnection,
    shared: SharedObjects,
    status: EtlStatusStore,
    progress: CliProgressReporter,
) -> None:
    """Populate the target person table from source_db.
    """
    
    action_status = await status.get_action_status("person")
    if MODULE_VERSION != action_status.get("version"):
        action_status["progress"] = 0

    cases_df =shared.cases_df
    await progress.init_progress(
        title="Processing person table",
        module="person",
        description="processing...",
        overall_progress="...",
        progress=0,
        progress_max=cases_df.shape[0],
        detail="Opening source cursor",
    )

    for index, row in cases_df.iterrows():
        if index < action_status.get("progress", 0):
            continue

        if index % 200 == 0:
            await progress.update_progress(
                progress=index + 1,
                detail=f"Processing case {row['CaseID']}"
            )
            await status.update_action(
                name="person",
                progress=index,
                version=MODULE_VERSION,
                completed=False
            )

        omop_row = {
            "person_id": row["PatientID"],
            "gender_concept_id": 8532 if row["Sex"]== 736 else 8507,
            "year_of_birth": int(row["AdmissionYear"])-int(row["AgeOnAdmission"]),
            "month_of_birth": None, 
            "day_of_birth": None,
            "race_concept_id": 0,
            "ethnicity_concept_id": 0
        }
        await upsert_row(target_db, "person", omop_row)
        
    await target_db.commit()
    await status.update_action(
        name="person",
        progress=cases_df.shape[0],
        version=MODULE_VERSION,
        completed=True
    )
    await progress.end_progress()
    await progress.info("Table person updated.", source_db=source_db, target_db=target_db)
