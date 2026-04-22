"""Deterministic auto-promotion for discovered candidates."""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import List, Sequence
from uuid import UUID, uuid5

from media_calendar.models import (
    Deadline,
    DiscoveryCandidate,
    DiscoveryCandidateComparison,
    DiscoveryPromotionBatch,
    DiscoveryPromotionDecision,
)

_PROMOTION_NAMESPACE = UUID("1d3c4bc9-6ed4-41b7-8db9-c88620d547d5")
_YEAR_RE = re.compile(r"\b(20\d{2})\b")
_ORDINAL_SUFFIX_RE = re.compile(r"(\d{1,2})(st|nd|rd|th)\b", re.IGNORECASE)
_EVENT_RANGE_RE = re.compile(
    r"\b([A-Z][a-z]+) (\d{1,2})\s*(?:to|-)\s*(\d{1,2}), (\d{4})\b"
)
_NEW_CANDIDATE_CONFIDENCE_THRESHOLD = 0.72
_UPDATE_CANDIDATE_CONFIDENCE_THRESHOLD = 0.7
_UPDATE_MATCH_SCORE_THRESHOLD = 0.76
_AUTO_APPLY_AMBIGUOUS_UPDATE_MATCH_SCORE_THRESHOLD = 0.72
_DUPLICATE_MATCH_SCORE_THRESHOLD = 0.82
_DEFAULT_NOTIFICATION_WINDOWS = [30, 14, 3]


def auto_promote_discovery_results(
    comparisons: Sequence[DiscoveryCandidateComparison],
    deadlines: Sequence[Deadline],
    *,
    current_date: date,
) -> DiscoveryPromotionBatch:
    """Apply an autonomy-first automatic promotion policy to discovery results."""

    deadline_map = {deadline.id: deadline for deadline in deadlines}
    decisions: List[DiscoveryPromotionDecision] = []
    notes = [
        "Auto-promotion favors autonomy: high-confidence candidates are "
        "applied directly, and some single-target ambiguous updates are "
        "promoted automatically when they include actionable dates."
    ]

    for comparison in comparisons:
        decision = _apply_promotion_policy(
            comparison,
            deadline_map=deadline_map,
            current_date=current_date,
        )
        decisions.append(decision)

        if decision.promoted_deadline is not None:
            deadline_map[decision.promoted_deadline.id] = decision.promoted_deadline

    snapshot = sorted(
        deadline_map.values(),
        key=lambda item: (item.deadline_date, item.name.lower()),
    )

    return DiscoveryPromotionBatch(
        decisions=decisions,
        deadline_snapshot=snapshot,
        promoted_new_count=sum(
            1 for decision in decisions if decision.action == "promoted_new"
        ),
        promoted_update_count=sum(
            1 for decision in decisions if decision.action == "promoted_update"
        ),
        ignored_duplicate_count=sum(
            1 for decision in decisions if decision.action == "ignored_duplicate"
        ),
        rejected_uncertain_count=sum(
            1 for decision in decisions if decision.action == "rejected_uncertain"
        ),
        notes=notes,
    )


def _apply_promotion_policy(
    comparison: DiscoveryCandidateComparison,
    *,
    deadline_map: dict[UUID, Deadline],
    current_date: date,
) -> DiscoveryPromotionDecision:
    candidate = comparison.candidate
    parsed_fields = _extract_candidate_fields(candidate)

    if comparison.classification == "likely_duplicate":
        if comparison.match_score >= _DUPLICATE_MATCH_SCORE_THRESHOLD:
            return DiscoveryPromotionDecision(
                comparison=comparison,
                action="ignored_duplicate",
                target_deadline_id=comparison.primary_deadline_id,
                rationale=(
                    "Ignored because the candidate is a high-confidence duplicate "
                    "of an existing deadline."
                ),
            )
        return _reject_decision(
            comparison,
            "Duplicate classification was not strong enough to ignore automatically.",
        )

    if comparison.classification == "ambiguous":
        ambiguous_decision = _maybe_promote_ambiguous_update(
            comparison,
            deadline_map=deadline_map,
            current_date=current_date,
            parsed_fields=parsed_fields,
        )
        if ambiguous_decision is not None:
            return ambiguous_decision

        return _reject_decision(
            comparison,
            "Rejected because the candidate remained too ambiguous for "
            "automatic promotion.",
        )

    if comparison.classification == "likely_update":
        target_id = comparison.primary_deadline_id
        existing_deadline = deadline_map.get(target_id) if target_id else None
        if existing_deadline is None:
            return _reject_decision(
                comparison,
                "Rejected because the target existing deadline could not be found.",
            )
        if (
            candidate.confidence < _UPDATE_CANDIDATE_CONFIDENCE_THRESHOLD
            or comparison.match_score < _UPDATE_MATCH_SCORE_THRESHOLD
        ):
            return _reject_decision(
                comparison,
                "Rejected because the update did not meet the automatic "
                "confidence and match-score thresholds.",
            )
        if not parsed_fields["has_actionable_date"]:
            return _reject_decision(
                comparison,
                "Rejected because the update candidate did not contain a "
                "parseable deadline or event date.",
            )

        promoted_deadline = _build_updated_deadline(
            existing_deadline,
            candidate,
            parsed_fields,
            current_date=current_date,
        )
        return DiscoveryPromotionDecision(
            comparison=comparison,
            action="promoted_update",
            target_deadline_id=existing_deadline.id,
            promoted_deadline=promoted_deadline,
            rationale=(
                "Automatically applied because the candidate matched one existing "
                "deadline strongly and contained a parseable updated date signal."
            ),
        )

    if comparison.classification == "likely_new":
        if candidate.confidence < _NEW_CANDIDATE_CONFIDENCE_THRESHOLD:
            return _reject_decision(
                comparison,
                "Rejected because the new candidate did not meet the confidence "
                "threshold for auto-promotion.",
            )
        if not parsed_fields["has_actionable_date"]:
            return _reject_decision(
                comparison,
                "Rejected because the new candidate did not contain a parseable "
                "deadline or event date.",
            )
        if parsed_fields["year"] is None:
            return _reject_decision(
                comparison,
                "Rejected because the new candidate did not expose a reliable "
                "target year hint.",
            )

        promoted_deadline = _build_new_deadline(
            candidate,
            parsed_fields,
            current_date=current_date,
        )
        return DiscoveryPromotionDecision(
            comparison=comparison,
            action="promoted_new",
            target_deadline_id=promoted_deadline.id,
            promoted_deadline=promoted_deadline,
            rationale=(
                "Automatically promoted because the candidate was high confidence, "
                "had a parseable date, and did not match any existing deadline."
            ),
        )

    return _reject_decision(
        comparison,
        "Rejected because the comparison classification was not recognized.",
    )


def _maybe_promote_ambiguous_update(
    comparison: DiscoveryCandidateComparison,
    *,
    deadline_map: dict[UUID, Deadline],
    current_date: date,
    parsed_fields: dict,
) -> DiscoveryPromotionDecision | None:
    candidate = comparison.candidate
    matched_ids = comparison.matched_deadline_ids
    if len(matched_ids) != 1:
        return None
    if candidate.confidence < _UPDATE_CANDIDATE_CONFIDENCE_THRESHOLD:
        return None
    if comparison.match_score < _AUTO_APPLY_AMBIGUOUS_UPDATE_MATCH_SCORE_THRESHOLD:
        return None
    if not parsed_fields["has_actionable_date"]:
        return None

    existing_deadline = deadline_map.get(matched_ids[0])
    if existing_deadline is None:
        return None

    promoted_deadline = _build_updated_deadline(
        existing_deadline,
        candidate,
        parsed_fields,
        current_date=current_date,
    )
    return DiscoveryPromotionDecision(
        comparison=comparison,
        action="promoted_update",
        target_deadline_id=existing_deadline.id,
        promoted_deadline=promoted_deadline,
        rationale=(
            "Automatically applied despite an ambiguous classification because "
            "the candidate pointed to exactly one plausible existing deadline, "
            "met the autonomy thresholds, and included actionable date data."
        ),
    )


def _reject_decision(
    comparison: DiscoveryCandidateComparison,
    rationale: str,
) -> DiscoveryPromotionDecision:
    return DiscoveryPromotionDecision(
        comparison=comparison,
        action="rejected_uncertain",
        target_deadline_id=comparison.primary_deadline_id,
        rationale=rationale,
    )


def _build_new_deadline(
    candidate: DiscoveryCandidate,
    parsed_fields: dict,
    *,
    current_date: date,
) -> Deadline:
    year = parsed_fields["year"]
    deadline_date = parsed_fields["deadline_date"] or parsed_fields["event_start_date"]
    identifier = uuid5(
        _PROMOTION_NAMESPACE,
        f"{candidate.organization.lower()}|{candidate.name.lower()}|"
        f"{candidate.category}|{year}",
    )
    return Deadline(
        id=identifier,
        name=candidate.name,
        category=candidate.category,
        organization=candidate.organization,
        url=candidate.source_url,
        deadline_date=deadline_date,
        early_deadline_date=parsed_fields["early_deadline_date"],
        event_start_date=parsed_fields["event_start_date"],
        event_end_date=parsed_fields["event_end_date"],
        description=_build_description(candidate),
        eligibility_notes=candidate.eligibility_notes,
        notification_windows=list(_DEFAULT_NOTIFICATION_WINDOWS),
        status="confirmed",
        last_verified_date=current_date,
        source_url=candidate.source_url,
        tags=_dedupe_tags(candidate.tags),
        year=year,
    )


def _build_updated_deadline(
    existing_deadline: Deadline,
    candidate: DiscoveryCandidate,
    parsed_fields: dict,
    *,
    current_date: date,
) -> Deadline:
    return existing_deadline.model_copy(
        update={
            "deadline_date": (
                parsed_fields["deadline_date"] or existing_deadline.deadline_date
            ),
            "early_deadline_date": (
                parsed_fields["early_deadline_date"]
                if parsed_fields["early_deadline_date"] is not None
                else existing_deadline.early_deadline_date
            ),
            "event_start_date": (
                parsed_fields["event_start_date"]
                if parsed_fields["event_start_date"] is not None
                else existing_deadline.event_start_date
            ),
            "event_end_date": (
                parsed_fields["event_end_date"]
                if parsed_fields["event_end_date"] is not None
                else existing_deadline.event_end_date
            ),
            "eligibility_notes": (
                candidate.eligibility_notes or existing_deadline.eligibility_notes
            ),
            "last_verified_date": current_date,
            "source_url": candidate.source_url,
            "url": candidate.source_url or existing_deadline.url,
            "tags": _dedupe_tags([*existing_deadline.tags, *candidate.tags]),
            "year": parsed_fields["year"] or existing_deadline.year,
        }
    )


def _build_description(candidate: DiscoveryCandidate) -> str:
    excerpt = " ".join(candidate.raw_excerpt.split())
    if excerpt:
        return excerpt[:400]
    return candidate.rationale


def _extract_candidate_fields(candidate: DiscoveryCandidate) -> dict:
    deadline_date = _parse_single_date(candidate.detected_deadline_text)
    early_deadline_date = _parse_single_date(candidate.detected_early_deadline_text)
    event_start_date, event_end_date = _parse_event_range(candidate.detected_event_date_text)
    year = _extract_year(candidate, deadline_date, early_deadline_date, event_start_date)

    return {
        "deadline_date": deadline_date,
        "early_deadline_date": early_deadline_date,
        "event_start_date": event_start_date,
        "event_end_date": event_end_date,
        "year": year,
        "has_actionable_date": any(
            value is not None
            for value in [
                deadline_date,
                early_deadline_date,
                event_start_date,
                event_end_date,
            ]
        ),
    }


def _extract_year(
    candidate: DiscoveryCandidate,
    *dates: date | None,
) -> int | None:
    for value in dates:
        if value is not None:
            return value.year

    for text in [
        candidate.name,
        candidate.raw_excerpt,
        candidate.detected_deadline_text,
        candidate.detected_early_deadline_text,
        candidate.detected_event_date_text,
    ]:
        if not text:
            continue
        match = _YEAR_RE.search(text)
        if match:
            return int(match.group(1))
    return None


def _parse_single_date(text: str | None) -> date | None:
    if not text:
        return None

    normalized_text = _ORDINAL_SUFFIX_RE.sub(r"\1", text)

    for format_string in ("%B %d, %Y", "%d %B %Y", "%m/%d/%Y", "%m/%d/%y"):
        try:
            return datetime.strptime(normalized_text, format_string).date()
        except ValueError:
            continue
    return None


def _parse_event_range(text: str | None) -> tuple[date | None, date | None]:
    if not text:
        return (None, None)

    match = _EVENT_RANGE_RE.search(text)
    if not match:
        parsed_date = _parse_single_date(text)
        return (parsed_date, parsed_date)

    month_name, start_day, end_day, year = match.groups()
    parsed_dates: List[date] = []
    for day in (start_day, end_day):
        try:
            parsed_dates.append(
                datetime.strptime(
                    f"{month_name} {day}, {year}",
                    "%B %d, %Y",
                ).date()
            )
        except ValueError:
            continue

    if not parsed_dates:
        return (None, None)
    if len(parsed_dates) == 1:
        return (parsed_dates[0], parsed_dates[0])
    return (parsed_dates[0], parsed_dates[1])


def _dedupe_tags(tags: Sequence[str]) -> List[str]:
    return list(dict.fromkeys(tag for tag in tags if tag))
