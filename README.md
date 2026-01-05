# gh-actions: Org Fork Orchestrator

Centralized GitHub Actions automation for keeping forked repos in sync without installing workflows in each fork.

## What it does

This repository runs scheduled workflows that:

- discover forked repositories in the configured organization
- sync each fork's `main` from its upstream via the GitHub merge-upstream API (fast-forward only)
- create managed branches if missing (create-only)
- merge `main` into the product branch without PRs
- fast-forward staging when safe
- keep snapshot and release as create-once branches
- create or update canonical issues on conflicts/divergence
- mirror selected refs to GitLab under a `github/` namespace

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

Repo secret in `gh-actions`:

- `BWS_ACCESS_TOKEN` (Bitwarden Secrets Manager access token)

Repo variable:
- `BWS_PROJECT_ID` (Bitwarden Secrets Manager project UUID)
- `REPO_CACHE_TTL_DISCOVERY` (repo discovery cache TTL in seconds)
- `REPO_CACHE_TTL_META` (repo metadata + ref SHA cache TTL in seconds)
- `REPO_CACHE_TTL_NEGATIVE` (negative cache TTL in seconds)
- `REPO_CACHE_TTL_GITLAB_PROJ` (GitLab project existence cache TTL in seconds)
- `REPO_CACHE_TTL_GITLAB_BRANCH` (GitLab branch/protection cache TTL in seconds)

Bitwarden Secrets Manager keys (secret name → ENV):

All secrets are materialized to temp files under `${RUNNER_TEMP}/bws` and passed via `*_FILE` env vars (e.g., `GH_ORG_SHARED_PEM_FILE`).

Caches are stored under `${GITHUB_WORKSPACE}/.cache`, including `repo-discovery.json` and `repo-metadata.json`.

- `GH_ORG_SHARED_APP_ID`
- `GH_ORG_SHARED_PEM`
- `GH_BRANCH_PREFIX`
- `GH_BRANCH_PRODUCT`
- `GH_BRANCH_STAGING`
- `GH_BRANCH_SNAPSHOT`
- `GH_BRANCH_FEATURE`
- `GH_BRANCH_RELEASE`

Bitwarden Secrets Manager keys for org/group routing:

- `GH_ORG_TBOX`
- `GH_ORG_SECOPS`
- `GH_ORG_WIKI`
- `GH_ORG_DIVERGE`
- `GL_GROUP_ZFORKS`
- `GL_GROUP_TBOX`
- `GL_GROUP_SECOPS`
- `GL_GROUP_WIKI`
- `GL_GROUP_ZDIVERGE`
- `GL_GROUP_GENERAL`

## Branch model (GitHub)

- Mirror branch: `main` or `master` (fork mirror of upstream; fast-forward only)
- Product: `{GH_BRANCH_PREFIX}/{GH_BRANCH_PRODUCT}` (must always track mirror)
- Staging: `{GH_BRANCH_PREFIX}/{GH_BRANCH_STAGING}` (tracks product, kept at least one commit behind)
- Feature: `{GH_BRANCH_PREFIX}/{GH_BRANCH_FEATURE}` (tracks product, kept at least one commit behind)
- Snapshot: `{GH_BRANCH_PREFIX}/{GH_BRANCH_SNAPSHOT}` (create-once; never updated)

## Workflow schedule

The workflows use static cron entries (GitHub Actions cannot take them from secrets):

- `17 3 * * *`
- `17 23 * * *`

## Manual runs

You can run the workflow manually and optionally target a single repo:

- `repo`: fork repository name (string)
- `clear_cache`: clear repo discovery cache before running (boolean)

## GitLab mirror workflow

The `gitlab-mirror` workflow mirrors selected GitHub refs into GitLab under a `github/` namespace and creates developer branches in GitLab only once (using `GH_BRANCH_*` variables for all branch names):

- Mirror targets (updated every run, fast-forward only):
  - `{GH_BRANCH_PREFIX}/{GH_BRANCH_PRODUCT}` → `github/{GH_BRANCH_PREFIX}/{GH_BRANCH_PRODUCT}`
  - `{GH_BRANCH_PREFIX}/{GH_BRANCH_STAGING}` → `github/{GH_BRANCH_PREFIX}/{GH_BRANCH_STAGING}`
- Dev branches (create-once in GitLab):
  - `{GH_BRANCH_PREFIX}/{GH_BRANCH_PRODUCT}` (default branch in GitLab)
  - `{GH_BRANCH_PREFIX}/{GH_BRANCH_STAGING}` (protected)
  - `{GH_BRANCH_PREFIX}/{GH_BRANCH_FEATURE}` (create-once)
  - `{GH_BRANCH_PREFIX}/{GH_BRANCH_RELEASE}` (protected)

GitLab protection rules (managed by the `gitlab-mirror` workflow when a project is created):
- Protect only `{GH_BRANCH_PREFIX}/{GH_BRANCH_STAGING}` and `{GH_BRANCH_PREFIX}/{GH_BRANCH_RELEASE}`
- Do not protect any `github/*` branches

Required Bitwarden Secrets Manager keys for GitLab mirroring (secret name → ENV):

- `GL_TOKEN_MCZFORKS`

The GitLab token must include `api` scope so the workflow can create missing projects.

## Files

- `.github/workflows/org-fork-orchestrator.yml`
- `.github/workflows/gitlab-mirror.yml`
- `.github/scripts/orchestrator.py`
- `.github/scripts/gitlab_mirror.py`
- `.github/scripts/config.py`
- `.github/scripts/github_api.py`
- `.github/scripts/discover_repos.py`
- `.github/scripts/sync_mirror.py`
- `.github/scripts/ensure_branches.py`
- `.github/scripts/merge_into_product.py`
- `.github/scripts/promote_ff_only.py`
- `.github/scripts/issues.py`
- `.github/scripts/summary.py`
