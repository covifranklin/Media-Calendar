"""Discovery candidate model definitions."""

from __future__ import annotations

from typing import List, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class DiscoveryCandidate(BaseModel):
    """A potential new opportunity discovered from a monitored source page."""

    model_config = ConfigDict()

    id: UUID
    source_id: UUID
    source_url: str
    organization: str
    name: str
    category: Literal[
        "festival_submission",
        "funding_round",
        "lab_application",
        "fellowship",
        "industry_forum",
        "other",
    ]
    candidate_type: Literal["new_opportunity", "update_signal", "duplicate_signal"]
    confidence: float
    rationale: str
    detected_deadline_text: Optional[str] = None
    detected_early_deadline_text: Optional[str] = None
    detected_event_date_text: Optional[str] = None
    eligibility_notes: Optional[str] = None
    regions: List[str]
    tags: List[str]
    raw_excerpt: str
