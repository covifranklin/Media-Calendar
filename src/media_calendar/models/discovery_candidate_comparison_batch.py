"""Discovery candidate comparison batch model definitions."""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, ConfigDict

from media_calendar.models.discovery_candidate_comparison import (
    DiscoveryCandidateComparison,
)


class DiscoveryCandidateComparisonBatch(BaseModel):
    """Structured comparison results for one discovery candidate batch."""

    model_config = ConfigDict()

    source_id: str
    source_url: str
    organization: str
    program_name: str
    results: List[DiscoveryCandidateComparison]
    notes: Optional[str] = None
