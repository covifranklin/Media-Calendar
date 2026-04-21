"""Discovery decision log entry model definitions."""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class DiscoveryDecisionLogEntry(BaseModel):
    """Append-only log entry for one discovery auto-promotion decision."""

    model_config = ConfigDict()

    timestamp: datetime
    source_id: UUID
    candidate_id: UUID
    comparison_classification: Literal[
        "likely_new",
        "likely_update",
        "likely_duplicate",
        "ambiguous",
    ]
    promotion_action: Literal[
        "promoted_new",
        "promoted_update",
        "ignored_duplicate",
        "rejected_uncertain",
    ]
    match_score: float
    rationale: str
    affected_deadline_id: Optional[UUID] = None
