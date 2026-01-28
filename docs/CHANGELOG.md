# Changelog

## 2026-01-26
- Added event allowlist enforcement in shared workflows.
- Hardened input validation and branch policy parsing.
- Expanded JSON schema validation and summary output.
- Improved BWS secret handling and dispatch error reporting.
- Pinned actions/checkout and actions/setup-python (v6.1.0); enforced Python 3.14.2.
- Tightened GH_INSTALL_JSON parsing errors and aligned docs/AGENTS.
- Worker cron now drives fork drift checks (no polling repos).
- Workflow dispatch replaces repository_dispatch in wrapper repos.
