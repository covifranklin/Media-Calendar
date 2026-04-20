"""Calendar generator orchestration step."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Callable, Iterable

from media_calendar.components import generate_calendar

STEP_NAME = "Generate Calendar"
AGENT_NAME = "calendar_generator"
DESCRIPTION = (
    "Executes the deterministic script to read deadline data and generate the "
    "static HTML calendar."
)
INPUT_SOURCE = "data/deadlines/*.yaml files."
OUTPUT_DESTINATION = "build/calendar.html."
CONDITION = "Triggered on every push to main branch via GitHub Actions CI."
ERROR_HANDLING = "CI pipeline failure on script error, human review of generated HTML."

CalendarGenerator = Callable[..., Path]
ReportWriter = Callable[[dict], None]


def orchestration_step_calendar_generator(
    deadline_files: Iterable[str | Path] | None = None,
    *,
    root_dir: str | Path | None = None,
    generator: CalendarGenerator = generate_calendar,
    report_writer: ReportWriter | None = None,
    logger: logging.Logger | None = None,
) -> dict:
    """Generate the static calendar as a CI-friendly orchestration step."""

    active_logger = logger or logging.getLogger(__name__)
    root = Path(root_dir) if root_dir is not None else Path.cwd()
    resolved_input_files = _resolve_input_files(deadline_files, root=root)

    try:
        output_path = generator(deadline_files=deadline_files, root_dir=root)
    except Exception:
        active_logger.exception("calendar_generator failed")
        raise

    payload = {
        "step_name": STEP_NAME,
        "agent_name": AGENT_NAME,
        "description": DESCRIPTION,
        "input_source": INPUT_SOURCE,
        "output_destination": OUTPUT_DESTINATION,
        "condition": CONDITION,
        "error_handling": ERROR_HANDLING,
        "input_files": [str(path) for path in resolved_input_files],
        "output_path": str(output_path),
        "html_exists": output_path.exists(),
        "requires_human_review": True,
    }

    if report_writer is not None:
        report_writer(payload)

    return payload


def _resolve_input_files(
    deadline_files: Iterable[str | Path] | None,
    *,
    root: Path,
):
    if deadline_files is None:
        return sorted((root / "data" / "deadlines").glob("*.yaml"))
    return [Path(path) if Path(path).is_absolute() else root / Path(path) for path in deadline_files]
