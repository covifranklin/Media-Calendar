from __future__ import annotations

from datetime import date
import json
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


def test_orchestration_step_discovery_refresh_apply_mode_writes_yaml(tmp_path):
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
        mode="apply",
        llm_mode="off",
        fetch_url=fake_fetch_url,
        calendar_generator=fake_calendar_generator,
    )

    written_file = tmp_path / "data" / "deadlines" / "2026.yaml"
    assert payload["step_name"] == "Refresh Discovery Pipeline"
    assert payload["mode"] == "apply"
    assert payload["applied_changes"] is True
    assert payload["promoted_new_count"] == 1
    assert payload["promoted_update_count"] == 0
    assert payload["ignored_duplicate_count"] == 0
    assert payload["rejected_uncertain_count"] == 0
    assert payload["llm_enabled"] is False
    assert written_file.exists()
    assert "Example Documentary Lab 2026" in written_file.read_text(encoding="utf-8")
    assert (tmp_path / "build" / "discovery-refresh.json").exists()
    assert (tmp_path / "build" / "discovery-refresh.md").exists()
    assert (tmp_path / "build" / "discovery-metrics.json").exists()
    assert (tmp_path / "build" / "discovery-metrics.md").exists()
    assert (tmp_path / "build" / "source-freshness.json").exists()
    assert (tmp_path / "build" / "source-freshness.md").exists()
    assert payload["metrics_json_path"] == str(
        tmp_path / "build" / "discovery-metrics.json"
    )
    assert payload["freshness_report_json_path"] == str(
        tmp_path / "build" / "source-freshness.json"
    )
    log_path = tmp_path / "build" / "discovery-log.jsonl"
    assert payload["decision_log_path"] == str(log_path)
    lines = log_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    log_entry = json.loads(lines[0])
    assert log_entry["comparison_classification"] == "likely_new"
    assert log_entry["promotion_action"] == "promoted_new"
    assert log_entry["source_id"] == "11111111-1111-4111-8111-111111111111"
    assert log_entry["affected_deadline_id"] is not None


def test_orchestration_step_discovery_refresh_dry_run_does_not_write_yaml(tmp_path):
    _write_source_registry(tmp_path)
    deadline_dir = tmp_path / "data" / "deadlines"
    deadline_dir.mkdir(parents=True)
    written_file = deadline_dir / "2026.yaml"
    original_contents = "[]\n"
    written_file.write_text(original_contents, encoding="utf-8")

    def fake_fetch_url(url: str):
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
        mode="dry-run",
        llm_mode="off",
        fetch_url=fake_fetch_url,
        calendar_generator=fake_calendar_generator,
    )

    assert payload["mode"] == "dry-run"
    assert payload["applied_changes"] is False
    assert payload["promoted_new_count"] == 1
    assert payload["deadline_files"] == []
    assert written_file.read_text(encoding="utf-8") == original_contents
    assert (tmp_path / "build" / "discovery-refresh.json").exists()
    assert (tmp_path / "build" / "discovery-refresh.md").exists()
    assert (tmp_path / "build" / "discovery-metrics.json").exists()
    assert (tmp_path / "build" / "discovery-metrics.md").exists()
    assert (tmp_path / "build" / "source-freshness.json").exists()
    assert (tmp_path / "build" / "source-freshness.md").exists()
    assert (tmp_path / "build" / "calendar.html").exists()
    assert (tmp_path / "build" / "discovery-log.jsonl").exists()


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


def test_orchestration_step_discovery_refresh_appends_decision_logs(tmp_path):
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

    orchestration_step_discovery_refresh(
        root_dir=tmp_path,
        current_date=date(2026, 4, 21),
        mode="apply",
        llm_mode="off",
        fetch_url=fake_fetch_url,
        calendar_generator=fake_calendar_generator,
    )
    orchestration_step_discovery_refresh(
        root_dir=tmp_path,
        current_date=date(2026, 4, 28),
        mode="apply",
        llm_mode="off",
        fetch_url=fake_fetch_url,
        calendar_generator=fake_calendar_generator,
    )

    log_path = tmp_path / "build" / "discovery-log.jsonl"
    lines = log_path.read_text(encoding="utf-8").splitlines()

    assert len(lines) == 2
    first = json.loads(lines[0])
    second = json.loads(lines[1])
    assert first["promotion_action"] == "promoted_new"
    assert second["promotion_action"] in {"ignored_duplicate", "promoted_update", "rejected_uncertain"}
