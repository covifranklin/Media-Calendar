from __future__ import annotations

from datetime import date
from types import SimpleNamespace
from uuid import uuid4

from media_calendar.agents import curate_deadline_data
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


def test_dates_changed_clear():
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
    assert result.confidence == 0.93
    assert result.requires_human_review is True
    assert client.responses.calls[0]["model"] == "gpt-4o-mini"


def test_no_change():
    client = FakeClient(
        [
            (
                '{"status":"no_change","proposed_updates":null,"confidence":0.97,'
                '"reasoning":"The scraped text matches the existing deadline and event details.",'
                '"requires_human_review":false}'
            )
        ]
    )

    result = curate_deadline_data(build_agent_input(), client=client)

    assert result.status == "no_change"
    assert result.proposed_updates is None
    assert result.requires_human_review is False
    assert result.confidence == 0.97


def test_page_not_found_empty_text():
    agent_input = build_agent_input()
    agent_input = agent_input.model_copy(update={"scraped_page_text": ""})
    client = FakeClient(
        [
            (
                '{"status":"page_not_found","proposed_updates":null,"confidence":0.99,'
                '"reasoning":"No scraped text was provided, which suggests the page could not be loaded.",'
                '"requires_human_review":true}'
            )
        ]
    )

    result = curate_deadline_data(agent_input, client=client)

    assert result.status == "page_not_found"
    assert result.proposed_updates is None
    assert result.requires_human_review is True


def test_ambiguous_dates():
    client = FakeClient(
        [
            (
                '{"status":"ambiguous","proposed_updates":{"deadline_date":"June 2026"},'
                '"confidence":0.41,"reasoning":"The scraped text mentions June but does not provide a clear day.",'
                '"requires_human_review":true}'
            )
        ]
    )

    result = curate_deadline_data(build_agent_input(), client=client)

    assert result.status == "ambiguous"
    assert result.proposed_updates == {"deadline_date": "June 2026"}
    assert result.requires_human_review is True


def test_low_confidence_trigger_review():
    client = FakeClient(
        [
            '{"status":"ambiguous","confidence":0.2}',
            (
                '{"status":"dates_changed","proposed_updates":{"deadline_date":"2026-06-22"},'
                '"confidence":0.2,"reasoning":"A possible new date appears in the text, but the extraction is uncertain.",'
                '"requires_human_review":true}'
            ),
        ]
    )

    result = curate_deadline_data(build_agent_input(), client=client)

    assert result.status == "dates_changed"
    assert result.confidence == 0.2
    assert result.requires_human_review is True
    assert len(client.responses.calls) == 2
    retry_messages = client.responses.calls[1]["input"]
    assert retry_messages[-1]["role"] == "user"
    assert "could not be validated" in retry_messages[-1]["content"]
