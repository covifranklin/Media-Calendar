from __future__ import annotations

import logging
from datetime import date
from uuid import uuid4

from media_calendar.agents.data_curation_agent import DataCurationAgentError
from media_calendar.models import DataCurationAgentOutput, Deadline
from media_calendar.orchestration import orchestration_step_data_curation


def build_deadline() -> Deadline:
    return Deadline(
        id=uuid4(),
        name="Example Fellowship",
        category="fellowship",
        organization="Example Arts",
        url="https://example.com/deadline",
        deadline_date=date(2026, 7, 15),
        description="Annual fellowship deadline.",
        notification_windows=[30, 14, 3],
        status="confirmed",
        last_verified_date=date(2026, 4, 20),
        source_url="https://example.com/source",
        tags=["artists"],
        year=2026,
    )


def test_orchestration_step_data_curation_generates_report_item(monkeypatch):
    def fake_scrape_page(url: str) -> str:
        return "Applications close July 22, 2026."

    def fake_curate(agent_input, *, client=None, max_attempts=3):
        return DataCurationAgentOutput(
            status="dates_changed",
            proposed_updates={"deadline_date": "2026-07-22"},
            confidence=0.92,
            reasoning="A new date appears clearly on the source page.",
            requires_human_review=False,
        )

    monkeypatch.setattr(
        "media_calendar.orchestration.data_curation_step.curate_deadline_data",
        fake_curate,
    )

    report = orchestration_step_data_curation(
        [build_deadline()],
        scrape_page=fake_scrape_page,
        target_year=2026,
        current_date=date(2026, 4, 20),
    )

    assert len(report) == 1
    assert report[0]["step_name"] == "Cure Deadlines"
    assert report[0]["agent_name"] == "data_curation_agent"
    assert report[0]["status"] == "dates_changed"
    assert report[0]["requires_human_review"] is True
    assert '"deadline_date": "2026-07-22"' in report[0]["jsonl"]
    assert "## Example Fellowship" in report[0]["markdown"]


def test_orchestration_step_data_curation_handles_page_not_found(monkeypatch, caplog):
    def fake_scrape_page(url: str) -> str:
        raise RuntimeError("page missing")

    def fake_curate(agent_input, *, client=None, max_attempts=3):
        return DataCurationAgentOutput(
            status="page_not_found",
            proposed_updates=None,
            confidence=0.99,
            reasoning="No source text was available.",
            requires_human_review=False,
        )

    monkeypatch.setattr(
        "media_calendar.orchestration.data_curation_step.curate_deadline_data",
        fake_curate,
    )

    with caplog.at_level(logging.ERROR):
        report = orchestration_step_data_curation(
            [build_deadline()],
            scrape_page=fake_scrape_page,
            target_year=2026,
            current_date=date(2026, 4, 20),
        )

    assert len(report) == 1
    assert report[0]["status"] == "page_not_found"
    assert report[0]["requires_human_review"] is True
    assert "failed to fetch source_url=" in caplog.text


def test_orchestration_step_data_curation_falls_back_on_agent_failure(
    monkeypatch, caplog
):
    def fake_scrape_page(url: str) -> str:
        return "Some unclear content"

    def fake_curate(agent_input, *, client=None, max_attempts=3):
        raise DataCurationAgentError("invalid output")

    monkeypatch.setattr(
        "media_calendar.orchestration.data_curation_step.curate_deadline_data",
        fake_curate,
    )

    with caplog.at_level(logging.ERROR):
        report = orchestration_step_data_curation(
            [build_deadline()],
            scrape_page=fake_scrape_page,
            target_year=2026,
            current_date=date(2026, 4, 20),
        )

    assert len(report) == 1
    assert report[0]["status"] == "ambiguous"
    assert report[0]["requires_human_review"] is True
    assert "data_curation_agent failed" in caplog.text


def test_orchestration_step_data_curation_writes_report(monkeypatch):
    written = []

    def fake_scrape_page(url: str) -> str:
        return "Applications close July 22, 2026."

    def fake_curate(agent_input, *, client=None, max_attempts=3):
        return DataCurationAgentOutput(
            status="no_change",
            proposed_updates=None,
            confidence=0.88,
            reasoning="The source matches the existing record.",
            requires_human_review=False,
        )

    monkeypatch.setattr(
        "media_calendar.orchestration.data_curation_step.curate_deadline_data",
        fake_curate,
    )

    report = orchestration_step_data_curation(
        [build_deadline()],
        scrape_page=fake_scrape_page,
        target_year=2026,
        current_date=date(2026, 4, 20),
        report_writer=written.append,
    )

    assert len(report) == 1
    assert written == report
