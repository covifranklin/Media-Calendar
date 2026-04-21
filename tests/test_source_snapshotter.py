from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from media_calendar.components import extract_source_text, snapshot_fetch_results
from media_calendar.models import SourceFetchResult


def build_fetch_result(
    *,
    status="success",
    content_type="text/html; charset=utf-8",
    body="<html><body>Hello</body></html>",
    http_status=200,
    error_message=None,
) -> SourceFetchResult:
    return SourceFetchResult(
        source_id=uuid4(),
        organization="Example Org",
        program_name="Example Program",
        source_url="https://example.com/program",
        status=status,
        fetched_at=datetime(2026, 4, 21, 12, 0, tzinfo=timezone.utc),
        http_status=http_status,
        content_type=content_type,
        body=body,
        error_message=error_message,
    )


def test_extract_source_text_strips_html_and_ignores_script_and_style():
    html = """
    <html>
      <head>
        <style>body { color: red; }</style>
        <script>console.log("ignore me")</script>
      </head>
      <body>
        <h1>Festival Submissions</h1>
        <p>Deadline: June 1, 2026</p>
      </body>
    </html>
    """

    text = extract_source_text(html, content_type="text/html")

    assert "Festival Submissions" in text
    assert "Deadline: June 1, 2026" in text
    assert "console.log" not in text
    assert "color: red" not in text


def test_extract_source_text_normalizes_plain_text():
    body = "  Line one   \n\nLine   two  \n"

    text = extract_source_text(body, content_type="text/plain")

    assert text == "Line one\nLine two"


def test_snapshot_fetch_results_writes_raw_and_text_files(tmp_path):
    fetch_result = build_fetch_result(
        body="<html><body><h1>Open Call</h1><p>Apply now</p></body></html>"
    )

    results = snapshot_fetch_results([fetch_result], root_dir=tmp_path)

    assert len(results) == 1
    snapshot = results[0]
    assert snapshot.status == "success"
    assert snapshot.snapshot_path is not None
    assert snapshot.text_path is not None
    assert snapshot.extracted_text == "Open Call\nApply now"
    assert Path(snapshot.snapshot_path).read_text(encoding="utf-8").startswith("<html>")
    assert Path(snapshot.text_path).read_text(encoding="utf-8") == "Open Call\nApply now"


def test_snapshot_fetch_results_preserves_failures_without_writing_files(tmp_path):
    fetch_result = build_fetch_result(
        status="http_error",
        content_type=None,
        body=None,
        http_status=404,
        error_message="HTTP Error 404: Not Found",
    )

    results = snapshot_fetch_results([fetch_result], root_dir=tmp_path)

    assert len(results) == 1
    snapshot = results[0]
    assert snapshot.status == "http_error"
    assert snapshot.snapshot_path is None
    assert snapshot.text_path is None
    assert snapshot.extracted_text is None
    assert snapshot.error_message == "HTTP Error 404: Not Found"
