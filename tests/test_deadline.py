from datetime import date
from uuid import uuid4

from media_calendar.models import Deadline


def test_deadline_model_accepts_required_fields_and_optional_defaults():
    deadline = Deadline(
        id=uuid4(),
        name="Sundance Feature Submission",
        category="festival_submission",
        organization="Sundance Institute",
        url="https://example.com/deadline",
        deadline_date=date(2026, 9, 15),
        description="Final deadline for feature submissions.",
        notification_windows=[30, 7, 1],
        status="confirmed",
        last_verified_date=date(2026, 4, 20),
        source_url="https://example.com/source",
        tags=["festival", "film"],
        year=2026,
    )

    assert deadline.early_deadline_date is None
    assert deadline.event_start_date is None
    assert deadline.event_end_date is None
    assert deadline.eligibility_notes is None
    assert deadline.notification_windows == [30, 7, 1]
    assert deadline.tags == ["festival", "film"]
    assert deadline.year == 2026
