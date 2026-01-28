# Security

This repository orchestrates GitHub/GitLab operations across multiple orgs using
a GitHub App and Bitwarden Secrets Manager. The guidance below provides a
tailored threat model and mitigations for this codebase.

## Threat Model

### Assets
- GitHub App private key and App ID
- GitHub App installation tokens
- Cloudflare worker webhook secret
- Org identifiers and branch configuration
- Workflow integrity (what automation does to repos)

### Trust Boundaries
- GitHub Actions runner environment
- Bitwarden Secrets Manager CLI (`bws`)
- GitHub/GitLab APIs

### Attack Surfaces
- Workflow inputs and env variables
- Secret materialization (files + logs)
- API calls via GitHub tokens
- External tools (`bws`, `git`, `curl`)

### Key Risks
- Secret leakage in logs, outputs, or artifacts
- Overly broad token scopes or workflow permissions
- Unsafe inputs causing unintended repo actions
- Supply‑chain compromise of actions/tools
- Wrong org selection in multi‑org runs

## Mitigations Checklist

### A) Secret Handling
- [ ] Secrets are written to temp files under `${RUNNER_TEMP}/bws`.
- [ ] All scripts consume `*_FILE` env vars only (no inline secrets).
- [ ] `umask 077` + `chmod 600` applied for secret files.
 
- [ ] Cleanup removes temp files and clears env vars after runs.
 

### B) Least Privilege
- [ ] GitHub App permissions limited to **contents**, **metadata**, **issues**.
- [ ] Workflow/job permissions use minimal scopes.
- [ ] Worker webhook secret stored only in BWS and not logged.

### C) Input Validation
- [ ] `INPUT_REPO` is validated before use.
- [ ] Repo filters reject unsafe characters (no `/`, spaces, dot‑prefix).
- [ ] Branch names validated before use.
- [ ] Event allowlist enforced for workflow_dispatch.
- [ ] `job_type` required and validated against schema.

### D) Supply‑Chain Hygiene
- [ ] `bws` download is pinned by version and sha256.
- [ ] Actions use pinned versions (no `@main`).
- [ ] No network downloads without checksums.
- [ ] Python runtime pinned via `actions/setup-python` to latest stable.

### E) Operational Safety
- [ ] Fail fast on missing required env vars.
- [ ] Non‑interactive `git` use (`GIT_TERMINAL_PROMPT=0`).
- [ ] Cleanup runs with `if: always()`.

### F) Multi‑Org Safety
- [ ] Matrix‑based org selection ensures only one org file is used per run.
- [ ] Org mapping validated at runtime (fails closed on mismatch).

## Residual Risks to Monitor

- Bitwarden API outages (e.g., 503) may block runs.
- Excess GitHub App permissions can increase blast radius.

## Optional Hardening (If Needed)

- Preflight check for GitHub App token scopes.
- Rate‑limit guardrails for API usage.
- Audit logging summary for changes per run.
