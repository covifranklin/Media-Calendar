from __future__ import annotations

from search_discover import main


def test_search_discover_cli_writes_report_paths(tmp_path, monkeypatch, capsys):
    captured_call = {}

    def fake_open_web_discovery(
        source_files=None,
        deadline_files=None,
        *,
        root_dir=None,
        current_date=None,
        max_results_per_query=3,
        max_results_total=12,
        **kwargs,
    ):
        captured_call["root_dir"] = root_dir
        captured_call["current_date"] = current_date
        captured_call["max_results_per_query"] = max_results_per_query
        captured_call["max_results_total"] = max_results_total
        return {
            "query_count": 10,
            "search_result_count": 4,
            "classification_counts": {
                "likely_new": 2,
                "likely_update": 1,
                "likely_duplicate": 1,
                "ambiguous": 0,
            },
            "report_json_path": str(tmp_path / "build" / "open-web-discovery.json"),
            "report_markdown_path": str(tmp_path / "build" / "open-web-discovery.md"),
        }

    monkeypatch.setattr(
        "media_calendar.orchestration.orchestration_step_open_web_discovery",
        fake_open_web_discovery,
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "sys.argv",
        [
            "search_discover.py",
            "--root-dir",
            str(tmp_path),
            "--max-results-per-query",
            "2",
            "--max-results-total",
            "6",
        ],
    )

    exit_code = main()
    captured = capsys.readouterr()

    assert exit_code == 0
    assert captured_call["max_results_per_query"] == 2
    assert captured_call["max_results_total"] == 6
    assert "Open-web query count: 10" in captured.out
    assert "Search results reviewed: 4" in captured.out
