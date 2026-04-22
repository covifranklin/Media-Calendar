"""Deterministic discovery candidate detection from source snapshots."""

from __future__ import annotations

import re
from typing import Callable, Iterable, List, Sequence
from uuid import UUID, uuid5

from media_calendar.models import (
    DiscoveryCandidate,
    DiscoveryCandidateBatch,
    SourceRegistryEntry,
    SourceSnapshotResult,
)

_CANDIDATE_NAMESPACE = UUID("b76566c9-6ca0-4a73-8c30-ccbc541483da")

_DEADLINE_PATTERNS = [
    re.compile(
        r"\b(?:extended deadline|final deadline|apply by|"
        r"deadline to apply)\b[:\s-]*"
        r"([A-Z][a-z]+ \d{1,2}(?:st|nd|rd|th)?, \d{4})",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:extended deadline|final deadline|apply by|"
        r"deadline to apply)\b[:\s-]*"
        r"(\d{1,2}(?:st|nd|rd|th)? [A-Z][a-z]+ \d{4})",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bdeadline\b[:\s-]*([A-Z][a-z]+ \d{1,2}(?:st|nd|rd|th)?, \d{4})",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bdeadline\b[:\s-]*(\d{1,2}(?:st|nd|rd|th)? [A-Z][a-z]+ \d{4})",
        re.IGNORECASE,
    ),
]

_CLOSING_DATE_PATTERNS = [
    re.compile(
        r"\b(?:applications close|submissions close|entries close|closes|close on)\b"
        r"[:\s-]*([A-Z][a-z]+ \d{1,2}(?:st|nd|rd|th)?, \d{4})",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:applications close|submissions close|entries close|closes|close on)\b"
        r"[:\s-]*(\d{1,2}(?:st|nd|rd|th)? [A-Z][a-z]+ \d{4})",
        re.IGNORECASE,
    ),
    re.compile(
        r"([A-Z][a-z]+ \d{1,2}(?:st|nd|rd|th)?, \d{4})[:\s-]*"
        r"(?:applications close|submissions close|entries close|closes)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"(\d{1,2}(?:st|nd|rd|th)? [A-Z][a-z]+ \d{4})[:\s-]*"
        r"(?:applications close|submissions close|entries close|closes)\b",
        re.IGNORECASE,
    ),
]

_EARLY_DEADLINE_PATTERNS = [
    re.compile(
        r"\b(?:early deadline|early bird deadline|early application deadline)\b"
        r"[:\s-]*([A-Z][a-z]+ \d{1,2}(?:st|nd|rd|th)?, \d{4})",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:early deadline|early bird deadline|early application deadline)\b"
        r"[:\s-]*(\d{1,2}(?:st|nd|rd|th)? [A-Z][a-z]+ \d{4})",
        re.IGNORECASE,
    ),
]

_GENERIC_DATE_PATTERNS = [
    re.compile(r"\b([A-Z][a-z]+ \d{1,2}(?:st|nd|rd|th)?, \d{4})\b"),
    re.compile(r"\b(\d{1,2}(?:st|nd|rd|th)? [A-Z][a-z]+ \d{4})\b"),
    re.compile(r"\b(\d{1,2}/\d{1,2}/\d{2,4})\b"),
]

_EVENT_DATE_PATTERNS = [
    re.compile(r"\b([A-Z][a-z]+ \d{1,2}\s+to\s+\d{1,2}, \d{4})\b"),
    re.compile(r"\b([A-Z][a-z]+ \d{1,2}\s*-\s*\d{1,2}, \d{4})\b"),
    re.compile(r"\b([A-Z][a-z]+ \d{1,2}-\d{1,2}, \d{4})\b"),
]

_OPEN_CALL_RE = re.compile(
    r"\b(open call|call for applications|applications open|submissions open|"
    r"submit|deadline|deadline to apply|apply now|register now|pitching sessions|"
    r"grant|fund|lab|fellowship|market|forum)\b",
    re.IGNORECASE,
)

_UPDATE_SIGNAL_RE = re.compile(
    r"\b(deadline extended|extended deadline|new deadline|applications reopened|"
    r"submissions reopened|updated deadline|revised deadline|deadline moved)\b",
    re.IGNORECASE,
)

_CATEGORY_KEYWORDS = {
    "festival_submission": re.compile(
        r"\b(festival|submit your film|submissions|filmfreeway|eventival)\b",
        re.IGNORECASE,
    ),
    "funding_round": re.compile(
        r"\b(fund|grant|funding|award|financing)\b",
        re.IGNORECASE,
    ),
    "lab_application": re.compile(
        r"\b(lab|residency|intensive|workshop|program)\b",
        re.IGNORECASE,
    ),
    "fellowship": re.compile(
        r"\b(fellowship|fellows|fellow)\b",
        re.IGNORECASE,
    ),
    "industry_forum": re.compile(
        r"\b(forum|market|pitching|co-production|co-pro|industry)\b",
        re.IGNORECASE,
    ),
}

_SUNDANCE_SOURCE_ID = UUID("8f7fa5f3-0e89-41be-983d-e832622c7d1a")
_BFI_NETWORK_SOURCE_ID = UUID("f5e99faf-ac8b-4c58-bc8c-63807bcedf2e")
_SERIES_MANIA_SOURCE_ID = UUID("7f6b4ef8-d80b-4cb1-97db-181f0781cf25")

AdapterFunc = Callable[[str, SourceRegistryEntry], List[DiscoveryCandidate]]


def _normalize_source_url(value: str) -> str:
    normalized = re.sub(r"^https?://", "", value.lower()).strip("/")
    normalized = re.sub(r"^www\.", "", normalized)
    return normalized

_ADAPTERS_BY_SOURCE_ID: dict[UUID, AdapterFunc] = {
    _SUNDANCE_SOURCE_ID: lambda text, entry: _detect_structured_section_candidates(
        text,
        source_entry=entry,
        ignored_headings={"Artist Opportunities"},
    ),
    _BFI_NETWORK_SOURCE_ID: lambda text, entry: _detect_structured_section_candidates(
        text,
        source_entry=entry,
        ignored_headings={"Funding Opportunities"},
    ),
    _SERIES_MANIA_SOURCE_ID: lambda text, entry: _detect_structured_section_candidates(
        text,
        source_entry=entry,
        ignored_headings={"Forum and Co-Pro Pitching", "Series Mania Forum"},
    ),
}

_ADAPTERS_BY_SOURCE_URL: dict[str, AdapterFunc] = {
    _normalize_source_url("https://www.sundance.org/apply"): _ADAPTERS_BY_SOURCE_ID[
        _SUNDANCE_SOURCE_ID
    ],
    _normalize_source_url(
        "https://www.bfi.org.uk/get-funding-support/bfi-network/bfi-network-funding"
    ): _ADAPTERS_BY_SOURCE_ID[_BFI_NETWORK_SOURCE_ID],
    _normalize_source_url("https://seriesmania.com/forum/en/"): _ADAPTERS_BY_SOURCE_ID[
        _SERIES_MANIA_SOURCE_ID
    ],
}


def detect_candidates(
    snapshot_result: SourceSnapshotResult,
    source_entry: SourceRegistryEntry,
) -> DiscoveryCandidateBatch:
    """Detect likely opportunity candidates from one source snapshot."""

    if snapshot_result.status != "success":
        return DiscoveryCandidateBatch(
            source_id=str(source_entry.id),
            source_url=source_entry.source_url,
            organization=source_entry.organization,
            program_name=source_entry.program_name,
            candidates=[],
            notes="No candidates generated because the source fetch did not succeed.",
        )

    extracted_text = (snapshot_result.extracted_text or "").strip()
    if not extracted_text:
        return DiscoveryCandidateBatch(
            source_id=str(source_entry.id),
            source_url=source_entry.source_url,
            organization=source_entry.organization,
            program_name=source_entry.program_name,
            candidates=[],
            notes="No candidates generated because the extracted source text was empty.",
        )

    adapter_candidates = _detect_from_adapter(
        extracted_text,
        source_entry=source_entry,
    )
    if adapter_candidates:
        notes = (
            f"Detected {len(adapter_candidates)} source-specific adapter "
            "candidate(s) from extracted text."
        )
        return DiscoveryCandidateBatch(
            source_id=str(source_entry.id),
            source_url=source_entry.source_url,
            organization=source_entry.organization,
            program_name=source_entry.program_name,
            candidates=adapter_candidates,
            notes=notes,
        )

    candidates = _detect_from_text(
        extracted_text,
        source_entry=source_entry,
    )
    notes = (
        f"Detected {len(candidates)} deterministic candidate(s) from extracted text."
        if candidates
        else "No strong deterministic opportunity signals were found."
    )
    return DiscoveryCandidateBatch(
        source_id=str(source_entry.id),
        source_url=source_entry.source_url,
        organization=source_entry.organization,
        program_name=source_entry.program_name,
        candidates=candidates,
        notes=notes,
    )


def detect_candidate_batches(
    snapshot_results: Sequence[SourceSnapshotResult],
    source_entries: Sequence[SourceRegistryEntry],
) -> List[DiscoveryCandidateBatch]:
    """Detect candidates for multiple source snapshots matched by source id."""

    by_source_id = {entry.id: entry for entry in source_entries}
    batches: List[DiscoveryCandidateBatch] = []

    for snapshot_result in snapshot_results:
        source_entry = by_source_id.get(snapshot_result.source_id)
        if source_entry is None:
            continue
        batches.append(detect_candidates(snapshot_result, source_entry))

    return batches


def _detect_from_adapter(
    extracted_text: str,
    *,
    source_entry: SourceRegistryEntry,
) -> List[DiscoveryCandidate]:
    adapter = _ADAPTERS_BY_SOURCE_ID.get(source_entry.id)
    if adapter is None:
        adapter = _ADAPTERS_BY_SOURCE_URL.get(
            _normalize_source_url(source_entry.source_url)
        )
    if adapter is None:
        return []
    return adapter(extracted_text, source_entry)


def _detect_from_text(
    extracted_text: str,
    *,
    source_entry: SourceRegistryEntry,
) -> List[DiscoveryCandidate]:
    lines = [line.strip() for line in extracted_text.splitlines() if line.strip()]
    candidates: List[DiscoveryCandidate] = []
    seen_keys: set[str] = set()

    index = 0
    while index < len(lines):
        consumed = 0
        for window_size in (6, 5, 4, 3, 2, 1):
            excerpt_lines = lines[index : index + window_size]
            if not excerpt_lines:
                continue
            excerpt = "\n".join(excerpt_lines)
            if _append_candidate_from_excerpt(
                excerpt,
                source_entry=source_entry,
                candidates=candidates,
                seen_keys=seen_keys,
            ):
                consumed = window_size
                break

        index += consumed or 1

    return candidates


def _detect_structured_section_candidates(
    extracted_text: str,
    *,
    source_entry: SourceRegistryEntry,
    ignored_headings: set[str],
) -> List[DiscoveryCandidate]:
    lines = [line.strip() for line in extracted_text.splitlines() if line.strip()]
    candidates: List[DiscoveryCandidate] = []
    seen_keys: set[str] = set()

    for index, line in enumerate(lines):
        if not _looks_like_adapter_heading(line, ignored_headings):
            continue

        block_lines = [line]
        for next_index in range(index + 1, min(index + 7, len(lines))):
            next_line = lines[next_index]
            if _looks_like_adapter_heading(next_line, ignored_headings):
                break
            block_lines.append(next_line)

        excerpt = "\n".join(block_lines)
        _append_candidate_from_excerpt(
            excerpt,
            source_entry=source_entry,
            candidates=candidates,
            seen_keys=seen_keys,
            preferred_name=line,
        )

    return candidates


def _is_candidate_excerpt(excerpt: str) -> bool:
    if not _OPEN_CALL_RE.search(excerpt):
        return False

    date_text = _extract_deadline_text(excerpt)
    early_deadline_text = _extract_early_deadline_text(excerpt)
    event_date_text = _first_match(_EVENT_DATE_PATTERNS, excerpt)
    return (
        date_text is not None
        or early_deadline_text is not None
        or event_date_text is not None
        or bool(_UPDATE_SIGNAL_RE.search(excerpt))
    )


def _append_candidate_from_excerpt(
    excerpt: str,
    *,
    source_entry: SourceRegistryEntry,
    candidates: List[DiscoveryCandidate],
    seen_keys: set[str],
    preferred_name: str | None = None,
) -> bool:
    if not _is_candidate_excerpt(excerpt):
        return False
    if _is_bare_metadata_excerpt(excerpt):
        return False

    date_text = _extract_deadline_text(excerpt)
    early_deadline_text = _extract_early_deadline_text(excerpt)
    event_date_text = _first_match(_EVENT_DATE_PATTERNS, excerpt)
    candidate_type = (
        "update_signal" if _UPDATE_SIGNAL_RE.search(excerpt) else "new_opportunity"
    )
    category = _infer_category(excerpt, source_entry)
    name = preferred_name or _infer_name(excerpt, source_entry)
    key = (
        f"{candidate_type}|{category}|{name.lower()}|"
        f"{date_text or ''}|{early_deadline_text or ''}|{event_date_text or ''}"
    )
    if key in seen_keys:
        return False
    seen_keys.add(key)

    confidence = 0.8 if date_text else 0.66
    if early_deadline_text:
        confidence = max(confidence, 0.82)
    if event_date_text:
        confidence = max(confidence, 0.78)
    if candidate_type == "update_signal":
        confidence = max(confidence, 0.72)

    candidates.append(
        DiscoveryCandidate(
            id=uuid5(_CANDIDATE_NAMESPACE, key),
            source_id=source_entry.id,
            source_url=source_entry.source_url,
            organization=source_entry.organization,
            name=name,
            category=category,
            candidate_type=candidate_type,
            confidence=confidence,
            rationale=_build_rationale(
                candidate_type,
                category,
                date_text,
                early_deadline_text,
                event_date_text,
            ),
            detected_deadline_text=date_text,
            detected_early_deadline_text=early_deadline_text,
            detected_event_date_text=event_date_text,
            eligibility_notes=source_entry.notes,
            regions=list(source_entry.regions),
            tags=_build_tags(source_entry, category, candidate_type),
            raw_excerpt=excerpt,
        )
    )
    return True


def _first_match(
    patterns: Iterable[re.Pattern[str]],
    text: str,
) -> str | None:
    for pattern in patterns:
        match = pattern.search(text)
        if match:
            return match.group(1).strip()
    return None


def _last_match(
    patterns: Iterable[re.Pattern[str]],
    text: str,
) -> str | None:
    for pattern in patterns:
        matches = list(pattern.finditer(text))
        if matches:
            return matches[-1].group(1).strip()
    return None


def _extract_deadline_text(excerpt: str) -> str | None:
    deadline_text = _first_match(_DEADLINE_PATTERNS, excerpt)
    if deadline_text is not None:
        return deadline_text
    closing_date_text = _first_match(_CLOSING_DATE_PATTERNS, excerpt)
    if closing_date_text is not None:
        return closing_date_text
    if _extract_early_deadline_text(excerpt) is not None:
        return None
    return _last_match(
        _GENERIC_DATE_PATTERNS,
        excerpt,
    )


def _extract_early_deadline_text(excerpt: str) -> str | None:
    return _first_match(_EARLY_DEADLINE_PATTERNS, excerpt)


def _is_bare_metadata_excerpt(excerpt: str) -> bool:
    lines = [line.strip() for line in excerpt.splitlines() if line.strip()]
    if not lines:
        return False
    return all(_is_metadata_line(line) for line in lines)


def _is_metadata_line(line: str) -> bool:
    lowered = line.lower()
    return lowered.startswith(
        (
            "deadline:",
            "early deadline:",
            "final deadline:",
            "extended deadline:",
            "event dates:",
            "dates:",
            "applications open",
            "submissions open",
        )
    )


def _looks_like_adapter_heading(line: str, ignored_headings: set[str]) -> bool:
    if line in ignored_headings:
        return False
    if _is_metadata_line(line) or _contains_date_or_label(line):
        return False
    if len(line.split()) > 8:
        return False
    return any(character.isupper() for character in line)


def _infer_category(excerpt: str, source_entry: SourceRegistryEntry):
    for category, pattern in _CATEGORY_KEYWORDS.items():
        if pattern.search(excerpt):
            return category
    return source_entry.deadline_categories[0]


def _infer_name(excerpt: str, source_entry: SourceRegistryEntry) -> str:
    lines = [line.strip(" :-") for line in excerpt.splitlines() if line.strip()]
    heading = _select_heading_line(lines)
    if heading:
        return heading

    cleaned = re.sub(r"\s+", " ", excerpt).strip()
    cleaned = re.sub(
        r"\b(deadline to apply|applications open|submissions open|open call|"
        r"apply now|register now|deadline|extended deadline|early deadline|"
        r"final deadline|apply by)\b[:\s-]*.*$",
        "",
        cleaned,
        flags=re.IGNORECASE,
    ).strip(" :-")
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    if cleaned and len(cleaned.split()) <= 12:
        return cleaned
    return f"{source_entry.organization} - {source_entry.program_name}"


def _select_heading_line(lines: Sequence[str]) -> str | None:
    for line in lines:
        if _looks_like_heading(line):
            return line
    return None


def _looks_like_heading(line: str) -> bool:
    if not line or len(line.split()) > 10:
        return False
    if _contains_date_or_label(line):
        return False
    if line.endswith((".", "!", "?")):
        return False
    return any(character.isupper() for character in line)


def _contains_date_or_label(text: str) -> bool:
    lowered = text.lower()
    if _first_match(_GENERIC_DATE_PATTERNS, text) is not None:
        return True
    return any(
        label in lowered
        for label in [
            "deadline",
            "applications open",
            "submissions open",
            "open call",
            "apply now",
            "register now",
            "dates:",
            "event dates",
        ]
    )


def _build_rationale(
    candidate_type: str,
    category: str,
    date_text: str | None,
    early_deadline_text: str | None,
    event_date_text: str | None,
) -> str:
    parts = [
        f"Deterministic detection found a {candidate_type.replace('_', ' ')}",
        f"for category {category}.",
    ]
    if date_text:
        parts.append(f"Detected date text: {date_text}.")
    if early_deadline_text:
        parts.append(f"Detected early deadline text: {early_deadline_text}.")
    if event_date_text:
        parts.append(f"Detected event date text: {event_date_text}.")
    return " ".join(parts)


def _build_tags(
    source_entry: SourceRegistryEntry,
    category: str,
    candidate_type: str,
) -> List[str]:
    tags = [
        source_entry.source_type,
        source_entry.coverage_priority,
        category,
        candidate_type,
    ]
    return list(dict.fromkeys(tags))
