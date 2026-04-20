"""Notification composer input model definitions."""

from __future__ import annotations

from typing import List

from pydantic import BaseModel, ConfigDict

from media_calendar.models.notification_item import NotificationItem


class NotificationComposerInput(BaseModel):
    """Input model for the notification composer agent."""

    model_config = ConfigDict()

    deadlines: List[NotificationItem]
