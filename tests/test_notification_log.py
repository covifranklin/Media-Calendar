from datetime import datetime, timezone
from uuid import uuid4

from media_calendar.models import NotificationLog


def test_notification_log_model_accepts_required_fields():
    notification_log = NotificationLog(
        id=uuid4(),
        deadline_id=uuid4(),
        notification_type="upcoming_14d",
        sent_at=datetime(2026, 4, 20, 15, 30, tzinfo=timezone.utc),
        recipient_email="alerts@example.com",
        status="sent",
    )

    assert notification_log.notification_type == "upcoming_14d"
    assert notification_log.recipient_email == "alerts@example.com"
    assert notification_log.status == "sent"


def test_notification_log_model_accepts_previewed_status():
    notification_log = NotificationLog(
        id=uuid4(),
        deadline_id=uuid4(),
        notification_type="weekly_digest",
        sent_at=datetime(2026, 4, 20, 15, 30, tzinfo=timezone.utc),
        recipient_email="alerts@example.com",
        status="previewed",
    )

    assert notification_log.status == "previewed"
