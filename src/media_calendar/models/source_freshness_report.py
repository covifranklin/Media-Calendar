"""Source freshness reporting model definitions."""

from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class SourceFreshnessEntry(BaseModel):
    """Freshness classification for one monitored source."""

    model_config = ConfigDict()

    source_id: UUID
    organization: str
    program_name: str
    source_url: str
    coverage_priority: str
    freshness_status: Literal["healthy", "degraded", "stale", "failing"]
    latest_fetch_status: Optional[str] = None
    latest_fetched_at: Optional[datetime] = None
    latest_word_count: int = 0
    latest_candidate_count: int = 0
    snapshot_count: int = 0
    success_count: int = 0
    failure_count: int = 0
    weak_text_count: int = 0
    candidate_positive_count: int = 0
    candidate_zero_count: int = 0
    issue_codes: List[str] = Field(default_factory=list)
    summary: str


class SourceFreshnessReport(BaseModel):
    """Structured source freshness report."""

    model_config = ConfigDict()

    generated_at: datetime
    total_sources: int
    counts_by_status: Dict[str, int]
    entries: List[SourceFreshnessEntry]
    markdown: str
