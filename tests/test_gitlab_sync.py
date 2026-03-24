import sys
import unittest
from pathlib import Path
from unittest import mock

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / ".github" / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import gitlab_sync  # noqa: E402
import gitlab_org_sync  # noqa: E402
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
            "GL_BRIDGE_FORK_USER_SEEDBED": "seedbed-user",
            "GL_PAT_FORK_SEEDBED_SVC": "seedbed-token",
            "GL_BASE_URL": "https://gitlab.example",
        }
        with mock.patch.object(gitlab_sync, "require_secret", side_effect=lambda name: values[name]):
            target = gitlab_sync.resolve_gitlab_target("upstream", "demo", "seedbed/canonical")
        self.assertEqual(target.project_path, "seedbed/canonical/demo")
        self.assertEqual(target.git_username, "seedbed-user")
        self.assertEqual(target.api_token, "seedbed-token")

    def test_resolve_gitlab_target_maps_derived_profile(self):
        values = {
            "GL_BRIDGE_FORK_USER_DERIVED": "derived-user",
            "GL_PAT_FORK_DERIVED_SVC": "derived-token",
            "GL_BASE_URL": "https://gitlab.example",
        }
        with mock.patch.object(gitlab_sync, "require_secret", side_effect=lambda name: values[name]):
            target = gitlab_sync.resolve_gitlab_target("xf-secops", "demo", "derived/secops")
        self.assertEqual(target.project_path, "derived/secops/demo")
        self.assertEqual(target.git_username, "derived-user")
        self.assertEqual(target.api_token, "derived-token")

    def test_should_force_retry_matches_non_fast_forward_errors(self):
        self.assertTrue(gitlab_sync._should_force_retry("! [rejected] main -> main (non-fast-forward)"))
        self.assertTrue(gitlab_sync._should_force_retry("remote rejected ... fetch first"))
        self.assertFalse(gitlab_sync._should_force_retry("authentication failed"))

    def test_required_bws_secrets_are_profile_scoped(self):
        self.assertEqual(
            gitlab_sync_profile.required_bws_secrets("xf-qubit", mode="sync"),
            (
                "GL_BASE_URL",
                "GL_MAPPING_JSON",
                "GIT_BRANCH_PREFIX",
                "GIT_BRANCH_MAIN",
                "GIT_BRANCH_STAGING",
                "GIT_BRANCH_RELEASE",
                "GIT_BRANCH_SNAPSHOT",
                "GIT_BRANCH_FEATURE",
                "GL_GROUP_TOP_ALEMBIC",
                "GL_GROUP_SUB_XF_QUBIT",
                "GL_BRIDGE_FORK_USER_ALEMBIC",
                "GL_PAT_FORK_ALEMBIC_SVC",
            ),
        )
        self.assertEqual(
            gitlab_sync_profile.required_bws_secrets("xf-main", mode="sync"),
            (
                "GL_BASE_URL",
                "GL_MAPPING_JSON",
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
            gitlab_sync_profile.required_bws_secrets("upstream", mode="sync"),
            (
                "GL_BASE_URL",
                "GL_MAPPING_JSON",
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

    def test_required_bws_secrets_include_github_app_when_requested(self):
        self.assertEqual(
            gitlab_sync_profile.required_bws_secrets("xf-main", include_github_app=True, mode="sync"),
            (
                "GL_BASE_URL",
                "GL_MAPPING_JSON",
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
                "GH_ORG_SHARED_APP_ID",
                "GH_ORG_SHARED_APP_PEM",
                "GH_INSTALL_JSON",
            ),
        )

    def test_resolve_profile_group_path(self):
        values = {
            "GL_GROUP_TOP_DIVERGE": "derived",
            "GL_GROUP_SUB_XF_SECOPS": "secops",
        }
        self.assertEqual(
            gitlab_sync_profile.resolve_profile_group_path("xf-secops", lambda name: values[name]),
            "derived/secops",
        )

    def test_resolve_profile_group_path_supports_qubit(self):
        values = {
            "GL_GROUP_TOP_ALEMBIC": "alembic",
            "GL_GROUP_SUB_XF_QUBIT": "gh-xf-qubit",
        }
        self.assertEqual(
            gitlab_sync_profile.resolve_profile_group_path("xf-qubit", lambda name: values[name]),
            "alembic/gh-xf-qubit",
        )

    def test_resolve_profile_values_supports_qubit(self):
        values = {
            "GL_BRIDGE_FORK_USER_ALEMBIC": "alembic-user",
            "GL_PAT_FORK_ALEMBIC_SVC": "alembic-token",
        }
        self.assertEqual(
            gitlab_sync_profile.resolve_profile_values("xf-qubit", lambda name: values[name]),
            ("alembic-user", "alembic-token"),
        )

    def test_org_sync_group_path_prefers_mapping_alias_key(self):
        mapping = '{"GH_ORG_XF_CHECKOUT":"derived/gh-xf-checkout"}'
        with mock.patch.dict("os.environ", {"GL_MAPPING_JSON_FILE": "/tmp/mapping"}, clear=False):
            with mock.patch.object(gitlab_org_sync, "require_secret", side_effect=lambda name: mapping if name == "GL_MAPPING_JSON" else "unused"):
                self.assertEqual(
                    gitlab_org_sync._resolve_gitlab_group_path("xf-checkout", "xf-checkout"),
                    "derived/gh-xf-checkout",
                )

    def test_org_sync_group_path_prefers_qubit_alias_key(self):
        mapping = '{"GH_ORG_XF_QUBIT":"alembic/gh-xf-qubit"}'
        with mock.patch.dict("os.environ", {"GL_MAPPING_JSON_FILE": "/tmp/mapping"}, clear=False):
            with mock.patch.object(gitlab_org_sync, "require_secret", side_effect=lambda name: mapping if name == "GL_MAPPING_JSON" else "unused"):
                self.assertEqual(
                    gitlab_org_sync._resolve_gitlab_group_path("xf-qubit", "xf-qubit"),
                    "alembic/gh-xf-qubit",
                )

    def test_require_gitlab_group_path_requires_nested_path(self):
        self.assertEqual(
            gitlab_sync.require_gitlab_group_path({"gitlab_group_path": "derived/gh-xf-main"}),
            "derived/gh-xf-main",
        )
        with self.assertRaises(SystemExit):
            gitlab_sync.require_gitlab_group_path({"gitlab_group_path": "derived"})

    def test_get_gitlab_group_id_falls_back_to_group_search(self):
        def fake_request(method, _base_url, path, _token, payload=None, **_kwargs):
            self.assertIsNone(payload)
            if method != "GET":
                self.fail("expected only GET calls")
            if path == "/groups/derived%2Fxf-main":
                raise gitlab_sync.ApiError(404, '{"message":"404 Group Not Found"}')
            if path == "/groups?search=xf-main&per_page=100&page=1":
                return [{"id": 321, "full_path": "derived/xf-main", "path": "xf-main"}]
            self.fail(f"unexpected path: {path}")

        with mock.patch.object(gitlab_sync, "_gitlab_request", side_effect=fake_request):
            group_id = gitlab_sync._get_gitlab_group_id("https://gitlab.example", "token", "derived/xf-main")

        self.assertEqual(group_id, 321)

    def test_get_gitlab_group_id_reports_project_path_conflict(self):
        def fake_request(method, _base_url, path, _token, payload=None, **_kwargs):
            self.assertIsNone(payload)
            if method != "GET":
                self.fail("expected only GET calls")
            if path == "/groups/team%2Fsubspace":
                raise gitlab_sync.ApiError(404, '{"message":"404 Group Not Found"}')
            if path == "/groups?search=subspace&per_page=100&page=1":
                return []
            if path == "/projects/team%2Fsubspace":
                return {"id": 88, "path_with_namespace": "team/subspace"}
            self.fail(f"unexpected path: {path}")

        with mock.patch.object(gitlab_sync, "_gitlab_request", side_effect=fake_request):
            with self.assertRaises(SystemExit) as exc:
                gitlab_sync._get_gitlab_group_id("https://gitlab.example", "token", "team/subspace")

        self.assertEqual(str(exc.exception), "GitLab path exists as a project, not a group: team/subspace")

    def test_require_gitlab_group_path_falls_back_to_mapping(self):
        with mock.patch.dict("os.environ", {"TARGET_ORG": "xf-main"}, clear=False):
            with mock.patch.object(gitlab_sync, "require_secret", return_value='{"xf-main":"derived/gh-xf-main"}'):
                value = gitlab_sync.require_gitlab_group_path({"repo_full_name": "xf-main/demo"})
        self.assertEqual(value, "derived/gh-xf-main")

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

    def test_ensure_gitlab_protected_branch_is_noop_when_already_pushable(self):
        current = {
            "push_access_levels": [{"access_level": 40}],
            "allow_force_push": True,
        }
        with mock.patch.object(gitlab_sync, "_get_gitlab_protected_branch", return_value=current):
            with mock.patch.object(gitlab_sync, "_gitlab_request") as request:
                changed = gitlab_sync.ensure_gitlab_protected_branch("https://gitlab.example", "token", 77, "github/mcr/main")

        self.assertFalse(changed)
        request.assert_not_called()

    def test_ensure_gitlab_protected_branch_recreates_non_force_pushable_branch(self):
        current = {
            "push_access_levels": [{"access_level": 40}],
            "allow_force_push": False,
        }
        calls = []

        def fake_request(method, _base_url, path, _token, payload=None, **_kwargs):
            calls.append((method, path, payload))
            return None

        with mock.patch.object(gitlab_sync, "_get_gitlab_protected_branch", return_value=current):
            with mock.patch.object(gitlab_sync, "_gitlab_request", side_effect=fake_request):
                changed = gitlab_sync.ensure_gitlab_protected_branch("https://gitlab.example", "token", 77, "github/mcr/main")

        self.assertTrue(changed)
        self.assertEqual(calls[0], ("DELETE", "/projects/77/protected_branches/github%2Fmcr%2Fmain", None))
        self.assertEqual(calls[1][0], "POST")
        self.assertEqual(calls[1][1], "/projects/77/protected_branches")
        self.assertEqual(
            calls[1][2],
            {
                "name": "github/mcr/main",
                "push_access_level": 30,
                "merge_access_level": 40,
                "unprotect_access_level": 40,
                "allow_force_push": True,
            },
        )


if __name__ == "__main__":
    unittest.main()
