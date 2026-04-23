Refresh the project data from external sources.

Steps:
1. Run the data curation/fetch process against known source URLs
2. Diff the new data against the existing store — show what changed
3. Flag any entries that changed significantly for human review
4. Do NOT auto-commit changes — present them for review first
5. After human confirms, write the updated data and run validation

Always diff before write. Never silently overwrite existing records.