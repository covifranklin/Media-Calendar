from pathlib import Path

from datetime import date

from media_calendar.components import (
    load_source_registry,
    resolve_source_files,
    resolve_source_scope,
    select_source_registry,
)


def test_load_source_registry_accepts_list_payload_and_sorts_by_priority(tmp_path):
    data_dir = tmp_path / "data" / "sources"
    data_dir.mkdir(parents=True)
    source_file = data_dir / "core.yaml"
    source_file.write_text(
        """
        - id: "11111111-1111-4111-8111-111111111111"
          organization: "Film Independent"
          program_name: "Fast Track"
          source_url: "https://example.com/fast-track"
          source_type: "industry_forum"
          deadline_categories: ["industry_forum"]
          regions: ["North America"]
          cadence: "annual"
          coverage_priority: "high"
          discovery_strategy: "official_program_page"
        - id: "22222222-2222-4222-8222-222222222222"
          organization: "Sundance Institute"
          program_name: "Labs"
          source_url: "https://example.com/labs"
          source_type: "lab"
          deadline_categories: ["lab_application", "fellowship"]
          regions: ["North America"]
          cadence: "annual"
          coverage_priority: "must_have"
          discovery_strategy: "official_program_page"
        """,
        encoding="utf-8",
    )

    entries = load_source_registry([source_file])

    assert [entry.coverage_priority for entry in entries] == ["must_have", "high"]
    assert entries[0].organization == "Sundance Institute"
    assert entries[1].program_name == "Fast Track"


def test_load_source_registry_accepts_mapping_payload_and_optional_notes(tmp_path):
    data_dir = tmp_path / "data" / "sources"
    data_dir.mkdir(parents=True)
    source_file = data_dir / "regional.yaml"
    source_file.write_text(
        """
        sources:
          - id: "33333333-3333-4333-8333-333333333333"
            organization: "European Film Market"
            program_name: "Industry Programs"
            source_url: "https://example.com/efm"
            source_type: "market"
            deadline_categories: ["industry_forum", "other"]
            regions: ["Europe"]
            cadence: "periodic"
            coverage_priority: "medium"
            discovery_strategy: "official_deadlines_page"
            active: false
            notes: "Track for curated market deadlines."
        """,
        encoding="utf-8",
    )

    entries = load_source_registry([source_file])

    assert len(entries) == 1
    assert entries[0].active is False
    assert entries[0].notes == "Track for curated market deadlines."


def test_resolve_source_files_defaults_to_data_sources_directory(tmp_path):
    data_dir = tmp_path / "data" / "sources"
    data_dir.mkdir(parents=True)
    first = data_dir / "a.yaml"
    second = data_dir / "b.yaml"
    first.write_text("[]", encoding="utf-8")
    second.write_text("[]", encoding="utf-8")

    paths = resolve_source_files(None, root=tmp_path)

    assert paths == [first, second]


def test_resolve_source_scope_auto_switches_watchlist_on_even_weeks():
    assert resolve_source_scope("auto", current_date=date(2026, 4, 20)) == "all"
    assert resolve_source_scope("auto", current_date=date(2026, 4, 27)) == "core"


def test_select_source_registry_excludes_watchlist_in_core_mode(tmp_path):
    data_dir = tmp_path / "data" / "sources"
    data_dir.mkdir(parents=True)
    source_file = data_dir / "mixed.yaml"
    source_file.write_text(
        """
        - id: "11111111-1111-4111-8111-111111111111"
          organization: "Core Org"
          program_name: "Core Programme"
          source_url: "https://example.com/core"
          source_type: "fund"
          deadline_categories: ["funding_round"]
          regions: ["Global"]
          cadence: "annual"
          coverage_priority: "must_have"
          discovery_strategy: "official_program_page"
        - id: "22222222-2222-4222-8222-222222222222"
          organization: "Watchlist Org"
          program_name: "Watchlist Programme"
          source_url: "https://example.com/watchlist"
          source_type: "other"
          deadline_categories: ["other"]
          regions: ["Global"]
          cadence: "unknown"
          coverage_priority: "watchlist"
          discovery_strategy: "manual_watch"
        """,
        encoding="utf-8",
    )

    entries = load_source_registry([source_file])

    assert [entry.organization for entry in select_source_registry(
        entries,
        current_date=date(2026, 4, 27),
        scope="core",
    )] == ["Core Org"]
    assert [entry.organization for entry in select_source_registry(
        entries,
        current_date=date(2026, 4, 20),
        scope="all",
    )] == ["Core Org", "Watchlist Org"]


def test_repository_must_have_source_registry_loads_cleanly():
    repo_root = Path(__file__).resolve().parents[1]
    source_file = repo_root / "data" / "sources" / "must-have.yaml"

    entries = load_source_registry([source_file])

    assert len(entries) >= 10
    assert entries[0].coverage_priority == "must_have"
    assert {entry.organization for entry in entries}.issuperset(
        {
            "Sundance Institute",
            "Tribeca Festival",
            "Toronto International Film Festival",
            "Series Mania Forum",
        }
    )


def test_repository_default_source_registry_loads_all_source_files():
    repo_root = Path(__file__).resolve().parents[1]
    source_files = resolve_source_files(None, root=repo_root)

    entries = load_source_registry(source_files)

    assert len(source_files) >= 4
    assert {entry.organization for entry in entries}.issuperset(
        {
            "BBC Writersroom",
            "Channel 4",
            "Film London",
            "Screen Scotland",
            "Doc Society",
            "BBC Studios",
            "CPH:DOX",
            "Doha Film Institute",
        }
    )
