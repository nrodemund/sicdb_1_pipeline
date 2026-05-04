from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class ConfigError(RuntimeError):
    """Raised when the pipeline configuration is missing or invalid."""


@dataclass(frozen=True)
class DatabaseConfig:
    default_name: str
    source_db: str
    user: str
    password: str
    host: str
    port: int
    sslmode: str = "disable"
    maintenance_database: str = "postgres"


@dataclass(frozen=True)
class AppConfig:
    config_path: Path
    project_root: Path
    database: DatabaseConfig
    ddl_folder: Path
    mapping_file_source: str


def load_config(config_path: str | Path) -> AppConfig:
    resolved_path = Path(config_path).expanduser().resolve()
    if not resolved_path.exists():
        raise ConfigError(f"Config file not found: {resolved_path}")

    try:
        raw: dict[str, Any] = json.loads(resolved_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ConfigError(f"Config file is not valid JSON: {resolved_path}") from exc

    project_root = resolved_path.parent
    db_raw = raw.get("database", {})

    required_db_fields = ["default_name", "source_db", "user", "password", "host", "port"]
    missing = [field for field in required_db_fields if field not in db_raw]
    if missing:
        raise ConfigError(f"Missing database config field(s): {', '.join(missing)}")

    database = DatabaseConfig(
        default_name=str(db_raw["default_name"]),
        source_db=str(db_raw["source_db"]),
        user=str(db_raw["user"]),
        password=str(db_raw["password"]),
        host=str(db_raw["host"]),
        port=int(db_raw["port"]),
        sslmode=str(db_raw.get("sslmode", "disable")),
        maintenance_database=str(db_raw.get("maintenance_database", "postgres")),
    )

    mapping_file_source = raw.get("mapping_file_source", "mapping.csv")
    mapping_file_source = Path(str(mapping_file_source)).expanduser()
    if not mapping_file_source.is_absolute():
        mapping_file_source = project_root / mapping_file_source

    ddl_folder_raw = raw.get("ddl_folder", "ddl")
    ddl_folder = Path(str(ddl_folder_raw)).expanduser()
    if not ddl_folder.is_absolute():
        ddl_folder = project_root / ddl_folder

    return AppConfig(
        config_path=resolved_path,
        project_root=project_root,
        database=database,
        ddl_folder=ddl_folder,
        mapping_file_source=mapping_file_source,
    )
