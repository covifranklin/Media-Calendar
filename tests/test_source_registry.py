from pathlib import Path

from media_calendar.components import load_source_registry, resolve_source_files


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
