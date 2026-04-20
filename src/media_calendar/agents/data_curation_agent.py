"""Data curation agent implementation."""

from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from media_calendar.models import (
    DataCurationAgentInput,
    DataCurationAgentOutput,
)

MODEL_NAME = "gpt-4o-mini"
MAX_VALIDATION_ATTEMPTS = 3

SYSTEM_PROMPT = """
You are the data_curation_agent for a media industry deadline system.

Your job is to assist annual data refreshes by comparing an existing deadline
record against scraped source page text. You should identify likely changes,
summarize what you found, and produce a structured diff report for human review.
You must not autonomously update any database or pretend changes are confirmed.

Use the scraped text and current record to determine whether:
- there is no meaningful change
- dates or key fields appear to have changed
- the page content suggests the source is missing or unavailable
- the situation is ambiguous and requires human review

Return only valid JSON matching this schema exactly:
{
  "status": "no_change" | "dates_changed" | "page_not_found" | "ambiguous",
  "proposed_updates": object | null,
  "confidence": number,
  "reasoning": string,
  "requires_human_review": boolean
}

Do not wrap the JSON in markdown fences.
""".strip()


class DataCurationAgentError(RuntimeError):
    """Raised when the data curation agent cannot produce valid output."""


def curate_deadline_data(
    agent_input: DataCurationAgentInput,
    *,
    client: Any | None = None,
    max_attempts: int = MAX_VALIDATION_ATTEMPTS,
) -> DataCurationAgentOutput:
    """Compare deadline data against scraped source text."""

    active_client = client or _build_openai_client()
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": _build_user_prompt(agent_input)},
    ]

    last_error: Exception | None = None

    for attempt in range(max_attempts):
        response = active_client.chat.completions.create(
            model=MODEL_NAME,
            messages=messages,
        )

        try:
            content = _extract_response_text(response)
            return DataCurationAgentOutput.model_validate_json(content)
        except (ValidationError, ValueError, TypeError) as exc:
            last_error = exc
            if attempt == max_attempts - 1:
                break

            messages.append(
                {
                    "role": "assistant",
                    "content": _extract_response_text(response, default=""),
                }
            )
            messages.append(
                {
                    "role": "user",
                    "content": (
                        "Your previous response could not be validated as "
                        f"DataCurationAgentOutput. Return corrected JSON only. "
                        f"Validation issue: {exc}"
                    ),
                }
            )

    raise DataCurationAgentError(
        "data_curation_agent failed to produce valid DataCurationAgentOutput"
    ) from last_error


def _build_user_prompt(agent_input: DataCurationAgentInput) -> str:
    """Serialize the agent input for the LLM user message."""

    serialized_input = agent_input.model_dump_json(indent=2)
    return (
        "Compare the existing deadline record against the scraped source text.\n"
        "Produce a structured report for human review, not an automatic update.\n\n"
        f"{serialized_input}"
    )


def _extract_response_text(response: Any, *, default: str | None = None) -> str:
    """Extract text content from an OpenAI Chat Completions response."""

    choices = getattr(response, "choices", None)
    if isinstance(choices, list) and choices:
        message = getattr(choices[0], "message", None)
        content = getattr(message, "content", None)
        if isinstance(content, str) and content.strip():
            return content

    if default is not None:
        return default

    raise ValueError("No text content found in model response")


def _build_openai_client() -> Any:
    """Create an OpenAI client lazily so tests do not require the dependency."""

    try:
        from openai import OpenAI
    except ImportError as exc:
        raise DataCurationAgentError(
            "The 'openai' package is required to run data_curation_agent."
        ) from exc

    return OpenAI()
