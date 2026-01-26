# Security

This repository enforces strict input validation and event allowlists before
performing any GitHub operations.

## Controls in place
- **Event allowlist**: `configs/event-allowlist.json` enforced by `validate_event.py`
- **Org validation**: org must exist in `GH_INSTALL_JSON`
- **Branch validation**: branch names validated against strict ref rules
- **Secrets via files**: `*_FILE` only, never printed
- **Pinned tooling**: bws CLI pinned by version + sha256

See the root `SECURITY.md` for the full threat model and mitigation checklist.
