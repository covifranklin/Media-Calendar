from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from media_calendar.components import build_source_health_report
from media_calendar.models import SourceSnapshotResult


def build_snapshot_result(
    *,
    status="success",
    extracted_text=(
        "This is a healthy source result with enough words to pass the text "
        "threshold cleanly for reporting, giving the system a strong signal "
        "that the fetched page contains substantial usable content for later "
        "discovery and review workflows."
    ),
    http_status=200,
    error_message=None,
) -> SourceSnapshotResult:
    return SourceSnapshotResult(
        source_id=uuid4(),
        organization="Example Org",
        program_name="Example Program",
        source_url="https://example.com/program",
        status=status,
        fetched_at=datetime(2026, 4, 21, 12, 0, tzinfo=timezone.utc),
        http_status=http_status,
        content_type="text/html",
        snapshot_path="/tmp/example.html" if status == "success" else None,
        text_path="/tmp/example.txt" if status == "success" else None,
        extracted_text=extracted_text if status == "success" else None,
        error_message=error_message,
    )


def test_build_source_health_report_counts_healthy_sources():
    results = [build_snapshot_result()]

    report = build_source_health_report(results)

    assert report["total_sources"] == 1
    assert report["healthy_count"] == 1
    assert report["needs_attention_count"] == 0
    assert report["success_count"] == 1
    assert report["empty_text_count"] == 0
    assert report["thin_text_count"] == 0
    assert report["entries"][0]["health_status"] == "healthy"


def test_build_source_health_report_flags_http_errors():
    results = [
        build_snapshot_result(
            status="http_error",
            extracted_text=None,
            http_status=403,
            error_message="HTTP Error 403: Forbidden",
        )
    ]

    report = build_source_health_report(results)

    assert report["healthy_count"] == 0
    assert report["needs_attention_count"] == 1
    assert report["http_error_count"] == 1
    assert report["entries"][0]["issue_codes"] == ["http_error"]
    assert "status 403" in report["entries"][0]["summary"]


def test_build_source_health_report_flags_network_errors():
    results = [
        build_snapshot_result(
            status="network_error",
            extracted_text=None,
            http_status=None,
            error_message="timed out",
        )
    ]

    report = build_source_health_report(results)

    assert report["network_error_count"] == 1
    assert report["entries"][0]["issue_codes"] == ["network_error"]
    assert report["entries"][0]["health_status"] == "needs_attention"


def test_build_source_health_report_flags_empty_text():
    results = [build_snapshot_result(extracted_text="")]

    report = build_source_health_report(results)

    assert report["empty_text_count"] == 1
    assert report["entries"][0]["issue_codes"] == ["empty_text"]
    assert report["entries"][0]["word_count"] == 0


def test_build_source_health_report_flags_thin_text():
    results = [build_snapshot_result(extracted_text="too short to trust yet")]

    report = build_source_health_report(results)

    assert report["thin_text_count"] == 1
    assert report["entries"][0]["issue_codes"] == ["thin_text"]
    assert report["entries"][0]["health_status"] == "needs_attention"


def test_build_source_health_report_includes_markdown_summary():
    results = [build_snapshot_result()]

    report = build_source_health_report(results)

    assert "# Source Fetch Health Report" in report["markdown"]
    assert "## Example Org - Example Program" in report["markdown"]
    assert "- Healthy: `1`" in report["markdown"]
