"""Notification composer agent implementation."""

from __future__ import annotations

from typing import Any, List

from pydantic import ValidationError

from media_calendar.models import (
    NotificationComposerInput,
    NotificationComposerOutput,
)

MODEL_NAME = "gpt-4o-mini"
MAX_VALIDATION_ATTEMPTS = 3

SYSTEM_PROMPT = """
You are the notification_composer agent for a media industry deadline system.

Your job is to compose clear, actionable email notifications and weekly digest
summaries from structured deadline data. Adapt tone to urgency:
- 30-day reminders should feel informative and calm.
- 14-day reminders should feel more pointed and practical.
- 3-day reminders should feel urgent and action-oriented.
- Weekly digests should be concise, scannable, and useful.
- Annual refresh reminders should focus on verification and upkeep.

Return only valid JSON matching this schema exactly:
{
  "subject_line": string,
  "html_body": string,
  "plain_text_body": string,
  "priority_level": "normal" | "high"
}

Do not wrap the JSON in markdown fences.
""".strip()


class NotificationComposerError(RuntimeError):
    """Raised when the notification composer cannot produce valid output."""


def compose_notification(
    agent_input: NotificationComposerInput,
    *,
    client: Any | None = None,
    max_attempts: int = MAX_VALIDATION_ATTEMPTS,
) -> NotificationComposerOutput:
    """Compose notification email content from structured deadline data."""

    active_client = client or _build_openai_client()
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": _build_user_prompt(agent_input)},
    ]

    last_error: Exception | None = None

    for attempt in range(max_attempts):
        response = active_client.responses.create(
            model=MODEL_NAME,
            input=messages,
        )

        try:
            content = _extract_response_text(response)
            return NotificationComposerOutput.model_validate_json(content)
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
                        f"NotificationComposerOutput. Return corrected JSON only. "
                        f"Validation issue: {exc}"
                    ),
                }
            )

    raise NotificationComposerError(
        "notification_composer failed to produce valid NotificationComposerOutput"
    ) from last_error


def _build_user_prompt(agent_input: NotificationComposerInput) -> str:
    """Serialize the agent input for the LLM user message."""

    serialized_input = agent_input.model_dump_json(indent=2)
    return (
        "Generate email content for the following notification request.\n"
        "Use the structured data to decide the right tone and urgency.\n\n"
        f"{serialized_input}"
    )


def _extract_response_text(response: Any, *, default: str | None = None) -> str:
    """Extract text content from an OpenAI Responses API object."""

    output_text = getattr(response, "output_text", None)
    if isinstance(output_text, str) and output_text.strip():
        return output_text

    output = getattr(response, "output", None)
    if isinstance(output, list):
        parts: List[str] = []
        for item in output:
            contents = getattr(item, "content", None)
            if not isinstance(contents, list):
                continue
            for content_item in contents:
                text = getattr(content_item, "text", None)
                if isinstance(text, str) and text:
                    parts.append(text)
        if parts:
            return "".join(parts)

    if default is not None:
        return default

    raise ValueError("No text content found in model response")


def _build_openai_client() -> Any:
    """Create an OpenAI client lazily so tests do not require the dependency."""

    try:
        from openai import OpenAI
    except ImportError as exc:
        raise NotificationComposerError(
            "The 'openai' package is required to run notification_composer."
        ) from exc

    return OpenAI()
