"""Source coverage reporting model definitions."""

from __future__ import annotations

from typing import Dict, List

from pydantic import BaseModel, ConfigDict, Field


class SourceCoverageSourceSummary(BaseModel):
    """Compact source summary for coverage reports."""

    model_config = ConfigDict()

    organization: str
    program_name: str
    source_url: str
    source_type: str
    coverage_priority: str
    regions: List[str]
    deadline_categories: List[str]


class SourceCoverageGapSummary(BaseModel):
    """Coverage gaps and suspicious groupings derived from the registry."""

    model_config = ConfigDict()

    categories_without_must_have_coverage: List[str] = Field(default_factory=list)
    regions_without_must_have_coverage: List[str] = Field(default_factory=list)
    suspicious_groupings: List[str] = Field(default_factory=list)


class SourceCoverageReport(BaseModel):
    """Structured source coverage report for the monitored registry."""

    model_config = ConfigDict()

    total_source_count: int
    counts_by_coverage_priority: Dict[str, int]
    counts_by_source_type: Dict[str, int]
    counts_by_deadline_category: Dict[str, int]
    counts_by_region: Dict[str, int]
    must_have_sources: List[SourceCoverageSourceSummary] = Field(default_factory=list)
    high_sources: List[SourceCoverageSourceSummary] = Field(default_factory=list)
    gap_summary: SourceCoverageGapSummary
