"""LLM-assisted source discovery agent implementation."""

from __future__ import annotations

import json
from typing import Any

from pydantic import ValidationError

from media_calendar.models import DiscoveryAgentInput, DiscoveryCandidateBatch

MODEL_NAME = "gpt-4o-mini"
MAX_VALIDATION_ATTEMPTS = 3
MAX_EXTRACTED_TEXT_CHARS = 12000

SYSTEM_PROMPT = """
You are the source_discovery_agent for a media industry opportunity system.

Your job is to review cleaned source-page text and identify likely film or TV
industry opportunities that should be tracked. You are helping with discovery,
not with final approval, so you should be useful and cautious.

You may use deterministic candidates as hints, but you should improve or expand
them when the source text clearly supports doing so. Avoid obvious duplicates.

Return only valid JSON matching this schema exactly:
{
  "source_id": string,
  "source_url": string,
  "organization": string,
  "program_name": string,
  "candidates": [
    {
      "id": string,
      "source_id": string,
      "source_url": string,
      "organization": string,
      "name": string,
      "category": "festival_submission" | "funding_round" | "lab_application" | "fellowship" | "industry_forum" | "other",
      "candidate_type": "new_opportunity" | "update_signal" | "duplicate_signal",
      "confidence": number,
      "rationale": string,
      "detected_deadline_text": string | null,
      "detected_early_deadline_text": string | null,
      "detected_event_date_text": string | null,
      "eligibility_notes": string | null,
      "regions": string[],
      "tags": string[],
      "raw_excerpt": string
    }
  ],
  "notes": string | null
}

Do not wrap the JSON in markdown fences.
Candidate names must be intuitive human-facing opportunity titles, not page chrome
or navigation labels. Avoid generic names like "Home", "Dates", "Applications",
"Register", or "Overview". If the page text is ambiguous, prefer a title derived
from the organization/program context over a generic label.
""".strip()


class SourceDiscoveryAgentError(RuntimeError):
    """Raised when the source discovery agent cannot produce valid output."""


def discover_source_candidates(
    agent_input: DiscoveryAgentInput,
    *,
    client: Any | None = None,
    max_attempts: int = MAX_VALIDATION_ATTEMPTS,
) -> DiscoveryCandidateBatch:
    """Discover likely opportunity candidates from a cleaned source snapshot."""

    extracted_text = (agent_input.snapshot_result.extracted_text or "").strip()
    if agent_input.snapshot_result.status != "success":
        return _build_skipped_output(
            agent_input,
            "LLM discovery skipped because the source fetch was not successful.",
        )
    if not extracted_text:
        return _build_skipped_output(
            agent_input,
            "LLM discovery skipped because the extracted source text was empty.",
        )

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
            return DiscoveryCandidateBatch.model_validate_json(content)
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
                        f"DiscoveryCandidateBatch. Return corrected JSON only. "
                        f"Validation issue: {exc}"
                    ),
                }
            )

    raise SourceDiscoveryAgentError(
        "source_discovery_agent failed to produce valid DiscoveryCandidateBatch"
    ) from last_error


def _build_user_prompt(agent_input: DiscoveryAgentInput) -> str:
    """Serialize a token-efficient discovery request for the LLM."""

    payload = {
        "source_entry": agent_input.source_entry.model_dump(mode="json"),
        "snapshot_result": {
            "source_id": str(agent_input.snapshot_result.source_id),
            "organization": agent_input.snapshot_result.organization,
            "program_name": agent_input.snapshot_result.program_name,
            "source_url": agent_input.snapshot_result.source_url,
            "status": agent_input.snapshot_result.status,
            "http_status": agent_input.snapshot_result.http_status,
            "content_type": agent_input.snapshot_result.content_type,
            "extracted_text": (
                agent_input.snapshot_result.extracted_text or ""
            )[:MAX_EXTRACTED_TEXT_CHARS],
        },
        "deterministic_candidates": [
            candidate.model_dump(mode="json")
            for candidate in agent_input.deterministic_candidates
        ],
    }
    serialized_input = json.dumps(payload, indent=2)
    return (
        "Review the cleaned source text and identify likely film/TV opportunity "
        "candidates that should be tracked.\n"
        "Use deterministic candidates as hints, but improve them when the source "
        "text clearly supports a stronger result.\n"
        "Return intuitive opportunity names, not breadcrumb labels or generic page "
        "headings.\n\n"
        f"{serialized_input}"
    )


def _build_skipped_output(
    agent_input: DiscoveryAgentInput,
    notes: str,
) -> DiscoveryCandidateBatch:
    return DiscoveryCandidateBatch(
        source_id=str(agent_input.source_entry.id),
        source_url=agent_input.source_entry.source_url,
        organization=agent_input.source_entry.organization,
        program_name=agent_input.source_entry.program_name,
        candidates=[],
        notes=notes,
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
        raise SourceDiscoveryAgentError(
            "The 'openai' package is required to run source_discovery_agent."
        ) from exc

    return OpenAI()
