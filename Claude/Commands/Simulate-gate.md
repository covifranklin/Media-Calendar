Simulate a human review gate during development without blocking stdin.

The user will provide: $ARGUMENTS (gate name and decision: accept/reject/feedback)

Human gates in this project:
- Curation agent proposed deadline changes: Curation agent returns status 'dates_changed' or 'ambiguous' for any deadline during annual refresh, OR confidence < 0.85 on any extraction
- First notification send for a new deadline category or new year's data: The first time the scheduler processes deadlines from a newly curated year's YAML file, or when a deadline with a new category value is added
- LLM output validation failure: Post-generation validator detects a URL, date, or organization name in the composed email that does not exist verbatim in the input deadline data

Steps:
1. Identify which gate $ARGUMENTS refers to
2. Inject the specified decision programmatically (patch stdin or use a --auto flag)
3. Run the pipeline through that gate and report what happens next
4. Never use gate simulation in production — development only