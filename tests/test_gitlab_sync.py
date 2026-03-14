import sys
import unittest
from pathlib import Path
from unittest import mock

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / ".github" / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import gitlab_sync  # noqa: E402
import gitlab_sync_profile  # noqa: E402
from branch_policy import BranchPolicy, BranchSpec  # noqa: E402


def make_policy() -> BranchPolicy:
    specs = [
        BranchSpec("GIT_BRANCH_MAIN", "main", "mcr/main", "upstream", True),
        BranchSpec("GIT_BRANCH_STAGING", "staging", "mcr/staging", "main", True),
        BranchSpec("GIT_BRANCH_RELEASE", "release", "mcr/release", "main", True),
        BranchSpec("GIT_BRANCH_SNAPSHOT", "snapshot", "mcr/snapshot", "main", False),
        BranchSpec("GIT_BRANCH_FEATURE", "feature/initial", "mcr/feature/initial", "main", False),
    ]
    return BranchPolicy(prefix="mcr", order=specs, by_env={spec.name_env: spec for spec in specs})


class GitlabSyncTests(unittest.TestCase):
    def test_build_tracked_branches_uses_github_prefix(self):
        tracked = gitlab_sync.build_tracked_branches(make_policy())
        self.assertEqual(
            tracked,
            {
                "github/mcr/main": "mcr/main",
                "github/mcr/staging": "mcr/staging",
            },
        )

    def test_select_sync_sources_prefers_tracked_ref_for_sync(self):
        selected = gitlab_sync.select_sync_sources(
            {"job_type": "sync", "ref": "refs/heads/mcr/staging"},
            ["mcr/main", "mcr/staging"],
        )
        self.assertEqual(selected, ["mcr/staging"])

    def test_select_sync_sources_uses_all_tracked_for_create(self):
        selected = gitlab_sync.select_sync_sources(
            {"job_type": "create", "ref": None},
            ["mcr/main", "mcr/staging"],
        )
        self.assertEqual(selected, ["mcr/main", "mcr/staging"])

    def test_resolve_gitlab_target_maps_upstream_profile(self):
        values = {
            "GL_GROUP_TOP_UPSTREAM": "seedbed",
            "GL_GROUP_SUB_CANONICAL": "canonical",
            "GL_BRIDGE_FORK_USER_SEEDBED": "seedbed-user",
            "GL_PAT_FORK_SEEDBED_SVC": "seedbed-token",
            "GL_BASE_URL": "https://gitlab.example",
        }
        with mock.patch.object(gitlab_sync, "require_secret", side_effect=lambda name: values[name]):
            target = gitlab_sync.resolve_gitlab_target("upstream", "demo")
        self.assertEqual(target.project_path, "seedbed/canonical/demo")
        self.assertEqual(target.git_username, "seedbed-user")
        self.assertEqual(target.api_token, "seedbed-token")

    def test_resolve_gitlab_target_maps_derived_profile(self):
        values = {
            "GL_GROUP_TOP_DIVERGE": "derived",
            "GL_GROUP_SUB_XF_SECOPS": "secops",
            "GL_BRIDGE_FORK_USER_DERIVED": "derived-user",
            "GL_PAT_FORK_DERIVED_SVC": "derived-token",
            "GL_BASE_URL": "https://gitlab.example",
        }
        with mock.patch.object(gitlab_sync, "require_secret", side_effect=lambda name: values[name]):
            target = gitlab_sync.resolve_gitlab_target("xf-secops", "demo")
        self.assertEqual(target.project_path, "derived/secops/demo")
        self.assertEqual(target.git_username, "derived-user")
        self.assertEqual(target.api_token, "derived-token")

    def test_should_force_retry_matches_non_fast_forward_errors(self):
        self.assertTrue(gitlab_sync._should_force_retry("! [rejected] main -> main (non-fast-forward)"))
        self.assertTrue(gitlab_sync._should_force_retry("remote rejected ... fetch first"))
        self.assertFalse(gitlab_sync._should_force_retry("authentication failed"))

    def test_required_bws_secrets_are_profile_scoped(self):
        self.assertEqual(
            gitlab_sync_profile.required_bws_secrets("xf-main"),
            (
                "GL_BASE_URL",
                "GIT_BRANCH_PREFIX",
                "GIT_BRANCH_MAIN",
                "GIT_BRANCH_STAGING",
                "GIT_BRANCH_RELEASE",
                "GIT_BRANCH_SNAPSHOT",
                "GIT_BRANCH_FEATURE",
                "GL_GROUP_TOP_DIVERGE",
                "GL_GROUP_SUB_XF_MAIN",
                "GL_BRIDGE_FORK_USER_DERIVED",
                "GL_PAT_FORK_DERIVED_SVC",
            ),
        )
        self.assertEqual(
            gitlab_sync_profile.required_bws_secrets("upstream"),
            (
                "GL_BASE_URL",
                "GIT_BRANCH_PREFIX",
                "GIT_BRANCH_MAIN",
                "GIT_BRANCH_STAGING",
                "GIT_BRANCH_RELEASE",
                "GIT_BRANCH_SNAPSHOT",
                "GIT_BRANCH_FEATURE",
                "GL_GROUP_TOP_UPSTREAM",
                "GL_GROUP_SUB_CANONICAL",
                "GL_BRIDGE_FORK_USER_SEEDBED",
                "GL_PAT_FORK_SEEDBED_SVC",
            ),
        )

    def test_protect_branches_updates_force_push_when_existing_branch_disallows_it(self):
        calls = []

        def fake_request(method, _base_url, path, _token, payload=None, **_kwargs):
            calls.append((method, path, payload))
            if method == "GET":
                return [{"name": "github/mcr/main", "allow_force_push": False}]
            return {"name": "github/mcr/main", "allow_force_push": True}

        with mock.patch.object(gitlab_sync, "_gitlab_request", side_effect=fake_request):
            changed = gitlab_sync._protect_branches(
                "https://gitlab.example",
                "token",
                123,
                ["github/mcr/main"],
                allow_force_push=True,
            )

        self.assertEqual(changed, ["github/mcr/main"])
        self.assertEqual(calls[1][0], "PATCH")
        self.assertIn("allow_force_push=true", calls[1][1])

    def test_push_branch_retries_with_force_with_lease_when_needed(self):
        run_calls = []

        def fake_run(cmd, check, stdout, stderr):
            run_calls.append(cmd)
            if len(run_calls) == 1:
                return mock.Mock(returncode=1, stderr=b"! [rejected] branch -> branch (non-fast-forward)")
            return mock.Mock(returncode=0, stderr=b"")

        with mock.patch.object(gitlab_sync, "_lfs_push", return_value=None):
            with mock.patch.object(gitlab_sync.subprocess, "run", side_effect=fake_run):
                gitlab_sync._push_branch(
                    "/tmp/repo.git",
                    "https://gitlab.example/repo.git",
                    "mcr/main",
                    "github/mcr/main",
                    remote_name="gitlab",
                    lfs_ref="mcr/main",
                    secrets=(),
                    allow_force_if_needed=True,
                    expected_remote_sha="a" * 40,
                )

        self.assertEqual(run_calls[0][3], "push")
        self.assertIn("--force-with-lease=refs/heads/github/mcr/main:" + ("a" * 40), run_calls[1])


if __name__ == "__main__":
    unittest.main()
