from uuid import uuid4

from media_calendar.models import DiscoveryCandidateBatch


def test_discovery_candidate_batch_accepts_candidates_and_optional_notes():
    batch = DiscoveryCandidateBatch(
        source_id=str(uuid4()),
        source_url="https://example.com/program",
        organization="Example Fund",
        program_name="Open Calls",
        candidates=[
            {
                "id": str(uuid4()),
                "source_id": str(uuid4()),
                "source_url": "https://example.com/program",
                "organization": "Example Fund",
                "name": "Example Grant 2027",
                "category": "funding_round",
                "candidate_type": "new_opportunity",
                "confidence": 0.9,
                "rationale": "A clearly labeled funding round appears on the page.",
                "regions": ["North America"],
                "tags": ["grant"],
                "raw_excerpt": "The Example Grant 2027 call is now open.",
            }
        ],
        notes="First-pass candidate set from the source page.",
    )

    assert len(batch.candidates) == 1
    assert batch.candidates[0].name == "Example Grant 2027"
    assert batch.notes == "First-pass candidate set from the source page."
