"""Convenience entry point for running the CLI from VS Code or a terminal.

Examples:
    python scripts/run_cli.py check
    python scripts/run_cli.py init -reset
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from sicdb_1_pipeline.cli import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main())
