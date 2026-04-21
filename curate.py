"""CLI entry point for annual deadline curation."""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path
from urllib.request import Request, urlopen

PROJECT_ROOT = Path(__file__).resolve().parent
SRC_PATH = PROJECT_ROOT / "src"


def _ensure_src_path() -> None:
    if str(SRC_PATH) not in sys.path:
        sys.path.insert(0, str(SRC_PATH))


def main() -> int:
    _ensure_src_path()
    from media_calendar.components.deadline_store import (
        load_deadlines,
        resolve_deadline_files,
    )
    from media_calendar.orchestration import orchestration_step_data_curation
    from media_calendar.services import load_dotenv_file

    parser = argparse.ArgumentParser(
        description="Run the annual data curation pass for a given deadline year."
    )
    parser.add_argument(
        "--year",
        type=int,
        required=True,
        help="Deadline year to curate.",
    )
    parser.add_argument(
        "--root-dir",
        type=Path,
        default=Path.cwd(),
        help="Project root containing data/deadlines/ and build/.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Optional output directory for curation reports. Defaults to build/.",
    )
    args = parser.parse_args()

    load_dotenv_file(args.root_dir / ".env")
    deadline_paths = resolve_deadline_files(
        [f"data/deadlines/{args.year}.yaml"],
        root=args.root_dir,
    )
    if not deadline_paths or not deadline_paths[0].exists():
        raise SystemExit(f"Missing deadline file: data/deadlines/{args.year}.yaml")

    deadlines = load_deadlines(deadline_paths)
    output_dir = args.output_dir or args.root_dir / "build"
    output_dir.mkdir(parents=True, exist_ok=True)

    report = orchestration_step_data_curation(
        deadlines,
        scrape_page=_fetch_page_text,
        target_year=args.year,
        current_date=date.today(),
    )

    markdown_path = output_dir / f"curation-{args.year}.md"
    jsonl_path = output_dir / f"curation-{args.year}.jsonl"

    markdown_parts = [
        f"# Deadline Curation Report {args.year}",
        "",
        f"Generated on {date.today().isoformat()}",
        "",
    ]
    for item in report:
        markdown_parts.append(item["markdown"])
        markdown_parts.append("")

    markdown_path.write_text("\n".join(markdown_parts), encoding="utf-8")
    jsonl_path.write_text(
        "".join(f"{item['jsonl']}\n" for item in report),
        encoding="utf-8",
    )

    print(f"Wrote markdown report: {markdown_path}")
    print(f"Wrote JSONL report: {jsonl_path}")
    return 0


def _fetch_page_text(url: str) -> str:
    _ensure_src_path()
    from media_calendar.components import extract_source_text

    request = Request(
        url,
        headers={
            "User-Agent": "MediaCalendarBot/0.1 (+https://github.com/covifranklin/Media-Calendar)"
        },
    )
    with urlopen(request, timeout=20) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        content_type = response.headers.get("Content-Type")
        html = response.read().decode(charset, errors="replace")

    return extract_source_text(html, content_type=content_type)


if __name__ == "__main__":
    raise SystemExit(main())
