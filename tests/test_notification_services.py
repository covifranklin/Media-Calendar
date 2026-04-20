from datetime import date
from uuid import uuid4

import pytest

from media_calendar.models import Deadline
from media_calendar.services import (
    dispatch_notification_queue,
    group_upcoming_notifications,
    load_dotenv_file,
    load_smtp_settings,
)


def build_deadline(*, deadline_date: date, windows, status="confirmed") -> Deadline:
    return Deadline(
        id=uuid4(),
        name="Example Deadline",
        category="fellowship",
        organization="Example Org",
        url="https://example.com/deadline",
        deadline_date=deadline_date,
        description="Example description.",
        notification_windows=windows,
        status=status,
        last_verified_date=date(2026, 4, 20),
        source_url="https://example.com/source",
        tags=["artists"],
        year=2026,
    )


def test_group_upcoming_notifications_creates_expected_buckets():
    current_date = date(2026, 5, 4)
    deadlines = [
        build_deadline(deadline_date=date(2026, 6, 3), windows=[30]),
        build_deadline(deadline_date=date(2026, 5, 18), windows=[14]),
        build_deadline(deadline_date=date(2026, 5, 7), windows=[3]),
    ]

    grouped = group_upcoming_notifications(deadlines, current_date=current_date)

    assert sorted(grouped.keys()) == [
        "upcoming_14d",
        "upcoming_30d",
        "upcoming_3d",
        "weekly_digest",
    ]
    assert grouped["upcoming_30d"][0].notification_type == "upcoming_30d"
    assert grouped["upcoming_14d"][0].notification_type == "upcoming_14d"
    assert grouped["upcoming_3d"][0].notification_type == "upcoming_3d"


def test_load_dotenv_file_sets_environment(tmp_path, monkeypatch):
    dotenv_path = tmp_path / ".env"
    dotenv_path.write_text(
        "SMTP_HOST=smtp.example.com\nSMTP_PORT=2525\n", encoding="utf-8"
    )
    monkeypatch.delenv("SMTP_HOST", raising=False)
    monkeypatch.delenv("SMTP_PORT", raising=False)

    loaded = load_dotenv_file(dotenv_path)

    assert loaded["SMTP_HOST"] == "smtp.example.com"
    assert loaded["SMTP_PORT"] == "2525"


def test_load_smtp_settings_reads_required_values():
    settings = load_smtp_settings(
        {
            "SMTP_HOST": "smtp.example.com",
            "SMTP_PORT": "2525",
            "SMTP_FROM_EMAIL": "sender@example.com",
            "SMTP_USERNAME": "user",
            "SMTP_PASSWORD": "pass",
            "SMTP_USE_STARTTLS": "true",
            "SMTP_USE_SSL": "false",
        }
    )

    assert settings.host == "smtp.example.com"
    assert settings.port == 2525
    assert settings.use_starttls is True
    assert settings.use_ssl is False


def test_dispatch_notification_queue_supports_dry_run():
    queue = [
        {
            "notification_type": "upcoming_14d",
            "deadline_ids": [str(uuid4())],
            "email": {
                "subject_line": "Upcoming deadline",
                "html_body": "<p>Hello</p>",
                "plain_text_body": "Hello",
                "priority_level": "normal",
            },
        }
    ]

    results = dispatch_notification_queue(
        queue,
        recipient_email="friend@example.com",
        dry_run=True,
    )

    assert len(results) == 1
    assert results[0].status == "sent"
    assert results[0].recipient_email == "friend@example.com"


def test_dispatch_notification_queue_requires_smtp_settings_without_dry_run():
    queue = [
        {
            "notification_type": "upcoming_14d",
            "deadline_ids": [str(uuid4())],
            "email": {
                "subject_line": "Upcoming deadline",
                "html_body": "<p>Hello</p>",
                "plain_text_body": "Hello",
                "priority_level": "normal",
            },
        }
    ]

    with pytest.raises(ValueError, match="smtp_settings are required"):
        dispatch_notification_queue(
            queue,
            recipient_email="friend@example.com",
            dry_run=False,
        )
