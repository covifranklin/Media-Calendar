from datetime import date
from textwrap import dedent

import pytest
import yaml

from media_calendar.components import generate_calendar


def _write_deadline_yaml(tmp_path, filename, contents):
    data_dir = tmp_path / "data" / "deadlines"
    data_dir.mkdir(parents=True, exist_ok=True)
    yaml_path = data_dir / filename
    yaml_path.write_text(dedent(contents).strip(), encoding="utf-8")
    return yaml_path


def test_basic_html_output(tmp_path):
    _write_deadline_yaml(
        tmp_path,
        "2026.yaml",
        """
        - id: "123e4567-e89b-12d3-a456-426614174000"
          name: "Example Fellowship"
          category: "fellowship"
          organization: "Example Arts"
          url: "https://example.com/fellowship"
          deadline_date: 2026-07-15
          early_deadline_date:
          event_start_date:
          event_end_date:
          description: "Annual fellowship for emerging creators."
          eligibility_notes:
          notification_windows: [30, 14, 3]
          status: "confirmed"
          last_verified_date: 2026-04-20
          source_url: "https://example.com/source"
          tags: ["artists"]
          year: 2026
        """,
    )

    output_path = generate_calendar(
        root_dir=tmp_path,
        current_date=date(2026, 1, 1),
    )

    assert output_path == tmp_path / "build" / "calendar.html"
    assert (tmp_path / "build" / "index.html").read_text(encoding="utf-8") == (
        output_path.read_text(encoding="utf-8")
    )
    html = output_path.read_text(encoding="utf-8")
    assert "<!DOCTYPE html>" in html
    assert "Media Calendar" in html
    assert 'id="category-filter"' in html
    assert 'id="month-filter"' in html
    assert "Example Fellowship" in html
    assert "Showing <strong>1</strong> deadlines." in html


def test_filtering_by_category(tmp_path):
    _write_deadline_yaml(
        tmp_path,
        "2026.yaml",
        """
        - id: "123e4567-e89b-12d3-a456-426614174000"
          name: "Example Fellowship"
          category: "fellowship"
          organization: "Example Arts"
          url: "https://example.com/fellowship"
          deadline_date: 2026-07-15
          early_deadline_date:
          event_start_date:
          event_end_date:
          description: "Annual fellowship for emerging creators."
          eligibility_notes:
          notification_windows: [30, 14, 3]
          status: "confirmed"
          last_verified_date: 2026-04-20
          source_url: "https://example.com/source"
          tags: ["artists"]
          year: 2026
        - id: "223e4567-e89b-12d3-a456-426614174000"
          name: "Industry Forum"
          category: "industry_forum"
          organization: "Film Week"
          url: "https://example.com/forum"
          deadline_date: 2026-10-05
          early_deadline_date:
          event_start_date:
          event_end_date:
          description: "Forum registration deadline."
          eligibility_notes:
          notification_windows: [30, 14]
          status: "tentative"
          last_verified_date: 2026-04-20
          source_url: "https://example.com/forum-source"
          tags: ["networking"]
          year: 2026
        """,
    )

    html = generate_calendar(
        root_dir=tmp_path,
        current_date=date(2026, 1, 1),
    ).read_text(encoding="utf-8")

    assert '<option value="fellowship">Fellowship</option>' in html
    assert '<option value="industry_forum">Industry Forum</option>' in html
    assert 'data-category="fellowship"' in html
    assert 'data-category="industry_forum"' in html
    assert "categoryFilter" in html


def test_filtering_by_month(tmp_path):
    _write_deadline_yaml(
        tmp_path,
        "2026.yaml",
        """
        - id: "123e4567-e89b-12d3-a456-426614174000"
          name: "Spring Lab"
          category: "lab_application"
          organization: "Doc Lab"
          url: "https://example.com/lab"
          deadline_date: 2026-03-10
          early_deadline_date:
          event_start_date:
          event_end_date:
          description: "Applications close in March."
          eligibility_notes:
          notification_windows: [30, 14, 3]
          status: "confirmed"
          last_verified_date: 2026-01-15
          source_url: "https://example.com/lab-source"
          tags: ["lab"]
          year: 2026
        """,
    )

    html = generate_calendar(
        root_dir=tmp_path,
        current_date=date(2026, 1, 1),
    ).read_text(encoding="utf-8")

    assert '<option value="3">March</option>' in html
    assert 'data-month="3"' in html
    assert "monthFilter" in html


def test_empty_yaml_input(tmp_path):
    _write_deadline_yaml(tmp_path, "2026.yaml", "")

    html = generate_calendar(
        root_dir=tmp_path,
        current_date=date(2026, 1, 1),
    ).read_text(encoding="utf-8")

    assert "No deadlines were found in the provided YAML files." in html
    assert "Showing <strong>0</strong> deadlines." in html


def test_malformed_yaml_input(tmp_path):
    _write_deadline_yaml(
        tmp_path,
        "2026.yaml",
        """
        deadlines:
          - id: "123e4567-e89b-12d3-a456-426614174000"
            name: "Broken Entry"
            category: "fellowship"
            deadline_date: [2026-07-15
        """,
    )

    with pytest.raises(yaml.YAMLError):
        generate_calendar(
            root_dir=tmp_path,
            current_date=date(2026, 1, 1),
        )


def test_past_deadlines_are_excluded_from_calendar(tmp_path):
    _write_deadline_yaml(
        tmp_path,
        "2026.yaml",
        """
        - id: "123e4567-e89b-12d3-a456-426614174000"
          name: "Past Opportunity"
          category: "funding_round"
          organization: "Example Arts"
          url: "https://example.com/past"
          deadline_date: 2026-03-01
          early_deadline_date:
          event_start_date:
          event_end_date:
          description: "Already closed."
          eligibility_notes:
          notification_windows: [30, 14, 3]
          status: "confirmed"
          last_verified_date: 2026-02-15
          source_url: "https://example.com/past-source"
          tags: ["fund"]
          year: 2026
        - id: "223e4567-e89b-12d3-a456-426614174000"
          name: "Upcoming Opportunity"
          category: "funding_round"
          organization: "Example Arts"
          url: "https://example.com/upcoming"
          deadline_date: 2026-06-15
          early_deadline_date:
          event_start_date:
          event_end_date:
          description: "Still open."
          eligibility_notes:
          notification_windows: [30, 14, 3]
          status: "confirmed"
          last_verified_date: 2026-04-10
          source_url: "https://example.com/upcoming-source"
          tags: ["fund"]
          year: 2026
        """,
    )

    html = generate_calendar(
        root_dir=tmp_path,
        current_date=date(2026, 4, 21),
    ).read_text(encoding="utf-8")

    assert "Past Opportunity" not in html
    assert "Upcoming Opportunity" in html
    assert "Showing <strong>1</strong> deadlines." in html
