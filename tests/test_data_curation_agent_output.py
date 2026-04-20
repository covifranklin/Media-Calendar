from media_calendar.models import DataCurationAgentOutput


def test_data_curation_agent_output_model_accepts_required_fields_and_optional_defaults():
    agent_output = DataCurationAgentOutput(
        status="dates_changed",
        confidence=0.91,
        reasoning="The scraped page lists a different deadline date than the current record.",
        requires_human_review=True,
    )

    assert agent_output.proposed_updates is None
    assert agent_output.status == "dates_changed"
    assert agent_output.confidence == 0.91
    assert agent_output.requires_human_review is True
