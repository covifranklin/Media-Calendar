"""Data curation agent input model definitions."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict

from media_calendar.models.deadline import Deadline


class DataCurationAgentInput(BaseModel):
    """Input model for the data curation agent."""

    model_config = ConfigDict()

    current_deadline: Deadline
    scraped_page_text: str
    current_date: date
    target_year: int
