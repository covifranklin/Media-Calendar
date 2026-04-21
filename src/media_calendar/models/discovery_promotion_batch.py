"""Discovery promotion batch model definitions."""

from __future__ import annotations

from typing import List

from pydantic import BaseModel, ConfigDict, Field

from media_calendar.models.deadline import Deadline
from media_calendar.models.discovery_promotion_decision import (
    DiscoveryPromotionDecision,
)


class DiscoveryPromotionBatch(BaseModel):
    """Structured auto-promotion results for a discovery run."""

    model_config = ConfigDict()

    decisions: List[DiscoveryPromotionDecision]
    deadline_snapshot: List[Deadline]
    promoted_new_count: int = 0
    promoted_update_count: int = 0
    ignored_duplicate_count: int = 0
    rejected_uncertain_count: int = 0
    notes: List[str] = Field(default_factory=list)
