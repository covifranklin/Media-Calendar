from __future__ import annotations

from pathlib import Path
from urllib.error import HTTPError, URLError
from uuid import uuid4

from media_calendar.components import fetch_registered_sources, fetch_source, fetch_sources
from media_calendar.models import SourceRegistryEntry


def build_source_entry() -> SourceRegistryEntry:
    return SourceRegistryEntry(
        id=uuid4(),
        organization="Example Org",
        program_name="Example Program",
        source_url="https://example.com/program",
        source_type="lab",
        deadline_categories=["lab_application"],
        regions=["Global"],
        cadence="annual",
        coverage_priority="must_have",
        discovery_strategy="official_program_page",
    )


def test_fetch_source_returns_success_payload():
    entry = build_source_entry()

    def fake_fetch_url(url: str):
        assert url == entry.source_url
        return 200, "text/html; charset=utf-8", "<html>Example</html>"

    result = fetch_source(entry, fetch_url=fake_fetch_url)

    assert result.status == "success"
    assert result.http_status == 200
    assert result.content_type == "text/html; charset=utf-8"
    assert result.body == "<html>Example</html>"
    assert result.error_message is None


def test_fetch_source_returns_http_error_payload():
    entry = build_source_entry()

    def fake_fetch_url(url: str):
        raise HTTPError(url, 403, "Forbidden", hdrs=None, fp=None)

    result = fetch_source(entry, fetch_url=fake_fetch_url)

    assert result.status == "http_error"
    assert result.http_status == 403
    assert result.body is None
    assert "Forbidden" in (result.error_message or "")


def test_fetch_source_returns_network_error_payload():
    entry = build_source_entry()

    def fake_fetch_url(url: str):
        raise URLError("timed out")

    result = fetch_source(entry, fetch_url=fake_fetch_url)

    assert result.status == "network_error"
    assert result.http_status is None
    assert result.body is None
    assert result.error_message == "timed out"


def test_fetch_sources_preserves_input_order():
    first = build_source_entry()
    second = build_source_entry().model_copy(
        update={
            "organization": "Second Org",
            "program_name": "Second Program",
            "source_url": "https://example.com/second",
        }
    )

    def fake_fetch_url(url: str):
        return 200, "text/html", f"body for {url}"

    results = fetch_sources([first, second], fetch_url=fake_fetch_url)

    assert [result.organization for result in results] == ["Example Org", "Second Org"]
    assert results[0].body == "body for https://example.com/program"
    assert results[1].body == "body for https://example.com/second"


def test_fetch_registered_sources_loads_registry_then_fetches(tmp_path):
    source_dir = tmp_path / "data" / "sources"
    source_dir.mkdir(parents=True)
    source_file = source_dir / "registry.yaml"
    source_file.write_text(
        """
        sources:
          - id: "11111111-1111-4111-8111-111111111111"
            organization: "Sample Festival"
            program_name: "Submissions"
            source_url: "https://example.com/submissions"
            source_type: "festival"
            deadline_categories: ["festival_submission"]
            regions: ["Global"]
            cadence: "annual"
            coverage_priority: "must_have"
            discovery_strategy: "official_deadlines_page"
        """,
        encoding="utf-8",
    )

    def fake_fetch_url(url: str):
        return 200, "text/html", f"fetched {url}"

    results = fetch_registered_sources(root_dir=tmp_path, fetch_url=fake_fetch_url)

    assert len(results) == 1
    assert results[0].organization == "Sample Festival"
    assert results[0].status == "success"
    assert results[0].body == "fetched https://example.com/submissions"
