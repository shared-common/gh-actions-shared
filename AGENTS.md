# AGENTS.md (repo guidance)

## Repository purpose
Shared GitHub Actions workflows, scripts, and composite actions used by org-specific wrapper repos.

## Non-negotiables
- No org-specific data or secrets in this repo.
- All `uses:` references must be pinned to a commit SHA.
- Keep permissions minimal (`contents: read` by default).
- All shared workflows must validate event context against `configs/event-allowlist.json`.
- Shared workflows must pin `actions/setup-python` to the latest stable Python release.
- Scheduled polling should run from dedicated public `*-polling` repos.

## Security
- Do not print secrets.
- BWS secrets must be handled via files (`*_FILE`), not exported env values.
- Inputs must include `job_type` and pass schema validation.

## Workflow policy
- Reusable workflows only (`workflow_call`).
- No `workflow_dispatch` in shared workflows unless explicitly required.
