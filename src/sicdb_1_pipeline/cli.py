from __future__ import annotations

import argparse
import sys
from pathlib import Path

from sicdb_1_pipeline.commands.check import run_check
from sicdb_1_pipeline.commands.execute import run_execute
from sicdb_1_pipeline.commands.init_db import run_init
from sicdb_1_pipeline.config import ConfigError, load_config
from sicdb_1_pipeline.db.connection import DatabaseConnectionError

import asyncio

if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sicdb-pipeline",
        description="SICDB ETL pipeline command line interface.",
    )
    parser.add_argument(
        "--config",
        default="config.json",
        help="Path to config.json. Defaults to ./config.json.",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="Initialize the configured database and schema.")
    init_parser.add_argument(
        "-reset",
        action="store_true",
        help="Drop and recreate the configured database before initialization.",
    )

    subparsers.add_parser("execute", help="Start or continue the ETL pipeline.")
    subparsers.add_parser("check", help="Check database structure and ETL completion status.")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        config = load_config(Path(args.config))
        if args.command == "init":
            return run_init(config, reset=args.reset)
        if args.command == "execute":
            return run_execute(config)
        if args.command == "check":
            return run_check(config)
    except (ConfigError, DatabaseConnectionError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    parser.error(f"Unsupported command: {args.command}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
