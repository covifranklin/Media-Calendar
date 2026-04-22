from __future__ import annotations

import logging
from datetime import date
from uuid import uuid4

from media_calendar.agents.notification_composer import NotificationComposerError
from media_calendar.models import NotificationComposerOutput, NotificationItem
from media_calendar.orchestration import orchestration_step_notification_composer


def build_notification_item(notification_type: str) -> NotificationItem:
    return NotificationItem(
        id=uuid4(),
        name="Example Lab",
        category="lab_application",
        organization="Example Org",
        url="https://example.com/deadline",
        deadline_date=date(2026, 6, 1),
        description="Application deadline for an industry lab.",
        notification_windows=[30, 14, 3],
        status="confirmed",
        last_verified_date=date(2026, 4, 20),
        source_url="https://example.com/source",
        tags=["lab"],
        year=2026,
        notification_type=notification_type,
    )


def test_orchestration_step_notification_composer_enqueues_agent_output(monkeypatch):
    def fake_compose(agent_input, *, client=None, max_attempts=3):
        return NotificationComposerOutput(
            subject_line="Upcoming deadline reminder",
            html_body="<p>Hello</p>",
            plain_text_body="Hello",
            priority_level="normal",
        )

    monkeypatch.setattr(
        "media_calendar.orchestration.notification_composer_step.compose_notification",
        fake_compose,
    )

    queue = orchestration_step_notification_composer(
        {"upcoming_30d": [build_notification_item("upcoming_30d")]}
    )

    assert len(queue) == 1
    assert queue[0]["step_name"] == "Compose Notifications"
    assert queue[0]["agent_name"] == "notification_composer"
    assert queue[0]["used_fallback"] is False
    assert queue[0]["email"]["subject_line"] == "Upcoming deadline reminder"


def test_orchestration_step_notification_composer_uses_fallback_and_logs(
    monkeypatch, caplog
):
    def fake_compose(agent_input, *, client=None, max_attempts=3):
        raise NotificationComposerError("bad output")

    monkeypatch.setattr(
        "media_calendar.orchestration.notification_composer_step.compose_notification",
        fake_compose,
    )

    with caplog.at_level(logging.ERROR):
        queue = orchestration_step_notification_composer(
            {"upcoming_3d": [build_notification_item("upcoming_3d")]}
        )

    assert len(queue) == 1
    assert queue[0]["used_fallback"] is True
    assert queue[0]["email"]["priority_level"] == "high"
    assert "notification_composer failed" in caplog.text


def test_orchestration_step_notification_composer_skips_empty_groups(monkeypatch):
    called = False

    def fake_compose(agent_input, *, client=None, max_attempts=3):
        nonlocal called
        called = True
        return NotificationComposerOutput(
            subject_line="Unused",
            html_body="<p>Unused</p>",
            plain_text_body="Unused",
            priority_level="normal",
        )

    monkeypatch.setattr(
        "media_calendar.orchestration.notification_composer_step.compose_notification",
        fake_compose,
    )

    queue = orchestration_step_notification_composer({"upcoming_14d": []})

    assert queue == []
    assert called is False


def test_orchestration_step_notification_composer_writes_to_queue_writer(monkeypatch):
    written = []

    def fake_compose(agent_input, *, client=None, max_attempts=3):
        return NotificationComposerOutput(
            subject_line="Weekly digest",
            html_body="<p>Digest</p>",
            plain_text_body="Digest",
            priority_level="normal",
        )

    monkeypatch.setattr(
        "media_calendar.orchestration.notification_composer_step.compose_notification",
        fake_compose,
    )

    queue = orchestration_step_notification_composer(
        {"weekly_digest": [build_notification_item("weekly_digest")]},
        queue_writer=written.append,
    )

    assert len(queue) == 1
    assert written == queue


def test_orchestration_step_notification_composer_weekly_fallback_groups_by_category(
    monkeypatch,
):
    def fake_compose(agent_input, *, client=None, max_attempts=3):
        raise NotificationComposerError("bad output")

    monkeypatch.setattr(
        "media_calendar.orchestration.notification_composer_step.compose_notification",
        fake_compose,
    )

    funding_item = build_notification_item("weekly_digest").model_copy(
        update={
            "category": "funding_round",
            "name": "Funding Call",
            "deadline_date": date(2026, 5, 20),
        }
    )
    fellowship_item = build_notification_item("weekly_digest").model_copy(
        update={
            "category": "fellowship",
            "name": "Fellowship Opportunity",
            "deadline_date": date(2026, 5, 22),
        }
    )

    queue = orchestration_step_notification_composer(
        {"weekly_digest": [funding_item, fellowship_item]},
    )

    plain_text = queue[0]["email"]["plain_text_body"]
    html_body = queue[0]["email"]["html_body"]

    assert "funding_round" in plain_text
    assert "fellowship" in plain_text
    assert "<h2>funding_round</h2>" in html_body
    assert "<h2>fellowship</h2>" in html_body
