import sys
import unittest
from pathlib import Path
from unittest import mock

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / ".github" / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import gitlab_sync  # noqa: E402
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

    def test_resolve_gitlab_target_maps_upstream_org(self):
        values = {
            "GH_ORG_UPSTREAM": "upstream-org",
            "GH_ORG_XF_MAIN": "xf-main",
            "GH_ORG_XF_SECOPS": "xf-secops",
            "GH_ORG_XF_CHECKOUT": "xf-checkout",
            "GL_GROUP_TOP_UPSTREAM": "seedbed",
            "GL_GROUP_SUB_CANONICAL": "canonical",
            "GL_BRIDGE_FORK_USER_SEEDBED": "seedbed-user",
            "GL_PAT_FORK_SEEDBED_SVC": "seedbed-token",
            "GL_BASE_URL": "https://gitlab.example",
        }
        with mock.patch.object(gitlab_sync, "require_secret", side_effect=lambda name: values[name]):
            target = gitlab_sync.resolve_gitlab_target("upstream-org", "demo")
        self.assertEqual(target.project_path, "seedbed/canonical/demo")
        self.assertEqual(target.git_username, "seedbed-user")
        self.assertEqual(target.api_token, "seedbed-token")

    def test_resolve_gitlab_target_maps_derived_org(self):
        values = {
            "GH_ORG_UPSTREAM": "upstream-org",
            "GH_ORG_XF_MAIN": "xf-main",
            "GH_ORG_XF_SECOPS": "xf-secops",
            "GH_ORG_XF_CHECKOUT": "xf-checkout",
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


if __name__ == "__main__":
    unittest.main()
