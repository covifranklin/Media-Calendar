"""Discovery promotion decision model definitions."""

from __future__ import annotations

from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from media_calendar.models.deadline import Deadline
from media_calendar.models.discovery_candidate_comparison import (
    DiscoveryCandidateComparison,
)


class DiscoveryPromotionDecision(BaseModel):
    """Outcome of applying the auto-promotion policy to one comparison result."""

    model_config = ConfigDict()

    comparison: DiscoveryCandidateComparison
    action: Literal[
        "promoted_new",
        "promoted_update",
        "ignored_duplicate",
        "rejected_uncertain",
    ]
    target_deadline_id: Optional[UUID] = None
    promoted_deadline: Optional[Deadline] = None
    rationale: str
