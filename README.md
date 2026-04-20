# Media Calendar

Media Calendar is a small Python project for tracking deadline data, generating a static HTML calendar, and running AI-assisted annual curation and notification workflows.

## What works today

- Pydantic v2 models for deadlines, notifications, and curation logs
- `notification_composer` and `data_curation_agent` agent implementations
- deterministic static calendar generation
- orchestration steps for notifications, data curation, and calendar generation
- SMTP-backed notification sending
- GitHub Actions for tests, GitHub Pages deployment, daily notifications, and manual curation

## Requirements

- Python 3.10 or newer recommended
- an OpenAI API key for LLM-backed commands such as annual curation and notification composition
- SMTP credentials if you want the project to send email automatically

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

The repo now includes three workflows:

1. `.github/workflows/ci.yml`
   Runs `pytest` on pull requests and pushes, generates `build/calendar.html` on pushes to `main`, and deploys it to GitHub Pages.
2. `.github/workflows/notifications.yml`
   Runs daily on a schedule and can also be started manually to compose/send notifications.
3. `.github/workflows/curation.yml`
   Runs manually for a chosen year and uploads curation reports as workflow artifacts.

### GitHub secrets to configure

For notifications:

- `OPENAI_API_KEY`
- `SMTP_HOST`
- `SMTP_PORT`
- `SMTP_FROM_EMAIL`
- `SMTP_USERNAME`
- `SMTP_PASSWORD`
- `SMTP_USE_STARTTLS`
- `SMTP_USE_SSL`
- `NOTIFICATION_TO_EMAIL`

For manual curation:

- `OPENAI_API_KEY`

## Data format

Each deadline YAML entry should match the `Deadline` model. The included sample file is a good starting point.

## Current limitations

- The curation CLI fetches page text directly from source URLs and depends on a valid OpenAI key.
- The daily notification flow sends one email per notification bucket, not one email per deadline.
- SMTP delivery assumes a working SMTP provider such as Gmail with an app password, Mailgun SMTP, or similar.
