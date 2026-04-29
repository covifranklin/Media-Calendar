"""CLI entry point for composing and sending deadline notifications."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
SRC_PATH = PROJECT_ROOT / "src"


def _ensure_src_path() -> None:
    if str(SRC_PATH) not in sys.path:
        sys.path.insert(0, str(SRC_PATH))


def _resolve_current_date(
    current_date_override: str | None,
    *,
    use_latest_monday: bool = False,
    today: date | None = None,
) -> date:
    if current_date_override:
        return date.fromisoformat(current_date_override)

    resolved_today = today or date.today()
    if use_latest_monday:
        return resolved_today - timedelta(days=resolved_today.weekday())
    return resolved_today


def main() -> int:
    _ensure_src_path()
    from media_calendar.components.deadline_store import (
        load_deadlines,
        resolve_deadline_files,
    )
    from media_calendar.orchestration import (
        orchestration_step_notification_composer,
    )
    from media_calendar.services import (
        dispatch_notification_queue,
        group_upcoming_notifications,
        load_dotenv_file,
        load_resend_settings,
    )

    parser = argparse.ArgumentParser(
        description="Compose and optionally send upcoming deadline notifications."
    )
    parser.add_argument(
        "--root-dir",
        type=Path,
        default=Path.cwd(),
        help="Project root containing data/deadlines/ and build/.",
    )
    parser.add_argument(
        "--input",
        action="append",
        dest="inputs",
        help="Optional explicit YAML file path. May be passed multiple times.",
    )
    parser.add_argument(
        "--date",
        dest="current_date",
        help="Override current date in YYYY-MM-DD format.",
    )
    parser.add_argument(
        "--use-latest-monday",
        action="store_true",
        help=(
            "When no --date is provided, evaluate notifications using the most "
            "recent Monday. Intended for manual workflow replays."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Generate queue output without sending email.",
    )
    parser.add_argument(
        "--recipient",
        help="Override recipient email. Defaults to NOTIFICATION_TO_EMAIL from env.",
    )
    args = parser.parse_args()

    load_dotenv_file(args.root_dir / ".env")
    current_date = _resolve_current_date(
        args.current_date,
        use_latest_monday=args.use_latest_monday,
    )
    deadline_paths = resolve_deadline_files(args.inputs, root=args.root_dir)
    deadlines = load_deadlines(deadline_paths)
    grouped = group_upcoming_notifications(deadlines, current_date=current_date)

    build_dir = args.root_dir / "build"
    build_dir.mkdir(parents=True, exist_ok=True)

    if not grouped:
        queue_path = build_dir / "notification-queue.json"
        queue_path.write_text("[]\n", encoding="utf-8")
        print(f"No notifications to send on {current_date.isoformat()}.")
        print(f"Wrote empty queue: {queue_path}")
        return 0

    queue = orchestration_step_notification_composer(grouped)
    queue_path = build_dir / "notification-queue.json"
    queue_path.write_text(json.dumps(queue, indent=2), encoding="utf-8")

    recipient = args.recipient or os.environ.get("NOTIFICATION_TO_EMAIL")
    if not recipient:
        raise SystemExit(
            "Missing recipient email. Set NOTIFICATION_TO_EMAIL or pass --recipient."
        )

    resend_settings = None if args.dry_run else load_resend_settings()
    results = dispatch_notification_queue(
        queue,
        recipient_email=recipient,
        resend_settings=resend_settings,
        dry_run=args.dry_run,
    )

    log_path = build_dir / "notification-log.jsonl"
    with log_path.open("a", encoding="utf-8") as handle:
        for result in results:
            for log in result.logs:
                handle.write(log.model_dump_json())
                handle.write("\n")

    print(f"Wrote queue: {queue_path}")
    print(f"Wrote notification log: {log_path}")
    failed_count = sum(1 for result in results if result.status != "sent")
    if args.dry_run:
        previewed_count = sum(1 for result in results if result.status == "previewed")
        print(
            f"Dry run complete for {recipient}. "
            f"Previewed {previewed_count} notification email(s). No emails were sent."
        )
        return 0

    sent_count = len(results) - failed_count
    print(f"Sent {sent_count} notification email(s) to {recipient}.")
    if failed_count:
        for result in results:
            if result.status == "failed" and result.error_message:
                print(
                    "Notification send failed for "
                    f"{result.queue_item['notification_type']}: {result.error_message}"
                )
        print(
            f"{failed_count} notification email(s) failed. "
            "See build/notification-log.jsonl for details."
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
