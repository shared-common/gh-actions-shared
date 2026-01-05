from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

from config import Config, load_config
from discover_repos import discover_fork_repos
from github_api import GitHubApi, GitHubApiError
from issues import create_or_update_issue
from promote_ff_only import compare_refs, ff_update
from summary import format_summary
from sync_mirror import sync_mirror
from ensure_branches import ensure_branch
from secret_env import read_required_secret_file
from repo_metadata_cache import (
    get_ref_sha,
    get_repo_meta,
    load_cache,
    save_cache,
    set_ref_sha,
    set_repo_meta,
)


WORKFLOW_CRON_1 = "17 3 * * *"
WORKFLOW_CRON_2 = "17 23 * * *"


def _issue_body(title: str, details: str) -> str:
    return (
        f"{title}\n\n"
        f"Details:\n{details}\n\n"
        "This issue was created by the org fork orchestrator. "
        "Resolve the divergence manually, then re-run the workflow."
    )


def _comment_body(run_id: str, details: str) -> str:
    return f"Run `{run_id}` update:\n\n{details}"


def _format_issue_action(issue: Optional[Dict[str, Any]]) -> str:
    if not issue:
        return "none"
    return f"{issue.get('action')} #{issue.get('number')}"


def _compare_status(compare_data: Dict[str, Any]) -> str:
    status = compare_data.get("status")
    if status == "behind":
        return "behind"
    if status == "ahead":
        return "ahead"
    if status == "identical":
        return "identical"
    if status == "diverged":
        return "diverged"
    return status or "unknown"


def _ref_sha(api: GitHubApi, owner: str, repo: str, ref: str) -> str:
    resp = api.request("GET", f"/repos/{owner}/{repo}/git/ref/heads/{ref}")
    if not isinstance(resp.data, dict):
        raise GitHubApiError(resp.status, "Unexpected ref response")
    sha = resp.data.get("object", {}).get("sha")
    if not sha:
        raise GitHubApiError(resp.status, "Missing ref SHA")
    return sha


def _ref_sha_optional(api: GitHubApi, owner: str, repo: str, ref: str) -> Optional[str]:
    try:
        return _ref_sha(api, owner, repo, ref)
    except GitHubApiError as exc:
        if exc.status == 404:
            return None
        raise


def _select_mirror_branch(api: GitHubApi, owner: str, repo: str, repo_details: Dict[str, Any]) -> str:
    parent = repo_details.get("parent")
    if isinstance(parent, dict):
        parent_default = parent.get("default_branch")
        if isinstance(parent_default, str) and parent_default:
            if _ref_sha_optional(api, owner, repo, parent_default):
                return parent_default
    repo_default = repo_details.get("default_branch")
    if isinstance(repo_default, str) and repo_default:
        if _ref_sha_optional(api, owner, repo, repo_default):
            return repo_default
    for candidate in ("main", "master"):
        if _ref_sha_optional(api, owner, repo, candidate):
            return candidate
    raise GitHubApiError(404, "Missing mirror branch (default/main/master)")


def _parent_sha(api: GitHubApi, owner: str, repo: str, sha: str) -> Optional[str]:
    resp = api.request("GET", f"/repos/{owner}/{repo}/git/commits/{sha}")
    if not isinstance(resp.data, dict):
        raise GitHubApiError(resp.status, "Unexpected commit response")
    parents = resp.data.get("parents")
    if isinstance(parents, list) and parents:
        parent = parents[0]
        if isinstance(parent, dict) and parent.get("sha"):
            return parent["sha"]
    return None


def _validate_branch_name(name: str) -> None:
    if not name:
        raise ValueError("Branch name is empty")
    if name.strip("/") != name:
        raise ValueError(f"Branch name has leading/trailing slash: {name}")
    if "//" in name:
        raise ValueError(f"Branch name contains //: {name}")


def _validate_branch_config(cfg: Config) -> None:
    for name in (
        cfg.branch_prefix,
        cfg.product_branch,
        cfg.staging_branch,
        cfg.snapshot_branch,
        cfg.feature_branch,
    ):
        _validate_branch_name(name)


def _force_update(api: GitHubApi, owner: str, repo: str, ref: str, sha: str) -> None:
    api.patch(
        f"/repos/{owner}/{repo}/git/refs/heads/{ref}",
        payload={"sha": sha, "force": True},
    )


def _head_sha(compare_data: Dict[str, Any], fallback: str) -> str:
    commits = compare_data.get("commits")
    if isinstance(commits, list) and commits:
        last = commits[-1]
        if isinstance(last, dict) and last.get("sha"):
            return last["sha"]
    return fallback


def _repo_has_parent(repo: Dict[str, Any]) -> bool:
    return bool(repo.get("parent"))



def process_repo(
    api: GitHubApi,
    cfg: Config,
    repo: Dict[str, Any],
    run_id: str,
    cache: Dict[str, Any],
    ttl_meta: int,
) -> Dict[str, Any]:
    owner = cfg.org
    name = repo.get("name")
    result: Dict[str, Any] = {"name": name}

    if not name:
        result["notes"] = ["Skipped: missing repo name"]
        return result

    try:
        repo_details = get_repo_meta(cache, owner, name, ttl_meta)
        if repo_details is None:
            repo_details_resp = api.request("GET", f"/repos/{owner}/{name}")
            repo_details = repo_details_resp.data if isinstance(repo_details_resp.data, dict) else {}
            set_repo_meta(cache, owner, name, repo_details)
    except GitHubApiError as exc:
        result["notes"] = [f"Skipped: failed to fetch repo metadata ({exc.status})"]
        return result
    if repo_details.get("archived") or repo_details.get("disabled"):
        result["notes"] = ["Skipped: archived or disabled"]
        return result

    if not repo_details.get("fork") or not _repo_has_parent(repo_details):
        result["notes"] = ["Skipped: not a fork or missing upstream"]
        return result

    try:
        mirror = _select_mirror_branch(api, owner, name, repo_details)
    except GitHubApiError as exc:
        result["notes"] = [f"Skipped: missing mirror branch ({exc.status})"]
        return result
    result["mirror_branch"] = mirror
    product = cfg.product_ref
    staging = cfg.staging_ref
    snapshot = cfg.snapshot_ref
    feature = cfg.feature_ref

    # Step 1: mirror sync
    mirror_sync = sync_mirror(api, owner, name, mirror)
    if mirror_sync["status"] != "ok":
        issue = create_or_update_issue(
            api,
            owner,
            name,
            "[automation] mirror sync failed",
            _issue_body("Mirror sync failed", json.dumps(mirror_sync, indent=2)),
            _comment_body(run_id, json.dumps(mirror_sync, indent=2)),
        )
        result.update(
            {
                "mirror_sync": f"error ({mirror_sync.get('code')})",
                "issue": _format_issue_action(issue),
            }
        )
        result["notes"] = ["Skipped: mirror sync failed"]
        return result
    result["mirror_sync"] = mirror_sync.get("message", "ok")

    # Step 2: ensure branches exist (create-only)
    try:
        mirror_sha = get_ref_sha(cache, owner, name, mirror, ttl_meta)
        if mirror_sha is None:
            mirror_sha = _ref_sha(api, owner, name, mirror)
            set_ref_sha(cache, owner, name, mirror, mirror_sha)
    except GitHubApiError as exc:
        issue = create_or_update_issue(
            api,
            owner,
            name,
            "[automation] branch bootstrap failed",
            _issue_body("Failed to read mirror ref", str(exc)),
            _comment_body(run_id, str(exc)),
        )
        result.update(
            {
                "branch_bootstrap": "error",
                "branch_bootstrap_error": str(exc),
                "issue": _format_issue_action(issue),
            }
        )
        result["notes"] = ["Skipped: failed to read mirror ref"]
        return result

    branch_results: Dict[str, Any] = {}
    try:
        branch_results["product"] = ensure_branch(api, owner, name, product, mirror_sha)
        product_sha_before = get_ref_sha(cache, owner, name, product, ttl_meta)
        if product_sha_before is None:
            product_sha_before = _ref_sha(api, owner, name, product)
            set_ref_sha(cache, owner, name, product, product_sha_before)
        branch_results["staging"] = ensure_branch(api, owner, name, staging, product_sha_before)
        staging_sha = get_ref_sha(cache, owner, name, staging, ttl_meta)
        if staging_sha is None:
            staging_sha = _ref_sha(api, owner, name, staging)
            set_ref_sha(cache, owner, name, staging, staging_sha)
        branch_results["snapshot"] = ensure_branch(api, owner, name, snapshot, staging_sha)
        branch_results["feature"] = ensure_branch(api, owner, name, feature, product_sha_before)
        result["branch_bootstrap"] = json.dumps(branch_results)
    except GitHubApiError as exc:
        issue = create_or_update_issue(
            api,
            owner,
            name,
            "[automation] branch bootstrap failed",
            _issue_body("Branch bootstrap failed", str(exc)),
            _comment_body(run_id, str(exc)),
        )
        result.update(
            {
                "branch_bootstrap": "error",
                "branch_bootstrap_error": str(exc),
                "issue": _format_issue_action(issue),
            }
        )
        result["notes"] = ["Skipped: branch bootstrap failed"]
        return result

    # Presence summary (mask-safe)
    presence = {}
    for label, ref in (
        ("product", product),
        ("staging", staging),
        ("snapshot", snapshot),
        ("feature", feature),
    ):
        try:
            sha = get_ref_sha(cache, owner, name, ref, ttl_meta)
            if sha is None:
                sha = _ref_sha(api, owner, name, ref)
                set_ref_sha(cache, owner, name, ref, sha)
            presence[label] = "present"
        except GitHubApiError as exc:
            if exc.status == 404:
                presence[label] = "missing"
            else:
                presence[label] = f"error ({exc.status})"
    result["branch_presence"] = json.dumps(presence)
    result["mirror_branch"] = mirror

    # Step 3: enforce product == mirror (no local commits allowed)
    compare_pm = compare_refs(api, owner, name, product, mirror)
    status_pm = _compare_status(compare_pm)
    if status_pm == "identical":
        result["product_merge"] = "up_to_date"
    elif status_pm == "behind":
        try:
            ff_update(api, owner, name, product, _head_sha(compare_pm, mirror_sha))
            result["product_merge"] = "fast-forwarded"
        except GitHubApiError:
            _force_update(api, owner, name, product, mirror_sha)
            result["product_merge"] = "reset (ff failed)"
    else:
        _force_update(api, owner, name, product, mirror_sha)
        result["product_merge"] = f"reset ({status_pm})"

    # Step 4: keep staging + feature at least one commit behind product
    product_sha_after = get_ref_sha(cache, owner, name, product, ttl_meta)
    if product_sha_after is None:
        product_sha_after = _ref_sha(api, owner, name, product)
        set_ref_sha(cache, owner, name, product, product_sha_after)
    product_changed = product_sha_after != product_sha_before
    result["product_changed"] = "yes" if product_changed else "no"

    if product_changed:
        parent_sha = _parent_sha(api, owner, name, product_sha_after)
        downstream_target = parent_sha or product_sha_after
        result["downstream_target"] = "parent" if parent_sha else "product (no parent)"

        compare_ps = compare_refs(api, owner, name, staging, downstream_target)
        status_ps = _compare_status(compare_ps)
        compare_summary = {
            "status": status_ps,
            "ahead_by": compare_ps.get("ahead_by"),
            "behind_by": compare_ps.get("behind_by"),
            "base": compare_ps.get("base_commit", {}).get("sha")
            if isinstance(compare_ps.get("base_commit"), dict)
            else None,
            "head": compare_ps.get("head_commit", {}).get("sha")
            if isinstance(compare_ps.get("head_commit"), dict)
            else None,
        }
        if status_ps == "identical":
            result["staging_promo"] = "already at target"
        elif status_ps == "behind":
            ff_update(api, owner, name, staging, _head_sha(compare_ps, downstream_target))
            result["staging_promo"] = "fast-forwarded to target"
        else:
            _force_update(api, owner, name, staging, downstream_target)
            result["staging_promo"] = f"reset to target ({status_ps})"

        compare_fs = compare_refs(api, owner, name, feature, downstream_target)
        status_fs = _compare_status(compare_fs)
        if status_fs == "identical":
            result["feature_promo"] = "already at target"
        elif status_fs == "behind":
            ff_update(api, owner, name, feature, _head_sha(compare_fs, downstream_target))
            result["feature_promo"] = "fast-forwarded to target"
        else:
            _force_update(api, owner, name, feature, downstream_target)
            result["feature_promo"] = f"reset to target ({status_fs})"
    else:
        result["staging_promo"] = "skipped (no product change)"
        result["feature_promo"] = "skipped (no product change)"
        compare_summary = {"status": "skipped"}

    result["staging_compare"] = json.dumps(compare_summary)
    # Step 5: snapshot is create-once; never update after bootstrap
    result["snapshot_promo"] = "unchanged (create-once policy)"

    return result


def main() -> int:
    token = read_required_secret_file("GITHUB_APP_TOKEN")
    cfg = load_config()
    _validate_branch_config(cfg)
    repo_filter = os.environ.get("INPUT_REPO") or None
    if repo_filter:
        repo_filter = repo_filter.strip() or None
    run_id = os.environ.get("GITHUB_RUN_ID", "unknown")

    api = GitHubApi(token=token)
    repos = discover_fork_repos(api, cfg.org, repo_filter)

    cache_path = os.environ.get("REPO_META_CACHE_PATH") or os.environ.get("REPO_CACHE_PATH")
    cache = load_cache(cache_path) if cache_path else {"version": 1, "orgs": {}}
    def _ttl(name: str, default: int) -> int:
        raw = os.environ.get(name, "").strip()
        if not raw:
            return default
        try:
            return int(raw)
        except ValueError:
            return default

    ttl_meta = _ttl("REPO_CACHE_TTL_META", 800)

    results: List[Dict[str, Any]] = []
    for repo in repos:
        results.append(process_repo(api, cfg, repo, run_id, cache, ttl_meta))
    if cache_path:
        save_cache(cache_path, cache)

    config_summary = {
        "org": cfg.org,
        "branch_prefix": cfg.branch_prefix,
        "mirror_branch": cfg.mirror_branch,
        "product_branch": cfg.product_branch,
        "staging_branch": cfg.staging_branch,
        "snapshot_branch": cfg.snapshot_branch,
        "feature_branch": cfg.feature_branch,
    }
    summary = format_summary(
        config_summary,
        [WORKFLOW_CRON_1, WORKFLOW_CRON_2],
        results,
    )
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        with open(summary_path, "a", encoding="utf-8") as handle:
            handle.write(summary)
            handle.write("\n")
    else:
        print(summary)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
