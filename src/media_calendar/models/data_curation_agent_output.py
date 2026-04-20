"""Data curation agent output model definitions."""

from __future__ import annotations

from typing import Any, Dict, Literal, Optional

from pydantic import BaseModel, ConfigDict


class DataCurationAgentOutput(BaseModel):
    """Output model for the data curation agent."""

    model_config = ConfigDict()

    status: Literal["no_change", "dates_changed", "page_not_found", "ambiguous"]
    proposed_updates: Optional[Dict[str, Any]] = None
    confidence: float
    reasoning: str
    requires_human_review: bool
