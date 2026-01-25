# AGENTS.md (repo guidance)

## Repository purpose
Shared GitHub Actions workflows, scripts, and composite actions used by org-specific wrapper repos.

## Non-negotiables
- No org-specific data or secrets in this repo.
- All `uses:` references must be pinned to a commit SHA.
- Keep permissions minimal (`contents: read` by default).

## Security
- Do not print secrets.
- BWS secrets must be handled via files (`*_FILE`), not exported env values.

## Workflow policy
- Reusable workflows only (`workflow_call`).
- No `workflow_dispatch` in shared workflows unless explicitly required.
