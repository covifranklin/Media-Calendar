"""Helpers for loading and filtering deadline data from YAML files."""

from __future__ import annotations

from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Iterable, List, Sequence

from media_calendar.models import Deadline

DEFAULT_DATA_DIR = Path("data/deadlines")


def resolve_deadline_files(
    deadline_files: Iterable[str | Path] | None,
    *,
    root: Path,
) -> List[Path]:
    """Resolve explicit or default deadline YAML paths relative to a project root."""

    if deadline_files is None:
        return sorted((root / DEFAULT_DATA_DIR).glob("*.yaml"))

    resolved: List[Path] = []
    for path in deadline_files:
        candidate = Path(path)
        resolved.append(candidate if candidate.is_absolute() else root / candidate)
    return resolved


def load_deadlines(deadline_files: Sequence[Path]) -> List[Deadline]:
    """Load deadline records from YAML files."""

    yaml = import_yaml()
    deadlines: List[Deadline] = []

    for path in deadline_files:
        if not path.exists():
            continue

        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        if payload is None:
            continue

        records = payload.get("deadlines", []) if isinstance(payload, dict) else payload
        if not isinstance(records, list):
            raise ValueError(f"Expected a list of deadlines in {path}")

        for record in records:
            deadlines.append(Deadline.model_validate(record))

    deadlines.sort(key=lambda item: (item.deadline_date, item.name.lower()))
    return deadlines


def filter_upcoming_deadlines(
    deadlines: Sequence[Deadline],
    *,
    current_date: date,
) -> List[Deadline]:
    """Keep only deadlines that are still upcoming and active."""

    return sorted(
        [
            deadline
            for deadline in deadlines
            if deadline.status not in {"expired", "cancelled"}
            and deadline.deadline_date >= current_date
        ],
        key=lambda item: (item.deadline_date, item.name.lower()),
    )


def write_deadlines(
    deadlines: Sequence[Deadline],
    *,
    root: Path,
    output_dir: str | Path | None = None,
) -> List[Path]:
    """Write deadlines back to year-based YAML files deterministically."""

    yaml = import_yaml()
    target_dir = (
        Path(output_dir)
        if output_dir is not None and Path(output_dir).is_absolute()
        else root / (Path(output_dir) if output_dir is not None else DEFAULT_DATA_DIR)
    )
    target_dir.mkdir(parents=True, exist_ok=True)

    grouped: dict[int, List[Deadline]] = defaultdict(list)
    for deadline in deadlines:
        grouped[deadline.year].append(deadline)

    written_paths: List[Path] = []
    for year in sorted(grouped):
        path = target_dir / f"{year}.yaml"
        records = [
            deadline.model_dump(mode="json")
            for deadline in sorted(
                grouped[year],
                key=lambda item: (item.deadline_date, item.name.lower()),
            )
        ]
        path.write_text(
            yaml.safe_dump(records, sort_keys=False, allow_unicode=False),
            encoding="utf-8",
        )
        written_paths.append(path)

    return written_paths


def import_yaml():
    """Import PyYAML lazily so import errors surface only when YAML is needed."""

    try:
        import yaml
    except ImportError as exc:  # pragma: no cover - exercised in real runtime only
        raise RuntimeError("PyYAML is required to load deadline files.") from exc
    return yaml
