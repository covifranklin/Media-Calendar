"""Discovery candidate batch model definitions."""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, ConfigDict

from media_calendar.models.discovery_candidate import DiscoveryCandidate


class DiscoveryCandidateBatch(BaseModel):
    """A structured batch of discovery candidates from one source snapshot."""

    model_config = ConfigDict()

    source_id: str
    source_url: str
    organization: str
    program_name: str
    candidates: List[DiscoveryCandidate]
    notes: Optional[str] = None
