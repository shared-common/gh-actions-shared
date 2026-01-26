# Policy

## Shared repo rules
- No org‑specific data or secrets in this repo.
- All `uses:` references must be pinned to commit SHA.
- Secrets are consumed via `*_FILE` paths only.
- Events must pass allowlist validation before any action.

## Wrapper repo contract
Wrapper repos must:
- Be thin wrappers only (no orchestration logic).
- Avoid `workflow_dispatch`; only `repository_dispatch` in orchestrator wrappers is allowed.
- Scheduled poller runs in dedicated `*-polling` repos per org.
- Poller workflows must use polling app secrets:
  `GH_ORG_POLLING_APP_ID` and `GH_ORG_POLLING_APP_PEM`.
- Pass `event-context`, `event-name`, and `expected-event-action` inputs.
- Pass `target-org` for org validation.
- Provide BWS secrets via repo secrets (per‑org).

## Branch policy
Branch creation/update behavior is controlled by `configs/branch-policy.json`.
Changes to policy require updating validation and documentation together.
