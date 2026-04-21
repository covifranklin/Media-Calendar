import json
from datetime import date
from uuid import uuid4

import pytest

from media_calendar.models import Deadline
from media_calendar.services import (
    dispatch_notification_queue,
    group_upcoming_notifications,
    load_dotenv_file,
    load_resend_settings,
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
        "RESEND_API_KEY=re_test\nRESEND_FROM_EMAIL=onboarding@resend.dev\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("RESEND_API_KEY", raising=False)
    monkeypatch.delenv("RESEND_FROM_EMAIL", raising=False)

    loaded = load_dotenv_file(dotenv_path)

    assert loaded["RESEND_API_KEY"] == "re_test"
    assert loaded["RESEND_FROM_EMAIL"] == "onboarding@resend.dev"


def test_load_resend_settings_reads_required_values():
    settings = load_resend_settings(
        {
            "RESEND_API_KEY": "re_test",
            "RESEND_FROM_EMAIL": "onboarding@resend.dev",
            "RESEND_FROM_NAME": "Media Calendar",
        }
    )

    assert settings.api_key == "re_test"
    assert settings.from_email == "onboarding@resend.dev"
    assert settings.from_name == "Media Calendar"


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


def test_dispatch_notification_queue_requires_resend_settings_without_dry_run():
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

    with pytest.raises(ValueError, match="resend_settings are required"):
        dispatch_notification_queue(
            queue,
            recipient_email="friend@example.com",
            dry_run=False,
        )


def test_dispatch_notification_queue_calls_resend_api(monkeypatch):
    captured = {}

    class FakeResponse:
        def read(self):
            return b'{"id":"email_123"}'

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    def fake_urlopen(request, timeout=20):
        captured["url"] = request.full_url
        captured["headers"] = dict(request.header_items())
        captured["body"] = request.data
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr("media_calendar.services.notifications.urlopen", fake_urlopen)

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
        resend_settings=load_resend_settings(
            {
                "RESEND_API_KEY": "re_test",
                "RESEND_FROM_EMAIL": "onboarding@resend.dev",
                "RESEND_FROM_NAME": "Media Calendar",
            }
        ),
        dry_run=False,
    )

    payload = json.loads(captured["body"].decode("utf-8"))
    assert captured["url"] == "https://api.resend.com/emails"
    assert captured["timeout"] == 20
    assert captured["headers"]["Authorization"] == "Bearer re_test"
    assert payload["from"] == "Media Calendar <onboarding@resend.dev>"
    assert payload["to"] == ["friend@example.com"]
    assert payload["subject"] == "Upcoming deadline"
    assert len(results) == 1
