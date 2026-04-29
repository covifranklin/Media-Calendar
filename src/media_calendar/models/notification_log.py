"""Notification log model definitions."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class NotificationLog(BaseModel):
    """Secondary entity for tracking sent notifications."""

    model_config = ConfigDict()

    id: UUID
    deadline_id: UUID
    notification_type: Literal[
        "upcoming_30d",
        "upcoming_14d",
        "upcoming_3d",
        "weekly_digest",
        "annual_refresh_reminder",
    ]
    sent_at: datetime
    recipient_email: str
    status: Literal["sent", "failed", "bounced", "previewed"]
