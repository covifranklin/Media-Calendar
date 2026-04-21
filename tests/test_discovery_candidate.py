from uuid import uuid4

from media_calendar.models import DiscoveryCandidate


def test_discovery_candidate_accepts_required_fields_and_optional_defaults():
    candidate = DiscoveryCandidate(
        id=uuid4(),
        source_id=uuid4(),
        source_url="https://example.com/program",
        organization="Example Labs",
        name="Example Documentary Lab 2027",
        category="lab_application",
        candidate_type="new_opportunity",
        confidence=0.84,
        rationale="The page clearly presents an open call for a 2027 lab.",
        regions=["Global"],
        tags=["documentary", "lab"],
        raw_excerpt="Applications are now open for the Example Documentary Lab 2027.",
    )

    assert candidate.detected_deadline_text is None
    assert candidate.detected_early_deadline_text is None
    assert candidate.detected_event_date_text is None
    assert candidate.eligibility_notes is None
    assert candidate.category == "lab_application"
    assert candidate.candidate_type == "new_opportunity"

