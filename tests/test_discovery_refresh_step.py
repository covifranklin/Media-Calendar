from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from textwrap import dedent

import pytest

from media_calendar.orchestration import orchestration_step_discovery_refresh
from media_calendar.models import DiscoveryCandidate, DiscoveryCandidateBatch


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

    def fake_calendar_generator(*, root_dir=None, deadline_files=None, current_date=None):
        assert root_dir == tmp_path
        assert current_date == date(2026, 4, 21)
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
    assert payload["source_scope_requested"] == "auto"
    assert payload["source_scope_effective"] == "all"
    assert payload["selected_source_count"] == 1
    assert payload["total_source_count"] == 1
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

    def fake_calendar_generator(*, root_dir=None, deadline_files=None, current_date=None):
        assert root_dir == tmp_path
        assert current_date == date(2026, 4, 21)
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

    def fake_calendar_generator(*, root_dir=None, deadline_files=None, current_date=None):
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

    def fake_calendar_generator(*, root_dir=None, deadline_files=None, current_date=None):
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


def test_orchestration_step_discovery_refresh_apply_mode_prunes_past_deadlines(
    tmp_path,
):
    _write_source_registry(tmp_path)
    deadline_dir = tmp_path / "data" / "deadlines"
    deadline_dir.mkdir(parents=True)
    (deadline_dir / "2026.yaml").write_text(
        dedent(
            """
            - id: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
              name: "Past Market"
              category: "industry_forum"
              organization: "Example Org"
              url: "https://example.com/past-market"
              deadline_date: 2026-03-01
              early_deadline_date:
              event_start_date:
              event_end_date:
              description: "Old market deadline."
              eligibility_notes:
              notification_windows: [30, 14, 3]
              status: "confirmed"
              last_verified_date: 2026-02-15
              source_url: "https://example.com/past-market-source"
              tags: ["market"]
              year: 2026
            """
        ).strip(),
        encoding="utf-8",
    )

    def fake_fetch_url(url: str):
        return (
            200,
            "text/html",
            "<html><body><p>Example Documentary Lab 2026 "
            "Applications open now Deadline: June 1, 2026</p>"
            "</body></html>",
        )

    def fake_calendar_generator(*, root_dir=None, deadline_files=None, current_date=None):
        assert current_date == date(2026, 4, 21)
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

    written_file = deadline_dir / "2026.yaml"
    contents = written_file.read_text(encoding="utf-8")
    assert "Past Market" not in contents
    assert "Example Documentary Lab 2026" in contents


def test_orchestration_step_discovery_refresh_auto_scope_skips_watchlist_on_core_weeks(
    tmp_path,
):
    source_dir = tmp_path / "data" / "sources"
    source_dir.mkdir(parents=True)
    (source_dir / "mixed.yaml").write_text(
        dedent(
            """
            - id: "11111111-1111-4111-8111-111111111111"
              organization: "Core Labs"
              program_name: "Open Calls"
              source_url: "https://example.com/core"
              source_type: "lab"
              deadline_categories: ["lab_application"]
              regions: ["Global"]
              cadence: "annual"
              coverage_priority: "must_have"
              discovery_strategy: "official_program_page"
            - id: "22222222-2222-4222-8222-222222222222"
              organization: "Watchlist Media"
              program_name: "Corporate Watchlist"
              source_url: "https://example.com/watchlist"
              source_type: "other"
              deadline_categories: ["other"]
              regions: ["Global"]
              cadence: "unknown"
              coverage_priority: "watchlist"
              discovery_strategy: "manual_watch"
            """
        ).strip(),
        encoding="utf-8",
    )
    (tmp_path / "data" / "deadlines").mkdir(parents=True)
    fetched_urls = []

    def fake_fetch_url(url: str):
        fetched_urls.append(url)
        return (
            200,
            "text/html",
            "<html><body><p>Core Labs Open Call Deadline: June 1, 2026</p></body></html>",
        )

    def fake_calendar_generator(*, root_dir=None, deadline_files=None, current_date=None):
        output_path = tmp_path / "build" / "calendar.html"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text("<html></html>", encoding="utf-8")
        return output_path

    payload = orchestration_step_discovery_refresh(
        root_dir=tmp_path,
        current_date=date(2026, 4, 27),
        mode="dry-run",
        llm_mode="off",
        source_scope="auto",
        fetch_url=fake_fetch_url,
        calendar_generator=fake_calendar_generator,
    )

    assert payload["source_scope_effective"] == "core"
    assert payload["selected_source_count"] == 1
    assert payload["total_source_count"] == 2
    assert fetched_urls == ["https://example.com/core"]


def test_orchestration_step_discovery_refresh_merges_deterministic_and_llm_candidates(
    tmp_path,
    monkeypatch,
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

    def fake_calendar_generator(*, root_dir=None, deadline_files=None, current_date=None):
        output_path = tmp_path / "build" / "calendar.html"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text("<html></html>", encoding="utf-8")
        return output_path

    def fake_discover(agent_input, *, client=None, max_attempts=3):
        return DiscoveryCandidateBatch(
            source_id=str(agent_input.source_entry.id),
            source_url=agent_input.source_entry.source_url,
            organization=agent_input.source_entry.organization,
            program_name=agent_input.source_entry.program_name,
            candidates=[
                DiscoveryCandidate(
                    id="11111111-1111-4111-8111-111111111111",
                    source_id=agent_input.source_entry.id,
                    source_url=agent_input.source_entry.source_url,
                    organization=agent_input.source_entry.organization,
                    name="Example Documentary Lab 2026",
                    category="lab_application",
                    candidate_type="new_opportunity",
                    confidence=0.95,
                    rationale="LLM found the same opportunity but missed the precise date.",
                    detected_deadline_text=None,
                    detected_early_deadline_text=None,
                    detected_event_date_text=None,
                    eligibility_notes=None,
                    regions=["Global"],
                    tags=["llm_reviewed"],
                    raw_excerpt="Example Documentary Lab 2026 applications are open.",
                )
            ],
            notes="LLM returned a partial candidate.",
        )

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

    assert payload["llm_batches_used"] == 1
    assert payload["promoted_new_count"] == 1
    assert payload["rejected_uncertain_count"] == 0


def test_orchestration_step_discovery_refresh_rewrites_generic_candidate_titles(
    tmp_path,
    monkeypatch,
):
    _write_source_registry(tmp_path)
    (tmp_path / "data" / "deadlines").mkdir(parents=True)

    def fake_fetch_url(url: str):
        return (
            200,
            "text/html",
            "<html><body><p>Example Labs Open Calls applications are open "
            "Deadline: June 1, 2026</p></body></html>",
        )

    def fake_calendar_generator(*, root_dir=None, deadline_files=None, current_date=None):
        output_path = tmp_path / "build" / "calendar.html"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text("<html></html>", encoding="utf-8")
        return output_path

    def fake_discover(agent_input, *, client=None, max_attempts=3):
        return DiscoveryCandidateBatch(
            source_id=str(agent_input.source_entry.id),
            source_url=agent_input.source_entry.source_url,
            organization=agent_input.source_entry.organization,
            program_name=agent_input.source_entry.program_name,
            candidates=[
                DiscoveryCandidate(
                    id="22222222-2222-4222-8222-222222222222",
                    source_id=agent_input.source_entry.id,
                    source_url=agent_input.source_entry.source_url,
                    organization=agent_input.source_entry.organization,
                    name="Dates.",
                    category="lab_application",
                    candidate_type="new_opportunity",
                    confidence=0.88,
                    rationale="LLM found a future-dated opportunity.",
                    detected_deadline_text="June 1, 2026",
                    detected_early_deadline_text=None,
                    detected_event_date_text=None,
                    eligibility_notes=None,
                    regions=["Global"],
                    tags=["llm_reviewed"],
                    raw_excerpt=(
                        "Applications open now\n"
                        "Deadline: June 1, 2026"
                    ),
                )
            ],
            notes="LLM returned a generic page label as the candidate name.",
        )

    monkeypatch.setattr(
        "media_calendar.orchestration.discovery_refresh_step.discover_source_candidates",
        fake_discover,
    )

    orchestration_step_discovery_refresh(
        root_dir=tmp_path,
        current_date=date(2026, 4, 21),
        mode="apply",
        llm_mode="auto",
        llm_client=object(),
        fetch_url=fake_fetch_url,
        calendar_generator=fake_calendar_generator,
    )

    written_file = tmp_path / "data" / "deadlines" / "2026.yaml"
    contents = written_file.read_text(encoding="utf-8")
    assert "Dates." not in contents
    assert "Example Labs - Open Calls" in contents
