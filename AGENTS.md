# AGENTS.md (repo guidance)

## Repository purpose
Shared GitHub Actions workflows, scripts, and composite actions used by org-specific wrapper repos.

## Non-negotiables
- No org-specific data or secrets in this repo.
- Third-party `uses:` references must be pinned to a commit SHA.
- Wrapper repos must reference shared workflows by release tag (for example, `v0.0.1`).
- Keep permissions minimal (`contents: read` by default).
- All shared workflows must validate event context against `configs/event-allowlist.json`.
- Shared workflows must pin `actions/setup-python` to the latest stable Python release.
- Fork drift polling is initiated by the Worker cron; no dedicated polling repos are used.
- Workflow-level permissions must be `{}`; set minimal permissions per job.

## Security
- Do not print secrets.
- BWS secrets must be handled via files (`*_FILE`), not exported env values.
- Inputs must include `job_type` and pass schema validation.
- Event validation must check `sender` type and GitHub App id.

## Workflow policy
- Reusable workflows only (`workflow_call`).
- No `workflow_dispatch` in shared workflows unless explicitly required.

## Release tags: creation, push, and roll-forward
Tags are the contract for wrapper repos. Do not move tags after publication.

### Helper script (preferred)
Use the repo helper to roll a new tag and update workflow allowlists:
```bash
./roll-tags.sh --v0.0.2
```

### Create + push a new tag (in gh-actions-shared)
1) Make the workflow/script changes in `main` and update `allowed_refs` to include the new tag.
2) Ensure workflows pass linting/tests.
3) Create an annotated tag on the exact commit you want wrappers to consume:
   ```bash
   git tag -a v0.0.1 -m "gh-actions-shared v0.0.1"
   git push origin v0.0.1
   ```

### Roll forward to a new tag
1) Make changes on `main` and update `allowed_refs` to include the **new** tag.
2) Create and push a new tag (e.g., `v0.0.2`).
3) Update wrapper repos to use `@v0.0.2` and `shared-ref: v0.0.2`.
4) Keep the previous tag in `allowed_refs` during rollout for fast rollback.
5) After stabilization, remove older tags from `allowed_refs` if policy requires a single active tag.

### Rollback guidance
If you must rollback, point wrappers back to the previous tag and keep it in `allowed_refs`.
Do not delete or re-point tags without explicit approval.
