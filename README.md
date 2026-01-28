# gh-actions-shared

Shared, reusable GitHub Actions workflows and scripts for the multi‑org GitHub/GitLab
sync orchestration. **All org‑specific configuration and secrets live in the wrapper
repos**; this repository stays org‑agnostic.

## What lives here
- Reusable workflows (`.github/workflows/*-core.yml`)
- Composite actions (`.github/actions/*`)
- Python scripts for validation, branch orchestration, discovery, and summary
- JSON configs/schemas used by the workflows

## Key guarantees
- **Pinned dependencies**: all `uses:` references pinned to commit SHA.
- **Secrets via files**: secrets are materialized into `*_FILE` paths only.
- **Event validation**: workflow_dispatch events are checked against
  `configs/event-allowlist.json` before work begins.
- **Branch policy**: enforced from `configs/branch-policy.json`.
- **Latest Python only**: workflows pin `actions/setup-python` (v6.1.0) to Python 3.14.2.

## Wrapper repo contract
Wrapper repositories must:
- Call only the reusable workflows in this repo.
- Rely on Worker cron for fork drift detection (no polling repos).
- Pass `event-context`, `event-name`, and `expected-event-action`.
- Pass `target-org` to enforce org allowlists.
- Provide BWS secrets via repo secrets (no inline secrets).

See `docs/` for architecture, policies, and troubleshooting.
