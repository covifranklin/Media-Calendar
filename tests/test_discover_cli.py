from __future__ import annotations

from discover import main


def test_discover_cli_defaults_to_dry_run(tmp_path, monkeypatch, capsys):
    captured_call = {}

    def fake_refresh(
        source_files=None,
        deadline_files=None,
        *,
        root_dir=None,
        current_date=None,
        mode="dry-run",
        llm_mode="auto",
        **kwargs,
    ):
        captured_call["root_dir"] = root_dir
        captured_call["current_date"] = current_date
        captured_call["mode"] = mode
        captured_call["llm_mode"] = llm_mode
        return {
            "mode": mode,
            "deadline_files": [],
            "calendar_path": str(tmp_path / "build" / "calendar.html"),
            "report_json_path": str(tmp_path / "build" / "discovery-refresh.json"),
            "report_markdown_path": str(tmp_path / "build" / "discovery-refresh.md"),
            "promoted_new_count": 0,
            "promoted_update_count": 0,
            "ignored_duplicate_count": 0,
            "rejected_uncertain_count": 0,
        }

    monkeypatch.setattr(
        "media_calendar.orchestration.orchestration_step_discovery_refresh",
        fake_refresh,
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("sys.argv", ["discover.py", "--root-dir", str(tmp_path)])

    exit_code = main()
    captured = capsys.readouterr()

    assert exit_code == 0
    assert captured_call["mode"] == "dry-run"
    assert captured_call["llm_mode"] == "auto"
    assert "Refresh mode: dry-run" in captured.out
    assert "Updated deadline files: None" in captured.out


def test_discover_cli_accepts_apply_mode(tmp_path, monkeypatch):
    captured_call = {}

    def fake_refresh(
        source_files=None,
        deadline_files=None,
        *,
        root_dir=None,
        current_date=None,
        mode="dry-run",
        llm_mode="auto",
        **kwargs,
    ):
        captured_call["mode"] = mode
        captured_call["llm_mode"] = llm_mode
        return {
            "mode": mode,
            "deadline_files": [str(tmp_path / "data" / "deadlines" / "2026.yaml")],
            "calendar_path": str(tmp_path / "build" / "calendar.html"),
            "report_json_path": str(tmp_path / "build" / "discovery-refresh.json"),
            "report_markdown_path": str(tmp_path / "build" / "discovery-refresh.md"),
            "promoted_new_count": 1,
            "promoted_update_count": 0,
            "ignored_duplicate_count": 0,
            "rejected_uncertain_count": 0,
        }

    monkeypatch.setattr(
        "media_calendar.orchestration.orchestration_step_discovery_refresh",
        fake_refresh,
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "sys.argv",
        [
            "discover.py",
            "--root-dir",
            str(tmp_path),
            "--mode",
            "apply",
            "--llm-mode",
            "off",
        ],
    )

    exit_code = main()

    assert exit_code == 0
    assert captured_call["mode"] == "apply"
    assert captured_call["llm_mode"] == "off"
