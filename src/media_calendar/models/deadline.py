"""Deadline model definitions."""

from __future__ import annotations

from datetime import date
from typing import List, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class Deadline(BaseModel):
    """Primary entity representing a single industry deadline."""

    model_config = ConfigDict()

    id: UUID
    name: str
    category: Literal[
        "festival_submission",
        "funding_round",
        "lab_application",
        "fellowship",
        "industry_forum",
        "other",
    ]
    organization: str
    url: str
    deadline_date: date
    early_deadline_date: Optional[date] = None
    event_start_date: Optional[date] = None
    event_end_date: Optional[date] = None
    description: str
    eligibility_notes: Optional[str] = None
    notification_windows: List[int]
    status: Literal["confirmed", "tentative", "expired", "cancelled"]
    last_verified_date: date
    source_url: str
    tags: List[str]
    year: int
