# Automation Roadmap

This project currently maintains known deadlines well, but it does not yet
guarantee broad discovery across film and TV events and opportunities.

The path to a reliable automated system is to treat coverage as a first-class
product concern, not just a scraping problem. We need a source inventory,
repeatable extraction, structured review, and explicit coverage checks.

## Phase 1: Coverage Foundation

1. Define the coverage taxonomy.
   Categories should include festivals, labs, fellowships, funds, markets,
   industry forums, broadcasters, guild programs, and other strategic
   opportunities.
2. Create a source registry.
   Each source should represent an authoritative organization or program page,
   include category tags, region tags, cadence, and a priority level.
3. Add a source loader and validator.
   The registry should live in YAML, load deterministically, and be validated
   with Pydantic models.
4. Add a coverage scorecard.
   The project should be able to report how many must-have and high-priority
   sources are tracked by category and region.

## Phase 2: Automated Discovery Inputs

5. Add a fetch pipeline for registered sources.
   Fetch source pages with consistent headers, retries, and basic failure
   handling.
6. Store raw snapshots.
   Save the fetched HTML or extracted text so the system has an audit trail and
   can be re-run without hitting the network repeatedly.
7. Extract clean text and candidate date signals.
   Use deterministic parsing first and reserve the LLM for interpretation, not
   raw scraping.
8. Track fetch health.
   Report which sources failed, redirected, blocked bots, or returned weak
   content.

## Phase 3: Candidate Generation

9. Introduce a discovery candidate model.
   Candidates should represent potential new deadlines or opportunities found on
   source pages.
10. Build deterministic heuristics for candidate detection.
    Look for date phrases, submission windows, application wording, and target
    year matches before involving the LLM.
11. Add an LLM-assisted discovery agent.
    The agent should transform cleaned source text into structured candidate
    opportunities and confidence scores.
12. Deduplicate candidates.
    Normalize names, organizations, URLs, and year data so the same opportunity
    is not surfaced multiple times.

## Phase 4: Review and Promotion

13. Compare discovered candidates against the known deadline database.
    Split results into existing records with changes, likely duplicates, and net
    new opportunities.
14. Generate a human review queue.
    Output Markdown and JSONL reports for changed records, new candidates, and
    low-confidence findings.
15. Add promotion tools.
    Approved candidates should be convertible into `Deadline` entries with a
    predictable workflow.
16. Add curation logs for discovery decisions.
    We should track why a candidate was accepted, rejected, merged, or deferred.

## Phase 5: Ongoing Automation

17. Run scheduled refreshes by priority.
    Must-have sources should refresh more often than watchlist sources.
18. Add coverage alerts.
    Notify when a must-have source has no upcoming deadline, has not been
    verified recently, or repeatedly fails to fetch.
19. Add annual rollover support.
    Identify sources that have not yet published the next cycle and remind for
    manual review.
20. Add quality metrics.
    Track source freshness, candidate acceptance rate, duplicate rate, and
    category coverage over time.

## What We Should Build First

The first implementation step is a source registry. Without that, there is no
explicit definition of which authoritative pages the system is expected to
monitor, and we cannot reason about completeness.

The second step should be a deterministic source fetcher with snapshot output.

The third step should be a discovery candidate pipeline that separates:

- net new opportunities
- updates to existing deadlines
- ambiguous findings that require review

Only after those three pieces are in place will the project be able to move
from "refresh known entries" to "automatically search the film and TV landscape
for important opportunities."
