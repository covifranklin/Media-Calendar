"""CLI entry point for source coverage reporting."""

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
    from media_calendar.components import (
        build_source_coverage_report,
        write_source_coverage_report,
    )

    parser = argparse.ArgumentParser(
        description="Generate build/coverage-report.{json,md} from data/sources/*.yaml."
    )
    parser.add_argument(
        "--root-dir",
        type=Path,
        default=Path.cwd(),
        help="Project root containing data/sources/ and build/.",
    )
    parser.add_argument(
        "--input",
        action="append",
        dest="inputs",
        help="Optional explicit source registry YAML file path. May be passed multiple times.",
    )
    args = parser.parse_args()

    report = build_source_coverage_report(args.inputs, root_dir=args.root_dir)
    paths = write_source_coverage_report(report, root_dir=args.root_dir)

    print(f"Wrote JSON report: {paths['json']}")
    print(f"Wrote Markdown report: {paths['markdown']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
