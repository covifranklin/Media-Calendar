from datetime import date
from uuid import uuid4

from media_calendar.models import NotificationItem


def test_notification_item_model_accepts_required_fields_and_optional_defaults():
    notification_item = NotificationItem(
        id=uuid4(),
        name="Writers Lab",
        category="lab_application",
        organization="Example Org",
        url="https://example.com/deadline",
        deadline_date=date(2026, 6, 1),
        description="Application deadline for the writers lab.",
        notification_windows=[30, 14, 3],
        status="confirmed",
        last_verified_date=date(2026, 4, 20),
        source_url="https://example.com/source",
        tags=["lab", "screenwriting"],
        year=2026,
        notification_type="weekly_digest",
    )

    assert notification_item.early_deadline_date is None
    assert notification_item.event_start_date is None
    assert notification_item.event_end_date is None
    assert notification_item.eligibility_notes is None
    assert notification_item.notification_type == "weekly_digest"
    assert notification_item.category == "lab_application"
