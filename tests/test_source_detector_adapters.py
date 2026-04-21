from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from media_calendar.components import detect_candidates
from media_calendar.models import SourceRegistryEntry, SourceSnapshotResult


def build_snapshot_result(
    *,
    source_entry: SourceRegistryEntry,
    extracted_text: str,
) -> SourceSnapshotResult:
    return SourceSnapshotResult(
        source_id=source_entry.id,
        organization=source_entry.organization,
        program_name=source_entry.program_name,
        source_url=source_entry.source_url,
        status="success",
        fetched_at=datetime(2026, 4, 21, 12, 0, tzinfo=timezone.utc),
        http_status=200,
        content_type="text/html",
        snapshot_path="/tmp/source.html",
        text_path="/tmp/source.txt",
        extracted_text=extracted_text,
        error_message=None,
    )


def test_sundance_adapter_extracts_multiple_program_blocks():
    source_entry = SourceRegistryEntry(
        id=UUID("8f7fa5f3-0e89-41be-983d-e832622c7d1a"),
        organization="Sundance Institute",
        program_name="Artist Opportunities",
        source_url="https://www.sundance.org/apply",
        source_type="lab",
        deadline_categories=["lab_application", "fellowship"],
        regions=["North America", "Global"],
        cadence="annual",
        coverage_priority="must_have",
        discovery_strategy="official_program_page",
    )
    snapshot_result = build_snapshot_result(
        source_entry=source_entry,
        extracted_text=(
            "Artist Opportunities\n"
            "Documentary Film Program\n"
            "Applications open\n"
            "Early deadline: May 1, 2026\n"
            "Final deadline: June 1, 2026\n"
            "Episodic Lab\n"
            "Applications open\n"
            "Deadline: July 15, 2026"
        ),
    )

    batch = detect_candidates(snapshot_result, source_entry)

    assert "source-specific adapter" in (batch.notes or "")
    assert len(batch.candidates) == 2
    assert [candidate.name for candidate in batch.candidates] == [
        "Documentary Film Program",
        "Episodic Lab",
    ]
    assert batch.candidates[0].detected_early_deadline_text == "May 1, 2026"
    assert batch.candidates[0].detected_deadline_text == "June 1, 2026"
    assert batch.candidates[1].detected_deadline_text == "July 15, 2026"


def test_bfi_network_adapter_extracts_multiple_funding_blocks():
    source_entry = SourceRegistryEntry(
        id=UUID("f5e99faf-ac8b-4c58-bc8c-63807bcedf2e"),
        organization="BFI NETWORK",
        program_name="Funding Opportunities",
        source_url="https://www.bfi.org.uk/get-funding-support/bfi-network/bfi-network-funding",
        source_type="fund",
        deadline_categories=["funding_round", "other"],
        regions=["United Kingdom"],
        cadence="periodic",
        coverage_priority="must_have",
        discovery_strategy="official_application_page",
    )
    snapshot_result = build_snapshot_result(
        source_entry=source_entry,
        extracted_text=(
            "Funding Opportunities\n"
            "Early Development Fund\n"
            "Deadline: March 15, 2026\n"
            "Short Film Funding\n"
            "Deadline: April 30, 2026"
        ),
    )

    batch = detect_candidates(snapshot_result, source_entry)

    assert len(batch.candidates) == 2
    assert [candidate.name for candidate in batch.candidates] == [
        "Early Development Fund",
        "Short Film Funding",
    ]
    assert all(candidate.category == "funding_round" for candidate in batch.candidates)


def test_series_mania_adapter_extracts_forum_programmes_with_dates():
    source_entry = SourceRegistryEntry(
        id=UUID("7f6b4ef8-d80b-4cb1-97db-181f0781cf25"),
        organization="Series Mania Forum",
        program_name="Forum and Co-Pro Pitching",
        source_url="https://seriesmania.com/forum/en/",
        source_type="market",
        deadline_categories=["industry_forum", "other"],
        regions=["Europe", "Global"],
        cadence="annual",
        coverage_priority="must_have",
        discovery_strategy="official_program_page",
    )
    snapshot_result = build_snapshot_result(
        source_entry=source_entry,
        extracted_text=(
            "Series Mania Forum\n"
            "Seriesmakers\n"
            "Applications open\n"
            "Deadline: October 7, 2026\n"
            "Co-Pro Pitching Sessions\n"
            "Deadline: November 3, 2026\n"
            "Event dates: March 20-27, 2027"
        ),
    )

    batch = detect_candidates(snapshot_result, source_entry)

    assert len(batch.candidates) == 2
    assert [candidate.name for candidate in batch.candidates] == [
        "Seriesmakers",
        "Co-Pro Pitching Sessions",
    ]
    assert batch.candidates[0].detected_deadline_text == "October 7, 2026"
    assert batch.candidates[1].detected_deadline_text == "November 3, 2026"
    assert batch.candidates[1].detected_event_date_text == "March 20-27, 2027"
