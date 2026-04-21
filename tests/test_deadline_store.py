from __future__ import annotations

from datetime import date
from uuid import uuid4

from media_calendar.components import load_deadlines, write_deadlines
from media_calendar.models import Deadline


def build_deadline(*, name: str, year: int, deadline_date: date) -> Deadline:
    return Deadline(
        id=uuid4(),
        name=name,
        category="industry_forum",
        organization="Example Org",
        url="https://example.com/opportunity",
        deadline_date=deadline_date,
        description="Tracked opportunity.",
        notification_windows=[30, 14, 3],
        status="confirmed",
        last_verified_date=date(2026, 4, 21),
        source_url="https://example.com/source",
        tags=["forum"],
        year=year,
    )


def test_write_deadlines_round_trips_year_grouped_yaml(tmp_path):
    deadlines = [
        build_deadline(
            name="Example Market 2027",
            year=2027,
            deadline_date=date(2027, 2, 1),
        ),
        build_deadline(
            name="Example Forum 2026",
            year=2026,
            deadline_date=date(2026, 5, 10),
        ),
    ]

    written_paths = write_deadlines(deadlines, root=tmp_path)
    reloaded = load_deadlines(written_paths)

    assert [path.name for path in written_paths] == ["2026.yaml", "2027.yaml"]
    assert [deadline.name for deadline in reloaded] == [
        "Example Forum 2026",
        "Example Market 2027",
    ]
