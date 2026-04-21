"""Source snapshot result model definitions."""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class SourceSnapshotResult(BaseModel):
    """Structured result for a saved source snapshot and extracted text."""

    model_config = ConfigDict()

    source_id: UUID
    organization: str
    program_name: str
    source_url: str
    status: Literal["success", "http_error", "network_error"]
    fetched_at: datetime
    http_status: Optional[int] = None
    content_type: Optional[str] = None
    snapshot_path: Optional[str] = None
    text_path: Optional[str] = None
    extracted_text: Optional[str] = None
    error_message: Optional[str] = None
