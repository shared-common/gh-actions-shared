from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from discover_repos import discover_fork_repos
from github_api import GitHubApi, GitHubApiError
from logging_util import log_event, redact_text
from ref_validation import validate_ref_names
from secret_env import (
    ensure_file_env,
    has_env_or_file,
    read_optional_value,
    read_required_secret_file,
    read_required_value,
)


@dataclass(frozen=True)
class WorkerConfig:
    github_org: str
    branch_prefix: str
    product_branch: str
    staging_branch: str
    feature_branch: str
    release_branch: str
    webhook_url: str
    webhook_secret: str
    github_token: str
    repo_filter: Optional[str]

    @property
    def branches(self) -> List[str]:
        return [
            f"{self.branch_prefix}/{self.product_branch}",
            f"{self.branch_prefix}/{self.staging_branch}",
            f"{self.branch_prefix}/{self.feature_branch}/initial",
            f"{self.branch_prefix}/{self.release_branch}",
        ]


_REQUIRED_ENV = {
    "GH_ORG_SHARED",
    "GH_BRANCH_PREFIX",
    "GH_BRANCH_PRODUCT",
    "GH_BRANCH_STAGING",
    "GH_BRANCH_FEATURE",
    "GH_BRANCH_RELEASE",
    "CF_FORKS_WEBHOOK_URL",
    "CF_FORKS_WEBHOOK_SECRET",
    "GITHUB_APP_TOKEN",
}


def load_config() -> WorkerConfig:
    for name in _REQUIRED_ENV:
        ensure_file_env(name)
    missing = [name for name in _REQUIRED_ENV if not has_env_or_file(name)]
    if missing:
        raise ValueError(f"Missing required env vars: {', '.join(sorted(missing))}")
    return WorkerConfig(
        github_org=read_required_value("GH_ORG_SHARED", allow_env=False),
        branch_prefix=read_required_value("GH_BRANCH_PREFIX", allow_env=False),
        product_branch=read_required_value("GH_BRANCH_PRODUCT", allow_env=False),
        staging_branch=read_required_value("GH_BRANCH_STAGING", allow_env=False),
        feature_branch=read_required_value("GH_BRANCH_FEATURE", allow_env=False),
        release_branch=read_required_value("GH_BRANCH_RELEASE", allow_env=False),
        webhook_url=read_required_value("CF_FORKS_WEBHOOK_URL", allow_env=False),
        webhook_secret=read_required_secret_file("CF_FORKS_WEBHOOK_SECRET"),
        github_token=read_required_secret_file("GITHUB_APP_TOKEN"),
        repo_filter=read_optional_value("INPUT_REPO"),
    )


class WorkerWebhookError(RuntimeError):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status


def _delivery_id(repo: str, ref: str) -> str:
    run_id = os.environ.get("GITHUB_RUN_ID", "local")
    attempt = os.environ.get("GITHUB_RUN_ATTEMPT", "1")
    raw = f"{run_id}:{attempt}:{repo}:{ref}"
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return f"gha-{digest}"


def _sign(secret: str, body: bytes) -> str:
    digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def _request_with_retry(req: urllib.request.Request) -> Dict[str, Any]:
    max_attempts = 4
    for attempt in range(1, max_attempts + 1):
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                status = resp.status
                body = resp.read().decode("utf-8") if resp.readable() else ""
                return {"status": status, "body": body}
        except urllib.error.HTTPError as exc:
            status = exc.code
            body = exc.read().decode("utf-8") if exc.fp else ""
            if status in (429, 500, 502, 503, 504):
                time.sleep(min(2**attempt, 10))
                continue
            raise WorkerWebhookError(status, body or "Worker webhook error") from exc
        except urllib.error.URLError as exc:
            if attempt == max_attempts:
                raise WorkerWebhookError(0, f"Network error: {exc}") from exc
            time.sleep(min(2**attempt, 10))
    raise WorkerWebhookError(0, "Worker webhook retry limit exceeded")


def _send_webhook(cfg: WorkerConfig, repo: str, ref: str) -> Dict[str, Any]:
    payload = {
        "ref": f"refs/heads/{ref}",
        "repository": {"name": repo, "owner": {"login": cfg.github_org}},
    }
    body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    req = urllib.request.Request(
        url=cfg.webhook_url,
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "User-Agent": "gh-actions-upstream-worker",
            "X-GitHub-Event": "push",
            "X-GitHub-Delivery": _delivery_id(repo, ref),
            "X-Hub-Signature-256": _sign(cfg.webhook_secret, body),
        },
    )
    return _request_with_retry(req)


def _validate_branches(cfg: WorkerConfig) -> None:
    validate_ref_names(
        (
            cfg.branch_prefix,
            cfg.product_branch,
            cfg.staging_branch,
            cfg.feature_branch,
            cfg.release_branch,
        ),
        label="branch",
    )
    validate_ref_names(cfg.branches, label="ref")


def _is_fork(api: GitHubApi, org: str, repo: str) -> bool:
    try:
        resp = api.get(f"/repos/{org}/{repo}")
    except GitHubApiError:
        return False
    data = resp.data if isinstance(resp.data, dict) else {}
    return bool(data.get("fork") and data.get("parent"))


def main() -> int:
    cfg = load_config()
    _validate_branches(cfg)
    api = GitHubApi(cfg.github_token)
    repos = discover_fork_repos(api, cfg.github_org, cfg.repo_filter)
    secrets_to_redact = [cfg.webhook_secret]
    total = 0
    failures: List[str] = []

    for repo in repos:
        name = repo.get("name")
        if not isinstance(name, str) or not name:
            continue
        if not _is_fork(api, cfg.github_org, name):
            continue
        for ref in cfg.branches:
            total += 1
            try:
                resp = _send_webhook(cfg, name, ref)
                log_event(
                    "worker_webhook",
                    repo=name,
                    ref=ref,
                    status=resp["status"],
                    body=redact_text(str(resp.get("body", ""))),
                )
            except WorkerWebhookError as exc:
                failures.append(f"{name}:{ref}:{exc.status}")
                log_event(
                    "worker_webhook_error",
                    repo=name,
                    ref=ref,
                    status=exc.status,
                    error=redact_text(str(exc)),
                )

    if failures:
        raise SystemExit(f"Worker webhook failures: {', '.join(failures)}")
    log_event("worker_webhook_complete", repos=len(repos), requests=total)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
