# gh-actions: Org Fork Orchestrator

Centralized GitHub Actions automation for keeping forked repos in sync without installing workflows in each fork.

## What it does

This repository runs workflows that:

- discover forked repositories in the configured organization
- sync each fork's `main` from its upstream via the GitHub merge-upstream API (fast-forward only)
- create managed branches if missing (create-only)
- merge `main` into the product branch without PRs
- fast-forward staging when safe
- keep snapshot as a create-once branch
- keep release tracking product (fast-forward when possible; reset on divergence)
- create or update canonical issues on conflicts/divergence
- rely on GitHub App webhooks to reach the forks worker for GitLab automation (no synthetic dispatch)

No PRs are created. Branches are fast-forwarded when possible; divergent branches are reset to policy targets. If a repo diverges or conflicts, the run records an issue and skips remaining steps for that repo.

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

- `BWS_TOKEN_GL_FORKS` (Bitwarden Secrets Manager access token for org-fork-orchestrator)

Repo variables:
- `BWS_PROJ_GL_FORKS` (Bitwarden Secrets Manager project UUID for org-fork-orchestrator)

Bitwarden Secrets Manager keys (secret name → ENV):

All secrets are materialized to temp files under `${RUNNER_TEMP}/bws` and passed via `*_FILE` env vars (e.g., `GH_ORG_SHARED_APP_PEM_FILE`).

**Orchestrator project** (`BWS_PROJ_GL_FORKS`):

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

## Branch model (GitHub)

- Mirror branch: `main` or `master` (fork mirror of upstream; fast-forward only)
- Product: `{GH_BRANCH_PREFIX}/{GH_BRANCH_PRODUCT}` (must always track mirror)
- Staging: `{GH_BRANCH_PREFIX}/{GH_BRANCH_STAGING}` (tracks product, kept at least one commit behind)
- Feature: `{GH_BRANCH_PREFIX}/{GH_BRANCH_FEATURE}` (tracks product, kept at least one commit behind)
- Release: `{GH_BRANCH_PREFIX}/{GH_BRANCH_RELEASE}` (tracks product; reset to product on divergence)
- Snapshot: `{GH_BRANCH_PREFIX}/{GH_BRANCH_SNAPSHOT}` (create-once; never updated)

## Workflow schedule

- `org-fork-orchestrator` runs only when dispatched by the workers or by `upstream-poll`.
- `upstream-poll` runs every 15 minutes to detect upstream HEAD changes and dispatch the orchestrator.

## Manual runs

You can run the workflows manually and optionally target a single repo:

- `org`: optional org name (limits the org matrix)
- `repo`: fork repository name (string)

## GitHub App webhooks (real deliveries)

Configure the GitHub App webhook to point at the forks worker:

- Endpoint: `https://gl-forks.<zone>/v1/webhook/github`
- Events: `fork`, `repository`, `create`, `push`, `workflow_run`, `check_suite`
- Secret: must match `CF_FORKS_WEBHOOK_SECRET` configured for the worker (stored in BWS for the worker deploy)

## Upstream polling (when you don't control upstream orgs)

The `upstream-poll` workflow checks upstream default branch HEADs and dispatches the orchestrator
for forks that have fallen behind. This is a best-effort fallback when upstream owners do **not**
install your GitHub App, so no upstream webhook events are delivered.

## Token minting

GitHub App installation tokens are minted locally via a JWT flow in
`.github/scripts/github_app_token.py`. The PEM and App ID are read from
`*_FILE` paths under `${RUNNER_TEMP}/bws`, and the access token is written to
`${RUNNER_TEMP}/bws/GITHUB_APP_TOKEN` with `0600` permissions.

## Files

- `.github/workflows/org-fork-orchestrator.yml`
- `.github/workflows/upstream-poll.yml`
- `.github/scripts/orchestrator.py`
- `.github/scripts/poll_upstream.py`
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
