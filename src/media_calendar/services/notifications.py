"""Notification runtime helpers."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Dict, List, Literal, Mapping, Optional, Sequence, cast
from urllib.request import Request, urlopen
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
RESEND_API_URL = "https://api.resend.com/emails"


@dataclass
class ResendSettings:
    api_key: str
    from_email: str
    from_name: Optional[str] = None


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


def load_resend_settings(env: Mapping[str, str] | None = None) -> ResendSettings:
    """Load Resend configuration from environment variables."""

    source = env or os.environ
    required = ["RESEND_API_KEY", "RESEND_FROM_EMAIL"]
    missing = [key for key in required if not source.get(key)]
    if missing:
        raise ValueError(f"Missing Resend configuration: {', '.join(missing)}")

    return ResendSettings(
        api_key=source["RESEND_API_KEY"],
        from_email=source["RESEND_FROM_EMAIL"],
        from_name=source.get("RESEND_FROM_NAME") or None,
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
            groups["upcoming_3d"].append(
                _to_notification_item(deadline, "upcoming_3d")
            )

        if current_date.weekday() == 0 and 0 <= days_until_deadline <= 14:
            groups["weekly_digest"].append(
                _to_notification_item(deadline, "weekly_digest")
            )

    return {key: value for key, value in groups.items() if value}


def dispatch_notification_queue(
    queue: Sequence[dict],
    *,
    recipient_email: str,
    resend_settings: ResendSettings | None = None,
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
            if resend_settings is None:
                raise ValueError(
                    "resend_settings are required when dry_run is False"
                )
            _send_email_via_resend(
                subject_line=email_payload["subject_line"],
                html_body=email_payload["html_body"],
                plain_text_body=email_payload["plain_text_body"],
                recipient_email=recipient_email,
                resend_settings=resend_settings,
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


def _send_email_via_resend(
    *,
    subject_line: str,
    html_body: str,
    plain_text_body: str,
    recipient_email: str,
    resend_settings: ResendSettings,
) -> None:
    payload = {
        "from": _build_from_value(resend_settings),
        "to": [recipient_email],
        "subject": subject_line,
        "html": html_body,
        "text": plain_text_body,
    }
    request = Request(
        RESEND_API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {resend_settings.api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urlopen(request, timeout=20) as response:
        response.read()


def _build_from_value(resend_settings: ResendSettings) -> str:
    if resend_settings.from_name:
        return f"{resend_settings.from_name} <{resend_settings.from_email}>"
    return resend_settings.from_email
