"""CLI entry point for the review-only open-web discovery sweep."""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
SRC_PATH = PROJECT_ROOT / "src"


def _ensure_src_path() -> None:
    if str(SRC_PATH) not in sys.path:
        sys.path.insert(0, str(SRC_PATH))


def main() -> int:
    _ensure_src_path()
    from media_calendar.orchestration import orchestration_step_open_web_discovery
    from media_calendar.services import load_dotenv_file

    parser = argparse.ArgumentParser(
        description=(
            "Run a low-cost, review-only open-web sweep to suggest missed "
            "opportunities outside the monitored source list."
        )
    )
    parser.add_argument(
        "--root-dir",
        type=Path,
        default=Path.cwd(),
        help="Project root containing data/sources/, data/deadlines/, and build/.",
    )
    parser.add_argument(
        "--source-input",
        action="append",
        dest="source_inputs",
        help="Optional explicit source registry YAML file path. May be passed multiple times.",
    )
    parser.add_argument(
        "--deadline-input",
        action="append",
        dest="deadline_inputs",
        help="Optional explicit deadline YAML file path. May be passed multiple times.",
    )
    parser.add_argument(
        "--date",
        dest="current_date",
        help="Override current date in YYYY-MM-DD format.",
    )
    parser.add_argument(
        "--max-results-per-query",
        type=int,
        default=3,
        help="Cap the number of search hits kept per query before deduplication.",
    )
    parser.add_argument(
        "--max-results-total",
        type=int,
        default=12,
        help="Cap the total number of result pages fetched for the sweep.",
    )
    args = parser.parse_args()

    load_dotenv_file(args.root_dir / ".env")
    current_date = (
        date.fromisoformat(args.current_date) if args.current_date else date.today()
    )
    payload = orchestration_step_open_web_discovery(
        args.source_inputs,
        args.deadline_inputs,
        root_dir=args.root_dir,
        current_date=current_date,
        max_results_per_query=args.max_results_per_query,
        max_results_total=args.max_results_total,
    )

    print(f"Open-web query count: {payload['query_count']}")
    print(f"Search results reviewed: {payload['search_result_count']}")
    print(
        "Classification counts: "
        f"{payload['classification_counts']}"
    )
    print(f"JSON report: {payload['report_json_path']}")
    print(f"Markdown report: {payload['report_markdown_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
