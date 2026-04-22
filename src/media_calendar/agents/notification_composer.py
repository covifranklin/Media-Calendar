"""Notification composer agent implementation."""

from __future__ import annotations

from typing import Any

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
- For weekly digests, group opportunities by category using clear section
  headings so the reader can scan the full landscape quickly.

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
        response = active_client.chat.completions.create(
            model=MODEL_NAME,
            messages=messages,
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
    notification_type = (
        agent_input.deadlines[0].notification_type
        if agent_input.deadlines
        else "weekly_digest"
    )
    extra_instruction = ""
    if notification_type == "weekly_digest":
        extra_instruction = (
            "For this weekly digest, break the email into category sections "
            "with headings and keep each section easy to scan.\n"
        )
    return (
        "Generate email content for the following notification request.\n"
        "Use the structured data to decide the right tone and urgency.\n\n"
        f"{extra_instruction}"
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
        raise NotificationComposerError(
            "The 'openai' package is required to run notification_composer."
        ) from exc

    return OpenAI()
