"""Notification item model definitions."""

from __future__ import annotations

from typing import Literal

from pydantic import ConfigDict

from media_calendar.models.deadline import Deadline


class NotificationItem(Deadline):
    """A deadline record extended with notification type."""

    model_config = ConfigDict()

    notification_type: Literal[
        "upcoming_30d",
        "upcoming_14d",
        "upcoming_3d",
        "weekly_digest",
        "annual_refresh_reminder",
    ]
