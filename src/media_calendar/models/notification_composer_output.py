"""Notification composer output model definitions."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict


class NotificationComposerOutput(BaseModel):
    """Output model for the notification composer agent."""

    model_config = ConfigDict()

    subject_line: str
    html_body: str
    plain_text_body: str
    priority_level: Literal["normal", "high"]
