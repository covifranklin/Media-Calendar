"""CLI entry point for the automated discovery refresh pipeline."""

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
    from media_calendar.orchestration import orchestration_step_discovery_refresh
    from media_calendar.services import load_dotenv_file

    parser = argparse.ArgumentParser(
        description=(
            "Refresh monitored opportunity sources, auto-promote safe changes, "
            "write deadline YAML, and regenerate the calendar."
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
        "--llm-mode",
        choices=["auto", "off", "required"],
        default="auto",
        help=(
            "Use `auto` to call the discovery LLM when OPENAI_API_KEY is present, "
            "`off` for deterministic-only mode, or `required` to fail if the LLM "
            "cannot be used."
        ),
    )
    args = parser.parse_args()

    load_dotenv_file(args.root_dir / ".env")
    current_date = (
        date.fromisoformat(args.current_date) if args.current_date else date.today()
    )
    payload = orchestration_step_discovery_refresh(
        args.source_inputs,
        args.deadline_inputs,
        root_dir=args.root_dir,
        current_date=current_date,
        llm_mode=args.llm_mode,
    )

    print(
        "Discovery refresh complete: "
        f"{payload['promoted_new_count']} new, "
        f"{payload['promoted_update_count']} updated, "
        f"{payload['ignored_duplicate_count']} duplicate, "
        f"{payload['rejected_uncertain_count']} rejected."
    )
    print(f"Updated deadline files: {', '.join(payload['deadline_files'])}")
    print(f"Calendar written to: {payload['calendar_path']}")
    print(f"JSON report: {payload['report_json_path']}")
    print(f"Markdown report: {payload['report_markdown_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
