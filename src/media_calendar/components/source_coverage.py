"""Deterministic source coverage reporting."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Dict, Iterable

from media_calendar.components.source_registry import (
    load_source_registry,
    resolve_source_files,
)
from media_calendar.models import (
    SourceCoverageGapSummary,
    SourceCoverageReport,
    SourceCoverageSourceSummary,
    SourceRegistryEntry,
)

_COVERAGE_PRIORITIES = ["must_have", "high", "medium", "watchlist"]
_SOURCE_TYPES = [
    "festival",
    "fund",
    "lab",
    "fellowship",
    "market",
    "guild_program",
    "broadcaster_program",
    "industry_forum",
    "other",
]
_DEADLINE_CATEGORIES = [
    "festival_submission",
    "funding_round",
    "lab_application",
    "fellowship",
    "industry_forum",
    "other",
]


def build_source_coverage_report(
    source_files: Iterable[str | Path] | None = None,
    *,
    root_dir: str | Path | None = None,
) -> SourceCoverageReport:
    """Build a structured coverage report from source registry YAML files."""

    root = Path(root_dir) if root_dir is not None else Path.cwd()
    paths = resolve_source_files(source_files, root=root)
    entries = load_source_registry(paths)
    return _build_report_from_entries(entries)


def write_source_coverage_report(
    report: SourceCoverageReport,
    *,
    root_dir: str | Path | None = None,
    output_dir: str | Path | None = None,
) -> Dict[str, Path]:
    """Persist a JSON and Markdown coverage report to the build directory."""

    root = Path(root_dir) if root_dir is not None else Path.cwd()
    target_dir = (
        Path(output_dir)
        if output_dir is not None and Path(output_dir).is_absolute()
        else root / (Path(output_dir) if output_dir is not None else Path("build"))
    )
    target_dir.mkdir(parents=True, exist_ok=True)

    json_path = target_dir / "coverage-report.json"
    markdown_path = target_dir / "coverage-report.md"

    json_path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    markdown_path.write_text(_build_markdown_report(report), encoding="utf-8")
    return {"json": json_path, "markdown": markdown_path}


def _build_report_from_entries(
    entries: list[SourceRegistryEntry],
) -> SourceCoverageReport:
    priority_counts = _initialize_counts(_COVERAGE_PRIORITIES)
    source_type_counts = _initialize_counts(_SOURCE_TYPES)
    category_counts = _initialize_counts(_DEADLINE_CATEGORIES)
    region_counts: Counter[str] = Counter()

    for entry in entries:
        priority_counts[entry.coverage_priority] += 1
        source_type_counts[entry.source_type] += 1
        region_counts.update(entry.regions)
        for category in entry.deadline_categories:
            category_counts[category] += 1

    must_have_sources = [
        _to_source_summary(entry)
        for entry in entries
        if entry.coverage_priority == "must_have"
    ]
    high_sources = [
        _to_source_summary(entry)
        for entry in entries
        if entry.coverage_priority == "high"
    ]

    return SourceCoverageReport(
        total_source_count=len(entries),
        counts_by_coverage_priority=priority_counts,
        counts_by_source_type=source_type_counts,
        counts_by_deadline_category=category_counts,
        counts_by_region=dict(sorted(region_counts.items())),
        must_have_sources=must_have_sources,
        high_sources=high_sources,
        gap_summary=_build_gap_summary(
            entries=entries,
            priority_counts=priority_counts,
            source_type_counts=source_type_counts,
            category_counts=category_counts,
        ),
    )


def _initialize_counts(keys: list[str]) -> Dict[str, int]:
    return {key: 0 for key in keys}


def _to_source_summary(entry: SourceRegistryEntry) -> SourceCoverageSourceSummary:
    return SourceCoverageSourceSummary(
        organization=entry.organization,
        program_name=entry.program_name,
        source_url=entry.source_url,
        source_type=entry.source_type,
        coverage_priority=entry.coverage_priority,
        regions=list(entry.regions),
        deadline_categories=list(entry.deadline_categories),
    )


def _build_gap_summary(
    *,
    entries: list[SourceRegistryEntry],
    priority_counts: Dict[str, int],
    source_type_counts: Dict[str, int],
    category_counts: Dict[str, int],
) -> SourceCoverageGapSummary:
    must_have_entries = [
        entry for entry in entries if entry.coverage_priority == "must_have"
    ]
    must_have_categories = {
        category
        for entry in must_have_entries
        for category in entry.deadline_categories
    }
    tracked_regions = {region for entry in entries for region in entry.regions}
    must_have_regions = {
        region
        for entry in must_have_entries
        for region in entry.regions
    }

    suspicious_groupings: list[str] = []
    if not entries:
        suspicious_groupings.append("No source entries were loaded.")
    if priority_counts["must_have"] == 0:
        suspicious_groupings.append("No must-have sources are currently tracked.")
    if priority_counts["high"] == 0:
        suspicious_groupings.append("No high-priority sources are currently tracked.")

    for source_type, count in source_type_counts.items():
        if count == 0:
            suspicious_groupings.append(
                f"No sources are tracked for source_type={source_type}."
            )

    for category, count in category_counts.items():
        if count == 0:
            suspicious_groupings.append(
                f"No sources are tracked for deadline_category={category}."
            )

    return SourceCoverageGapSummary(
        categories_without_must_have_coverage=sorted(
            category
            for category in _DEADLINE_CATEGORIES
            if category not in must_have_categories
        ),
        regions_without_must_have_coverage=sorted(tracked_regions - must_have_regions),
        suspicious_groupings=suspicious_groupings,
    )


def _build_markdown_report(report: SourceCoverageReport) -> str:
    lines = [
        "# Source Coverage Report",
        "",
        f"- Total source count: `{report.total_source_count}`",
        "",
        "## Counts By Coverage Priority",
        "",
    ]
    lines.extend(_format_count_lines(report.counts_by_coverage_priority))
    lines.extend(["", "## Counts By Source Type", ""])
    lines.extend(_format_count_lines(report.counts_by_source_type))
    lines.extend(["", "## Counts By Deadline Category", ""])
    lines.extend(_format_count_lines(report.counts_by_deadline_category))
    lines.extend(["", "## Counts By Region", ""])
    lines.extend(_format_count_lines(report.counts_by_region))
    lines.extend(["", "## Must-Have Sources", ""])
    lines.extend(_format_source_lines(report.must_have_sources))
    lines.extend(["", "## High-Priority Sources", ""])
    lines.extend(_format_source_lines(report.high_sources))
    lines.extend(["", "## Gap Summary", ""])
    lines.append(
        "- Categories without must-have coverage: "
        + _format_list_value(report.gap_summary.categories_without_must_have_coverage)
    )
    lines.append(
        "- Regions without must-have coverage: "
        + _format_list_value(report.gap_summary.regions_without_must_have_coverage)
    )
    lines.append(
        "- Suspicious groupings: "
        + _format_list_value(report.gap_summary.suspicious_groupings)
    )
    return "\n".join(lines)


def _format_count_lines(counts: Dict[str, int]) -> list[str]:
    return [f"- `{key}`: `{value}`" for key, value in counts.items()]


def _format_source_lines(sources: list[SourceCoverageSourceSummary]) -> list[str]:
    if not sources:
        return ["- None"]
    return [
        f"- {source.organization} - {source.program_name} ({source.source_url})"
        for source in sources
    ]


def _format_list_value(values: list[str]) -> str:
    if not values:
        return "None"
    return ", ".join(f"`{value}`" for value in values)
