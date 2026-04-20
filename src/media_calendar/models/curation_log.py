"""Curation log model definitions."""

from __future__ import annotations

from datetime import datetime
from typing import List, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class CurationLog(BaseModel):
    """Tertiary entity for tracking data curation actions."""

    model_config = ConfigDict()

    id: UUID
    deadline_id: UUID
    action: Literal[
        "created",
        "updated",
        "verified_no_change",
        "flagged_for_review",
        "expired",
    ]
    changed_fields: Optional[List[str]] = None
    curator: Literal["human", "curation_agent"]
    reviewed_by_human: bool
    timestamp: datetime
