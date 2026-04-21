# Operations Guide

This guide is for the person running Media Calendar in normal use.
You do not need to read the code to use the project.

## What Happens Automatically

Three GitHub Actions workflows matter for day-to-day operation:

1. `CI and Pages`
   Runs when code is pushed to `main`.
   It tests the project, rebuilds the static calendar, and publishes the calendar website to GitHub Pages.

2. `Weekly Discovery Refresh`
   Runs every Monday.
   It checks monitored source websites, looks for new or changed opportunities, uploads monitoring reports, and can publish deadline changes automatically.
   It now runs in `apply` mode by default, which means discovered deadline changes are committed back to the repository automatically.

3. `Weekly Notifications`
   Runs every Monday.
   It builds the weekly digest plus any urgent deadline alerts and sends email if the required Resend secrets are configured.

There is also a fourth workflow:

4. `Manual Curation`
   This does not run automatically.
   Use it only when you want a one-off annual review of an existing deadline year.

## What Updates Automatically

These outputs are created automatically by workflows:

- Calendar site:
  `build/calendar.html` during the Pages workflow, then published to GitHub Pages.
- Discovery monitoring artifacts:
  uploaded from `build/` by the weekly discovery workflow.
- Notification artifacts:
  uploaded from `build/` by the weekly notifications workflow.
- Curation artifacts:
  uploaded from `build/` when you manually run curation.

These files now update automatically from the weekly discovery run:

- `data/deadlines/*.yaml`
  The weekly discovery workflow commits these files when it finds promotable changes.

## Where The Calendar Lives

The public calendar is the GitHub Pages site for this repository.

Typical URL:

- `https://covifranklin.github.io/Media-Calendar/`

If the site does not look updated, check:

- the latest successful `CI and Pages` workflow run
- that GitHub Pages is enabled in the repository settings
- that the latest push was to `main`

## Where Discovery Reports Live

Discovery reports are stored as GitHub Actions artifacts on each `Weekly Discovery Refresh` run.

Open them here:

1. Go to the repository on GitHub.
2. Click `Actions`.
3. Open the latest `Weekly Discovery Refresh` run.
4. Download the artifact named `discovery-monitoring-artifacts`.

Important files inside that artifact:

- `coverage-report.json`
- `coverage-report.md`
- `source-freshness.json`
- `source-freshness.md`
- `discovery-refresh.json`
- `discovery-refresh.md`
- `discovery-metrics.json`
- `discovery-metrics.md`
- `discovery-log.jsonl`

If you only want the easiest human-readable files, start with:

- `coverage-report.md`
- `source-freshness.md`
- `discovery-refresh.md`
- `discovery-metrics.md`

## Secrets Required

Set these in GitHub repository `Settings` -> `Secrets and variables` -> `Actions`.

### Needed For Discovery

- `OPENAI_API_KEY`
  Optional for discovery if you are happy with deterministic-only mode.
  Recommended if you want the optional LLM-assisted discovery mode.

### Needed For Notifications

- `OPENAI_API_KEY`
- `RESEND_API_KEY`
- `RESEND_FROM_EMAIL`
- `RESEND_FROM_NAME`
- `NOTIFICATION_TO_EMAIL`

### Needed For Manual Curation

- `OPENAI_API_KEY`

## How To Trigger Workflows Manually

### Rebuild The Calendar Website

The calendar website rebuilds on any push to `main`.
If you need to force a rebuild, make a normal commit to `main` or merge a PR into `main`.

### Run Discovery Manually

1. Go to `Actions`.
2. Open `Weekly Discovery Refresh`.
3. Click `Run workflow`.
4. Choose a mode:
   `apply` is now the default and writes deadline YAML updates back to `main`.
   `dry-run` is still available if you want a preview without changing repository data.
5. Choose `llm_mode`:
   `auto` is the normal default.
   `off` disables the LLM layer.
   `required` forces the run to fail if the LLM cannot be used.
6. Click `Run workflow`.

Recommendation:

- Leave the scheduled run alone for full autonomy.
- Use `dry-run` only when you want to preview behavior without letting it publish changes.

### Run Notifications Manually

1. Go to `Actions`.
2. Open `Weekly Notifications`.
3. Click `Run workflow`.
4. Choose whether to use `dry_run`.
   `true` previews the run without sending email.
   `false` actually sends email.
5. Click `Run workflow`.

Recommendation:

- Use `dry_run=true` whenever you are testing configuration or checking copy before a live send.

### Run Annual Curation Manually

1. Go to `Actions`.
2. Open `Manual Curation`.
3. Click `Run workflow`.
4. Enter the year you want to curate, such as `2026`.
5. Click `Run workflow`.

## What Runs Weekly

Every Monday:

- `Weekly Discovery Refresh` checks monitored sources and uploads discovery/health reports.
- `Weekly Discovery Refresh` also commits promoted deadline changes automatically when it finds them.
- `Weekly Notifications` prepares the weekly digest and any urgent alerts.

The calendar website itself is not rebuilt on a timer.
It rebuilds when `main` changes.

That means:

- on a normal week, discovery can update `data/deadlines/*.yaml` automatically
- once that commit lands on `main`, the Pages workflow rebuilds the public calendar
- if you manually choose `dry-run`, the reports update but the public calendar does not change

## What To Check If Something Fails

Start with the relevant GitHub Actions run log.

### If The Calendar Website Is Missing Or Stale

Check:

- `CI and Pages` succeeded
- the latest commit reached `main`
- GitHub Pages is enabled
- the Pages deployment job succeeded

### If Discovery Failed

Check:

- `OPENAI_API_KEY` is present if you expected LLM mode
- the workflow was not run in `required` LLM mode without a valid key
- the monitored source sites were reachable
- the uploaded artifacts for `source-freshness.md` and `discovery-refresh.md`

Common interpretation:

- If the run succeeded but `data/deadlines/*.yaml` did not change, it may have run in `dry-run`, or the system may simply have found nothing promotable that week.
- If the run failed, the uploaded discovery artifacts should still be available and are the best first place to inspect what went wrong.

### If Notifications Failed

Check:

- `RESEND_API_KEY`
- `RESEND_FROM_EMAIL`
- `RESEND_FROM_NAME`
- `NOTIFICATION_TO_EMAIL`
- `OPENAI_API_KEY`

Then check the uploaded `notification-artifacts` and the workflow logs.

Common interpretation:

- If the run succeeded in `dry_run`, no email is sent by design.
- If the run says there were no notifications, there may have been no matching weekly digest or urgent reminder items for that date.
- If the run failed after queue creation, check `notification-log.jsonl` in the uploaded artifact for failed send records.

### If Manual Curation Failed

Check:

- `OPENAI_API_KEY`
- that the year file exists, for example `data/deadlines/2026.yaml`
- the workflow logs for fetch or validation failures

## Quick Weekly Checklist

For a light-touch operator routine:

1. Check the latest `Weekly Discovery Refresh` run.
2. Download and skim:
   `coverage-report.md`, `source-freshness.md`, and `discovery-refresh.md`.
3. Check the latest `Weekly Notifications` run.
4. If needed, manually rerun notifications in `dry_run=true` first, then rerun with `dry_run=false`.
5. Confirm the public calendar page looks correct after automated discovery changes.
