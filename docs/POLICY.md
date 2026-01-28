# Policy

## Shared repo rules
- No org‑specific data or secrets in this repo.
- All `uses:` references must be pinned to commit SHA.
- Secrets are consumed via `*_FILE` paths only.
- Events must pass allowlist validation before any action.

## Wrapper repo contract
Wrapper repos must:
- Be thin wrappers only (no orchestration logic).
- Use `workflow_dispatch` only (no `repository_dispatch`).
- Fork drift polling is initiated by the Worker cron (no polling repos).
- Pass `event-context`, `event-name`, and `expected-event-action` inputs.
- Require `inputs.dispatch_action` and `inputs.app_id` in workflow_dispatch wrappers.
- Pass `target-org` for org validation.
- Provide BWS secrets via repo secrets (per‑org).

## Branch policy
Branch creation/update behavior is controlled by `configs/branch-policy.json`.
Changes to policy require updating validation and documentation together.
