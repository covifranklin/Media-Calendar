"""Deterministic comparison of discovered candidates against known deadlines."""

from __future__ import annotations

import re
from datetime import date, datetime
from difflib import SequenceMatcher
from typing import Iterable, List, Sequence
from urllib.parse import urlsplit

from media_calendar.models import (
    Deadline,
    DiscoveryCandidate,
    DiscoveryCandidateBatch,
    DiscoveryCandidateComparison,
    DiscoveryCandidateComparisonBatch,
)

_WORD_RE = re.compile(r"[a-z0-9]+")
_YEAR_RE = re.compile(r"\b(20\d{2})\b")
_EVENT_RANGE_RE = re.compile(
    r"\b([A-Z][a-z]+) (\d{1,2})\s*(?:to|-)\s*(\d{1,2}), (\d{4})\b"
)
_STOP_WORDS = {"a", "an", "and", "for", "of", "the", "to"}


def compare_candidate_batch(
    candidate_batch: DiscoveryCandidateBatch,
    deadlines: Sequence[Deadline],
) -> DiscoveryCandidateComparisonBatch:
    """Compare one discovery batch against the known deadline database."""

    results = compare_candidates(candidate_batch.candidates, deadlines)
    return DiscoveryCandidateComparisonBatch(
        source_id=candidate_batch.source_id,
        source_url=candidate_batch.source_url,
        organization=candidate_batch.organization,
        program_name=candidate_batch.program_name,
        results=results,
        notes=(
            f"Compared {len(candidate_batch.candidates)} candidate(s) against "
            f"{len(deadlines)} known deadline(s)."
        ),
    )


def compare_candidate_batches(
    candidate_batches: Sequence[DiscoveryCandidateBatch],
    deadlines: Sequence[Deadline],
) -> List[DiscoveryCandidateComparisonBatch]:
    """Compare multiple discovery batches against the known deadline database."""

    return [
        compare_candidate_batch(candidate_batch, deadlines)
        for candidate_batch in candidate_batches
    ]


def compare_candidates(
    candidates: Sequence[DiscoveryCandidate],
    deadlines: Sequence[Deadline],
) -> List[DiscoveryCandidateComparison]:
    """Compare discovered candidates against existing deadlines."""

    return [
        _compare_candidate(candidate, deadlines)
        for candidate in candidates
    ]


def _compare_candidate(
    candidate: DiscoveryCandidate,
    deadlines: Sequence[Deadline],
) -> DiscoveryCandidateComparison:
    candidate_years = _extract_candidate_year_hints(candidate)
    same_category = [
        deadline
        for deadline in deadlines
        if deadline.category == candidate.category
    ]

    scored_matches = sorted(
        (
            _build_scored_match(candidate, deadline, candidate_years)
            for deadline in same_category
        ),
        key=lambda item: item["identity_score"],
        reverse=True,
    )
    plausible_matches = [
        match for match in scored_matches if match["identity_score"] >= 0.62
    ]

    if not plausible_matches:
        return DiscoveryCandidateComparison(
            candidate=candidate,
            classification="likely_new",
            match_score=0.0,
            rationale=(
                "No strong same-category match was found after comparing "
                "normalized organization, name, source URL, and year hints."
            ),
        )

    top_match = plausible_matches[0]
    top_deadline = top_match["deadline"]
    top_score = float(top_match["identity_score"])
    same_strength_matches = [
        match
        for match in plausible_matches
        if top_score - float(match["identity_score"]) <= 0.08
    ]

    if len(same_strength_matches) > 1:
        matched_ids = [match["deadline"].id for match in same_strength_matches]
        names = ", ".join(match["deadline"].name for match in same_strength_matches)
        return DiscoveryCandidateComparison(
            candidate=candidate,
            classification="ambiguous",
            matched_deadline_ids=matched_ids,
            match_score=top_score,
            rationale=(
                "Multiple existing deadlines look similarly plausible after "
                f"normalization and scoring: {names}."
            ),
        )

    if candidate_years and top_deadline.year not in candidate_years:
        return DiscoveryCandidateComparison(
            candidate=candidate,
            classification="likely_new",
            match_score=top_score,
            rationale=(
                f"The closest match is {top_deadline.name}, but the candidate "
                f"points to year {sorted(candidate_years)} while the stored "
                f"deadline is for {top_deadline.year}."
            ),
        )

    if top_score < 0.78:
        return DiscoveryCandidateComparison(
            candidate=candidate,
            classification="ambiguous",
            matched_deadline_ids=[top_deadline.id],
            match_score=top_score,
            rationale=(
                f"The candidate partially matches {top_deadline.name}, but the "
                "normalized identity score is not strong enough to classify it "
                "as clearly new, updated, or duplicate."
            ),
        )

    if (
        candidate.candidate_type == "update_signal"
        or top_match["date_relation"] == "different"
    ):
        return DiscoveryCandidateComparison(
            candidate=candidate,
            classification="likely_update",
            primary_deadline_id=top_deadline.id,
            matched_deadline_ids=[top_deadline.id],
            match_score=top_score,
            rationale=_build_update_rationale(candidate, top_deadline, top_match),
        )

    return DiscoveryCandidateComparison(
        candidate=candidate,
        classification="likely_duplicate",
        primary_deadline_id=top_deadline.id,
        matched_deadline_ids=[top_deadline.id],
        match_score=top_score,
        rationale=(
            f"Matched existing deadline {top_deadline.name} by normalized "
            "organization, name, category, source URL, and compatible year/date "
            "hints."
        ),
    )


def _build_scored_match(
    candidate: DiscoveryCandidate,
    deadline: Deadline,
    candidate_years: set[int],
):
    organization_score = _text_similarity(candidate.organization, deadline.organization)
    name_score = _name_similarity(candidate.name, deadline.name)
    source_score = _source_similarity(
        candidate.source_url,
        [deadline.source_url, deadline.url],
    )
    year_score = _year_similarity(candidate_years, deadline.year)
    date_relation = _compare_date_hints(candidate, deadline)

    identity_score = (
        0.34 * organization_score
        + 0.38 * name_score
        + 0.18 * source_score
        + 0.10 * year_score
    )

    return {
        "deadline": deadline,
        "identity_score": round(identity_score, 4),
        "organization_score": organization_score,
        "name_score": name_score,
        "source_score": source_score,
        "year_score": year_score,
        "date_relation": date_relation,
    }


def _build_update_rationale(
    candidate: DiscoveryCandidate,
    deadline: Deadline,
    top_match,
) -> str:
    if top_match["date_relation"] == "different":
        return (
            f"Matched existing deadline {deadline.name}, but the candidate "
            f"carries different date hints ({candidate.detected_deadline_text or candidate.detected_event_date_text}) "
            f"than the stored record ({deadline.deadline_date.isoformat()})."
        )

    return (
        f"Matched existing deadline {deadline.name}, and the candidate is marked "
        "as an update signal, so it should be reviewed as a likely update."
    )


def _text_similarity(left: str, right: str) -> float:
    normalized_left = _normalize_text(left)
    normalized_right = _normalize_text(right)
    if not normalized_left or not normalized_right:
        return 0.0
    if normalized_left == normalized_right:
        return 1.0

    left_tokens = _token_set(normalized_left)
    right_tokens = _token_set(normalized_right)
    token_overlap = _jaccard_similarity(left_tokens, right_tokens)
    sequence_score = SequenceMatcher(
        None,
        normalized_left,
        normalized_right,
    ).ratio()
    return round(max(token_overlap, sequence_score), 4)


def _name_similarity(left: str, right: str) -> float:
    normalized_left = _normalize_text(left)
    normalized_right = _normalize_text(right)
    if not normalized_left or not normalized_right:
        return 0.0
    if normalized_left == normalized_right:
        return 1.0

    base_left = _strip_year_tokens(normalized_left)
    base_right = _strip_year_tokens(normalized_right)
    if base_left and base_left == base_right:
        return 0.96
    if base_left and base_right and (
        base_left in base_right or base_right in base_left
    ):
        return 0.88

    token_overlap = _jaccard_similarity(_token_set(base_left), _token_set(base_right))
    sequence_score = SequenceMatcher(None, base_left, base_right).ratio()
    return round(max(token_overlap, sequence_score), 4)


def _source_similarity(candidate_url: str, deadline_urls: Iterable[str]) -> float:
    normalized_candidate = _normalize_url(candidate_url)
    if not normalized_candidate:
        return 0.0

    best_score = 0.0
    for deadline_url in deadline_urls:
        normalized_deadline = _normalize_url(deadline_url)
        if not normalized_deadline:
            continue
        if normalized_candidate == normalized_deadline:
            return 1.0

        candidate_host = normalized_candidate.split("/", 1)[0]
        deadline_host = normalized_deadline.split("/", 1)[0]
        if candidate_host == deadline_host:
            best_score = max(best_score, 0.72)

    return best_score


def _year_similarity(candidate_years: set[int], deadline_year: int) -> float:
    if not candidate_years:
        return 0.5
    if deadline_year in candidate_years:
        return 1.0
    if any(abs(year - deadline_year) == 1 for year in candidate_years):
        return 0.2
    return 0.0


def _compare_date_hints(candidate: DiscoveryCandidate, deadline: Deadline) -> str:
    candidate_dates = _extract_candidate_dates(candidate)
    if not candidate_dates:
        return "unknown"

    known_dates = {
        value
        for value in [
            deadline.deadline_date,
            deadline.early_deadline_date,
            deadline.event_start_date,
            deadline.event_end_date,
        ]
        if value is not None
    }
    if any(candidate_date in known_dates for candidate_date in candidate_dates):
        return "same"

    if any(candidate_date.year == deadline.year for candidate_date in candidate_dates):
        return "different"

    return "unknown"


def _extract_candidate_year_hints(candidate: DiscoveryCandidate) -> set[int]:
    texts = [
        candidate.name,
        candidate.raw_excerpt,
        candidate.detected_deadline_text,
        candidate.detected_early_deadline_text,
        candidate.detected_event_date_text,
    ]
    years: set[int] = set()
    for text in texts:
        if not text:
            continue
        years.update(int(match.group(1)) for match in _YEAR_RE.finditer(text))
    return years


def _extract_candidate_dates(candidate: DiscoveryCandidate) -> set[date]:
    dates: set[date] = set()
    for text in [
        candidate.detected_deadline_text,
        candidate.detected_early_deadline_text,
    ]:
        parsed_date = _parse_single_date(text)
        if parsed_date is not None:
            dates.add(parsed_date)

    if candidate.detected_event_date_text:
        dates.update(_parse_event_dates(candidate.detected_event_date_text))

    return dates


def _parse_single_date(text: str | None) -> date | None:
    if not text:
        return None

    for format_string in ("%B %d, %Y", "%d %B %Y", "%m/%d/%Y", "%m/%d/%y"):
        try:
            return datetime.strptime(text, format_string).date()
        except ValueError:
            continue
    return None


def _parse_event_dates(text: str) -> set[date]:
    match = _EVENT_RANGE_RE.search(text)
    if not match:
        parsed_date = _parse_single_date(text)
        return {parsed_date} if parsed_date is not None else set()

    month_name, start_day, end_day, year = match.groups()
    dates: set[date] = set()
    for day in (start_day, end_day):
        try:
            dates.add(
                datetime.strptime(
                    f"{month_name} {day}, {year}",
                    "%B %d, %Y",
                ).date()
            )
        except ValueError:
            continue
    return dates


def _normalize_text(value: str) -> str:
    return " ".join(_WORD_RE.findall(value.lower()))


def _strip_year_tokens(value: str) -> str:
    return " ".join(token for token in value.split() if not token.isdigit())


def _token_set(value: str) -> set[str]:
    return {
        token
        for token in value.split()
        if token and token not in _STOP_WORDS
    }


def _jaccard_similarity(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def _normalize_url(value: str) -> str:
    if not value:
        return ""

    parts = urlsplit(value)
    host = parts.netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    path = parts.path.rstrip("/").lower()
    return f"{host}{path}"
