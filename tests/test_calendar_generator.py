from pathlib import Path

from media_calendar.components import generate_calendar


def test_generate_calendar_reads_yaml_and_writes_build_html(tmp_path):
    data_dir = tmp_path / "data" / "deadlines"
    data_dir.mkdir(parents=True)
    yaml_path = data_dir / "2026.yaml"
    yaml_path.write_text(
        """
- id: "123e4567-e89b-12d3-a456-426614174000"
  name: "Example Fellowship"
  category: "fellowship"
  organization: "Example Arts"
  url: "https://example.com/fellowship"
  deadline_date: 2026-07-15
  early_deadline_date:
  event_start_date: 2026-09-01
  event_end_date: 2026-09-10
  description: "Annual fellowship for emerging creators."
  eligibility_notes: "Open to first- and second-time applicants."
  notification_windows: [30, 14, 3]
  status: "confirmed"
  last_verified_date: 2026-04-20
  source_url: "https://example.com/source"
  tags: ["artists", "development"]
  year: 2026
- id: "223e4567-e89b-12d3-a456-426614174000"
  name: "Industry Forum"
  category: "industry_forum"
  organization: "Film Week"
  url: "https://example.com/forum"
  deadline_date: 2026-10-05
  early_deadline_date: 2026-09-10
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
""".strip(),
        encoding="utf-8",
    )

    output_path = generate_calendar(root_dir=tmp_path)

    assert output_path == tmp_path / "build" / "calendar.html"
    assert output_path.exists()

    html = output_path.read_text(encoding="utf-8")
    assert "Media Calendar" in html
    assert 'id="category-filter"' in html
    assert 'id="month-filter"' in html
    assert "Example Fellowship" in html
    assert "Industry Forum" in html
    assert 'data-category="fellowship"' in html
    assert 'data-month="7"' in html
    assert "Showing <strong>2</strong> deadlines." in html


def test_generate_calendar_accepts_explicit_yaml_paths(tmp_path):
    data_dir = tmp_path / "data" / "deadlines"
    data_dir.mkdir(parents=True)
    yaml_path = data_dir / "2027.yaml"
    yaml_path.write_text(
        """
deadlines:
  - id: "323e4567-e89b-12d3-a456-426614174000"
    name: "Lab Application"
    category: "lab_application"
    organization: "Doc Lab"
    url: "https://example.com/lab"
    deadline_date: 2027-03-10
    early_deadline_date:
    event_start_date:
    event_end_date:
    description: "Applications close in March."
    eligibility_notes:
    notification_windows: [30, 14, 3]
    status: "confirmed"
    last_verified_date: 2027-01-15
    source_url: "https://example.com/lab-source"
    tags: ["lab"]
    year: 2027
""".strip(),
        encoding="utf-8",
    )

    output_path = generate_calendar(["data/deadlines/2027.yaml"], root_dir=tmp_path)

    html = output_path.read_text(encoding="utf-8")
    assert "Lab Application" in html
    assert "March" in html
