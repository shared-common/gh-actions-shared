# Architecture

## Overview
This repository provides reusable GitHub Actions workflows used by multiple org‑specific
wrapper repos. The wrappers only pass inputs and secrets; **all orchestration logic
lives here**.

## Components
- **Reusable workflows** (`*-core.yml`):
  - `orchestrator-core`: branch creation/update
  - `gitlab-create-core`: GitLab project/bootstrap/mirror/protection for a single repo
  - `gitlab-sync-core`: hourly/manual GitLab reconciliation across all repos in an org
  - `discover-core`: enumerate org repos for discovery runs
  - `summary-core`: render summaries for job outputs
- **Composite actions**: BWS secret fetch, JSON validation, dispatch helper, job summary.
- **Python scripts**: validation, GitHub App token generation, branch operations, and
  event normalization.

## Data flow
1. GitHub App webhook → Cloudflare Worker
2. Worker sends `workflow_dispatch` to **private** wrapper repo
3. Worker cron detects fork drift and dispatches `polling.yml` as needed
4. Wrapper `sync.yml` runs hourly per org (and manually on demand) to reconcile tracked GitHub/GitLab branches
5. Wrapper invokes shared workflows with event context + payload for bootstrap flows
6. Shared workflows validate the event, run branch operations, then run GitLab create/bootstrap or org-wide sync

Wrapper mutation workflows serialize by `repo_full_name` so a single repo cannot run
overlapping `repository`/`fork`/`orchestrator`/`polling` jobs.

## Security boundaries
- Secrets are fetched via BWS and written to `*_FILE` paths only.
- Events are validated against allowlists and org mappings.
- Branch policies are enforced from `configs/branch-policy.json`.
