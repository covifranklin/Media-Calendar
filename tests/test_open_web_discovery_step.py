from __future__ import annotations

from datetime import date
from pathlib import Path
from textwrap import dedent

from media_calendar.orchestration import orchestration_step_open_web_discovery


def _write_source_registry(tmp_path: Path) -> Path:
    source_dir = tmp_path / "data" / "sources"
    source_dir.mkdir(parents=True, exist_ok=True)
    source_file = source_dir / "must-have.yaml"
    source_file.write_text(
        dedent(
            """
            - id: "11111111-1111-4111-8111-111111111111"
              organization: "Tracked Org"
              program_name: "Tracked Program"
              source_url: "https://tracked.example.com/program"
              source_type: "lab"
              deadline_categories: ["lab_application"]
              regions: ["Global"]
              cadence: "annual"
              coverage_priority: "must_have"
              discovery_strategy: "official_program_page"
            """
        ).strip(),
        encoding="utf-8",
    )
    return source_file


def _write_deadlines(tmp_path: Path) -> Path:
    deadline_dir = tmp_path / "data" / "deadlines"
    deadline_dir.mkdir(parents=True, exist_ok=True)
    deadline_file = deadline_dir / "2026.yaml"
    deadline_file.write_text("[]\n", encoding="utf-8")
    return deadline_file


def test_open_web_discovery_writes_review_only_reports(tmp_path):
    _write_source_registry(tmp_path)
    _write_deadlines(tmp_path)

    query_specs = [
        {
            "query": "documentary lab applications 2026",
            "category": "lab_application",
            "source_type": "lab",
        }
    ]

    def fake_search_provider(
        query_specs,
        *,
        max_results_per_query=3,
        max_results_total=12,
    ):
        assert max_results_per_query == 2
        assert max_results_total == 4
        assert len(query_specs) == 1
        return [
            {
                "query": query_specs[0]["query"],
                "query_category": "lab_application",
                "query_source_type": "lab",
                "title": "Tracked Program",
                "url": "https://tracked.example.com/program",
                "snippet": "Already monitored source.",
                "rank": 1,
            },
            {
                "query": query_specs[0]["query"],
                "query_category": "lab_application",
                "query_source_type": "lab",
                "title": "New Documentary Lab 2026",
                "url": "https://newsource.example.org/opportunities/doc-lab",
                "snippet": "Applications open now.",
                "rank": 2,
            },
        ]

    def fake_fetch_url(url: str):
        assert url == "https://newsource.example.org/opportunities/doc-lab"
        return (
            200,
            "text/html",
            "<html><body>"
            "<h1>New Documentary Lab 2026</h1>"
            "<p>Applications open now. Deadline: June 1, 2026</p>"
            "</body></html>",
        )

    payload = orchestration_step_open_web_discovery(
        root_dir=tmp_path,
        current_date=date(2026, 4, 23),
        query_specs=query_specs,
        max_results_per_query=2,
        max_results_total=4,
        search_provider=fake_search_provider,
        fetch_url=fake_fetch_url,
    )

    assert payload["step_name"] == "Open-Web Discovery Sweep"
    assert payload["query_count"] == 1
    assert payload["search_result_count"] == 1
    assert payload["skipped_monitored_result_count"] == 1
    assert payload["candidate_count"] == 1
    assert payload["classification_counts"]["likely_new"] == 1
    assert (tmp_path / "build" / "open-web-discovery.json").exists()
    assert (tmp_path / "build" / "open-web-discovery.md").exists()
    assert payload["findings"][0]["title"] == "New Documentary Lab 2026"
    assert payload["findings"][0]["candidates"][0]["name"] == "New Documentary Lab 2026"


def test_open_web_discovery_keeps_fetch_failures_in_report(tmp_path):
    _write_source_registry(tmp_path)
    _write_deadlines(tmp_path)

    query_specs = [
        {
            "query": "documentary fund applications 2026",
            "category": "funding_round",
            "source_type": "fund",
        }
    ]

    def fake_search_provider(
        query_specs,
        *,
        max_results_per_query=3,
        max_results_total=12,
    ):
        return [
            {
                "query": query_specs[0]["query"],
                "query_category": "funding_round",
                "query_source_type": "fund",
                "title": "Broken Result",
                "url": "https://broken.example.org/fund",
                "snippet": "Should remain reviewable even if fetch fails.",
                "rank": 1,
            }
        ]

    def fake_fetch_url(url: str):
        raise OSError("network down")

    payload = orchestration_step_open_web_discovery(
        root_dir=tmp_path,
        current_date=date(2026, 4, 23),
        query_specs=query_specs,
        search_provider=fake_search_provider,
        fetch_url=fake_fetch_url,
    )

    assert payload["search_result_count"] == 1
    assert payload["candidate_count"] == 0
    assert payload["findings"][0]["fetch_status"] == "network_error"
    assert payload["findings"][0]["candidate_count"] == 0
