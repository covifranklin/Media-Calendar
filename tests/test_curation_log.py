from datetime import datetime, timezone
from uuid import uuid4

from media_calendar.models import CurationLog


def test_curation_log_model_accepts_required_fields_and_optional_defaults():
    curation_log = CurationLog(
        id=uuid4(),
        deadline_id=uuid4(),
        action="updated",
        curator="curation_agent",
        reviewed_by_human=False,
        timestamp=datetime(2026, 4, 20, 18, 45, tzinfo=timezone.utc),
    )

    assert curation_log.changed_fields is None
    assert curation_log.action == "updated"
    assert curation_log.curator == "curation_agent"
    assert curation_log.reviewed_by_human is False
