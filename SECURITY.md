# Security

This repository orchestrates GitHub/GitLab operations across multiple orgs using
a GitHub App and Bitwarden Secrets Manager. The guidance below provides a
tailored threat model and mitigations for this codebase.

## Threat Model

### Assets
- GitHub App private key and App ID
- GitHub App installation tokens
- GitLab API token
- Org identifiers and branch configuration
- Repo discovery cache
- Workflow integrity (what automation does to repos)

### Trust Boundaries
- GitHub Actions runner environment
- Bitwarden Secrets Manager CLI (`bws`)
- GitHub/GitLab APIs
- Actions cache storage

### Attack Surfaces
- Workflow inputs and env variables
- Secret materialization (files + logs)
- API calls via GitHub/GitLab tokens
- Cached data reuse
- External tools (`bws`, `git`, `curl`)

### Key Risks
- Secret leakage in logs, outputs, or artifacts
- Overly broad token scopes or workflow permissions
- Unsafe inputs causing unintended repo actions
- Supply‑chain compromise of actions/tools
- Cache poisoning or stale data
- Wrong org selection in multi‑org runs

## Mitigations Checklist

### A) Secret Handling
- [ ] Secrets are written to temp files under `${RUNNER_TEMP}/bws`.
- [ ] All scripts consume `*_FILE` env vars only (no inline secrets).
- [ ] `umask 077` + `chmod 600` applied for secret files.
- [ ] `::add-mask::` used for any secret output lines.
- [ ] Cleanup removes temp files and clears env vars after runs.
- [ ] No secrets uploaded to caches or artifacts.

### B) Least Privilege
- [ ] GitHub App permissions limited to **contents**, **metadata**, **issues**.
- [ ] Workflow/job permissions use minimal scopes.
- [ ] GitLab token has `api` scope only.

### C) Input Validation
- [ ] `INPUT_REPO` is validated before use.
- [ ] Repo filters reject unsafe characters (no `/`, spaces, dot‑prefix).
- [ ] Branch names validated before use.

### D) Cache Safety
- [ ] Cache contains only repo names (no secrets).
- [ ] Cache size is bounded and validated before use.
- [ ] `clear_cache` + `REPO_CACHE_TTL_DISCOVERY` enforced.

### E) Supply‑Chain Hygiene
- [ ] `bws` download is pinned by version and sha256.
- [ ] Actions use pinned versions (no `@main`).
- [ ] No network downloads without checksums.

### F) Operational Safety
- [ ] Fail fast on missing required env vars.
- [ ] Non‑interactive `git` use (`GIT_TERMINAL_PROMPT=0`).
- [ ] Cleanup runs with `if: always()`.

### G) Multi‑Org Safety
- [ ] Matrix‑based org selection ensures only one org file is used per run.
- [ ] Org mapping validated at runtime (fails closed on mismatch).

## Cache Design

This repo uses two on-runner caches under `${GITHUB_WORKSPACE}/.cache`:
- `repo-discovery.json`: list of repos for org discovery.
- `repo-metadata.json`: per-repo metadata, ref SHAs, and GitLab status (non-secret).

TTLs are controlled by repo variables:
- `REPO_CACHE_TTL_DISCOVERY`: discovery cache TTL (seconds).
- `REPO_CACHE_TTL_META`: repo metadata + ref SHA cache TTL (seconds).
- `REPO_CACHE_TTL_GITLAB_PROJ`: GitLab project existence cache TTL (seconds).
- `REPO_CACHE_TTL_GITLAB_BRANCH`: GitLab branch/protection cache TTL (seconds).

Caches must never store secrets. Use `clear_cache` or the "Clear Repo Caches" workflow to force refresh.

## Residual Risks to Monitor

- Bitwarden API outages (e.g., 503) may block runs.
- Excess GitHub App permissions can increase blast radius.
- Cache poisoning if cache is reused incorrectly.

## Optional Hardening (If Needed)

- Preflight check for GitHub App token scopes.
- Rate‑limit guardrails for API usage.
- Audit logging summary for changes per run.
