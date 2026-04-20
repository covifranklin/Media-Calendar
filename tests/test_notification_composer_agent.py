from __future__ import annotations

from datetime import date
from types import SimpleNamespace
from uuid import uuid4

import pytest

from media_calendar.agents import compose_notification
from media_calendar.agents.notification_composer import NotificationComposerError
from media_calendar.models import NotificationComposerInput, NotificationItem


class FakeChatCompletionsAPI:
    def __init__(self, payloads):
        self.payloads = payloads
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        payload = self.payloads[len(self.calls) - 1]
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=payload))]
        )


class FakeClient:
    def __init__(self, payloads):
        self.chat = SimpleNamespace(completions=FakeChatCompletionsAPI(payloads))


def build_notification_input() -> NotificationComposerInput:
    return NotificationComposerInput(
        deadlines=[
            NotificationItem(
                id=uuid4(),
                name="Festival Submission Deadline",
                category="festival_submission",
                organization="Example Festival",
                url="https://example.com/festival",
                deadline_date=date(2026, 5, 20),
                description="Final day to submit feature films.",
                notification_windows=[30, 14, 3],
                status="confirmed",
                last_verified_date=date(2026, 4, 20),
                source_url="https://example.com/source",
                tags=["festival", "feature"],
                year=2026,
                notification_type="upcoming_30d",
            )
        ]
    )


def test_compose_notification_returns_validated_output():
    client = FakeClient(
        [
            (
                '{"subject_line":"30-day reminder","html_body":"<p>Hello</p>",'
                '"plain_text_body":"Hello","priority_level":"normal"}'
            )
        ]
    )

    result = compose_notification(build_notification_input(), client=client)

    assert result.subject_line == "30-day reminder"
    assert result.priority_level == "normal"
    assert client.chat.completions.calls[0]["model"] == "gpt-4o-mini"


def test_compose_notification_retries_after_validation_failure():
    client = FakeClient(
        [
            '{"subject_line":"Broken","html_body":"<p>Hi</p>"}',
            (
                '{"subject_line":"Urgent reminder","html_body":"<p>Act now</p>",'
                '"plain_text_body":"Act now","priority_level":"high"}'
            ),
        ]
    )

    result = compose_notification(build_notification_input(), client=client)

    assert result.priority_level == "high"
    assert len(client.chat.completions.calls) == 2
    retry_messages = client.chat.completions.calls[1]["messages"]
    assert retry_messages[-1]["role"] == "user"
    assert "could not be validated" in retry_messages[-1]["content"]


def test_compose_notification_raises_after_exhausting_retries():
    client = FakeClient(["{}", "{}", "{}"])

    with pytest.raises(NotificationComposerError):
        compose_notification(build_notification_input(), client=client)
