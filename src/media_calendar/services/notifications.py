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
WEEKLY_DIGEST_LOOKAHEAD_DAYS = 30
_NOTIFICATION_DISPATCH_ORDER: Dict[NotificationType, int] = {
    "upcoming_3d": 0,
    "upcoming_14d": 1,
    "weekly_digest": 2,
    "upcoming_30d": 3,
    "annual_refresh_reminder": 4,
}


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

    is_digest_day = current_date.weekday() == 0
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

        has_upcoming_3d = 3 in deadline.notification_windows and days_until_deadline == 3
        has_upcoming_14d = (
            14 in deadline.notification_windows and days_until_deadline == 14
        )
        has_upcoming_30d = (
            30 in deadline.notification_windows
            and days_until_deadline == 30
            and not is_digest_day
        )

        if has_upcoming_30d:
            groups["upcoming_30d"].append(
                _to_notification_item(deadline, "upcoming_30d")
            )
        if has_upcoming_14d:
            groups["upcoming_14d"].append(
                _to_notification_item(deadline, "upcoming_14d")
            )
        if has_upcoming_3d:
            groups["upcoming_3d"].append(
                _to_notification_item(deadline, "upcoming_3d")
            )

        if (
            is_digest_day
            and 0 <= days_until_deadline <= WEEKLY_DIGEST_LOOKAHEAD_DAYS
            and not has_upcoming_3d
            and not has_upcoming_14d
        ):
            groups["weekly_digest"].append(
                _to_notification_item(deadline, "weekly_digest")
            )

    normalized_groups = {
        key: _sort_notification_items(value, notification_type=key)
        for key, value in groups.items()
        if value
    }
    return normalized_groups


def dispatch_notification_queue(
    queue: Sequence[dict],
    *,
    recipient_email: str,
    resend_settings: ResendSettings | None = None,
    dry_run: bool = False,
) -> List[NotificationDispatchResult]:
    """Send or preview notification queue items and return structured results."""

    results: List[NotificationDispatchResult] = []

    for queue_item in _prepare_queue_for_dispatch(queue):
        email_payload = queue_item["email"]
        notification_type = cast(NotificationType, queue_item["notification_type"])
        logs = _build_notification_logs(
            deadline_ids=queue_item["deadline_ids"],
            notification_type=notification_type,
            recipient_email=recipient_email,
            status="sent" if dry_run else "failed",
        )
        result_status: str = "sent" if dry_run else "failed"

        if not dry_run:
            if resend_settings is None:
                raise ValueError(
                    "resend_settings are required when dry_run is False"
                )
            try:
                _send_email_via_resend(
                    subject_line=email_payload["subject_line"],
                    html_body=email_payload["html_body"],
                    plain_text_body=email_payload["plain_text_body"],
                    recipient_email=recipient_email,
                    resend_settings=resend_settings,
                )
            except Exception:
                logs = _build_notification_logs(
                    deadline_ids=queue_item["deadline_ids"],
                    notification_type=notification_type,
                    recipient_email=recipient_email,
                    status="failed",
                )
                result_status = "failed"
            else:
                logs = _build_notification_logs(
                    deadline_ids=queue_item["deadline_ids"],
                    notification_type=notification_type,
                    recipient_email=recipient_email,
                    status="sent",
                )
                result_status = "sent"
        else:
            logs = _build_notification_logs(
                deadline_ids=queue_item["deadline_ids"],
                notification_type=notification_type,
                recipient_email=recipient_email,
                status="sent",
            )

        results.append(
            NotificationDispatchResult(
                queue_item=queue_item,
                recipient_email=recipient_email,
                status=result_status,
                logs=logs,
            )
        )

    return results


def _prepare_queue_for_dispatch(queue: Sequence[dict]) -> List[dict]:
    """Remove exact duplicates and send urgent notifications first."""

    seen_signatures: set[tuple[str, tuple[str, ...], str, str]] = set()
    prepared: List[dict] = []

    for queue_item in queue:
        notification_type = str(queue_item["notification_type"])
        deadline_ids = tuple(sorted(str(deadline_id) for deadline_id in queue_item["deadline_ids"]))
        email_payload = queue_item["email"]
        signature = (
            notification_type,
            deadline_ids,
            str(email_payload["subject_line"]),
            str(email_payload["plain_text_body"]),
        )
        if signature in seen_signatures:
            continue
        seen_signatures.add(signature)
        prepared.append(queue_item)

    prepared.sort(
        key=lambda item: (
            _NOTIFICATION_DISPATCH_ORDER.get(
                cast(NotificationType, item["notification_type"]),
                len(_NOTIFICATION_DISPATCH_ORDER),
            ),
            str(item["email"]["subject_line"]).lower(),
        )
    )
    return prepared


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


def _sort_notification_items(
    items: Sequence[NotificationItem],
    *,
    notification_type: str,
) -> List[NotificationItem]:
    if notification_type == "weekly_digest":
        return sorted(
            items,
            key=lambda item: (
                item.category,
                item.deadline_date,
                item.organization.lower(),
                item.name.lower(),
            ),
        )
    return sorted(
        items,
        key=lambda item: (
            item.deadline_date,
            item.organization.lower(),
            item.name.lower(),
        ),
    )


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
