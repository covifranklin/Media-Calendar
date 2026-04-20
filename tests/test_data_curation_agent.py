from __future__ import annotations

from datetime import date
from types import SimpleNamespace
from uuid import uuid4

import pytest

from media_calendar.agents import curate_deadline_data
from media_calendar.agents.data_curation_agent import DataCurationAgentError
from media_calendar.models import DataCurationAgentInput


class FakeResponsesAPI:
    def __init__(self, payloads):
        self.payloads = payloads
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        payload = self.payloads[len(self.calls) - 1]
        return SimpleNamespace(output_text=payload)


class FakeClient:
    def __init__(self, payloads):
        self.responses = FakeResponsesAPI(payloads)


def build_agent_input() -> DataCurationAgentInput:
    return DataCurationAgentInput(
        current_deadline={
            "id": uuid4(),
            "name": "Documentary Lab",
            "category": "lab_application",
            "organization": "Example Institute",
            "url": "https://example.com/lab",
            "deadline_date": date(2026, 6, 15),
            "description": "Applications for the annual documentary lab.",
            "notification_windows": [30, 14, 3],
            "status": "confirmed",
            "last_verified_date": date(2026, 4, 20),
            "source_url": "https://example.com/source",
            "tags": ["lab", "documentary"],
            "year": 2026,
        },
        scraped_page_text="Applications close June 22, 2026. Notification in July.",
        current_date=date(2026, 4, 20),
        target_year=2026,
    )


def test_curate_deadline_data_returns_validated_output():
    client = FakeClient(
        [
            (
                '{"status":"dates_changed","proposed_updates":{"deadline_date":"2026-06-22"},'
                '"confidence":0.93,"reasoning":"The scraped text lists June 22, 2026.",'
                '"requires_human_review":true}'
            )
        ]
    )

    result = curate_deadline_data(build_agent_input(), client=client)

    assert result.status == "dates_changed"
    assert result.proposed_updates == {"deadline_date": "2026-06-22"}
    assert client.responses.calls[0]["model"] == "gpt-4o-mini"


def test_curate_deadline_data_retries_after_validation_failure():
    client = FakeClient(
        [
            '{"status":"ambiguous","confidence":0.4}',
            (
                '{"status":"ambiguous","proposed_updates":null,"confidence":0.4,'
                '"reasoning":"The scraped text does not clearly identify the target year.",'
                '"requires_human_review":true}'
            ),
        ]
    )

    result = curate_deadline_data(build_agent_input(), client=client)

    assert result.status == "ambiguous"
    assert len(client.responses.calls) == 2
    retry_messages = client.responses.calls[1]["input"]
    assert retry_messages[-1]["role"] == "user"
    assert "could not be validated" in retry_messages[-1]["content"]


def test_curate_deadline_data_raises_after_exhausting_retries():
    client = FakeClient(["{}", "{}", "{}"])

    with pytest.raises(DataCurationAgentError):
        curate_deadline_data(build_agent_input(), client=client)
