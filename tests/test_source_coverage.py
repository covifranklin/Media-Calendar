from __future__ import annotations

import json
from textwrap import dedent

from media_calendar.components import (
    build_source_coverage_report,
    write_source_coverage_report,
)


def _write_source_yaml(tmp_path, filename: str, contents: str):
    data_dir = tmp_path / "data" / "sources"
    data_dir.mkdir(parents=True, exist_ok=True)
    path = data_dir / filename
    path.write_text(dedent(contents).strip(), encoding="utf-8")
    return path


def test_build_source_coverage_report_counts_and_gaps(tmp_path):
    _write_source_yaml(
        tmp_path,
        "core.yaml",
        """
        - id: "11111111-1111-4111-8111-111111111111"
          organization: "Sundance Institute"
          program_name: "Artist Opportunities"
          source_url: "https://example.com/sundance"
          source_type: "lab"
          deadline_categories: ["lab_application", "fellowship"]
          regions: ["North America", "Global"]
          cadence: "annual"
          coverage_priority: "must_have"
          discovery_strategy: "official_program_page"
        - id: "22222222-2222-4222-8222-222222222222"
          organization: "Series Mania Forum"
          program_name: "Forum"
          source_url: "https://example.com/series-mania"
          source_type: "market"
          deadline_categories: ["industry_forum"]
          regions: ["Europe", "Global"]
          cadence: "annual"
          coverage_priority: "high"
          discovery_strategy: "official_program_page"
        - id: "33333333-3333-4333-8333-333333333333"
          organization: "BFI NETWORK"
          program_name: "Funding"
          source_url: "https://example.com/bfi-network"
          source_type: "fund"
          deadline_categories: ["funding_round"]
          regions: ["United Kingdom"]
          cadence: "periodic"
          coverage_priority: "high"
          discovery_strategy: "official_application_page"
        """,
    )

    report = build_source_coverage_report(root_dir=tmp_path)

    assert report.total_source_count == 3
    assert report.counts_by_coverage_priority == {
        "must_have": 1,
        "high": 2,
        "medium": 0,
        "watchlist": 0,
    }
    assert report.counts_by_source_type["lab"] == 1
    assert report.counts_by_source_type["market"] == 1
    assert report.counts_by_source_type["fund"] == 1
    assert report.counts_by_deadline_category["lab_application"] == 1
    assert report.counts_by_deadline_category["fellowship"] == 1
    assert report.counts_by_deadline_category["funding_round"] == 1
    assert report.counts_by_deadline_category["industry_forum"] == 1
    assert report.counts_by_region == {
        "Europe": 1,
        "Global": 2,
        "North America": 1,
        "United Kingdom": 1,
    }
    assert [source.organization for source in report.must_have_sources] == [
        "Sundance Institute"
    ]
    assert [source.organization for source in report.high_sources] == [
        "BFI NETWORK",
        "Series Mania Forum",
    ]
    assert "funding_round" in report.gap_summary.categories_without_must_have_coverage
    assert "industry_forum" in report.gap_summary.categories_without_must_have_coverage
    assert report.gap_summary.regions_without_must_have_coverage == [
        "Europe",
        "United Kingdom",
    ]
    assert (
        "No sources are tracked for deadline_category=festival_submission."
        in report.gap_summary.suspicious_groupings
    )


def test_write_source_coverage_report_writes_json_and_markdown(tmp_path):
    _write_source_yaml(
        tmp_path,
        "core.yaml",
        """
        - id: "11111111-1111-4111-8111-111111111111"
          organization: "Sundance Institute"
          program_name: "Artist Opportunities"
          source_url: "https://example.com/sundance"
          source_type: "lab"
          deadline_categories: ["lab_application"]
          regions: ["Global"]
          cadence: "annual"
          coverage_priority: "must_have"
          discovery_strategy: "official_program_page"
        """,
    )

    report = build_source_coverage_report(root_dir=tmp_path)
    paths = write_source_coverage_report(report, root_dir=tmp_path)

    payload = json.loads(paths["json"].read_text(encoding="utf-8"))
    markdown = paths["markdown"].read_text(encoding="utf-8")

    assert payload["total_source_count"] == 1
    assert "# Source Coverage Report" in markdown
    assert "Sundance Institute - Artist Opportunities" in markdown
