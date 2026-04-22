"""Notification composer orchestration step."""

from __future__ import annotations

import logging
from typing import Callable, List, Mapping, Sequence

from media_calendar.agents import compose_notification
from media_calendar.models import NotificationComposerInput, NotificationItem

STEP_NAME = "Compose Notifications"
AGENT_NAME = "notification_composer"
DESCRIPTION = (
    "Invokes the notification composer agent to generate email content for "
    "identified upcoming opportunities and events."
)
INPUT_SOURCE = "Filtered upcoming opportunities from the database, grouped by notification window/type."
OUTPUT_DESTINATION = "Queue for email sender."
CONDITION = "Triggered daily by scheduler if upcoming opportunities are found."
ERROR_HANDLING = "LLM output validation, fallback to template, log failures."

NotificationGroupMap = Mapping[str, Sequence[NotificationItem]]
QueueWriter = Callable[[dict], None]


def orchestration_step_notification_composer(
    grouped_deadlines: NotificationGroupMap,
    *,
    client=None,
    queue_writer: QueueWriter | None = None,
    logger: logging.Logger | None = None,
) -> List[dict]:
    """Compose notifications for grouped upcoming deadlines and enqueue them."""

    active_logger = logger or logging.getLogger(__name__)
    queue: List[dict] = []

    for notification_type, deadlines in grouped_deadlines.items():
        if not deadlines:
            continue

        composer_input = NotificationComposerInput(deadlines=list(deadlines))

        try:
            output = compose_notification(composer_input, client=client)
            used_fallback = False
        except Exception:
            active_logger.exception(
                "notification_composer failed for notification_type=%s",
                notification_type,
            )
            output = _build_fallback_output(list(deadlines), notification_type)
            used_fallback = True

        queue_item = {
            "step_name": STEP_NAME,
            "agent_name": AGENT_NAME,
            "description": DESCRIPTION,
            "input_source": INPUT_SOURCE,
            "output_destination": OUTPUT_DESTINATION,
            "condition": CONDITION,
            "error_handling": ERROR_HANDLING,
            "notification_type": notification_type,
            "deadline_count": len(deadlines),
            "deadline_ids": [str(deadline.id) for deadline in deadlines],
            "email": output.model_dump(),
            "used_fallback": used_fallback,
        }
        queue.append(queue_item)

        if queue_writer is not None:
            queue_writer(queue_item)

    return queue


def _build_fallback_output(
    deadlines: Sequence[NotificationItem],
    notification_type: str,
):
    from media_calendar.models import NotificationComposerOutput

    subject = f"Upcoming opportunities: {len(deadlines)} item(s)"

    if notification_type == "weekly_digest":
        grouped = _group_deadlines_by_category(deadlines)
        plain_sections = []
        html_sections = []
        for category, items in grouped.items():
            plain_sections.append(category)
            plain_sections.extend(
                f"- {deadline.deadline_date.isoformat()} | {deadline.organization} | {deadline.name}"
                for deadline in items
            )
            html_items = "".join(
                "<li>"
                f"<strong>{deadline.deadline_date.isoformat()}</strong> - "
                f"{deadline.organization}: {deadline.name}"
                "</li>"
                for deadline in items
            )
            html_sections.append(f"<h2>{category}</h2><ul>{html_items}</ul>")

        plain_text = (
            f"Notification type: {notification_type}\n\n"
            + "\n\n".join(plain_sections)
            + "\n\nPlease review the source records before sending."
        )
        html_body = (
            f"<p><strong>Notification type:</strong> {notification_type}</p>"
            + "".join(html_sections)
            + "<p>Please review the source records before sending.</p>"
        )
    else:
        names = ", ".join(deadline.name for deadline in deadlines)
        plain_text = (
            f"Notification type: {notification_type}\n"
            f"Upcoming opportunities: {names}\n"
            "Please review the source records before sending."
        )
        html_body = (
            "<p><strong>Notification type:</strong> "
            f"{notification_type}</p>"
            f"<p><strong>Upcoming opportunities:</strong> {names}</p>"
            "<p>Please review the source records before sending.</p>"
        )

    return NotificationComposerOutput(
        subject_line=subject,
        html_body=html_body,
        plain_text_body=plain_text,
        priority_level="high" if notification_type == "upcoming_3d" else "normal",
    )


def _group_deadlines_by_category(
    deadlines: Sequence[NotificationItem],
) -> dict[str, list[NotificationItem]]:
    grouped: dict[str, list[NotificationItem]] = {}
    for deadline in deadlines:
        grouped.setdefault(deadline.category, []).append(deadline)
    return grouped
