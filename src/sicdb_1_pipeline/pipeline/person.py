from __future__ import annotations
import asyncio

from psycopg import AsyncConnection

from sicdb_1_pipeline.runtime.progress import CliProgressReporter
from sicdb_1_pipeline.runtime.status import EtlStatusStore
from sicdb_1_pipeline.shared.shared import SharedObjects
from sicdb_1_pipeline.db.util import upsert_row

async def exec(
    source_db: AsyncConnection,
    target_db: AsyncConnection,
    shared: SharedObjects,
    status: EtlStatusStore,
    progress: CliProgressReporter,
) -> None:
    """Populate the target person table from source_db.

    Implementation intentionally left empty until the person ETL mapping is defined.
    """
    
    cases_df =shared.cases_df
    await progress.init_progress(
        title="Importing people",
        module="person",
        description="Reading source rows",
        overall_progress="...",
        progress=0,
        progress_max=cases_df.shape[0],
        detail="Opening source cursor",
    )

    for index, row in cases_df.iterrows():
        if index % 100 == 0:
            await progress.update_progress(
                progress=index + 1,
                detail=f"Processing case {row['CaseID']}"
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
        
    
    await progress.end_progress()
    await progress.info("Table person updated.", source_db=source_db, target_db=target_db)
