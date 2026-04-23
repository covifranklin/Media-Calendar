Create a focused git commit for the current changes.

Before committing:
1. Run `Three-tier testing approach: (1) Unit tests (pytest): Validate deadline YAML schema parsing, notification window calculation logic, duplicate-send prevention logic, date comparison functions, and HTML calendar generation. Cover edge cases: leap years, deadlines on weekends, empty deadline files, malformed YAML. Target: 90%+ coverage on processing layer. (2) Integration tests: End-to-end test with a fixture deadline database containing 10 test deadlines across all categories. Run the scheduler in test mode with a mock email backend (no actual sends); verify correct emails are composed for correct deadlines at correct windows. Verify NotificationLog entries are created. Test curation agent with fixture scraped text (both changed and unchanged scenarios) and validate structured output. (3) LLM output validation tests: For notification_composer, run 20 test cases with known inputs and validate outputs against a checklist: valid JSON, subject line contains deadline name, no URLs or dates not present in input, word count under limit. For curation agent, run 10 test cases with known diffs and validate that proposed_updates match expected changes. Use deterministic seed where possible (temperature=0). (4) Manual acceptance test before launch: Send test digest and individual notification emails to the client's inbox, review formatting across Gmail and Apple Mail.` — all tests must pass
2. Run the linter and fix any issues
3. Stage only files relevant to the current change — never `git add -A` blindly
4. Commit message: explain *why*, not *what* (the diff shows what)
5. Never commit `.env`, API keys, or secrets

If tests fail, fix the root cause. Do not use `--no-verify`.
