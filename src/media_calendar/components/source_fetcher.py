"""Deterministic source fetch helpers."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterable, List, Optional, Sequence
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from media_calendar.components.source_registry import (
    load_source_registry,
    resolve_source_files,
)
from media_calendar.models import SourceFetchResult, SourceRegistryEntry

FetchUrl = Callable[[str], tuple[int, Optional[str], str]]

DEFAULT_USER_AGENT = (
    "MediaCalendarBot/0.1 (+https://github.com/covifranklin/Media-Calendar)"
)


def fetch_registered_sources(
    source_files: Iterable[str | Path] | None = None,
    *,
    root_dir: str | Path | None = None,
    fetch_url: FetchUrl | None = None,
) -> List[SourceFetchResult]:
    """Load source registry files and fetch each registered source page."""

    root = Path(root_dir) if root_dir is not None else Path.cwd()
    paths = resolve_source_files(source_files, root=root)
    entries = load_source_registry(paths)
    return fetch_sources(entries, fetch_url=fetch_url)


def fetch_sources(
    entries: Sequence[SourceRegistryEntry],
    *,
    fetch_url: FetchUrl | None = None,
) -> List[SourceFetchResult]:
    """Fetch all source URLs and return structured results in input order."""

    active_fetch_url = fetch_url or _default_fetch_url
    return [fetch_source(entry, fetch_url=active_fetch_url) for entry in entries]


def fetch_source(
    entry: SourceRegistryEntry,
    *,
    fetch_url: FetchUrl | None = None,
) -> SourceFetchResult:
    """Fetch a single source URL and normalize the result."""

    active_fetch_url = fetch_url or _default_fetch_url
    fetched_at = datetime.now(timezone.utc)

    try:
        http_status, content_type, body = active_fetch_url(entry.source_url)
    except HTTPError as exc:
        return SourceFetchResult(
            source_id=entry.id,
            organization=entry.organization,
            program_name=entry.program_name,
            source_url=entry.source_url,
            status="http_error",
            fetched_at=fetched_at,
            http_status=exc.code,
            error_message=str(exc),
        )
    except URLError as exc:
        return SourceFetchResult(
            source_id=entry.id,
            organization=entry.organization,
            program_name=entry.program_name,
            source_url=entry.source_url,
            status="network_error",
            fetched_at=fetched_at,
            error_message=str(exc.reason),
        )
    except OSError as exc:
        return SourceFetchResult(
            source_id=entry.id,
            organization=entry.organization,
            program_name=entry.program_name,
            source_url=entry.source_url,
            status="network_error",
            fetched_at=fetched_at,
            error_message=str(exc),
        )

    return SourceFetchResult(
        source_id=entry.id,
        organization=entry.organization,
        program_name=entry.program_name,
        source_url=entry.source_url,
        status="success",
        fetched_at=fetched_at,
        http_status=http_status,
        content_type=content_type,
        body=body,
    )


def _default_fetch_url(url: str) -> tuple[int, Optional[str], str]:
    request = Request(url, headers={"User-Agent": DEFAULT_USER_AGENT})
    with urlopen(request, timeout=20) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        content_type = response.headers.get("Content-Type")
        body = response.read().decode(charset, errors="replace")
        return response.status, content_type, body
