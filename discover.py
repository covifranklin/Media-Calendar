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
            "write reports, and optionally update deadline YAML."
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
        "--mode",
        choices=["dry-run", "apply"],
        default="dry-run",
        help=(
            "Use `dry-run` to write discovery reports without changing "
            "data/deadlines/*.yaml, or `apply` to write deadline YAML so a "
            "workflow can commit it."
        ),
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
    parser.add_argument(
        "--source-scope",
        choices=["auto", "core", "all"],
        default="auto",
        help=(
            "Use `core` to skip watchlist sources, `all` to include every "
            "registered source, or `auto` to include watchlist sources every "
            "other ISO week."
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
        mode=args.mode,
        llm_mode=args.llm_mode,
        source_scope=args.source_scope,
    )

    print(
        "Discovery refresh complete: "
        f"{payload['promoted_new_count']} new, "
        f"{payload['promoted_update_count']} updated, "
        f"{payload['ignored_duplicate_count']} duplicate, "
        f"{payload['rejected_uncertain_count']} rejected."
    )
    print(f"Refresh mode: {payload['mode']}")
    print(
        "Source scope: "
        f"{payload['source_scope_requested']} "
        f"(effective: {payload['source_scope_effective']}, "
        f"{payload['selected_source_count']}/{payload['total_source_count']} sources)"
    )
    print(
        "Updated deadline files: "
        f"{', '.join(payload['deadline_files']) if payload['deadline_files'] else 'None'}"
    )
    print(f"Calendar written to: {payload['calendar_path']}")
    print(f"JSON report: {payload['report_json_path']}")
    print(f"Markdown report: {payload['report_markdown_path']}")
    print(f"Metrics JSON: {payload['metrics_json_path']}")
    print(f"Metrics Markdown: {payload['metrics_markdown_path']}")
    print(f"Freshness JSON: {payload['freshness_report_json_path']}")
    print(f"Freshness Markdown: {payload['freshness_report_markdown_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
