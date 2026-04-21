"""Deterministic project components."""

from media_calendar.components.calendar_generator import generate_calendar
from media_calendar.components.deadline_store import (
    load_deadlines,
    resolve_deadline_files,
    write_deadlines,
)
from media_calendar.components.discovery_comparator import (
    compare_candidate_batch,
    compare_candidate_batches,
    compare_candidates,
)
from media_calendar.components.discovery_promoter import (
    auto_promote_discovery_results,
)
from media_calendar.components.source_fetcher import (
    fetch_registered_sources,
    fetch_source,
    fetch_sources,
)
from media_calendar.components.source_health import build_source_health_report
from media_calendar.components.source_detector import (
    detect_candidate_batches,
    detect_candidates,
)
from media_calendar.components.source_registry import (
    load_source_registry,
    resolve_source_files,
)
from media_calendar.components.source_snapshotter import snapshot_fetch_results
from media_calendar.components.source_text import extract_source_text

__all__ = [
    "build_source_health_report",
    "auto_promote_discovery_results",
    "compare_candidate_batch",
    "compare_candidate_batches",
    "compare_candidates",
    "detect_candidate_batches",
    "detect_candidates",
    "extract_source_text",
    "fetch_registered_sources",
    "fetch_source",
    "fetch_sources",
    "generate_calendar",
    "load_deadlines",
    "load_source_registry",
    "resolve_deadline_files",
    "resolve_source_files",
    "snapshot_fetch_results",
    "write_deadlines",
]
