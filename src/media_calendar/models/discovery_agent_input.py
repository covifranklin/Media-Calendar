"""Discovery agent input model definitions."""

from __future__ import annotations

from typing import List

from pydantic import BaseModel, ConfigDict, Field

from media_calendar.models.discovery_candidate import DiscoveryCandidate
from media_calendar.models.source_registry_entry import SourceRegistryEntry
from media_calendar.models.source_snapshot_result import SourceSnapshotResult


class DiscoveryAgentInput(BaseModel):
    """Input payload for the LLM-assisted source discovery agent."""

    model_config = ConfigDict()

    source_entry: SourceRegistryEntry
    snapshot_result: SourceSnapshotResult
    deterministic_candidates: List[DiscoveryCandidate] = Field(default_factory=list)
