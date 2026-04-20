"""Notification runtime helpers."""

from __future__ import annotations

import os
import smtplib
from dataclasses import dataclass
from datetime import date, datetime, timezone
from email.message import EmailMessage
from pathlib import Path
from typing import Dict, List, Literal, Mapping, Optional, Sequence, cast
from uuid import UUID, uuid4

from media_calendar.models import Deadline, NotificationItem, NotificationLog

NotificationGroupMap = Dict[str, List[NotificationItem]]
NotificationType = Literal[
    "upcoming_30d",
    "upcoming_14d",
    "upcoming_3d",
    "weekly_digest",
    "annual_refresh_reminder",
]
NotificationStatus = Literal["sent", "failed", "bounced"]


@dataclass
class SMTPSettings:
    host: str
    port: int
    from_email: str
    username: Optional[str] = None
    password: Optional[str] = None
    use_starttls: bool = True
    use_ssl: bool = False


@dataclass
class NotificationDispatchResult:
    queue_item: dict
    recipient_email: str
    status: str
    logs: List[NotificationLog]


def load_dotenv_file(path: str | Path) -> dict:
    """Load a simple .env file into process environment."""

    dotenv_path = Path(path)
    loaded: dict[str, str] = {}
    if not dotenv_path.exists():
        return loaded

    for raw_line in dotenv_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)
        loaded[key] = value
    return loaded


def load_smtp_settings(env: Mapping[str, str] | None = None) -> SMTPSettings:
    """Load SMTP configuration from environment variables."""

    source = env or os.environ
    required = ["SMTP_HOST", "SMTP_PORT", "SMTP_FROM_EMAIL"]
    missing = [key for key in required if not source.get(key)]
    if missing:
        raise ValueError(f"Missing SMTP configuration: {', '.join(missing)}")

    return SMTPSettings(
        host=source["SMTP_HOST"],
        port=int(source["SMTP_PORT"]),
        from_email=source["SMTP_FROM_EMAIL"],
        username=source.get("SMTP_USERNAME") or None,
        password=source.get("SMTP_PASSWORD") or None,
        use_starttls=_parse_bool(source.get("SMTP_USE_STARTTLS", "true")),
        use_ssl=_parse_bool(source.get("SMTP_USE_SSL", "false")),
    )


def group_upcoming_notifications(
    deadlines: Sequence[Deadline],
    *,
    current_date: date,
) -> NotificationGroupMap:
    """Group deadlines into notification buckets for the current day."""

    groups: NotificationGroupMap = {
        "upcoming_30d": [],
        "upcoming_14d": [],
        "upcoming_3d": [],
        "weekly_digest": [],
    }

    for deadline in deadlines:
        if deadline.status in {"expired", "cancelled"}:
            continue

        days_until_deadline = (deadline.deadline_date - current_date).days
        if days_until_deadline < 0:
            continue

        if 30 in deadline.notification_windows and days_until_deadline == 30:
            groups["upcoming_30d"].append(
                _to_notification_item(deadline, "upcoming_30d")
            )
        if 14 in deadline.notification_windows and days_until_deadline == 14:
            groups["upcoming_14d"].append(
                _to_notification_item(deadline, "upcoming_14d")
            )
        if 3 in deadline.notification_windows and days_until_deadline == 3:
            groups["upcoming_3d"].append(_to_notification_item(deadline, "upcoming_3d"))

        if current_date.weekday() == 0 and 0 <= days_until_deadline <= 14:
            groups["weekly_digest"].append(
                _to_notification_item(deadline, "weekly_digest")
            )

    return {key: value for key, value in groups.items() if value}


def dispatch_notification_queue(
    queue: Sequence[dict],
    *,
    recipient_email: str,
    smtp_settings: SMTPSettings | None = None,
    dry_run: bool = False,
) -> List[NotificationDispatchResult]:
    """Send or preview notification queue items and return structured results."""

    results: List[NotificationDispatchResult] = []

    for queue_item in queue:
        email_payload = queue_item["email"]
        notification_type = cast(NotificationType, queue_item["notification_type"])
        logs = _build_notification_logs(
            deadline_ids=queue_item["deadline_ids"],
            notification_type=notification_type,
            recipient_email=recipient_email,
            status="sent",
        )

        if not dry_run:
            if smtp_settings is None:
                raise ValueError("smtp_settings are required when dry_run is False")
            _send_email(
                subject_line=email_payload["subject_line"],
                html_body=email_payload["html_body"],
                plain_text_body=email_payload["plain_text_body"],
                recipient_email=recipient_email,
                smtp_settings=smtp_settings,
            )

        results.append(
            NotificationDispatchResult(
                queue_item=queue_item,
                recipient_email=recipient_email,
                status="sent",
                logs=logs,
            )
        )

    return results


def _to_notification_item(
    deadline: Deadline,
    notification_type: NotificationType,
) -> NotificationItem:
    payload = deadline.model_dump()
    payload["notification_type"] = notification_type
    return NotificationItem.model_validate(payload)


def _build_notification_logs(
    *,
    deadline_ids: Sequence[str],
    notification_type: NotificationType,
    recipient_email: str,
    status: NotificationStatus,
) -> List[NotificationLog]:
    sent_at = datetime.now(timezone.utc)
    return [
        NotificationLog(
            id=uuid4(),
            deadline_id=UUID(deadline_id),
            notification_type=notification_type,
            sent_at=sent_at,
            recipient_email=recipient_email,
            status=status,
        )
        for deadline_id in deadline_ids
    ]


def _send_email(
    *,
    subject_line: str,
    html_body: str,
    plain_text_body: str,
    recipient_email: str,
    smtp_settings: SMTPSettings,
) -> None:
    message = EmailMessage()
    message["Subject"] = subject_line
    message["From"] = smtp_settings.from_email
    message["To"] = recipient_email
    message.set_content(plain_text_body)
    message.add_alternative(html_body, subtype="html")

    if smtp_settings.use_ssl:
        with smtplib.SMTP_SSL(smtp_settings.host, smtp_settings.port) as server:
            _login_if_needed(server, smtp_settings)
            server.send_message(message)
        return

    with smtplib.SMTP(smtp_settings.host, smtp_settings.port) as server:
        server.ehlo()
        if smtp_settings.use_starttls:
            server.starttls()
            server.ehlo()
        _login_if_needed(server, smtp_settings)
        server.send_message(message)


def _login_if_needed(server, smtp_settings: SMTPSettings) -> None:
    if smtp_settings.username and smtp_settings.password:
        server.login(smtp_settings.username, smtp_settings.password)


def _parse_bool(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}
