"""Review-only open-web discovery sweep orchestration."""

from __future__ import annotations

import json
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional, Sequence
from urllib.parse import urlparse
from uuid import UUID, uuid5

from media_calendar.components import (
    compare_candidate_batch,
    detect_candidate_batches,
    load_deadlines,
    load_source_registry,
    resolve_deadline_files,
    resolve_source_files,
    search_open_web,
    snapshot_fetch_results,
)
from media_calendar.components.source_fetcher import fetch_sources
from media_calendar.models import SourceRegistryEntry

STEP_NAME = "Open-Web Discovery Sweep"
AGENT_NAME = "open_web_discovery_pipeline"
DESCRIPTION = (
    "Runs a light-touch web search outside the monitored source list, fetches a "
    "small number of candidate pages, detects opportunity signals, compares them "
    "against the existing deadline database, and writes review-only reports."
)
INPUT_SOURCE = (
    "data/sources/*.yaml, data/deadlines/*.yaml, plus a capped open-web search "
    "query set."
)
OUTPUT_DESTINATION = (
    "build/open-web-discovery.json, build/open-web-discovery.md, and "
    "build/source_snapshots/."
)
CONDITION = "Triggered fortnightly by scheduler or manually via CLI."
ERROR_HANDLING = (
    "Search results are capped and deduplicated, already monitored URLs are "
    "skipped, fetch failures remain in the report, and the sweep never writes "
    "deadline YAML automatically."
)

SearchProvider = Callable[..., List[Dict[str, object]]]
FetchUrl = Callable[[str], tuple[int, Optional[str], str]]

_OPEN_WEB_SOURCE_NAMESPACE = UUID("d4be88fa-b785-4c1b-a1b0-b9729480fa0b")


def orchestration_step_open_web_discovery(
    source_files: Iterable[str | Path] | None = None,
    deadline_files: Iterable[str | Path] | None = None,
    *,
    root_dir: str | Path | None = None,
    current_date: date | None = None,
    query_specs: Sequence[Dict[str, str]] | None = None,
    max_results_per_query: int = 3,
    max_results_total: int = 12,
    search_provider: SearchProvider = search_open_web,
    fetch_url: FetchUrl | None = None,
) -> dict:
    """Run a review-first open-web discovery sweep."""

    root = Path(root_dir) if root_dir is not None else Path.cwd()
    active_date = current_date or date.today()
    source_paths = resolve_source_files(source_files, root=root)
    deadline_paths = resolve_deadline_files(deadline_files, root=root)
    source_entries = load_source_registry(source_paths)
    deadlines = load_deadlines(deadline_paths)
    monitored_urls = {_normalize_url(entry.source_url) for entry in source_entries}

    active_queries = list(query_specs or _build_default_query_specs(active_date))
    raw_search_results = search_provider(
        active_queries,
        max_results_per_query=max_results_per_query,
        max_results_total=max_results_total,
    )

    search_results = []
    skipped_monitored_results = 0
    for result in raw_search_results:
        normalized_url = _normalize_url(str(result["url"]))
        if normalized_url in monitored_urls:
            skipped_monitored_results += 1
            continue
        search_results.append(result)

    fetched_entries = [_build_search_source_entry(result) for result in search_results]
    fetch_results = fetch_sources(fetched_entries, fetch_url=fetch_url)
    snapshot_results = snapshot_fetch_results(fetch_results, root_dir=root)
    candidate_batches = detect_candidate_batches(snapshot_results, fetched_entries)

    findings = []
    classification_counts: Counter[str] = Counter()
    candidate_total = 0

    for result, batch, snapshot in zip(search_results, candidate_batches, snapshot_results):
        comparisons = compare_candidate_batch(batch, deadlines)
        candidate_total += len(batch.candidates)
        classification_counts.update(
            item.classification for item in comparisons.results
        )
        findings.append(
            {
                "query": result["query"],
                "search_rank": result["rank"],
                "title": result["title"],
                "url": result["url"],
                "snippet": result["snippet"],
                "host": _host_label(str(result["url"])),
                "query_category": result["query_category"],
                "fetch_status": snapshot.status,
                "candidate_count": len(batch.candidates),
                "candidate_batch_notes": batch.notes,
                "comparison_counts": dict(
                    Counter(item.classification for item in comparisons.results)
                ),
                "candidates": [
                    {
                        "name": item.candidate.name,
                        "candidate_type": item.candidate.candidate_type,
                        "category": item.candidate.category,
                        "confidence": item.candidate.confidence,
                        "classification": item.classification,
                        "match_score": item.match_score,
                        "matched_deadline_id": (
                            str(item.primary_deadline_id)
                            if item.primary_deadline_id is not None
                            else None
                        ),
                        "detected_deadline_text": item.candidate.detected_deadline_text,
                    }
                    for item in comparisons.results
                ],
            }
        )

    report_paths = _write_open_web_reports(
        root=root,
        current_date=active_date,
        findings=findings,
        query_specs=active_queries,
        skipped_monitored_results=skipped_monitored_results,
        classification_counts=classification_counts,
    )

    payload = {
        "step_name": STEP_NAME,
        "agent_name": AGENT_NAME,
        "description": DESCRIPTION,
        "input_source": INPUT_SOURCE,
        "output_destination": OUTPUT_DESTINATION,
        "condition": CONDITION,
        "error_handling": ERROR_HANDLING,
        "current_date": active_date.isoformat(),
        "query_count": len(active_queries),
        "search_result_count": len(search_results),
        "skipped_monitored_result_count": skipped_monitored_results,
        "fetched_result_count": len(fetch_results),
        "candidate_count": candidate_total,
        "classification_counts": {
            "likely_new": classification_counts.get("likely_new", 0),
            "likely_update": classification_counts.get("likely_update", 0),
            "likely_duplicate": classification_counts.get("likely_duplicate", 0),
            "ambiguous": classification_counts.get("ambiguous", 0),
        },
        "report_json_path": str(report_paths["json"]),
        "report_markdown_path": str(report_paths["markdown"]),
        "findings": findings,
    }
    return payload


def _build_default_query_specs(current_date: date) -> List[Dict[str, str]]:
    from media_calendar.components import build_open_web_queries

    return build_open_web_queries(current_date)


def _build_search_source_entry(result: Dict[str, object]) -> SourceRegistryEntry:
    source_url = str(result["url"])
    return SourceRegistryEntry(
        id=uuid5(_OPEN_WEB_SOURCE_NAMESPACE, _normalize_url(source_url)),
        organization=_host_label(source_url),
        program_name=str(result["title"])[:120],
        source_url=source_url,
        source_type=str(result["query_source_type"]),
        deadline_categories=[str(result["query_category"])],
        regions=["Global"],
        cadence="unknown",
        coverage_priority="watchlist",
        discovery_strategy="manual_watch",
        notes=(
            "Open-web sweep candidate found via query "
            f"'{result['query']}'. Treat as review-first until promoted."
        ),
    )


def _host_label(url: str) -> str:
    hostname = urlparse(url).hostname or "Unknown Host"
    if hostname.startswith("www."):
        hostname = hostname[4:]
    return hostname


def _normalize_url(url: str) -> str:
    return url.rstrip("/").lower()


def _write_open_web_reports(
    *,
    root: Path,
    current_date: date,
    findings: Sequence[Dict[str, object]],
    query_specs: Sequence[Dict[str, str]],
    skipped_monitored_results: int,
    classification_counts: Counter[str],
) -> Dict[str, Path]:
    output_dir = root / "build"
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "open-web-discovery.json"
    markdown_path = output_dir / "open-web-discovery.md"

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "current_date": current_date.isoformat(),
        "query_count": len(query_specs),
        "queries": [item["query"] for item in query_specs],
        "search_result_count": len(findings),
        "skipped_monitored_result_count": skipped_monitored_results,
        "classification_counts": {
            "likely_new": classification_counts.get("likely_new", 0),
            "likely_update": classification_counts.get("likely_update", 0),
            "likely_duplicate": classification_counts.get("likely_duplicate", 0),
            "ambiguous": classification_counts.get("ambiguous", 0),
        },
        "findings": list(findings),
    }
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    markdown_path.write_text(
        _build_markdown_report(
            current_date=current_date,
            findings=findings,
            query_specs=query_specs,
            skipped_monitored_results=skipped_monitored_results,
            classification_counts=classification_counts,
        ),
        encoding="utf-8",
    )
    return {"json": json_path, "markdown": markdown_path}


def _build_markdown_report(
    *,
    current_date: date,
    findings: Sequence[Dict[str, object]],
    query_specs: Sequence[Dict[str, str]],
    skipped_monitored_results: int,
    classification_counts: Counter[str],
) -> str:
    lines = [
        "# Open-Web Discovery Report",
        "",
        f"- Run Date: `{current_date.isoformat()}`",
        f"- Query Count: `{len(query_specs)}`",
        f"- Search Results Reviewed: `{len(findings)}`",
        f"- Already Monitored URLs Skipped: `{skipped_monitored_results}`",
        f"- Likely New Candidates: `{classification_counts.get('likely_new', 0)}`",
        f"- Likely Updates: `{classification_counts.get('likely_update', 0)}`",
        f"- Likely Duplicates: `{classification_counts.get('likely_duplicate', 0)}`",
        f"- Ambiguous Candidates: `{classification_counts.get('ambiguous', 0)}`",
        "",
        "## Queries",
        "",
    ]

    lines.extend(f"- `{item['query']}`" for item in query_specs)
    lines.append("")
    lines.append("## Findings")
    lines.append("")

    if not findings:
        lines.append("No open-web results survived filtering for this run.")
        return "\n".join(lines)

    for finding in findings:
        lines.extend(
            [
                f"### {finding['title']}",
                f"- URL: {finding['url']}",
                f"- Query: `{finding['query']}`",
                f"- Host: `{finding['host']}`",
                f"- Fetch Status: `{finding['fetch_status']}`",
                f"- Candidate Count: `{finding['candidate_count']}`",
                (
                    "- Comparison Counts: "
                    f"`{json.dumps(finding['comparison_counts'], sort_keys=True)}`"
                ),
                f"- Notes: {finding['candidate_batch_notes']}",
            ]
        )
        if finding["candidates"]:
            lines.append("- Candidate Highlights:")
            for candidate in finding["candidates"][:5]:
                lines.append(
                    f"  {candidate['name']} "
                    f"({candidate['classification']}, score={candidate['match_score']:.2f})"
                )
        lines.append("")

    return "\n".join(lines)
