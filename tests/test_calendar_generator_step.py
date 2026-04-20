from __future__ import annotations

import logging
from pathlib import Path

import pytest

from media_calendar.orchestration import orchestration_step_calendar_generator


def test_orchestration_step_calendar_generator_returns_ci_payload(tmp_path):
    data_dir = tmp_path / "data" / "deadlines"
    data_dir.mkdir(parents=True)
    first = data_dir / "2026.yaml"
    second = data_dir / "2027.yaml"
    first.write_text("", encoding="utf-8")
    second.write_text("", encoding="utf-8")
    output_path = tmp_path / "build" / "calendar.html"
    output_path.parent.mkdir(parents=True)
    output_path.write_text("<html></html>", encoding="utf-8")

    def fake_generator(*, deadline_files=None, root_dir=None):
        assert deadline_files is None
        assert root_dir == tmp_path
        return output_path

    payload = orchestration_step_calendar_generator(
        root_dir=tmp_path,
        generator=fake_generator,
    )

    assert payload["step_name"] == "Generate Calendar"
    assert payload["agent_name"] == "calendar_generator"
    assert payload["input_source"] == "data/deadlines/*.yaml files."
    assert payload["output_destination"] == "build/calendar.html."
    assert payload["condition"] == "Triggered on every push to main branch via GitHub Actions CI."
    assert payload["html_exists"] is True
    assert payload["requires_human_review"] is True
    assert payload["input_files"] == [str(first), str(second)]


def test_orchestration_step_calendar_generator_accepts_explicit_input_files(tmp_path):
    data_dir = tmp_path / "data" / "deadlines"
    data_dir.mkdir(parents=True)
    explicit = data_dir / "2025.yaml"
    explicit.write_text("", encoding="utf-8")
    output_path = tmp_path / "build" / "calendar.html"
    output_path.parent.mkdir(parents=True)
    output_path.write_text("<html></html>", encoding="utf-8")

    def fake_generator(*, deadline_files=None, root_dir=None):
        assert deadline_files == ["data/deadlines/2025.yaml"]
        return output_path

    payload = orchestration_step_calendar_generator(
        ["data/deadlines/2025.yaml"],
        root_dir=tmp_path,
        generator=fake_generator,
    )

    assert payload["input_files"] == [str(explicit)]
    assert payload["output_path"] == str(output_path)


def test_orchestration_step_calendar_generator_writes_report(tmp_path):
    output_path = tmp_path / "build" / "calendar.html"
    output_path.parent.mkdir(parents=True)
    output_path.write_text("<html></html>", encoding="utf-8")
    written = []

    def fake_generator(*, deadline_files=None, root_dir=None):
        return output_path

    payload = orchestration_step_calendar_generator(
        root_dir=tmp_path,
        generator=fake_generator,
        report_writer=written.append,
    )

    assert written == [payload]


def test_orchestration_step_calendar_generator_raises_on_generator_error(tmp_path, caplog):
    def fake_generator(*, deadline_files=None, root_dir=None):
        raise RuntimeError("generation failed")

    with caplog.at_level(logging.ERROR):
        with pytest.raises(RuntimeError, match="generation failed"):
            orchestration_step_calendar_generator(
                root_dir=tmp_path,
                generator=fake_generator,
            )

    assert "calendar_generator failed" in caplog.text
