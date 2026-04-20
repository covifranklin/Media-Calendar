"""Data curation orchestration step."""

from __future__ import annotations

import json
import logging
from datetime import date
from typing import Callable, List, Sequence

from media_calendar.agents import curate_deadline_data
from media_calendar.agents.data_curation_agent import DataCurationAgentError
from media_calendar.models import DataCurationAgentInput, DataCurationAgentOutput, Deadline

STEP_NAME = "Cure Deadlines"
AGENT_NAME = "data_curation_agent"
DESCRIPTION = (
    "Iterates through existing deadlines, fetches source URLs, and uses the "
    "curation agent to identify potential updates for human review."
)
INPUT_SOURCE = "Existing deadline records (YAML), scraped web page text."
OUTPUT_DESTINATION = "Curation report (Markdown/JSONL) for human review."
CONDITION = "Triggered annually via CLI `python curate.py --year 2025`."
ERROR_HANDLING = (
    "Gracefully handles page_not_found, flags all agent outputs for human review."
)

ScrapePage = Callable[[str], str]
ReportWriter = Callable[[dict], None]


def orchestration_step_data_curation(
    deadlines: Sequence[Deadline],
    *,
    scrape_page: ScrapePage,
    target_year: int,
    current_date: date,
    client=None,
    report_writer: ReportWriter | None = None,
    logger: logging.Logger | None = None,
) -> List[dict]:
    """Run annual curation over existing deadline records."""

    active_logger = logger or logging.getLogger(__name__)
    report: List[dict] = []

    for deadline in deadlines:
        scraped_page_text = _fetch_scraped_text(
            deadline.source_url,
            scrape_page=scrape_page,
            logger=active_logger,
        )
        agent_input = DataCurationAgentInput(
            current_deadline=deadline,
            scraped_page_text=scraped_page_text,
            current_date=current_date,
            target_year=target_year,
        )

        try:
            output = curate_deadline_data(agent_input, client=client)
        except DataCurationAgentError:
            active_logger.exception(
                "data_curation_agent failed for deadline_id=%s", deadline.id
            )
            output = _build_fallback_output(scraped_page_text)

        report_item = _build_report_item(deadline, output)
        report.append(report_item)

        if report_writer is not None:
            report_writer(report_item)

    return report


def _fetch_scraped_text(
    source_url: str,
    *,
    scrape_page: ScrapePage,
    logger: logging.Logger,
) -> str:
    try:
        return scrape_page(source_url)
    except Exception:
        logger.exception("failed to fetch source_url=%s", source_url)
        return ""


def _build_fallback_output(scraped_page_text: str) -> DataCurationAgentOutput:
    if not scraped_page_text:
        return DataCurationAgentOutput(
            status="page_not_found",
            proposed_updates=None,
            confidence=0.0,
            reasoning="Source page could not be fetched for automated review.",
            requires_human_review=True,
        )

    return DataCurationAgentOutput(
        status="ambiguous",
        proposed_updates=None,
        confidence=0.0,
        reasoning="Agent output could not be validated; manual review is required.",
        requires_human_review=True,
    )


def _build_report_item(deadline: Deadline, output: DataCurationAgentOutput) -> dict:
    forced_review_output = output.model_copy(update={"requires_human_review": True})
    base_payload = {
        "step_name": STEP_NAME,
        "agent_name": AGENT_NAME,
        "description": DESCRIPTION,
        "input_source": INPUT_SOURCE,
        "output_destination": OUTPUT_DESTINATION,
        "condition": CONDITION,
        "error_handling": ERROR_HANDLING,
        "deadline_id": str(deadline.id),
        "deadline_name": deadline.name,
        "source_url": deadline.source_url,
        "status": forced_review_output.status,
        "requires_human_review": True,
        "curation_result": forced_review_output.model_dump(),
    }

    base_payload["jsonl"] = json.dumps(base_payload["curation_result"], sort_keys=True)
    base_payload["markdown"] = _build_markdown(deadline, forced_review_output)
    return base_payload


def _build_markdown(
    deadline: Deadline,
    output: DataCurationAgentOutput,
) -> str:
    updates = output.proposed_updates or {}
    if updates:
        update_lines = "\n".join(
            f"- `{key}`: `{value}`" for key, value in sorted(updates.items())
        )
    else:
        update_lines = "- None"

    return (
        f"## {deadline.name}\n"
        f"- Deadline ID: `{deadline.id}`\n"
        f"- Source URL: {deadline.source_url}\n"
        f"- Status: `{output.status}`\n"
        f"- Confidence: `{output.confidence}`\n"
        "- Requires Human Review: `True`\n"
        f"- Reasoning: {output.reasoning}\n"
        "- Proposed Updates:\n"
        f"{update_lines}"
    )
