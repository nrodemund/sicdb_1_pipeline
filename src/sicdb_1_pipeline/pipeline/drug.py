from __future__ import annotations
import asyncio
import sys
from psycopg import AsyncConnection

from sicdb_1_pipeline.runtime.progress import CliProgressReporter
from sicdb_1_pipeline.runtime.status import EtlStatusStore
from sicdb_1_pipeline.shared.shared import SharedObjects
from sicdb_1_pipeline.db.util import upsert_row, upsert_rows

MODULE_VERSION = "0.1.0"

async def exec(
    source_db: AsyncConnection,
    target_db: AsyncConnection,
    shared: SharedObjects,
    status: EtlStatusStore,
    progress: CliProgressReporter,
) -> None:
    """Populate the target drug tables from source_db.
    """
    
    action_status = await status.get_action_status("drug")
    if MODULE_VERSION != action_status.get("version"):
        action_status["progress"] = 0

    cases_df =shared.cases_df
    await progress.init_progress(
        title="Processing drug table",
        module="drug",
        description="processing...",
        overall_progress="...",
        progress=0,
        progress_max=cases_df.shape[0],
        detail="Opening source cursor",
    )
    count_actions=0
    for index, row in cases_df.iterrows():
        case_batch_insert = []
        if index < action_status.get("progress", 0):
            continue

        if index % 25 == 0:
           
            await progress.update_progress(progress=index + 1,detail=f"Processing case {row['CaseID']} - Overall entries inserted: {count_actions:,}")
            await status.update_action(name="drug",progress=index,version=MODULE_VERSION,completed=False)
        query = f"""SELECT * FROM medication WHERE "CaseID" = {row['CaseID']}
        """
        async with source_db.cursor() as cur:
            await cur.execute(query)
            drug_rows = await cur.fetchall()
        for drug_row in drug_rows:


            mappings = shared.get_mappings(drug_row["DrugID"])
            index =0
            for mapping in mappings:
                drug_concept_id = None
                drug_unit_concept_id = 0
                for element in mapping["concepts"]:
                    if element["property_name"]=="concept":
                        drug_concept_id = element["concept_id"]
                    if element["property_name"]=="unit":
                        drug_unit_concept_id = element["concept_id"]

                if drug_concept_id is None:
                    continue
                
                datetime_start,date_start = shared.create_timestamp(row, drug_row["Offset"])
                datetime_end,date_end = shared.create_timestamp(row, drug_row["OffsetDrugEnd"])
                transform_fn = await shared.get_transform(drug_row["DrugID"],index,mapping)
                omop_row = {
                    "drug_exposure_id":drug_row["id"] + index*10000000, # create drug_exposure_id by combining drug_row id and index of mapping to ensure uniqueness
                    "drug_concept_id": drug_concept_id,
                    "person_id": row["PatientID"],
                    "drug_exposure_start_date": date_start,
                    "drug_exposure_start_datetime": datetime_start,
                    "drug_exposure_end_date": date_end,
                    "drug_exposure_end_datetime": datetime_end,
                    "drug_type_concept_id":32818, # ehr admission record
                    "route_concept_id": 0,
                    "quantity": transform_fn(drug_row["Amount"]),
                }
                #await upsert_row(target_db, "drug_exposure", omop_row)
                case_batch_insert.append(omop_row)
                count_actions+=1
                index +=1
        if len(case_batch_insert) > 0:
            await upsert_rows(target_db, "drug_exposure", case_batch_insert)
                

        
    await target_db.commit()
    await status.update_action(name="drug",progress=cases_df.shape[0],version=MODULE_VERSION,completed=True)
    await progress.end_progress()
    await progress.info("Table drug updated.", source_db=source_db, target_db=target_db)
