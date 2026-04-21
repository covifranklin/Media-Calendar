from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from media_calendar.components import detect_candidate_batches, detect_candidates
from media_calendar.models import SourceRegistryEntry, SourceSnapshotResult


def build_source_entry() -> SourceRegistryEntry:
    return SourceRegistryEntry(
        id=uuid4(),
        organization="Example Festival",
        program_name="Submissions",
        source_url="https://example.com/submissions",
        source_type="festival",
        deadline_categories=["festival_submission"],
        regions=["Global"],
        cadence="annual",
        coverage_priority="must_have",
        discovery_strategy="official_deadlines_page",
    )


def build_snapshot_result(
    *,
    source_id,
    status="success",
    extracted_text="Submissions open\nDeadline: June 1, 2026",
) -> SourceSnapshotResult:
    return SourceSnapshotResult(
        source_id=source_id,
        organization="Example Festival",
        program_name="Submissions",
        source_url="https://example.com/submissions",
        status=status,
        fetched_at=datetime(2026, 4, 21, 12, 0, tzinfo=timezone.utc),
        http_status=200 if status == "success" else None,
        content_type="text/html",
        snapshot_path="/tmp/example.html" if status == "success" else None,
        text_path="/tmp/example.txt" if status == "success" else None,
        extracted_text=extracted_text if status == "success" else None,
        error_message=None,
    )


def test_detect_candidates_returns_new_opportunity_with_date():
    source_entry = build_source_entry()
    snapshot_result = build_snapshot_result(
        source_id=source_entry.id,
        extracted_text="Festival submissions open now\nDeadline: June 1, 2026",
    )

    batch = detect_candidates(snapshot_result, source_entry)

    assert batch.source_id == str(source_entry.id)
    assert len(batch.candidates) == 1
    candidate = batch.candidates[0]
    assert candidate.category == "festival_submission"
    assert candidate.candidate_type == "new_opportunity"
    assert candidate.detected_deadline_text == "June 1, 2026"
    assert candidate.organization == "Example Festival"
    assert candidate.name == "Festival"


def test_detect_candidates_returns_update_signal_when_deadline_extended():
    source_entry = build_source_entry().model_copy(
        update={
            "source_type": "market",
            "deadline_categories": ["industry_forum"],
            "program_name": "Co-Pro Pitching",
        }
    )
    snapshot_result = build_snapshot_result(
        source_id=source_entry.id,
        extracted_text=(
            "Co-Pro Pitching Sessions\n"
            "Extended deadline: March 15, 2026\n"
            "Apply now"
        ),
    ).model_copy(
        update={
            "program_name": "Co-Pro Pitching",
            "organization": source_entry.organization,
            "source_url": source_entry.source_url,
        }
    )

    batch = detect_candidates(snapshot_result, source_entry)

    assert len(batch.candidates) == 1
    candidate = batch.candidates[0]
    assert candidate.candidate_type == "update_signal"
    assert candidate.category == "industry_forum"
    assert candidate.detected_deadline_text == "March 15, 2026"
    assert candidate.name == "Co-Pro Pitching Sessions"


def test_detect_candidates_returns_empty_batch_for_failed_fetch():
    source_entry = build_source_entry()
    snapshot_result = build_snapshot_result(source_id=source_entry.id, status="http_error")

    batch = detect_candidates(snapshot_result, source_entry)

    assert batch.candidates == []
    assert "did not succeed" in (batch.notes or "")


def test_detect_candidates_deduplicates_repeated_signals():
    source_entry = build_source_entry()
    snapshot_result = build_snapshot_result(
        source_id=source_entry.id,
        extracted_text=(
            "Festival submissions open now\n"
            "Deadline: June 1, 2026\n"
            "Festival submissions open now\n"
            "Deadline: June 1, 2026"
        ),
    )

    batch = detect_candidates(snapshot_result, source_entry)

    assert len(batch.candidates) == 1


def test_detect_candidates_uses_heading_when_deadline_is_on_adjacent_line():
    source_entry = build_source_entry().model_copy(
        update={
            "organization": "Example Labs",
            "program_name": "Artist Opportunities",
            "source_url": "https://example.com/labs",
            "source_type": "lab",
            "deadline_categories": ["lab_application"],
        }
    )
    snapshot_result = build_snapshot_result(
        source_id=source_entry.id,
        extracted_text=(
            "Documentary Lab 2026\n"
            "Applications open now\n"
            "Deadline: June 1, 2026"
        ),
    ).model_copy(
        update={
            "organization": source_entry.organization,
            "program_name": source_entry.program_name,
            "source_url": source_entry.source_url,
        }
    )

    batch = detect_candidates(snapshot_result, source_entry)

    assert len(batch.candidates) == 1
    candidate = batch.candidates[0]
    assert candidate.name == "Documentary Lab 2026"
    assert candidate.detected_deadline_text == "June 1, 2026"


def test_detect_candidates_extracts_early_deadline_and_event_range():
    source_entry = build_source_entry().model_copy(
        update={
            "organization": "Example Market",
            "program_name": "MeetMarket",
            "source_url": "https://example.com/meetmarket",
            "source_type": "market",
            "deadline_categories": ["industry_forum"],
        }
    )
    snapshot_result = build_snapshot_result(
        source_id=source_entry.id,
        extracted_text=(
            "MeetMarket 2026\n"
            "Early deadline: May 10, 2026\n"
            "Final deadline: June 1, 2026\n"
            "Event dates: October 10-13, 2026"
        ),
    ).model_copy(
        update={
            "organization": source_entry.organization,
            "program_name": source_entry.program_name,
            "source_url": source_entry.source_url,
        }
    )

    batch = detect_candidates(snapshot_result, source_entry)

    assert len(batch.candidates) == 1
    candidate = batch.candidates[0]
    assert candidate.name == "MeetMarket 2026"
    assert candidate.detected_early_deadline_text == "May 10, 2026"
    assert candidate.detected_deadline_text == "June 1, 2026"
    assert candidate.detected_event_date_text == "October 10-13, 2026"


def test_detect_candidates_detects_revised_deadline_wording_as_update_signal():
    source_entry = build_source_entry().model_copy(
        update={
            "organization": "Example Fellowship",
            "program_name": "Fellows Program",
            "source_url": "https://example.com/fellows",
            "source_type": "fellowship",
            "deadline_categories": ["fellowship"],
        }
    )
    snapshot_result = build_snapshot_result(
        source_id=source_entry.id,
        extracted_text=(
            "Fellows Program 2026\n"
            "Applications reopened with revised deadline: April 2, 2026"
        ),
    ).model_copy(
        update={
            "organization": source_entry.organization,
            "program_name": source_entry.program_name,
            "source_url": source_entry.source_url,
        }
    )

    batch = detect_candidates(snapshot_result, source_entry)

    assert len(batch.candidates) == 1
    candidate = batch.candidates[0]
    assert candidate.candidate_type == "update_signal"
    assert candidate.detected_deadline_text == "April 2, 2026"


def test_detect_candidates_handles_realistic_high_value_market_fixture():
    source_entry = build_source_entry().model_copy(
        update={
            "organization": "Sheffield DocFest",
            "program_name": "MeetMarket",
            "source_url": "https://example.com/sheffield-meetmarket",
            "source_type": "market",
            "deadline_categories": ["industry_forum"],
        }
    )
    snapshot_result = build_snapshot_result(
        source_id=source_entry.id,
        extracted_text=(
            "MeetMarket\n"
            "Sheffield DocFest 2026\n"
            "Applications open now for documentary projects seeking "
            "financiers, broadcasters, and partners.\n"
            "Early deadline: November 20, 2025\n"
            "Final deadline: December 12, 2025\n"
            "Event dates: June 18-23, 2026"
        ),
    ).model_copy(
        update={
            "organization": source_entry.organization,
            "program_name": source_entry.program_name,
            "source_url": source_entry.source_url,
        }
    )

    batch = detect_candidates(snapshot_result, source_entry)

    assert len(batch.candidates) == 1
    candidate = batch.candidates[0]
    assert candidate.name == "MeetMarket"
    assert candidate.detected_early_deadline_text == "November 20, 2025"
    assert candidate.detected_deadline_text == "December 12, 2025"
    assert candidate.detected_event_date_text == "June 18-23, 2026"
    assert candidate.category == "industry_forum"


def test_detect_candidate_batches_matches_snapshots_by_source_id():
    first = build_source_entry()
    second = build_source_entry().model_copy(
        update={
            "id": uuid4(),
            "organization": "Example Fund",
            "program_name": "Grants",
            "source_url": "https://example.com/grants",
            "source_type": "fund",
            "deadline_categories": ["funding_round"],
        }
    )
    snapshots = [
        build_snapshot_result(source_id=first.id),
        build_snapshot_result(
            source_id=second.id,
            extracted_text="Grant applications open\nDeadline: 12 March 2026",
        ).model_copy(
            update={
                "organization": second.organization,
                "program_name": second.program_name,
                "source_url": second.source_url,
            }
        ),
    ]

    batches = detect_candidate_batches(snapshots, [first, second])

    assert len(batches) == 2
    assert batches[0].source_id == str(first.id)
    assert batches[1].source_id == str(second.id)
    assert batches[1].candidates[0].category == "funding_round"
