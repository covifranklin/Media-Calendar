# Media Calendar

Media Calendar is a small Python project for tracking deadline data, generating a static HTML calendar, and running AI-assisted annual curation and notification workflows.

## What works today

- Pydantic v2 models for deadlines, notifications, and curation logs
- `notification_composer` and `data_curation_agent` agent implementations
- deterministic static calendar generation
- orchestration steps for notifications, data curation, and calendar generation
- GitHub Actions CI for tests and GitHub Pages deployment

## Requirements

- Python 3.10 or newer recommended
- an OpenAI API key for LLM-backed commands such as annual curation

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

4. Run the test suite:

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

The workflow at `.github/workflows/ci.yml` does three things:

1. Runs `pytest` on pull requests and pushes.
2. On pushes to `main`, generates `build/calendar.html`.
3. Deploys the `build/` directory to GitHub Pages.

## Data format

Each deadline YAML entry should match the `Deadline` model. The included sample file is a good starting point.

## Current limitations

- There is no email sender service wired up yet.
- The curation CLI fetches page text directly from source URLs and depends on a valid OpenAI key.
- Notification composition is implemented as library/orchestration code, not yet as a standalone end-user CLI.
