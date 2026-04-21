"""Source registry model definitions."""

from __future__ import annotations

from typing import List, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class SourceRegistryEntry(BaseModel):
    """Authoritative source definition for discovery and refresh workflows."""

    model_config = ConfigDict()

    id: UUID
    organization: str
    program_name: str
    source_url: str
    source_type: Literal[
        "festival",
        "fund",
        "lab",
        "fellowship",
        "market",
        "guild_program",
        "broadcaster_program",
        "industry_forum",
        "other",
    ]
    deadline_categories: List[
        Literal[
            "festival_submission",
            "funding_round",
            "lab_application",
            "fellowship",
            "industry_forum",
            "other",
        ]
    ]
    regions: List[str]
    cadence: Literal["annual", "rolling", "periodic", "unknown"]
    coverage_priority: Literal["must_have", "high", "medium", "watchlist"]
    discovery_strategy: Literal[
        "official_program_page",
        "official_deadlines_page",
        "official_application_page",
        "manual_watch",
    ]
    active: bool = True
    notes: Optional[str] = None
