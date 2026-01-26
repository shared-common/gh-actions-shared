# Events

## Allowed event types
The shared workflows only accept the following:
- `repository_dispatch` with actions: `orchestrator`, `discover`, `summary`
- `schedule` with action label `poller` (wrapper passes `expected-event-action: poller`)

The allowlist is defined in `configs/event-allowlist.json` and enforced by
`scripts/validate_event.py`.

## Payload schema
The `repository_dispatch` payload is validated against `configs/inputs.schema.json`.
Required fields:
- `repo_full_name` (format: `<org>/<repo>`)
- `job_type` (`create`, `polling`, `sync`)

Optional fields:
- `repo_default_branch`
- `repo_is_fork`
- `repo_parent_full_name`
- `repo_parent_default_branch`

All payloads are JSON objects; invalid payloads fail closed.
