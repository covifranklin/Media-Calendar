from __future__ import annotations

from datetime import date
from pathlib import Path
from textwrap import dedent

import pytest

from media_calendar.orchestration import orchestration_step_discovery_refresh


def _write_source_registry(tmp_path: Path) -> Path:
    source_dir = tmp_path / "data" / "sources"
    source_dir.mkdir(parents=True)
    source_file = source_dir / "must-have.yaml"
    source_file.write_text(
        dedent(
            """
            - id: "11111111-1111-4111-8111-111111111111"
              organization: "Example Labs"
              program_name: "Open Calls"
              source_url: "https://example.com/open-calls"
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


def test_orchestration_step_discovery_refresh_promotes_and_writes_yaml(tmp_path):
    _write_source_registry(tmp_path)
    (tmp_path / "data" / "deadlines").mkdir(parents=True)

    def fake_fetch_url(url: str):
        assert url == "https://example.com/open-calls"
        return (
            200,
            "text/html",
            "<html><body><p>Example Documentary Lab 2026 "
            "Applications open now Deadline: June 1, 2026</p>"
            "</body></html>",
        )

    def fake_calendar_generator(*, root_dir=None, deadline_files=None):
        assert root_dir == tmp_path
        output_path = tmp_path / "build" / "calendar.html"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text("<html></html>", encoding="utf-8")
        return output_path

    payload = orchestration_step_discovery_refresh(
        root_dir=tmp_path,
        current_date=date(2026, 4, 21),
        llm_mode="off",
        fetch_url=fake_fetch_url,
        calendar_generator=fake_calendar_generator,
    )

    written_file = tmp_path / "data" / "deadlines" / "2026.yaml"
    assert payload["step_name"] == "Refresh Discovery Pipeline"
    assert payload["promoted_new_count"] == 1
    assert payload["promoted_update_count"] == 0
    assert payload["ignored_duplicate_count"] == 0
    assert payload["rejected_uncertain_count"] == 0
    assert payload["llm_enabled"] is False
    assert written_file.exists()
    assert "Example Documentary Lab 2026" in written_file.read_text(encoding="utf-8")
    assert (tmp_path / "build" / "discovery-refresh.json").exists()
    assert (tmp_path / "build" / "discovery-refresh.md").exists()


def test_orchestration_step_discovery_refresh_falls_back_when_llm_fails(
    tmp_path, monkeypatch
):
    _write_source_registry(tmp_path)
    (tmp_path / "data" / "deadlines").mkdir(parents=True)

    def fake_fetch_url(url: str):
        return (
            200,
            "text/html",
            "<html><body><p>Example Documentary Lab 2026 "
            "Applications open now Deadline: June 1, 2026</p>"
            "</body></html>",
        )

    def fake_calendar_generator(*, root_dir=None, deadline_files=None):
        output_path = tmp_path / "build" / "calendar.html"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text("<html></html>", encoding="utf-8")
        return output_path

    def fake_discover(agent_input, *, client=None, max_attempts=3):
        raise RuntimeError("llm unavailable")

    monkeypatch.setattr(
        "media_calendar.orchestration.discovery_refresh_step.discover_source_candidates",
        fake_discover,
    )

    payload = orchestration_step_discovery_refresh(
        root_dir=tmp_path,
        current_date=date(2026, 4, 21),
        llm_mode="auto",
        llm_client=object(),
        fetch_url=fake_fetch_url,
        calendar_generator=fake_calendar_generator,
    )

    assert payload["promoted_new_count"] == 1
    assert payload["deterministic_fallback_batches"] == 1
    assert payload["llm_enabled"] is True


def test_orchestration_step_discovery_refresh_requires_llm_when_requested(tmp_path):
    _write_source_registry(tmp_path)
    (tmp_path / "data" / "deadlines").mkdir(parents=True)

    with pytest.raises(RuntimeError, match="llm_mode='required'"):
        orchestration_step_discovery_refresh(
            root_dir=tmp_path,
            current_date=date(2026, 4, 21),
            llm_mode="required",
        )
