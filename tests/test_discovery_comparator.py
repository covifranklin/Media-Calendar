from __future__ import annotations

from datetime import date
from uuid import uuid4

from media_calendar.components import compare_candidate_batch, compare_candidates
from media_calendar.models import Deadline, DiscoveryCandidate, DiscoveryCandidateBatch


def build_deadline(
    *,
    name="Example Documentary Lab 2026",
    category="lab_application",
    organization="Example Labs",
    url="https://example.org/lab",
    deadline_date=date(2026, 3, 10),
    source_url="https://example.org/lab",
    year=2026,
):
    return Deadline(
        id=uuid4(),
        name=name,
        category=category,
        organization=organization,
        url=url,
        deadline_date=deadline_date,
        description="Tracked opportunity in the deadline database.",
        notification_windows=[30, 14, 3],
        status="confirmed",
        last_verified_date=date(2026, 4, 21),
        source_url=source_url,
        tags=["lab"],
        year=year,
    )


def build_candidate(
    *,
    name="Example Documentary Lab 2026",
    category="lab_application",
    organization="Example Labs",
    source_url="https://example.org/lab",
    candidate_type="new_opportunity",
    detected_deadline_text=None,
    raw_excerpt="Applications are now open for Example Documentary Lab 2026.",
):
    return DiscoveryCandidate(
        id=uuid4(),
        source_id=uuid4(),
        source_url=source_url,
        organization=organization,
        name=name,
        category=category,
        candidate_type=candidate_type,
        confidence=0.88,
        rationale="Detected from official source text.",
        detected_deadline_text=detected_deadline_text,
        regions=["Global"],
        tags=["lab"],
        raw_excerpt=raw_excerpt,
    )


def test_compare_candidates_classifies_likely_new_when_no_match_exists():
    deadlines = [build_deadline()]
    candidate = build_candidate(
        name="Global Producers Accelerator 2026",
        organization="Producers Alliance",
        source_url="https://producers.example/accelerator",
        raw_excerpt=(
            "Applications are now open for the Global Producers Accelerator 2026."
        ),
    )

    result = compare_candidates([candidate], deadlines)[0]

    assert result.classification == "likely_new"
    assert result.primary_deadline_id is None
    assert result.matched_deadline_ids == []


def test_compare_candidates_classifies_duplicate_for_same_existing_deadline():
    deadline = build_deadline()
    candidate = build_candidate(detected_deadline_text="March 10, 2026")

    result = compare_candidates([candidate], [deadline])[0]

    assert result.classification == "likely_duplicate"
    assert result.primary_deadline_id == deadline.id
    assert result.matched_deadline_ids == [deadline.id]


def test_compare_candidates_classifies_update_when_date_hint_changes():
    deadline = build_deadline(deadline_date=date(2026, 3, 10))
    candidate = build_candidate(
        candidate_type="update_signal",
        detected_deadline_text="April 2, 2026",
        raw_excerpt="Extended deadline: April 2, 2026 for Example Documentary Lab 2026.",
    )

    result = compare_candidates([candidate], [deadline])[0]

    assert result.classification == "likely_update"
    assert result.primary_deadline_id == deadline.id
    assert result.matched_deadline_ids == [deadline.id]


def test_compare_candidates_classifies_ambiguous_when_multiple_matches_are_close():
    first = build_deadline(
        name="Example Producers Lab 2026",
        source_url="https://example.org/labs",
        url="https://example.org/labs",
    )
    second = build_deadline(
        name="Example Directors Lab 2026",
        source_url="https://example.org/labs",
        url="https://example.org/labs",
    )
    candidate = build_candidate(
        name="Example Lab 2026",
        source_url="https://example.org/labs",
        raw_excerpt="Applications are now open for Example Lab 2026.",
    )

    result = compare_candidates([candidate], [first, second])[0]

    assert result.classification == "ambiguous"
    assert result.primary_deadline_id is None
    assert set(result.matched_deadline_ids) == {first.id, second.id}


def test_compare_candidate_batch_wraps_results_with_source_metadata():
    deadline = build_deadline()
    candidate = build_candidate(detected_deadline_text="March 10, 2026")
    batch = DiscoveryCandidateBatch(
        source_id=str(candidate.source_id),
        source_url=candidate.source_url,
        organization=candidate.organization,
        program_name="Open Calls",
        candidates=[candidate],
        notes="One candidate found.",
    )

    comparison_batch = compare_candidate_batch(batch, [deadline])

    assert comparison_batch.source_id == str(candidate.source_id)
    assert comparison_batch.source_url == candidate.source_url
    assert len(comparison_batch.results) == 1
    assert comparison_batch.results[0].classification == "likely_duplicate"
