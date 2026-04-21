from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest

from media_calendar.agents import discover_source_candidates
from media_calendar.agents.source_discovery_agent import SourceDiscoveryAgentError
from media_calendar.models import (
    DiscoveryAgentInput,
    DiscoveryCandidate,
    SourceRegistryEntry,
    SourceSnapshotResult,
)


class FakeChatCompletionsAPI:
    def __init__(self, payloads):
        self.payloads = payloads
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        payload = self.payloads[len(self.calls) - 1]
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=payload))]
        )


class FakeClient:
    def __init__(self, payloads):
        self.chat = SimpleNamespace(completions=FakeChatCompletionsAPI(payloads))


def build_agent_input(*, extracted_text="Applications open now\nDeadline: June 1, 2026"):
    source_entry = SourceRegistryEntry(
        id=uuid4(),
        organization="Example Lab",
        program_name="Open Calls",
        source_url="https://example.com/open-calls",
        source_type="lab",
        deadline_categories=["lab_application"],
        regions=["Global"],
        cadence="annual",
        coverage_priority="must_have",
        discovery_strategy="official_program_page",
    )
    snapshot_result = SourceSnapshotResult(
        source_id=source_entry.id,
        organization=source_entry.organization,
        program_name=source_entry.program_name,
        source_url=source_entry.source_url,
        status="success",
        fetched_at=datetime(2026, 4, 21, 12, 0, tzinfo=timezone.utc),
        http_status=200,
        content_type="text/html",
        snapshot_path="/tmp/source.html",
        text_path="/tmp/source.txt",
        extracted_text=extracted_text,
    )
    deterministic_candidate = DiscoveryCandidate(
        id=uuid4(),
        source_id=source_entry.id,
        source_url=source_entry.source_url,
        organization=source_entry.organization,
        name="Example Lab Open Call",
        category="lab_application",
        candidate_type="new_opportunity",
        confidence=0.8,
        rationale="Deterministic detection found an open call and a deadline.",
        detected_deadline_text="June 1, 2026",
        regions=["Global"],
        tags=["lab", "must_have"],
        raw_excerpt="Applications open now Deadline: June 1, 2026",
    )
    return DiscoveryAgentInput(
        source_entry=source_entry,
        snapshot_result=snapshot_result,
        deterministic_candidates=[deterministic_candidate],
    )


def test_discover_source_candidates_returns_validated_output():
    agent_input = build_agent_input()
    client = FakeClient(
        [
            (
                '{"source_id":"%s","source_url":"https://example.com/open-calls",'
                '"organization":"Example Lab","program_name":"Open Calls","candidates":['
                '{"id":"%s","source_id":"%s","source_url":"https://example.com/open-calls",'
                '"organization":"Example Lab","name":"Example Lab Open Call 2026",'
                '"category":"lab_application","candidate_type":"new_opportunity",'
                '"confidence":0.91,"rationale":"The source page clearly lists an open call.",'
                '"detected_deadline_text":"June 1, 2026","detected_early_deadline_text":null,'
                '"detected_event_date_text":null,"eligibility_notes":null,'
                '"regions":["Global"],"tags":["lab_application","llm_reviewed"],'
                '"raw_excerpt":"Applications open now Deadline: June 1, 2026"}],'
                '"notes":"LLM reviewed the cleaned source text."}'
            )
            % (agent_input.source_entry.id, uuid4(), agent_input.source_entry.id)
        ]
    )

    result = discover_source_candidates(agent_input, client=client)

    assert result.organization == "Example Lab"
    assert len(result.candidates) == 1
    assert result.candidates[0].confidence == 0.91
    assert client.chat.completions.calls[0]["model"] == "gpt-4o-mini"


def test_discover_source_candidates_retries_after_validation_failure():
    agent_input = build_agent_input()
    client = FakeClient(
        [
            '{"source_id":"broken"}',
            (
                '{"source_id":"%s","source_url":"https://example.com/open-calls",'
                '"organization":"Example Lab","program_name":"Open Calls",'
                '"candidates":[],"notes":"Corrected after retry."}'
            )
            % agent_input.source_entry.id
        ]
    )

    result = discover_source_candidates(agent_input, client=client)

    assert result.notes == "Corrected after retry."
    assert len(client.chat.completions.calls) == 2
    retry_messages = client.chat.completions.calls[1]["messages"]
    assert retry_messages[-1]["role"] == "user"
    assert "could not be validated" in retry_messages[-1]["content"]


def test_discover_source_candidates_raises_after_exhausting_retries():
    agent_input = build_agent_input()
    client = FakeClient(["{}", "{}", "{}"])

    with pytest.raises(SourceDiscoveryAgentError):
        discover_source_candidates(agent_input, client=client)


def test_discover_source_candidates_skips_empty_text_without_llm_call():
    agent_input = build_agent_input(extracted_text="")
    client = FakeClient([])

    result = discover_source_candidates(agent_input, client=client)

    assert result.candidates == []
    assert "extracted source text was empty" in (result.notes or "")
    assert client.chat.completions.calls == []
