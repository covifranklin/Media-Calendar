# Building a system for a small media company focused on impact production. Wants 

## What This Is
A deadline and opportunity tracking system for a small impact media company, aggregating key film industry dates — festivals, funding rounds, labs, fellowships, and industry forums — into a unified yearly calendar with email notifications and summary outputs.
*MVP | Viability assessed at 82%*

## Commands
- **Run:** GitHub Actions scheduled workflow (`schedule:` cron, daily 08:00 UTC). Trigger manually via `workflow_dispatch`. Curation script run locally or via `workflow_dispatch`: `python curate.py --year 2025`. No server, no crontab. All secrets in GitHub Actions secrets.
- **Test:** `Three-tier testing approach: (1) Unit tests (pytest): Validate deadline YAML schema parsing, notification window calculation logic, duplicate-send prevention logic, date comparison functions, and HTML calendar generation. Cover edge cases: leap years, deadlines on weekends, empty deadline files, malformed YAML. Target: 90%+ coverage on processing layer. (2) Integration tests: End-to-end test with a fixture deadline database containing 10 test deadlines across all categories. Run the scheduler in test mode with a mock email backend (no actual sends); verify correct emails are composed for correct deadlines at correct windows. Verify NotificationLog entries are created. Test curation agent with fixture scraped text (both changed and unchanged scenarios) and validate structured output. (3) LLM output validation tests: For notification_composer, run 20 test cases with known inputs and validate outputs against a checklist: valid JSON, subject line contains deadline name, no URLs or dates not present in input, word count under limit. For curation agent, run 10 test cases with known diffs and validate that proposed_updates match expected changes. Use deterministic seed where possible (temperature=0). (4) Manual acceptance test before launch: Send test digest and individual notification emails to the client's inbox, review formatting across Gmail and Apple Mail.`
- **Audit log:** Append-only files in the data/ directory of the Git repository: SQLite for notification log (data/notifications.sqlite), JSONL for curation log (data/curation_log.jsonl), JSONL for LLM call audit (data/audit/{YYYY-MM}.jsonl). All files are committed to Git on each scheduler run, providing immutable version history via Git's commit log.

## Hard Constraints
- No PII is processed beyond email addresses of the client's team members (likely 1-5 addresses). No GDPR or CCPA special handling is required at this scale, but email addresses should not be committed to the public Git repository — store them in a .env file excluded from version control. No financial transactions are processed. Content scraped from public websites for curation purposes falls under fair use (factual date extraction, not content republication). If the client later expands to serve external users, a privacy policy and explicit opt-in for email notifications would be required. SendGrid's compliance features (unsubscribe headers, CAN-SPAM compliance) should be enabled on all outbound emails even at MVP to establish good practice.
- If OpenAI API spend exceeds $5 in a calendar month (tracked via per-call cost logging in data/audit/{YYYY-MM}.jsonl, summed by the scheduler before each call), all LLM calls are skipped and template-based fallback is used for remaining notifications
- If the scheduler detects more than 50 notification sends queued in a single run (indicating a possible data error like all deadlines set to the same date), it halts, sends zero emails, and alerts the admin via Slack webhook
- If SendGrid reports 5+ bounced emails in a 7-day window, notification sending is paused and a manual review is required before re-enabling (flag in config: NOTIFICATIONS_PAUSED=true)

## Human Review Gates — Never Skip
- Before Curation agent proposed deadline changes: Curation agent returns status 'dates_changed' or 'ambiguous' for any deadline during annual refresh, OR confidence < 0.85 on any extraction
- Before First notification send for a new deadline category or new year's data: The first time the scheduler processes deadlines from a newly curated year's YAML file, or when a deadline with a new category value is added
- Before LLM output validation failure: Post-generation validator detects a URL, date, or organization name in the composed email that does not exist verbatim in the input deadline data

## Known Failure Modes (watch for these)
- Stale data: Deadlines not refreshed annually, causing users to rely on outdated dates. Mitigation: Annual curation workflow triggered by calendar reminder in September, curation agent flags all records older than 10 months since last_verified_date, and a monthly staleness report is emailed to the curator.
- Duplicate notifications: Scheduler runs multiple times or crashes mid-run, sending the same email twice. Mitigation: NotificationLog table enforces a unique constraint on (deadline_id, notification_type, year); the sender checks before dispatching.
- Email delivery failure: SendGrid/SES quota exceeded, API key expired, or recipient mailbox full. Mitigation: NotificationLog records 'failed' status; a daily retry job re-attempts failed sends up to 3 times; alerts sent to admin Slack channel on 2+ consecutive failures.
- LLM hallucination in notifications: Notification composer fabricates details not in the input (e.g., wrong eligibility criteria). Mitigation: Prompt strictly prohibits adding information; a post-generation validator checks that all URLs, dates, and names in the output exist verbatim in the input JSON. Mismatches block the email and flag for human review.

## Never Do This
- Access the filesystem, network, or any external APIs
- Modify deadline data or notification logs
- Send emails directly (sending is handled by a separate non-LLM function)
- Add information not present in the input (e.g., fabricated eligibility criteria, invented URLs)
- Access or reference data from previous invocations (stateless per call)
- Directly modify the deadline YAML database
