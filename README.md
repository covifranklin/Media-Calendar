# Media Calendar

Media Calendar is a small Python project for tracking deadline data, generating a static HTML calendar, and running AI-assisted annual curation and notification workflows.

## What works today

- Pydantic v2 models for deadlines, notifications, and curation logs
- `notification_composer` and `data_curation_agent` agent implementations
- deterministic static calendar generation
- automated source discovery refresh with conservative auto-promotion
- orchestration steps for notifications, data curation, and calendar generation
- Resend API-backed notification sending
- GitHub Actions for tests, GitHub Pages deployment, weekly discovery refresh, weekly notifications, and manual curation

## Requirements

- Python 3.10 or newer recommended
- an OpenAI API key for LLM-backed commands such as annual curation and notification composition
- a Resend API key if you want the project to send email automatically

## Local setup

1. Clone the repository:

```bash
git clone https://github.com/covifranklin/Media-Calendar.git
cd Media-Calendar
```

2. Create and activate a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

On Windows PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

3. Install the project:

```bash
python -m pip install --upgrade pip
python -m pip install -e .
```

4. Copy the example environment file and fill in your secrets:

```bash
cp .env.example .env
```

5. Run the test suite:

```bash
python -m pytest -q
```

## Project layout

- `data/deadlines/*.yaml`: source deadline files
- `build/calendar.html`: generated static site output
- `build/curation-<year>.md`: human-readable curation report
- `build/curation-<year>.jsonl`: machine-friendly curation report

## Generate the calendar locally

The repo includes sample data at `data/deadlines/2026.yaml`.

```bash
python generate_calendar.py
```

This writes:

- `build/calendar.html`

You can then open the file in a browser.

## Run the automated discovery refresh locally

This workflow fetches the monitored official sources, detects likely
opportunities, compares them with the existing deadline database, auto-promotes
only high-confidence results, writes updated YAML, and regenerates the
calendar.

Deterministic-only mode:

```bash
python discover.py --llm-mode off
```

Automatic LLM mode when `OPENAI_API_KEY` is available:

```bash
python discover.py
```

This writes:

- `data/deadlines/<year>.yaml` when you pass `--mode apply`
- `build/discovery-refresh.json`
- `build/discovery-refresh.md`
- `build/discovery-metrics.json`
- `build/discovery-metrics.md`
- `build/source-freshness.json`
- `build/source-freshness.md`
- `build/calendar.html`

Safer weekly preview mode:

```bash
python discover.py --mode dry-run --llm-mode off
```

Explicit apply mode:

```bash
python discover.py --mode apply
```

To generate a source coverage snapshot separately:

```bash
python coverage_report.py
```

## Compose and send notifications locally

The notifications CLI loads all deadline YAML files, finds deadlines that match the current reminder windows, composes email content, and optionally sends it.

Preview without sending:

```bash
python notify.py --dry-run
```

Send for real:

```bash
python notify.py
```

Optional flags:

```bash
python notify.py --date 2026-05-04
python notify.py --recipient friend@example.com
python notify.py --input data/deadlines/2026.yaml
```

This writes:

- `build/notification-queue.json`
- `build/notification-log.jsonl`

Set these environment variables in `.env`:

```env
RESEND_API_KEY=your_resend_api_key
RESEND_FROM_EMAIL=onboarding@resend.dev
RESEND_FROM_NAME=Media Calendar
NOTIFICATION_TO_EMAIL=recipient@example.com
```

Resend supports a friendly sender name in the `from` field using the format `Your Name <sender@domain.com>`, and this project now builds that automatically from `RESEND_FROM_NAME` plus `RESEND_FROM_EMAIL`.

## Run annual curation locally

Set your OpenAI API key first:

```bash
export OPENAI_API_KEY="your_api_key_here"
```

On Windows PowerShell:

```powershell
$env:OPENAI_API_KEY="your_api_key_here"
```

Then run:

```bash
python curate.py --year 2026
```

This reads:

- `data/deadlines/2026.yaml`

And writes:

- `build/curation-2026.md`
- `build/curation-2026.jsonl`

## GitHub Actions

The repo now includes four workflows:

1. `.github/workflows/ci.yml`
   Runs `pytest` on pull requests and pushes, generates `build/calendar.html` on pushes to `main`, and deploys it to GitHub Pages.
2. `.github/workflows/discovery-refresh.yml`
   Runs weekly in safe dry-run mode to fetch monitored sources and upload monitoring artifacts, including coverage, source freshness, discovery refresh, and discovery metrics reports. Manual runs can switch to apply mode to write and commit `data/deadlines/*.yaml`.
3. `.github/workflows/notifications.yml`
   Runs weekly on Mondays and can also be started manually to compose/send notifications.
4. `.github/workflows/curation.yml`
   Runs manually for a chosen year and uploads curation reports as workflow artifacts.

### GitHub secrets to configure

For automated discovery:

- `OPENAI_API_KEY` if you want `discover.py` to use the optional LLM-assisted source discovery mode

The discovery workflow uploads these artifacts on each run:

- `coverage-report.json` and `coverage-report.md`
- `source-freshness.json` and `source-freshness.md`
- `discovery-refresh.json` and `discovery-refresh.md`
- `discovery-metrics.json` and `discovery-metrics.md`
- `discovery-log.jsonl`

For notifications:

- `OPENAI_API_KEY`
- `RESEND_API_KEY`
- `RESEND_FROM_EMAIL`
- `RESEND_FROM_NAME`
- `NOTIFICATION_TO_EMAIL`

For manual curation:

- `OPENAI_API_KEY`

## Data format

Each deadline YAML entry should match the `Deadline` model. The included sample file is a good starting point.

## Current limitations

- The curation CLI fetches page text directly from source URLs and depends on a valid OpenAI key.
- The weekly discovery refresh is conservative by design and rejects uncertain candidates instead of queueing them for human review.
- The weekly notification flow sends one email per notification bucket, not one email per deadline.
- The default `onboarding@resend.dev` sender is useful for testing, but for a polished production setup you will likely want a verified domain in Resend.
