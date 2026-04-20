from datetime import date
from uuid import uuid4

from media_calendar.models import DataCurationAgentInput


def test_data_curation_agent_input_model_accepts_deadline_and_context():
    agent_input = DataCurationAgentInput(
        current_deadline={
            "id": uuid4(),
            "name": "Grant Round",
            "category": "funding_round",
            "organization": "Example Fund",
            "url": "https://example.com/grant",
            "deadline_date": date(2026, 8, 15),
            "description": "Funding application deadline.",
            "notification_windows": [30, 14, 3],
            "status": "confirmed",
            "last_verified_date": date(2026, 4, 20),
            "source_url": "https://example.com/source",
            "tags": ["funding", "documentary"],
            "year": 2026,
        },
        scraped_page_text="Applications close on August 15, 2026.",
        current_date=date(2026, 4, 20),
        target_year=2026,
    )

    assert agent_input.current_deadline.name == "Grant Round"
    assert agent_input.scraped_page_text == "Applications close on August 15, 2026."
    assert agent_input.current_date == date(2026, 4, 20)
    assert agent_input.target_year == 2026
