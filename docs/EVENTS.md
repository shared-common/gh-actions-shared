# Events

## Allowed event types
The shared workflows only accept the following:
- `workflow_dispatch` with `inputs.dispatch_action`: `orchestrator`, `discover`, `summary`, `repository`, `fork`, `polling`

The allowlist is defined in `configs/event-allowlist.json` and enforced by
`scripts/validate_event.py`.

`workflow_dispatch` inputs must include:
- `dispatch_action` (must match allowlist)
- `app_id` (must match `GH_ORG_SHARED_APP_ID`)
- `repo_full_name` for repo-mutation workflows (`orchestrator`, `repository`, `fork`, `polling`)

> Fork drift polling is initiated by the Cloudflare Worker
> and dispatched to the private wrapper repos via `workflow_dispatch`.

Standalone wrapper `sync.yml` runs on `schedule`/manual `workflow_dispatch` and does not use
`inputs.dispatch_action` or `inputs.event_payload`.

## Payload schema
The `workflow_dispatch` payload (`inputs.event_payload`) is validated against `configs/inputs.schema.json`.
Required fields:
- `repo_full_name` (format: `<org>/<repo>`)
- `job_type` (`create`, `polling`, `sync`)

Optional fields:
- `gitlab_group_path` (if omitted, shared create/bootstrap workflows backfill it from `GL_MAPPING_JSON`)
- `repo_default_branch`
- `repo_is_fork`
- `repo_parent_full_name`
- `repo_parent_default_branch`

All payloads are JSON objects; invalid payloads fail closed.

> If `repo_parent_full_name` is provided, `repo_parent_default_branch` **must** be set
> (this supports fork parents whose default branch is not `main`).
