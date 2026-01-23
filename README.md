# gh-actions: Org Fork Orchestrator

Centralized GitHub Actions automation for keeping forked repos in sync without installing workflows in each fork.

## What it does

This repository runs workflows that:

- discover forked repositories in the configured organization
- sync each fork's `main` from its upstream via the GitHub merge-upstream API (fast-forward only)
- create managed branches if missing (create-only)
- merge `main` into the product branch without PRs
- fast-forward staging when safe
- keep snapshot and release as create-once branches
- create or update canonical issues on conflicts/divergence
- dispatch signed webhooks to the forks worker for GitLab automation

No PRs are created. No force pushes are performed. If a repo diverges or conflicts, the run records an issue and skips remaining steps for that repo.

## Security
See `SECURITY.md` for the repo-specific threat model and mitigations.

## Required GitHub App permissions

Install a GitHub App on the organization with **minimum** permissions:

- Repository contents: **Read & Write** (refs updates + merge endpoints)
- Issues: **Read & Write** (create/update canonical issues)
- Metadata: **Read**

No pull request permissions are required.

## Required secrets (GitHub)

Repo secrets in `gh-actions`:

- `BWS_GH_FORKS_TOKEN` (Bitwarden Secrets Manager access token for org-fork-orchestrator)
- `BWS_GLAB_FORKS_TOKEN` (Bitwarden Secrets Manager access token for worker-dispatch)

Repo variables:
- `BWS_GH_FORKS_PROJ_ID` (Bitwarden Secrets Manager project UUID for org-fork-orchestrator)
- `BWS_GLAB_FORKS_PROJ_ID` (Bitwarden Secrets Manager project UUID for worker-dispatch)

Bitwarden Secrets Manager keys (secret name → ENV):

All secrets are materialized to temp files under `${RUNNER_TEMP}/bws` and passed via `*_FILE` env vars (e.g., `GH_ORG_SHARED_APP_PEM_FILE`).

**Orchestrator project** (`BWS_GH_FORKS_PROJ_ID`):

- `GH_ORG_SHARED_APP_ID`
- `GH_ORG_SHARED_APP_PEM`
- `GH_BRANCH_PREFIX`
- `GH_BRANCH_PRODUCT`
- `GH_BRANCH_STAGING`
- `GH_BRANCH_SNAPSHOT`
- `GH_BRANCH_FEATURE`
- `GH_BRANCH_RELEASE`
- `GH_ORG_TOOLS`
- `GH_ORG_SECOPS`
- `GH_ORG_WIKI`
- `GH_ORG_DIVERGE`
- `GH_ORG_CHECKOUT`

**Web project** (`BWS_GLAB_FORKS_PROJ_ID`):

- `CF_FORKS_WEBHOOK_URL`
- `CF_FORKS_WEBHOOK_SECRET`

## Branch model (GitHub)

- Mirror branch: `main` or `master` (fork mirror of upstream; fast-forward only)
- Product: `{GH_BRANCH_PREFIX}/{GH_BRANCH_PRODUCT}` (must always track mirror)
- Staging: `{GH_BRANCH_PREFIX}/{GH_BRANCH_STAGING}` (tracks product, kept at least one commit behind)
- Feature: `{GH_BRANCH_PREFIX}/{GH_BRANCH_FEATURE}` (tracks product, kept at least one commit behind)
- Snapshot: `{GH_BRANCH_PREFIX}/{GH_BRANCH_SNAPSHOT}` (create-once; never updated)

## Workflow schedule

- `org-fork-orchestrator` runs on a schedule:
  - `17 3 * * *`
  - `17 23 * * *`
- `worker-dispatch` runs only when `org-fork-orchestrator` completes successfully, or via manual dispatch.

## Manual runs

You can run the workflows manually and optionally target a single repo:

- `repo`: fork repository name (string)

## Worker dispatch workflow (via forks worker)

The `worker-dispatch` workflow **triggers the forks Cloudflare worker** instead of calling GitLab directly.
The worker then triggers the appropriate GitLab pipelines based on the webhook payload.

- It emits signed **GitHub webhook payloads** (push-style) to the worker endpoint.
- The worker validates the HMAC signature and applies its allowlist rules.
- The org matrix, GitHub App credentials (`GH_ORG_SHARED_APP_ID/PEM`), and branch config are read from
  the **orchestrator** BWS project. The web project only provides the worker webhook URL/secret.

Required Bitwarden Secrets Manager keys to reach the worker:

- `CF_FORKS_WEBHOOK_URL`
- `CF_FORKS_WEBHOOK_SECRET`

## Token minting

GitHub App installation tokens are minted locally via a JWT flow in
`.github/scripts/github_app_token.py`. The PEM and App ID are read from
`*_FILE` paths under `${RUNNER_TEMP}/bws`, and the access token is written to
`${RUNNER_TEMP}/bws/GITHUB_APP_TOKEN` with `0600` permissions.

## Files

- `.github/workflows/org-fork-orchestrator.yml`
- `.github/workflows/worker-dispatch.yml`
- `.github/scripts/orchestrator.py`
- `.github/scripts/worker_trigger.py`
- `.github/scripts/config.py`
- `.github/scripts/github_api.py`
- `.github/scripts/discover_repos.py`
- `.github/scripts/sync_mirror.py`
- `.github/scripts/ensure_branches.py`
- `.github/scripts/github_app_token.py`
- `.github/scripts/logging_util.py`
- `.github/scripts/promote_ff_only.py`
- `.github/scripts/issues.py`
- `.github/scripts/summary.py`
