"""Helpers for loading source registry data from YAML files."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, List, Sequence

from media_calendar.models import SourceRegistryEntry

DEFAULT_SOURCE_DIR = Path("data/sources")

_PRIORITY_ORDER = {
    "must_have": 0,
    "high": 1,
    "medium": 2,
    "watchlist": 3,
}


def resolve_source_files(
    source_files: Iterable[str | Path] | None,
    *,
    root: Path,
) -> List[Path]:
    """Resolve explicit or default source registry paths relative to a root."""

    if source_files is None:
        return sorted((root / DEFAULT_SOURCE_DIR).glob("*.yaml"))

    resolved: List[Path] = []
    for path in source_files:
        candidate = Path(path)
        resolved.append(candidate if candidate.is_absolute() else root / candidate)
    return resolved


def load_source_registry(source_files: Sequence[Path]) -> List[SourceRegistryEntry]:
    """Load validated source registry entries from YAML files."""

    yaml = import_yaml()
    entries: List[SourceRegistryEntry] = []

    for path in source_files:
        if not path.exists():
            continue

        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        if payload is None:
            continue

        records = payload.get("sources", []) if isinstance(payload, dict) else payload
        if not isinstance(records, list):
            raise ValueError(f"Expected a list of sources in {path}")

        for record in records:
            entries.append(SourceRegistryEntry.model_validate(record))

    entries.sort(
        key=lambda item: (
            _PRIORITY_ORDER[item.coverage_priority],
            item.organization.lower(),
            item.program_name.lower(),
        )
    )
    return entries


def import_yaml():
    """Import PyYAML lazily so errors surface only when YAML is needed."""

    try:
        import yaml
    except ImportError as exc:  # pragma: no cover - exercised in real runtime only
        raise RuntimeError("PyYAML is required to load source files.") from exc
    return yaml
