"""CLI entry point for generating the static calendar."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
SRC_PATH = PROJECT_ROOT / "src"


def _ensure_src_path() -> None:
    if str(SRC_PATH) not in sys.path:
        sys.path.insert(0, str(SRC_PATH))


def main() -> int:
    _ensure_src_path()
    from media_calendar.orchestration import orchestration_step_calendar_generator

    parser = argparse.ArgumentParser(
        description="Generate build/calendar.html from data/deadlines/*.yaml."
    )
    parser.add_argument(
        "--root-dir",
        type=Path,
        default=Path.cwd(),
        help="Project root containing data/deadlines/ and build/.",
    )
    parser.add_argument(
        "--input",
        action="append",
        dest="inputs",
        help="Optional explicit YAML file path. May be passed multiple times.",
    )
    args = parser.parse_args()

    payload = orchestration_step_calendar_generator(
        args.inputs,
        root_dir=args.root_dir,
    )
    print(f"Generated calendar: {payload['output_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
