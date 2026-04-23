from __future__ import annotations

import json
from datetime import date, datetime, timezone
from uuid import uuid4

from media_calendar.models import Deadline, NotificationLog
from media_calendar.services import NotificationDispatchResult
from notify import main


def _build_deadline() -> Deadline:
    return Deadline(
        id=uuid4(),
        name="Example Deadline",
        category="fellowship",
        organization="Example Org",
        url="https://example.com/deadline",
        deadline_date=date(2026, 5, 18),
        description="Example description.",
        notification_windows=[14, 3],
        status="confirmed",
        last_verified_date=date(2026, 5, 1),
        source_url="https://example.com/source",
        tags=["artists"],
        year=2026,
    )


def test_notify_cli_returns_nonzero_when_send_fails(tmp_path, monkeypatch, capsys):
    deadline = _build_deadline()
    queue = [
        {
            "notification_type": "upcoming_14d",
            "deadline_ids": [str(deadline.id)],
            "email": {
                "subject_line": "Upcoming deadline",
                "html_body": "<p>Hello</p>",
                "plain_text_body": "Hello",
                "priority_level": "normal",
            },
        }
    ]
    failed_log = NotificationLog(
        id=uuid4(),
        deadline_id=deadline.id,
        notification_type="upcoming_14d",
        sent_at=datetime(2026, 5, 4, 12, 0, tzinfo=timezone.utc),
        recipient_email="friend@example.com",
        status="failed",
    )

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "media_calendar.components.deadline_store.resolve_deadline_files",
        lambda inputs, *, root: [tmp_path / "data" / "deadlines" / "2026.yaml"],
    )
    monkeypatch.setattr(
        "media_calendar.components.deadline_store.load_deadlines",
        lambda paths: [deadline],
    )
    monkeypatch.setattr(
        "media_calendar.services.group_upcoming_notifications",
        lambda deadlines, *, current_date: {"upcoming_14d": [object()]},
    )
    monkeypatch.setattr(
        "media_calendar.orchestration.orchestration_step_notification_composer",
        lambda grouped, **kwargs: queue,
    )
    monkeypatch.setattr(
        "media_calendar.services.load_resend_settings",
        lambda env=None: object(),
    )
    monkeypatch.setattr(
        "media_calendar.services.dispatch_notification_queue",
        lambda queue, *, recipient_email, resend_settings=None, dry_run=False: [
            NotificationDispatchResult(
                queue_item=queue[0],
                recipient_email=recipient_email,
                status="failed",
                logs=[failed_log],
                error_message="resend unavailable",
            )
        ],
    )
    monkeypatch.setattr(
        "sys.argv",
        [
            "notify.py",
            "--root-dir",
            str(tmp_path),
            "--recipient",
            "friend@example.com",
        ],
    )

    exit_code = main()
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "failed" in captured.out.lower()
    assert "resend unavailable" in captured.out
    log_path = tmp_path / "build" / "notification-log.jsonl"
    queue_path = tmp_path / "build" / "notification-queue.json"
    assert log_path.exists()
    assert queue_path.exists()
    queue_payload = json.loads(queue_path.read_text(encoding="utf-8"))
    assert queue_payload[0]["notification_type"] == "upcoming_14d"
    logged = log_path.read_text(encoding="utf-8")
    assert '"status":"failed"' in logged
