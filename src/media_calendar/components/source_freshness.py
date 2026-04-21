"""Deterministic source freshness reporting."""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Sequence
from uuid import UUID

from media_calendar.components.source_health import THIN_TEXT_WORD_THRESHOLD
from media_calendar.models import (
    DiscoveryCandidateBatch,
    SourceFreshnessEntry,
    SourceFreshnessReport,
    SourceRegistryEntry,
    SourceSnapshotResult,
)

_STATUS_ORDER = {
    "healthy": 0,
    "degraded": 1,
    "stale": 2,
    "failing": 3,
}


def build_source_freshness_report(
    source_entries: Sequence[SourceRegistryEntry],
    snapshot_results: Sequence[SourceSnapshotResult],
    candidate_batches: Sequence[DiscoveryCandidateBatch],
) -> SourceFreshnessReport:
    """Build a deterministic freshness report across monitored sources."""

    snapshots_by_source: Dict[UUID, List[SourceSnapshotResult]] = defaultdict(list)
    for snapshot in snapshot_results:
        snapshots_by_source[snapshot.source_id].append(snapshot)
    for snapshots in snapshots_by_source.values():
        snapshots.sort(key=lambda item: item.fetched_at, reverse=True)

    batches_by_source: Dict[str, List[DiscoveryCandidateBatch]] = defaultdict(list)
    for batch in candidate_batches:
        batches_by_source[batch.source_id].append(batch)

    entries = [
        _build_entry(
            source_entry,
            snapshots_by_source.get(source_entry.id, []),
            batches_by_source.get(str(source_entry.id), []),
        )
        for source_entry in source_entries
    ]
    entries.sort(
        key=lambda item: (
            _STATUS_ORDER[item.freshness_status],
            item.coverage_priority,
            item.organization.lower(),
            item.program_name.lower(),
        )
    )

    counts = Counter(entry.freshness_status for entry in entries)
    counts_by_status = {
        "healthy": counts.get("healthy", 0),
        "degraded": counts.get("degraded", 0),
        "stale": counts.get("stale", 0),
        "failing": counts.get("failing", 0),
    }

    report = SourceFreshnessReport(
        generated_at=datetime.now(timezone.utc),
        total_sources=len(source_entries),
        counts_by_status=counts_by_status,
        entries=entries,
        markdown="",
    )
    return report.model_copy(update={"markdown": _build_markdown_report(report)})


def write_source_freshness_report(
    report: SourceFreshnessReport,
    *,
    root_dir: str | Path | None = None,
    output_dir: str | Path | None = None,
) -> Dict[str, Path]:
    """Persist a JSON and Markdown freshness report to the build directory."""

    root = Path(root_dir) if root_dir is not None else Path.cwd()
    target_dir = (
        Path(output_dir)
        if output_dir is not None and Path(output_dir).is_absolute()
        else root / (Path(output_dir) if output_dir is not None else Path("build"))
    )
    target_dir.mkdir(parents=True, exist_ok=True)

    json_path = target_dir / "source-freshness.json"
    markdown_path = target_dir / "source-freshness.md"

    json_path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    markdown_path.write_text(report.markdown, encoding="utf-8")
    return {"json": json_path, "markdown": markdown_path}


def _build_entry(
    source_entry: SourceRegistryEntry,
    snapshots: Sequence[SourceSnapshotResult],
    candidate_batches: Sequence[DiscoveryCandidateBatch],
) -> SourceFreshnessEntry:
    latest_snapshot = snapshots[0] if snapshots else None
    latest_batch = candidate_batches[-1] if candidate_batches else None

    success_snapshots = [snapshot for snapshot in snapshots if snapshot.status == "success"]
    failure_snapshots = [snapshot for snapshot in snapshots if snapshot.status != "success"]
    weak_text_snapshots = [
        snapshot
        for snapshot in success_snapshots
        if _is_weak_text(snapshot.extracted_text)
    ]
    candidate_positive_count = sum(1 for batch in candidate_batches if batch.candidates)
    candidate_zero_count = sum(1 for batch in candidate_batches if not batch.candidates)
    latest_word_count = _word_count(latest_snapshot.extracted_text) if latest_snapshot else 0
    latest_candidate_count = len(latest_batch.candidates) if latest_batch else 0

    status, issue_codes = _classify_source(
        source_entry=source_entry,
        snapshots=snapshots,
        success_count=len(success_snapshots),
        failure_count=len(failure_snapshots),
        weak_text_count=len(weak_text_snapshots),
        candidate_positive_count=candidate_positive_count,
        candidate_zero_count=candidate_zero_count,
        latest_snapshot=latest_snapshot,
        latest_candidate_count=latest_candidate_count,
    )

    return SourceFreshnessEntry(
        source_id=source_entry.id,
        organization=source_entry.organization,
        program_name=source_entry.program_name,
        source_url=source_entry.source_url,
        coverage_priority=source_entry.coverage_priority,
        freshness_status=status,
        latest_fetch_status=latest_snapshot.status if latest_snapshot is not None else None,
        latest_fetched_at=latest_snapshot.fetched_at if latest_snapshot is not None else None,
        latest_word_count=latest_word_count,
        latest_candidate_count=latest_candidate_count,
        snapshot_count=len(snapshots),
        success_count=len(success_snapshots),
        failure_count=len(failure_snapshots),
        weak_text_count=len(weak_text_snapshots),
        candidate_positive_count=candidate_positive_count,
        candidate_zero_count=candidate_zero_count,
        issue_codes=issue_codes,
        summary=_build_summary(
            status=status,
            source_entry=source_entry,
            latest_snapshot=latest_snapshot,
            latest_candidate_count=latest_candidate_count,
            issue_codes=issue_codes,
            weak_text_count=len(weak_text_snapshots),
            failure_count=len(failure_snapshots),
            candidate_positive_count=candidate_positive_count,
            candidate_zero_count=candidate_zero_count,
        ),
    )


def _classify_source(
    *,
    source_entry: SourceRegistryEntry,
    snapshots: Sequence[SourceSnapshotResult],
    success_count: int,
    failure_count: int,
    weak_text_count: int,
    candidate_positive_count: int,
    candidate_zero_count: int,
    latest_snapshot: SourceSnapshotResult | None,
    latest_candidate_count: int,
) -> tuple[str, List[str]]:
    issue_codes: List[str] = []
    is_strict_priority = source_entry.coverage_priority == "must_have"
    failing_threshold = 2 if is_strict_priority else 3
    stale_threshold = 2 if is_strict_priority else 3

    if not snapshots:
        issue_codes.append("missing_history")
        return "stale", issue_codes

    if latest_snapshot is not None and latest_snapshot.status != "success":
        issue_codes.append(latest_snapshot.status)
        if failure_count >= failing_threshold or success_count == 0:
            issue_codes.append("repeated_fetch_failures")
            return "failing", issue_codes
        return "degraded", issue_codes

    if latest_snapshot is not None and _is_empty_text(latest_snapshot.extracted_text):
        issue_codes.append("empty_text")
    elif latest_snapshot is not None and _is_weak_text(latest_snapshot.extracted_text):
        issue_codes.append("thin_text")

    if weak_text_count >= stale_threshold:
        issue_codes.append("repeated_weak_text")
        return "stale", issue_codes

    if candidate_positive_count == 0 and candidate_zero_count >= stale_threshold:
        issue_codes.append("no_recent_candidates")
        return "stale", issue_codes

    if issue_codes:
        return "degraded", issue_codes

    if latest_candidate_count == 0:
        issue_codes.append("latest_batch_no_candidates")
        return "degraded", issue_codes

    return "healthy", issue_codes


def _build_summary(
    *,
    status: str,
    source_entry: SourceRegistryEntry,
    latest_snapshot: SourceSnapshotResult | None,
    latest_candidate_count: int,
    issue_codes: Sequence[str],
    weak_text_count: int,
    failure_count: int,
    candidate_positive_count: int,
    candidate_zero_count: int,
) -> str:
    if not latest_snapshot:
        return "No recent snapshot history is available for this monitored source."

    if status == "failing":
        return (
            f"{source_entry.coverage_priority} source is failing because recent fetches "
            f"did not succeed often enough ({failure_count} failed snapshot(s))."
        )
    if status == "stale":
        if "repeated_weak_text" in issue_codes:
            return (
                f"Recent successful fetches were repeatedly weak "
                f"({weak_text_count} weak text result(s)), so discovery signals look stale."
            )
        return (
            "Recent successful fetches did not yield usable opportunity signals often "
            f"enough ({candidate_zero_count} candidate-free batch(es))."
        )
    if status == "degraded":
        return (
            f"Latest fetch status is {latest_snapshot.status} with {latest_candidate_count} "
            "candidate(s), so this source needs attention but is not yet stale."
        )
    return (
        f"Latest successful snapshot produced {latest_candidate_count} candidate(s), "
        f"and recent history shows {candidate_positive_count} productive batch(es)."
    )


def _build_markdown_report(report: SourceFreshnessReport) -> str:
    lines = [
        "# Source Freshness Report",
        "",
        f"- Total Sources: `{report.total_sources}`",
        f"- Healthy: `{report.counts_by_status['healthy']}`",
        f"- Degraded: `{report.counts_by_status['degraded']}`",
        f"- Stale: `{report.counts_by_status['stale']}`",
        f"- Failing: `{report.counts_by_status['failing']}`",
        "",
    ]

    for entry in report.entries:
        lines.extend(
            [
                f"## {entry.organization} - {entry.program_name}",
                f"- Coverage Priority: `{entry.coverage_priority}`",
                f"- Freshness Status: `{entry.freshness_status}`",
                f"- Latest Fetch Status: `{entry.latest_fetch_status}`",
                f"- Latest Word Count: `{entry.latest_word_count}`",
                f"- Latest Candidate Count: `{entry.latest_candidate_count}`",
                f"- Snapshot Count: `{entry.snapshot_count}`",
                f"- Success Count: `{entry.success_count}`",
                f"- Failure Count: `{entry.failure_count}`",
                f"- Weak Text Count: `{entry.weak_text_count}`",
                f"- Candidate-Positive Batches: `{entry.candidate_positive_count}`",
                f"- Candidate-Zero Batches: `{entry.candidate_zero_count}`",
                f"- Issues: `{', '.join(entry.issue_codes) or 'none'}`",
                f"- Summary: {entry.summary}",
                "",
            ]
        )

    return "\n".join(lines)


def _word_count(extracted_text: str | None) -> int:
    return len((extracted_text or "").split())


def _is_empty_text(extracted_text: str | None) -> bool:
    return not (extracted_text or "").strip()


def _is_weak_text(extracted_text: str | None) -> bool:
    text = (extracted_text or "").strip()
    return not text or len(text.split()) < THIN_TEXT_WORD_THRESHOLD
