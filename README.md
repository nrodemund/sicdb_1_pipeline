# sicdb_1_pipeline

Python CLI package for a config-driven ETL pipeline backed by PostgreSQL.

The PostgreSQL server must already be running. This project no longer starts a local PostgreSQL server or uses bundled PostgreSQL binaries.

## Current capabilities

- `init`: creates/initializes the configured database, runs all SQL files in `ddl/` in alphabetical order, and ensures the `etl_values` metadata table exists.
- `init -reset`: drops and recreates the configured database before running initialization.
- `execute`: connects to the database and calls a placeholder ETL executor.
- `check`: checks whether the database exists, whether it appears initialized, and whether the ETL is marked finished.

PostgreSQL connection logic is isolated in `src/sicdb_1_pipeline/db/connection.py`. All commands use that shared connection layer.

## Installation

```bash
python -m venv .venv
. .venv/bin/activate  # Windows: .venv\\Scripts\\activate
python -m pip install -e .
```

## Usage

```bash
sicdb-pipeline init
sicdb-pipeline init -reset
sicdb-pipeline execute
sicdb-pipeline check
```

Use another config file:

```bash
sicdb-pipeline --config path/to/config.json init
```

You can also run the module directly:

```bash
python -m sicdb_1_pipeline --config config.json check
python -m sicdb_1_pipeline --config config.json init
python -m sicdb_1_pipeline --config config.json init -reset
python -m sicdb_1_pipeline --config config.json execute
```

## Config

Default config is `config.json` in the repository root:

```json
{
  "database": {
    "default_name": "sicdb_1",
    "maintenance_database": "postgres",
    "user": "postgres",
    "password": "postgres",
    "host": "127.0.0.1",
    "port": 5432,
    "sslmode": "disable"
  },
  "ddl_folder": "ddl"
}
```

Field notes:

- `database.default_name`: the ETL database name created and used by the pipeline.
- `database.maintenance_database`: an existing database used for `CREATE DATABASE`, `DROP DATABASE`, and database-existence checks. Usually `postgres`.
- `database.user`, `database.password`, `database.host`, `database.port`, `database.sslmode`: normal PostgreSQL connection settings.
- `ddl_folder`: folder containing `.sql` files to execute during `init`.

The configured PostgreSQL user must have permission to create/drop databases when using `init` or `init -reset`.

## DDL files

Place schema files in `ddl/`. Files ending in `.sql` are executed in alphabetical order during `init`.

## ETL status table

The initializer always creates this table:

```sql
CREATE TABLE IF NOT EXISTS etl_values (
    identifier TEXT PRIMARY KEY,
    data TEXT NOT NULL,
    updated TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

The current `execute` command writes a placeholder running state. Later ETL steps should update `etl_values` with status/configuration JSON objects.

## Running from VS Code

This repository includes VS Code launch configurations in `.vscode/launch.json`.

Recommended setup on Windows:

```bash
python -m venv .venv
.venv\Scripts\activate
python -m pip install -e .
```

Then open the repository folder in VS Code and choose one of these debug targets:

- `sicdb-pipeline: check`
- `sicdb-pipeline: init`
- `sicdb-pipeline: init -reset`
- `sicdb-pipeline: execute`

If VS Code does not automatically select the virtual environment, run **Python: Select Interpreter** and choose `.venv\Scripts\python.exe`.

The helper script is also available:

```bash
python scripts/run_cli.py --config config.json check
```
