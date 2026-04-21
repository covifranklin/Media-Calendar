"""Automated discovery refresh orchestration step."""

from __future__ import annotations

import json
import logging
import os
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Callable, Iterable, List, Literal, Optional

from media_calendar.agents import discover_source_candidates
from media_calendar.components import (
    auto_promote_discovery_results,
    build_source_freshness_report,
    compare_candidate_batch,
    detect_candidate_batches,
    filter_upcoming_deadlines,
    fetch_sources,
    generate_calendar,
    load_deadlines,
    load_source_registry,
    resolve_deadline_files,
    resolve_source_files,
    snapshot_fetch_results,
    write_deadlines,
    write_source_freshness_report,
)
from media_calendar.models import DiscoveryAgentInput, DiscoveryDecisionLogEntry

STEP_NAME = "Refresh Discovery Pipeline"
AGENT_NAME = "source_discovery_pipeline"
DESCRIPTION = (
    "Fetches monitored official sources, detects opportunity candidates, "
    "compares them to the deadline database, auto-promotes only high-confidence "
    "results, optionally writes updated YAML, and regenerates the static "
    "calendar."
)
INPUT_SOURCE = "data/sources/*.yaml registry files plus data/deadlines/*.yaml."
OUTPUT_DESTINATION = (
    "build/discovery-refresh.json, build/discovery-metrics.json, "
    "build/source-freshness.json, build/calendar.html, and optionally updated "
    "data/deadlines/*.yaml files."
)
CONDITION = "Triggered weekly by scheduler or manually via CLI."
ERROR_HANDLING = (
    "Fetch failures are skipped, LLM discovery falls back to deterministic "
    "detection unless required, uncertain candidates are rejected, and dry-run "
    "mode avoids deadline YAML writes."
)

FetchUrl = Callable[[str], tuple[int, Optional[str], str]]
CalendarGenerator = Callable[..., Path]
ReportWriter = Callable[[dict], None]
LlmMode = Literal["auto", "off", "required"]
RefreshMode = Literal["dry-run", "apply"]


def orchestration_step_discovery_refresh(
    source_files: Iterable[str | Path] | None = None,
    deadline_files: Iterable[str | Path] | None = None,
    *,
    root_dir: str | Path | None = None,
    current_date: date | None = None,
    mode: RefreshMode = "dry-run",
    llm_mode: LlmMode = "auto",
    llm_client=None,
    fetch_url: FetchUrl | None = None,
    calendar_generator: CalendarGenerator = generate_calendar,
    report_writer: ReportWriter | None = None,
    logger: logging.Logger | None = None,
) -> dict:
    """Run the fully automated discovery refresh pipeline."""

    active_logger = logger or logging.getLogger(__name__)
    root = Path(root_dir) if root_dir is not None else Path.cwd()
    active_date = current_date or date.today()
    source_paths = resolve_source_files(source_files, root=root)
    deadline_paths = resolve_deadline_files(deadline_files, root=root)
    source_entries = load_source_registry(source_paths)
    deadlines = load_deadlines(deadline_paths)

    fetch_results = fetch_sources(source_entries, fetch_url=fetch_url)
    snapshot_results = snapshot_fetch_results(fetch_results, root_dir=root)
    deterministic_batches = detect_candidate_batches(snapshot_results, source_entries)

    current_deadlines = list(deadlines)
    all_decisions = []
    batch_summaries = []
    freshness_batches = []
    llm_batches_used = 0
    deterministic_fallback_batches = 0

    llm_enabled = _resolve_llm_enabled(
        llm_mode,
        llm_client=llm_client,
    )

    for source_entry, snapshot_result, deterministic_batch in zip(
        source_entries,
        snapshot_results,
        deterministic_batches,
    ):
        effective_batch = deterministic_batch
        batch_mode = "deterministic"

        if llm_enabled:
            try:
                effective_batch = discover_source_candidates(
                    DiscoveryAgentInput(
                        source_entry=source_entry,
                        snapshot_result=snapshot_result,
                        deterministic_candidates=deterministic_batch.candidates,
                    ),
                    client=llm_client,
                )
                batch_mode = "llm"
                llm_batches_used += 1
            except Exception:
                if llm_mode == "required":
                    active_logger.exception(
                        "source_discovery_agent failed for source_id=%s",
                        source_entry.id,
                    )
                    raise

                active_logger.exception(
                    "source_discovery_agent failed for source_id=%s; "
                    "falling back to deterministic detection",
                    source_entry.id,
                )
                deterministic_fallback_batches += 1

        comparison_batch = compare_candidate_batch(effective_batch, current_deadlines)
        freshness_batches.append(effective_batch)
        promotion_batch = auto_promote_discovery_results(
            comparison_batch.results,
            current_deadlines,
            current_date=active_date,
        )
        current_deadlines = promotion_batch.deadline_snapshot
        all_decisions.extend(promotion_batch.decisions)

        batch_summary = {
            "source_id": str(source_entry.id),
            "source_url": source_entry.source_url,
            "organization": source_entry.organization,
            "program_name": source_entry.program_name,
            "fetch_status": snapshot_result.status,
            "candidate_batch_mode": batch_mode,
            "candidate_count": len(effective_batch.candidates),
            "promoted_new_count": promotion_batch.promoted_new_count,
            "promoted_update_count": promotion_batch.promoted_update_count,
            "ignored_duplicate_count": promotion_batch.ignored_duplicate_count,
            "rejected_uncertain_count": promotion_batch.rejected_uncertain_count,
            "notes": effective_batch.notes,
        }
        batch_summaries.append(batch_summary)

    current_deadlines = filter_upcoming_deadlines(
        current_deadlines,
        current_date=active_date,
    )

    if mode == "apply":
        written_deadline_files = write_deadlines(current_deadlines, root=root)
    else:
        written_deadline_files = []

    freshness_report = build_source_freshness_report(
        source_entries,
        snapshot_results,
        freshness_batches,
    )
    freshness_paths = write_source_freshness_report(
        freshness_report,
        root_dir=root,
    )
    calendar_path = calendar_generator(
        root_dir=root,
        current_date=active_date,
    )
    promoted_new_count = sum(
        1 for decision in all_decisions if decision.action == "promoted_new"
    )
    promoted_update_count = sum(
        1 for decision in all_decisions if decision.action == "promoted_update"
    )
    ignored_duplicate_count = sum(
        1 for decision in all_decisions if decision.action == "ignored_duplicate"
    )
    rejected_uncertain_count = sum(
        1 for decision in all_decisions if decision.action == "rejected_uncertain"
    )
    report_paths = _write_refresh_reports(
        root=root,
        current_date=active_date,
        decisions=all_decisions,
        batch_summaries=batch_summaries,
        mode=mode,
        written_deadline_files=written_deadline_files,
        calendar_path=calendar_path,
        llm_mode=llm_mode,
        llm_enabled=llm_enabled,
    )
    metrics_paths = _write_metrics_reports(
        root=root,
        current_date=active_date,
        mode=mode,
        batch_summaries=batch_summaries,
        llm_mode=llm_mode,
        llm_enabled=llm_enabled,
        promoted_new_count=promoted_new_count,
        promoted_update_count=promoted_update_count,
        ignored_duplicate_count=ignored_duplicate_count,
        rejected_uncertain_count=rejected_uncertain_count,
    )
    log_path = _append_decision_log(
        root=root,
        decisions=all_decisions,
    )

    payload = {
        "step_name": STEP_NAME,
        "agent_name": AGENT_NAME,
        "description": DESCRIPTION,
        "input_source": INPUT_SOURCE,
        "output_destination": OUTPUT_DESTINATION,
        "condition": CONDITION,
        "error_handling": ERROR_HANDLING,
        "current_date": active_date.isoformat(),
        "mode": mode,
        "applied_changes": mode == "apply",
        "source_files": [str(path) for path in source_paths],
        "deadline_files": [str(path) for path in written_deadline_files],
        "calendar_path": str(calendar_path),
        "report_json_path": str(report_paths["json"]),
        "report_markdown_path": str(report_paths["markdown"]),
        "metrics_json_path": str(metrics_paths["json"]),
        "metrics_markdown_path": str(metrics_paths["markdown"]),
        "freshness_report_json_path": str(freshness_paths["json"]),
        "freshness_report_markdown_path": str(freshness_paths["markdown"]),
        "decision_log_path": str(log_path),
        "llm_mode": llm_mode,
        "llm_enabled": llm_enabled,
        "llm_batches_used": llm_batches_used,
        "deterministic_fallback_batches": deterministic_fallback_batches,
        "promoted_new_count": promoted_new_count,
        "promoted_update_count": promoted_update_count,
        "ignored_duplicate_count": ignored_duplicate_count,
        "rejected_uncertain_count": rejected_uncertain_count,
        "decision_count": len(all_decisions),
        "batch_summaries": batch_summaries,
    }

    if report_writer is not None:
        report_writer(payload)

    return payload


def _write_metrics_reports(
    *,
    root: Path,
    current_date: date,
    mode: RefreshMode,
    batch_summaries: List[dict],
    llm_mode: str,
    llm_enabled: bool,
    promoted_new_count: int,
    promoted_update_count: int,
    ignored_duplicate_count: int,
    rejected_uncertain_count: int,
) -> dict:
    build_dir = root / "build"
    build_dir.mkdir(parents=True, exist_ok=True)

    json_path = build_dir / "discovery-metrics.json"
    markdown_path = build_dir / "discovery-metrics.md"
    total_candidates = sum(batch["candidate_count"] for batch in batch_summaries)
    total_processed = (
        promoted_new_count
        + promoted_update_count
        + ignored_duplicate_count
        + rejected_uncertain_count
    )
    acceptance_rate = (
        (promoted_new_count + promoted_update_count) / total_processed
        if total_processed
        else 0.0
    )
    metrics_payload = {
        "generated_on": current_date.isoformat(),
        "mode": mode,
        "llm_mode": llm_mode,
        "llm_enabled": llm_enabled,
        "candidate_count": total_candidates,
        "promoted_new_count": promoted_new_count,
        "promoted_update_count": promoted_update_count,
        "ignored_duplicate_count": ignored_duplicate_count,
        "rejected_uncertain_count": rejected_uncertain_count,
        "acceptance_rate": acceptance_rate,
        "batches_by_source": batch_summaries,
    }
    json_path.write_text(json.dumps(metrics_payload, indent=2), encoding="utf-8")
    markdown_path.write_text(
        _build_metrics_markdown(metrics_payload),
        encoding="utf-8",
    )
    return {"json": json_path, "markdown": markdown_path}


def _resolve_llm_enabled(llm_mode: LlmMode, *, llm_client) -> bool:
    if llm_mode == "off":
        return False
    if llm_client is not None:
        return True

    has_api_key = bool(os.environ.get("OPENAI_API_KEY"))
    if llm_mode == "required" and not has_api_key:
        raise RuntimeError(
            "llm_mode='required' needs either an injected llm_client or "
            "OPENAI_API_KEY in the environment."
        )
    return has_api_key


def _write_refresh_reports(
    *,
    root: Path,
    current_date: date,
    decisions,
    batch_summaries: List[dict],
    mode: RefreshMode,
    written_deadline_files: List[Path],
    calendar_path: Path,
    llm_mode: str,
    llm_enabled: bool,
) -> dict:
    build_dir = root / "build"
    build_dir.mkdir(parents=True, exist_ok=True)

    json_path = build_dir / "discovery-refresh.json"
    markdown_path = build_dir / "discovery-refresh.md"

    report_payload = {
        "generated_on": current_date.isoformat(),
        "mode": mode,
        "applied_changes": mode == "apply",
        "llm_mode": llm_mode,
        "llm_enabled": llm_enabled,
        "written_deadline_files": [str(path) for path in written_deadline_files],
        "calendar_path": str(calendar_path),
        "batch_summaries": batch_summaries,
        "decisions": [decision.model_dump(mode="json") for decision in decisions],
    }
    json_path.write_text(json.dumps(report_payload, indent=2), encoding="utf-8")

    markdown_path.write_text(
        _build_markdown_report(
            current_date=current_date,
            decisions=decisions,
            batch_summaries=batch_summaries,
            mode=mode,
            written_deadline_files=written_deadline_files,
            calendar_path=calendar_path,
            llm_mode=llm_mode,
            llm_enabled=llm_enabled,
        ),
        encoding="utf-8",
    )

    return {"json": json_path, "markdown": markdown_path}


def _append_decision_log(
    *,
    root: Path,
    decisions,
) -> Path:
    build_dir = root / "build"
    build_dir.mkdir(parents=True, exist_ok=True)
    log_path = build_dir / "discovery-log.jsonl"
    timestamp = datetime.now(timezone.utc)

    with log_path.open("a", encoding="utf-8") as handle:
        for decision in decisions:
            comparison = decision.comparison
            entry = DiscoveryDecisionLogEntry(
                timestamp=timestamp,
                source_id=comparison.candidate.source_id,
                candidate_id=comparison.candidate.id,
                comparison_classification=comparison.classification,
                promotion_action=decision.action,
                match_score=comparison.match_score,
                rationale=decision.rationale,
                affected_deadline_id=decision.target_deadline_id,
            )
            handle.write(entry.model_dump_json())
            handle.write("\n")

    return log_path


def _build_markdown_report(
    *,
    current_date: date,
    decisions,
    batch_summaries: List[dict],
    mode: RefreshMode,
    written_deadline_files: List[Path],
    calendar_path: Path,
    llm_mode: str,
    llm_enabled: bool,
) -> str:
    promoted_new = sum(1 for decision in decisions if decision.action == "promoted_new")
    promoted_update = sum(
        1 for decision in decisions if decision.action == "promoted_update"
    )
    ignored_duplicate = sum(
        1 for decision in decisions if decision.action == "ignored_duplicate"
    )
    rejected_uncertain = sum(
        1 for decision in decisions if decision.action == "rejected_uncertain"
    )

    parts = [
        "# Discovery Refresh Report",
        "",
        f"Generated on {current_date.isoformat()}",
        "",
        f"- Refresh mode: `{mode}`",
        f"- Applied deadline changes: `{mode == 'apply'}`",
        f"- LLM mode: `{llm_mode}`",
        f"- LLM enabled: `{llm_enabled}`",
        f"- Promoted new: `{promoted_new}`",
        f"- Promoted updates: `{promoted_update}`",
        f"- Ignored duplicates: `{ignored_duplicate}`",
        f"- Rejected uncertain: `{rejected_uncertain}`",
        f"- Calendar path: `{calendar_path}`",
        "- Deadline files:",
    ]

    if written_deadline_files:
        parts.extend(f"  - `{path}`" for path in written_deadline_files)
    else:
        parts.append("  - None")

    parts.extend(["", "## Source Batches", ""])
    for batch in batch_summaries:
        parts.extend(
            [
                f"### {batch['organization']} - {batch['program_name']}",
                f"- Fetch status: `{batch['fetch_status']}`",
                f"- Candidate batch mode: `{batch['candidate_batch_mode']}`",
                f"- Candidate count: `{batch['candidate_count']}`",
                f"- Promoted new: `{batch['promoted_new_count']}`",
                f"- Promoted updates: `{batch['promoted_update_count']}`",
                f"- Ignored duplicates: `{batch['ignored_duplicate_count']}`",
                f"- Rejected uncertain: `{batch['rejected_uncertain_count']}`",
                f"- Notes: {batch['notes'] or 'None'}",
                "",
            ]
        )

    parts.extend(["## Decisions", ""])
    if not decisions:
        parts.append("- No promotion decisions were generated.")
        return "\n".join(parts)

    for decision in decisions:
        comparison = decision.comparison
        parts.extend(
            [
                f"### {comparison.candidate.name}",
                f"- Action: `{decision.action}`",
                f"- Classification: `{comparison.classification}`",
                f"- Match score: `{comparison.match_score}`",
                f"- Source URL: {comparison.candidate.source_url}",
                f"- Rationale: {decision.rationale}",
                "",
            ]
        )

    return "\n".join(parts)


def _build_metrics_markdown(metrics_payload: dict) -> str:
    parts = [
        "# Discovery Metrics Report",
        "",
        f"- Generated on: `{metrics_payload['generated_on']}`",
        f"- Refresh mode: `{metrics_payload['mode']}`",
        f"- LLM mode: `{metrics_payload['llm_mode']}`",
        f"- LLM enabled: `{metrics_payload['llm_enabled']}`",
        f"- Candidate count: `{metrics_payload['candidate_count']}`",
        f"- Promoted new: `{metrics_payload['promoted_new_count']}`",
        f"- Promoted updates: `{metrics_payload['promoted_update_count']}`",
        f"- Ignored duplicates: `{metrics_payload['ignored_duplicate_count']}`",
        f"- Rejected uncertain: `{metrics_payload['rejected_uncertain_count']}`",
        f"- Acceptance rate: `{metrics_payload['acceptance_rate']:.2f}`",
        "",
        "## Source Batches",
        "",
    ]

    for batch in metrics_payload["batches_by_source"]:
        parts.extend(
            [
                f"### {batch['organization']} - {batch['program_name']}",
                f"- Fetch status: `{batch['fetch_status']}`",
                f"- Candidate batch mode: `{batch['candidate_batch_mode']}`",
                f"- Candidate count: `{batch['candidate_count']}`",
                f"- Promoted new: `{batch['promoted_new_count']}`",
                f"- Promoted updates: `{batch['promoted_update_count']}`",
                f"- Ignored duplicates: `{batch['ignored_duplicate_count']}`",
                f"- Rejected uncertain: `{batch['rejected_uncertain_count']}`",
                "",
            ]
        )

    return "\n".join(parts)
