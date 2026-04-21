"""Helpers for saving fetched source snapshots and extracted text."""

from __future__ import annotations

import re
from pathlib import Path
from typing import List, Sequence

from media_calendar.components.source_text import extract_source_text
from media_calendar.models import SourceFetchResult, SourceSnapshotResult

DEFAULT_SNAPSHOT_DIR = Path("build/source_snapshots")


def snapshot_fetch_results(
    fetch_results: Sequence[SourceFetchResult],
    *,
    root_dir: str | Path | None = None,
) -> List[SourceSnapshotResult]:
    """Persist raw fetch bodies and extracted text files for successful fetches."""

    root = Path(root_dir) if root_dir is not None else Path.cwd()
    output_dir = root / DEFAULT_SNAPSHOT_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    return [_snapshot_fetch_result(result, output_dir=output_dir) for result in fetch_results]


def _snapshot_fetch_result(
    fetch_result: SourceFetchResult,
    *,
    output_dir: Path,
) -> SourceSnapshotResult:
    snapshot_path = None
    text_path = None
    extracted_text = None

    if fetch_result.status == "success" and fetch_result.body is not None:
        stem = _build_snapshot_stem(fetch_result.organization, fetch_result.program_name)
        extension = _snapshot_extension(fetch_result.content_type)

        raw_path = output_dir / f"{stem}-{fetch_result.source_id}{extension}"
        raw_path.write_text(fetch_result.body, encoding="utf-8")
        snapshot_path = str(raw_path)

        extracted_text = extract_source_text(
            fetch_result.body,
            content_type=fetch_result.content_type,
        )
        extracted_path = output_dir / f"{stem}-{fetch_result.source_id}.txt"
        extracted_path.write_text(extracted_text, encoding="utf-8")
        text_path = str(extracted_path)

    return SourceSnapshotResult(
        source_id=fetch_result.source_id,
        organization=fetch_result.organization,
        program_name=fetch_result.program_name,
        source_url=fetch_result.source_url,
        status=fetch_result.status,
        fetched_at=fetch_result.fetched_at,
        http_status=fetch_result.http_status,
        content_type=fetch_result.content_type,
        snapshot_path=snapshot_path,
        text_path=text_path,
        extracted_text=extracted_text,
        error_message=fetch_result.error_message,
    )


def _build_snapshot_stem(organization: str, program_name: str) -> str:
    combined = f"{organization}-{program_name}".lower()
    cleaned = re.sub(r"[^a-z0-9]+", "-", combined).strip("-")
    return cleaned or "source"


def _snapshot_extension(content_type: str | None) -> str:
    normalized_type = (content_type or "").lower()
    if "html" in normalized_type:
        return ".html"
    if "json" in normalized_type:
        return ".json"
    return ".txt"
