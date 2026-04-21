from __future__ import annotations

from textwrap import dedent

from coverage_report import main


def _write_source_yaml(tmp_path, filename: str, contents: str):
    data_dir = tmp_path / "data" / "sources"
    data_dir.mkdir(parents=True, exist_ok=True)
    path = data_dir / filename
    path.write_text(dedent(contents).strip(), encoding="utf-8")
    return path


def test_coverage_report_cli_writes_default_reports(tmp_path, monkeypatch, capsys):
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
          regions: ["Global"]
          cadence: "annual"
          coverage_priority: "must_have"
          discovery_strategy: "official_program_page"
        """,
    )

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "sys.argv",
        ["coverage_report.py", "--root-dir", str(tmp_path)],
    )

    exit_code = main()
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Wrote JSON report:" in captured.out
    assert (tmp_path / "build" / "coverage-report.json").exists()
    assert (tmp_path / "build" / "coverage-report.md").exists()


def test_coverage_report_cli_accepts_explicit_inputs(tmp_path, monkeypatch):
    source_file = _write_source_yaml(
        tmp_path,
        "regional.yaml",
        """
        - id: "11111111-1111-4111-8111-111111111111"
          organization: "Example Market"
          program_name: "Forum"
          source_url: "https://example.com/forum"
          source_type: "market"
          deadline_categories: ["industry_forum"]
          regions: ["Europe"]
          cadence: "annual"
          coverage_priority: "high"
          discovery_strategy: "official_program_page"
        """,
    )

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "sys.argv",
        [
            "coverage_report.py",
            "--root-dir",
            str(tmp_path),
            "--input",
            f"data/sources/{source_file.name}",
        ],
    )

    exit_code = main()

    assert exit_code == 0
    assert (tmp_path / "build" / "coverage-report.json").exists()
