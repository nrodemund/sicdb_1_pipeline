import pandas as pd
import json
from psycopg import AsyncConnection
from .ast import compile_transform

from datetime import datetime, timezone, timedelta
from functools import lru_cache


class SharedObjects:
    def __init__(self, source_conn:AsyncConnection,  mapping_file_source, progress):

        self.source_conn = source_conn
        self.mapping_file_source = mapping_file_source
        self.d_references_dict={}
        self.progress = progress
        self.mapping_df = None
        self.tf_cache = {}
    async def load_mapping_file(self):
        # Check if exist
        if not self.mapping_file_source.exists():
            raise FileNotFoundError(f"Mapping file not found at {self.mapping_file_source}")
        self.mapping_df = pd.read_csv(self.mapping_file_source)
        # two minor changes, in source_concept_id remove drug. and signal. from each value, old version not compatible
        self.mapping_df['source_concept_id'] = self.mapping_df['source_concept_id'].str.replace('drug.', '', regex=False)
        self.mapping_df['source_concept_id'] = self.mapping_df['source_concept_id'].str.replace('signal.', '', regex=False)
    async def load_d_references(self):
        # get path from self.mapping_file_source
        folder = self.mapping_file_source.parent
        d_references_file = folder / "d_references.csv"
        if not d_references_file.exists():  
            raise FileNotFoundError(f"d_references file not found at {d_references_file}")
        d_references_df = pd.read_csv(d_references_file)

        self.d_references_dict = d_references_df.set_index("ReferenceGlobalID").to_dict(orient="index")

    async def load_cases(self):
        # Load cases from source_db and store in self.cases_df
        query = "SELECT * FROM cases"
        async with self.source_conn.cursor() as cur:
            await cur.execute(query)
            rows = await cur.fetchall()
        self.cases_df = pd.DataFrame(rows)

    @lru_cache(maxsize=None)
    def admission_year_start(self, admission_year: int) -> datetime:
        return datetime(admission_year, 1, 1, tzinfo=timezone.utc)


    def create_timestamp(self, row, offset: int):
        timestamp = (
            self.admission_year_start(int(row["AdmissionYear"]))
            + timedelta(seconds=int(offset) - int(row["ICUOffset"]))
        )

        return timestamp, timestamp.date()
    
    @lru_cache(maxsize=1000) # this method is called very often with same parameters, so we cache results to speed up
    def get_mappings(self, source_concept_id):
        # For one source_concept_id zero or more mappings exist. Ech of them has a field concepts, which is a json array of objects with properties 
        rows = self.mapping_df[self.mapping_df['source_concept_id'] == str(source_concept_id)]
        if rows.empty:
            return []
        result = []

        for _, row in rows.iterrows(): # iterate over rows but retain index for caching
            item = row.to_dict()
            item["concepts"] = json.loads(item["concepts"]) if item.get("concepts") else []
            result.append(item)

        return result
            

        
        
       
        
    async def get_transform(self, source_concept_id,index,mapping):
        # Return transform object for given source_concept_id and index, found as json in field concepts
      
        cache_key = f"{source_concept_id}_{index}"
        if cache_key in self.tf_cache:
            return self.tf_cache[cache_key] 
        if not isinstance(mapping["mapping_transformation"], str) or len(mapping["mapping_transformation"]) <= 1:
            mapping["mapping_transformation"] = "return value"
        tf = compile_transform(mapping["mapping_transformation"])
        self.tf_cache[cache_key] = tf
        return tf