from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from media_calendar.components import build_source_freshness_report
from media_calendar.models import (
    DiscoveryCandidate,
    DiscoveryCandidateBatch,
    SourceRegistryEntry,
    SourceSnapshotResult,
)


def build_source_entry(*, coverage_priority="must_have") -> SourceRegistryEntry:
    return SourceRegistryEntry(
        id=uuid4(),
        organization="Example Org",
        program_name="Example Program",
        source_url="https://example.com/program",
        source_type="lab",
        deadline_categories=["lab_application"],
        regions=["Global"],
        cadence="annual",
        coverage_priority=coverage_priority,
        discovery_strategy="official_program_page",
    )


def build_snapshot_result(
    source_entry: SourceRegistryEntry,
    *,
    fetched_at: datetime,
    status="success",
    extracted_text=(
        "This monitored source still has enough useful text to be considered "
        "substantial content for discovery, review, automated freshness checks, "
        "coverage monitoring, ongoing source maintenance, and reliable candidate "
        "detection across multiple scheduled refresh runs in the project."
    ),
) -> SourceSnapshotResult:
    return SourceSnapshotResult(
        source_id=source_entry.id,
        organization=source_entry.organization,
        program_name=source_entry.program_name,
        source_url=source_entry.source_url,
        status=status,
        fetched_at=fetched_at,
        http_status=200 if status == "success" else 403,
        content_type="text/html" if status == "success" else None,
        snapshot_path="/tmp/example.html" if status == "success" else None,
        text_path="/tmp/example.txt" if status == "success" else None,
        extracted_text=extracted_text if status == "success" else None,
        error_message="HTTP Error 403: Forbidden" if status != "success" else None,
    )


def build_candidate_batch(
    source_entry: SourceRegistryEntry,
    *,
    candidate_count: int,
) -> DiscoveryCandidateBatch:
    candidates = [
        DiscoveryCandidate(
            id=uuid4(),
            source_id=source_entry.id,
            source_url=source_entry.source_url,
            organization=source_entry.organization,
            name=f"Opportunity {index}",
            category="lab_application",
            candidate_type="new_opportunity",
            confidence=0.8,
            rationale="Deterministic signal.",
            detected_deadline_text="June 1, 2026",
            regions=["Global"],
            tags=["lab"],
            raw_excerpt="Applications open now Deadline: June 1, 2026",
        )
        for index in range(candidate_count)
    ]
    return DiscoveryCandidateBatch(
        source_id=str(source_entry.id),
        source_url=source_entry.source_url,
        organization=source_entry.organization,
        program_name=source_entry.program_name,
        candidates=candidates,
        notes=None,
    )


def test_build_source_freshness_report_marks_healthy_source():
    source_entry = build_source_entry()
    now = datetime(2026, 4, 21, 12, 0, tzinfo=timezone.utc)
    snapshots = [
        build_snapshot_result(source_entry, fetched_at=now),
        build_snapshot_result(source_entry, fetched_at=now - timedelta(days=7)),
    ]
    batches = [
        build_candidate_batch(source_entry, candidate_count=2),
        build_candidate_batch(source_entry, candidate_count=1),
    ]

    report = build_source_freshness_report([source_entry], snapshots, batches)

    assert report.counts_by_status["healthy"] == 1
    assert report.entries[0].freshness_status == "healthy"
    assert report.entries[0].latest_candidate_count == 1


def test_build_source_freshness_report_marks_stale_source_after_repeated_zero_candidate_batches():
    source_entry = build_source_entry(coverage_priority="must_have")
    now = datetime(2026, 4, 21, 12, 0, tzinfo=timezone.utc)
    snapshots = [
        build_snapshot_result(source_entry, fetched_at=now),
        build_snapshot_result(source_entry, fetched_at=now - timedelta(days=7)),
    ]
    batches = [
        build_candidate_batch(source_entry, candidate_count=0),
        build_candidate_batch(source_entry, candidate_count=0),
    ]

    report = build_source_freshness_report([source_entry], snapshots, batches)

    assert report.counts_by_status["stale"] == 1
    assert report.entries[0].freshness_status == "stale"
    assert "no_recent_candidates" in report.entries[0].issue_codes


def test_build_source_freshness_report_marks_failing_source_after_repeated_fetch_failures():
    source_entry = build_source_entry(coverage_priority="must_have")
    now = datetime(2026, 4, 21, 12, 0, tzinfo=timezone.utc)
    snapshots = [
        build_snapshot_result(source_entry, fetched_at=now, status="http_error"),
        build_snapshot_result(
            source_entry,
            fetched_at=now - timedelta(days=7),
            status="network_error",
        ),
    ]

    report = build_source_freshness_report([source_entry], snapshots, [])

    assert report.counts_by_status["failing"] == 1
    assert report.entries[0].freshness_status == "failing"
    assert "repeated_fetch_failures" in report.entries[0].issue_codes


def test_build_source_freshness_report_treats_watchlist_less_strictly_than_must_have():
    must_have = build_source_entry(coverage_priority="must_have")
    watchlist = build_source_entry(coverage_priority="watchlist").model_copy(
        update={
            "id": uuid4(),
            "organization": "Watchlist Org",
            "program_name": "Watchlist Program",
            "source_url": "https://example.com/watchlist",
        }
    )
    now = datetime(2026, 4, 21, 12, 0, tzinfo=timezone.utc)
    snapshots = [
        build_snapshot_result(must_have, fetched_at=now),
        build_snapshot_result(must_have, fetched_at=now - timedelta(days=7)),
        build_snapshot_result(watchlist, fetched_at=now),
        build_snapshot_result(watchlist, fetched_at=now - timedelta(days=7)),
    ]
    batches = [
        build_candidate_batch(must_have, candidate_count=0),
        build_candidate_batch(must_have, candidate_count=0),
        build_candidate_batch(watchlist, candidate_count=0),
        build_candidate_batch(watchlist, candidate_count=0),
    ]

    report = build_source_freshness_report(
        [must_have, watchlist],
        snapshots,
        batches,
    )
    statuses = {entry.organization: entry.freshness_status for entry in report.entries}

    assert statuses["Example Org"] == "stale"
    assert statuses["Watchlist Org"] == "degraded"


def test_build_source_freshness_report_includes_markdown_summary():
    source_entry = build_source_entry()
    now = datetime(2026, 4, 21, 12, 0, tzinfo=timezone.utc)
    snapshots = [build_snapshot_result(source_entry, fetched_at=now)]
    batches = [build_candidate_batch(source_entry, candidate_count=1)]

    report = build_source_freshness_report([source_entry], snapshots, batches)

    assert "# Source Freshness Report" in report.markdown
    assert "## Example Org - Example Program" in report.markdown
