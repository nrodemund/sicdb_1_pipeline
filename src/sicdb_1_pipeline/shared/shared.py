import pandas as pd
from psycopg import AsyncConnection
class SharedObjects:
    def __init__(self, source_conn:AsyncConnection,  mapping_file_source, progress):

        self.source_conn = source_conn
        self.mapping_file_source = mapping_file_source
        self.progress = progress
        self.mapping_df = None
    async def load_mapping_file(self):
        # Check if exist
        if not self.mapping_file_source.exists():
            raise FileNotFoundError(f"Mapping file not found at {self.mapping_file_source}")
        self.mapping_df = pd.read_csv(self.mapping_file_source)
        # two minor changes, in source_concept_id remove drug. and signal. from each value, old version not compatible
        self.mapping_df['source_concept_id'] = self.mapping_df['source_concept_id'].str.replace('drug.', '', regex=False)
        self.mapping_df['source_concept_id'] = self.mapping_df['source_concept_id'].str.replace('signal.', '', regex=False)
    async def load_cases(self):
        # Load cases from source_db and store in self.cases_df
        query = "SELECT * FROM cases"
        async with self.source_conn.cursor() as cur:
            await cur.execute(query)
            rows = await cur.fetchall()
        self.cases_df = pd.DataFrame(rows)
        