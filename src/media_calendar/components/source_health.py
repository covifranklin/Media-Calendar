"""Helpers for summarizing source fetch and snapshot health."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List, Sequence

from media_calendar.models import SourceSnapshotResult

THIN_TEXT_WORD_THRESHOLD = 30


def build_source_health_report(
    snapshot_results: Sequence[SourceSnapshotResult],
) -> dict:
    """Build a deterministic health report from source snapshot results."""

    entries = [_build_health_entry(result) for result in snapshot_results]

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_sources": len(snapshot_results),
        "healthy_count": sum(
            1 for entry in entries if entry["health_status"] == "healthy"
        ),
        "needs_attention_count": sum(
            1 for entry in entries if entry["health_status"] == "needs_attention"
        ),
        "success_count": sum(
            1 for result in snapshot_results if result.status == "success"
        ),
        "http_error_count": sum(
            1 for result in snapshot_results if result.status == "http_error"
        ),
        "network_error_count": sum(
            1 for result in snapshot_results if result.status == "network_error"
        ),
        "empty_text_count": sum(
            1 for entry in entries if "empty_text" in entry["issue_codes"]
        ),
        "thin_text_count": sum(
            1 for entry in entries if "thin_text" in entry["issue_codes"]
        ),
        "entries": entries,
    }
    report["markdown"] = _build_markdown_report(report)
    return report


def _build_health_entry(result: SourceSnapshotResult) -> dict:
    issue_codes: List[str] = []

    if result.status == "http_error":
        issue_codes.append("http_error")
    elif result.status == "network_error":
        issue_codes.append("network_error")

    extracted_text = (result.extracted_text or "").strip()
    word_count = len(extracted_text.split()) if extracted_text else 0

    if result.status == "success" and not extracted_text:
        issue_codes.append("empty_text")
    elif result.status == "success" and word_count < THIN_TEXT_WORD_THRESHOLD:
        issue_codes.append("thin_text")

    health_status = "healthy" if not issue_codes else "needs_attention"

    return {
        "source_id": str(result.source_id),
        "organization": result.organization,
        "program_name": result.program_name,
        "source_url": result.source_url,
        "fetch_status": result.status,
        "health_status": health_status,
        "issue_codes": issue_codes,
        "http_status": result.http_status,
        "snapshot_path": result.snapshot_path,
        "text_path": result.text_path,
        "word_count": word_count,
        "error_message": result.error_message,
        "summary": _summarize_health(result, issue_codes, word_count),
    }


def _summarize_health(
    result: SourceSnapshotResult,
    issue_codes: Sequence[str],
    word_count: int,
) -> str:
    if "http_error" in issue_codes:
        return f"HTTP fetch failed with status {result.http_status}."
    if "network_error" in issue_codes:
        return "Network fetch failed before content could be saved."
    if "empty_text" in issue_codes:
        return "Fetch succeeded but extracted text was empty."
    if "thin_text" in issue_codes:
        return (
            "Fetch succeeded but extracted text looked thin "
            f"({word_count} words)."
        )
    return f"Fetch and text extraction succeeded with {word_count} words."


def _build_markdown_report(report: Dict[str, object]) -> str:
    lines = [
        "# Source Fetch Health Report",
        "",
        f"- Total Sources: `{report['total_sources']}`",
        f"- Healthy: `{report['healthy_count']}`",
        f"- Needs Attention: `{report['needs_attention_count']}`",
        f"- Successes: `{report['success_count']}`",
        f"- HTTP Errors: `{report['http_error_count']}`",
        f"- Network Errors: `{report['network_error_count']}`",
        f"- Empty Text Results: `{report['empty_text_count']}`",
        f"- Thin Text Results: `{report['thin_text_count']}`",
        "",
    ]

    for entry in report["entries"]:
        lines.extend(
            [
                f"## {entry['organization']} - {entry['program_name']}",
                f"- Health Status: `{entry['health_status']}`",
                f"- Fetch Status: `{entry['fetch_status']}`",
                f"- Source URL: {entry['source_url']}",
                f"- Word Count: `{entry['word_count']}`",
                f"- Issues: `{', '.join(entry['issue_codes']) or 'none'}`",
                f"- Summary: {entry['summary']}",
                "",
            ]
        )

    return "\n".join(lines)
