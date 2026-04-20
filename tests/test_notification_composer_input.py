from datetime import date
from uuid import uuid4

from media_calendar.models import NotificationComposerInput


def test_notification_composer_input_model_accepts_notification_items():
    composer_input = NotificationComposerInput(
        deadlines=[
            {
                "id": uuid4(),
                "name": "Artist Fellowship",
                "category": "fellowship",
                "organization": "Example Foundation",
                "url": "https://example.com/fellowship",
                "deadline_date": date(2026, 7, 15),
                "description": "Final application deadline.",
                "notification_windows": [30, 14, 3],
                "status": "confirmed",
                "last_verified_date": date(2026, 4, 20),
                "source_url": "https://example.com/source",
                "tags": ["fellowship", "artists"],
                "year": 2026,
                "notification_type": "upcoming_30d",
            }
        ]
    )

    assert len(composer_input.deadlines) == 1
    assert composer_input.deadlines[0].notification_type == "upcoming_30d"
    assert composer_input.deadlines[0].early_deadline_date is None
