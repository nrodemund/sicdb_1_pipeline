import pandas as pd
class SharedObjects:
    def __init__(self, source_db, mapping_file_source, progress):
        self.source_db = source_db
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