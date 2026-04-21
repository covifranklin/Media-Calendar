"""Discovery candidate comparison model definitions."""

from __future__ import annotations

from typing import List, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from media_calendar.models.discovery_candidate import DiscoveryCandidate


class DiscoveryCandidateComparison(BaseModel):
    """Comparison result for one discovered candidate against known deadlines."""

    model_config = ConfigDict()

    candidate: DiscoveryCandidate
    classification: Literal[
        "likely_new",
        "likely_update",
        "likely_duplicate",
        "ambiguous",
    ]
    primary_deadline_id: Optional[UUID] = None
    matched_deadline_ids: List[UUID] = Field(default_factory=list)
    match_score: float
    rationale: str
