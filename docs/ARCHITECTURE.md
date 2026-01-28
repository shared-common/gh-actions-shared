# Architecture

## Overview
This repository provides reusable GitHub Actions workflows used by multiple org‑specific
wrapper repos. The wrappers only pass inputs and secrets; **all orchestration logic
lives here**.

## Components
- **Reusable workflows** (`*-core.yml`):
  - `orchestrator-core`: branch creation/update
  - `discover-core`: enumerate org repos for discovery runs
  - `summary-core`: render summaries for job outputs
- **Composite actions**: BWS secret fetch, JSON validation, dispatch helper, job summary.
- **Python scripts**: validation, GitHub App token generation, branch operations, and
  event normalization.

## Data flow
1. GitHub App webhook → Cloudflare Worker
2. Worker sends `workflow_dispatch` to **private** wrapper repo
3. Worker cron detects fork drift and dispatches `polling.yml` as needed
4. Wrapper invokes shared workflow with event context + payload
5. Shared workflow validates event, then performs the job

## Security boundaries
- Secrets are fetched via BWS and written to `*_FILE` paths only.
- Events are validated against allowlists and org mappings.
- Branch policies are enforced from `configs/branch-policy.json`.
