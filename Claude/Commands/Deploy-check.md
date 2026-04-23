Verify the deployment is healthy after any infrastructure change.

Steps:
1. Deploy using: push to `main` branch — GitHub Actions CI rebuilds the calendar and deploys to GitHub Pages automatically. Ensure the `schedule:` workflow is enabled (GitHub disables it after 60 days of repo inactivity).
2. Run a smoke test: hit the healthcheck endpoint or trigger a dry run
3. Check the last 20 lines of application logs for errors
4. Confirm the audit log is being written (check the configured path)
5. Report: deploy status, smoke test result, any warnings in logs
