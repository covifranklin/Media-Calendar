from __future__ import annotations

from datetime import date
from uuid import uuid4

from media_calendar.components import auto_promote_discovery_results
from media_calendar.models import (
    Deadline,
    DiscoveryCandidate,
    DiscoveryCandidateComparison,
)


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
    confidence=0.9,
    detected_deadline_text="March 10, 2026",
    detected_event_date_text=None,
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
        confidence=confidence,
        rationale="Detected from official source text.",
        detected_deadline_text=detected_deadline_text,
        detected_event_date_text=detected_event_date_text,
        regions=["Global"],
        tags=["lab", "official_source"],
        raw_excerpt=raw_excerpt,
    )


def build_comparison(
    candidate: DiscoveryCandidate,
    *,
    classification="likely_new",
    primary_deadline_id=None,
    matched_deadline_ids=None,
    match_score=0.0,
):
    return DiscoveryCandidateComparison(
        candidate=candidate,
        classification=classification,
        primary_deadline_id=primary_deadline_id,
        matched_deadline_ids=matched_deadline_ids or [],
        match_score=match_score,
        rationale="Comparison result for testing.",
    )


def test_auto_promote_discovery_results_adds_high_confidence_new_deadline():
    candidate = build_candidate(
        name="Global Producers Accelerator 2026",
        category="industry_forum",
        organization="Producers Alliance",
        source_url="https://producers.example/accelerator",
        confidence=0.93,
        detected_deadline_text="May 14, 2026",
        raw_excerpt="Apply by May 14, 2026 for the Global Producers Accelerator 2026.",
    )
    comparison = build_comparison(candidate, classification="likely_new")

    batch = auto_promote_discovery_results(
        [comparison],
        [],
        current_date=date(2026, 4, 21),
    )

    assert batch.promoted_new_count == 1
    assert batch.promoted_update_count == 0
    assert batch.decisions[0].action == "promoted_new"
    assert len(batch.deadline_snapshot) == 1
    assert batch.deadline_snapshot[0].name == "Global Producers Accelerator 2026"
    assert batch.deadline_snapshot[0].deadline_date == date(2026, 5, 14)


def test_auto_promote_discovery_results_updates_existing_deadline():
    existing_deadline = build_deadline(deadline_date=date(2026, 3, 10))
    candidate = build_candidate(
        candidate_type="update_signal",
        confidence=0.87,
        detected_deadline_text="April 2, 2026",
        raw_excerpt="Extended deadline: April 2, 2026 for Example Documentary Lab 2026.",
    )
    comparison = build_comparison(
        candidate,
        classification="likely_update",
        primary_deadline_id=existing_deadline.id,
        matched_deadline_ids=[existing_deadline.id],
        match_score=0.91,
    )

    batch = auto_promote_discovery_results(
        [comparison],
        [existing_deadline],
        current_date=date(2026, 4, 21),
    )

    assert batch.promoted_update_count == 1
    assert batch.decisions[0].action == "promoted_update"
    assert batch.deadline_snapshot[0].deadline_date == date(2026, 4, 2)
    assert batch.deadline_snapshot[0].last_verified_date == date(2026, 4, 21)


def test_auto_promote_discovery_results_parses_ordinal_deadline_text():
    candidate = build_candidate(
        name="The Whickers Film & TV Funding Award",
        category="funding_round",
        organization="The Whickers",
        source_url="https://www.whickerawards.com/apply/film-and-tv/",
        confidence=0.93,
        detected_deadline_text="30th January 2026",
        raw_excerpt=(
            "Applications are now open. 19th November 2025: Applications open. "
            "30th January 2026: Applications close."
        ),
    )
    comparison = build_comparison(candidate, classification="likely_new")

    batch = auto_promote_discovery_results(
        [comparison],
        [],
        current_date=date(2026, 4, 21),
    )

    assert batch.promoted_new_count == 1
    assert batch.deadline_snapshot[0].deadline_date == date(2026, 1, 30)


def test_auto_promote_discovery_results_parses_abbreviated_event_ranges():
    candidate = build_candidate(
        name="Sheffield DocFest MeetMarket 2026",
        category="industry_forum",
        organization="Sheffield DocFest",
        source_url="https://www.sheffdocfest.com/meetmarket",
        confidence=0.93,
        detected_deadline_text=None,
        detected_event_date_text="10 - 15 Jun 2026",
        raw_excerpt="MeetMarket runs 10 - 15 Jun 2026 during Sheffield DocFest.",
    )
    comparison = build_comparison(candidate, classification="likely_new")

    batch = auto_promote_discovery_results(
        [comparison],
        [],
        current_date=date(2026, 4, 21),
    )

    assert batch.promoted_new_count == 1
    assert batch.deadline_snapshot[0].deadline_date == date(2026, 6, 10)
    assert batch.deadline_snapshot[0].event_start_date == date(2026, 6, 10)
    assert batch.deadline_snapshot[0].event_end_date == date(2026, 6, 15)


def test_auto_promote_discovery_results_ignores_high_confidence_duplicates():
    existing_deadline = build_deadline()
    candidate = build_candidate(confidence=0.92)
    comparison = build_comparison(
        candidate,
        classification="likely_duplicate",
        primary_deadline_id=existing_deadline.id,
        matched_deadline_ids=[existing_deadline.id],
        match_score=0.9,
    )

    batch = auto_promote_discovery_results(
        [comparison],
        [existing_deadline],
        current_date=date(2026, 4, 21),
    )

    assert batch.ignored_duplicate_count == 1
    assert batch.decisions[0].action == "ignored_duplicate"
    assert batch.deadline_snapshot == [existing_deadline]


def test_auto_promote_discovery_results_rejects_uncertain_items():
    existing_deadline = build_deadline()
    ambiguous_candidate = build_candidate(
        name="Example Lab 2026",
        confidence=0.89,
        detected_deadline_text="March 10, 2026",
    )
    low_confidence_candidate = build_candidate(
        name="New Opportunity 2026",
        organization="New Org",
        source_url="https://example.org/new-opportunity",
        confidence=0.61,
        detected_deadline_text="June 1, 2026",
        raw_excerpt="Apply by June 1, 2026 for New Opportunity 2026.",
    )

    comparisons = [
        build_comparison(
            ambiguous_candidate,
            classification="ambiguous",
            matched_deadline_ids=[existing_deadline.id],
            match_score=0.82,
        ),
        build_comparison(
            low_confidence_candidate,
            classification="likely_new",
            match_score=0.0,
        ),
    ]

    batch = auto_promote_discovery_results(
        comparisons,
        [existing_deadline],
        current_date=date(2026, 4, 21),
    )

    assert batch.promoted_update_count == 1
    assert batch.promoted_new_count == 1
    assert batch.rejected_uncertain_count == 0
    assert [decision.action for decision in batch.decisions] == [
        "promoted_update",
        "promoted_new",
    ]
    assert batch.deadline_snapshot[0].deadline_date == date(2026, 3, 10)


def test_auto_promote_discovery_results_auto_applies_ambiguous_future_dated_new_items():
    candidate = build_candidate(
        name="Relevant Market 2026",
        category="industry_forum",
        organization="Relevant Org",
        source_url="https://example.org/relevant-market",
        confidence=0.58,
        detected_deadline_text=None,
        detected_event_date_text="10 - 15 Jun 2026",
        raw_excerpt="Relevant Market runs 10 - 15 Jun 2026 with project meetings and networking.",
    )
    comparison = build_comparison(
        candidate,
        classification="ambiguous",
        matched_deadline_ids=[uuid4(), uuid4()],
        match_score=0.61,
    )

    batch = auto_promote_discovery_results(
        [comparison],
        [],
        current_date=date(2026, 4, 21),
    )

    assert batch.promoted_new_count == 1
    assert batch.decisions[0].action == "promoted_new"
    assert batch.deadline_snapshot[0].event_start_date == date(2026, 6, 10)


def test_auto_promote_discovery_results_auto_applies_single_match_ambiguous_update():
    existing_deadline = build_deadline(deadline_date=date(2026, 3, 10))
    candidate = build_candidate(
        candidate_type="update_signal",
        confidence=0.74,
        detected_deadline_text="April 8, 2026",
        raw_excerpt="Updated application deadline: April 8, 2026.",
    )
    comparison = build_comparison(
        candidate,
        classification="ambiguous",
        matched_deadline_ids=[existing_deadline.id],
        match_score=0.75,
    )

    batch = auto_promote_discovery_results(
        [comparison],
        [existing_deadline],
        current_date=date(2026, 4, 21),
    )

    assert batch.promoted_update_count == 1
    assert batch.decisions[0].action == "promoted_update"
    assert batch.deadline_snapshot[0].deadline_date == date(2026, 4, 8)
