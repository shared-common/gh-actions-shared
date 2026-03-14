import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / ".github" / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import branch_ops  # noqa: E402
from branch_policy import BranchPolicy, BranchSpec  # noqa: E402


def make_policy() -> BranchPolicy:
    specs = [
        BranchSpec("GIT_BRANCH_MAIN", "main", "mcr/main", "upstream", True),
        BranchSpec("GIT_BRANCH_STAGING", "staging", "mcr/staging", "main", True),
        BranchSpec("GIT_BRANCH_RELEASE", "release", "mcr/release", "main", True),
        BranchSpec("GIT_BRANCH_SNAPSHOT", "snapshot", "mcr/snapshot", "main", False),
        BranchSpec("GIT_BRANCH_FEATURE", "feature/initial", "mcr/feature/initial", "main", False),
    ]
    return BranchPolicy(
        prefix="mcr",
        order=specs,
        by_env={spec.name_env: spec for spec in specs},
    )


class BranchOpsTests(unittest.TestCase):
    def run_branch_ops(self, update_side_effect):
        upstream_sha = "u" * 40
        state = {
            "main": "d" * 40,
            "mcr/main": "a" * 40,
            "mcr/staging": "b" * 40,
            "mcr/release": "c" * 40,
            "mcr/snapshot": "s" * 40,
            "mcr/feature/initial": "f" * 40,
        }
        update_calls = []

        def fake_get_branch_sha(token, owner, repo, branch):
            if token == "upstream-token":
                self.assertEqual((owner, repo, branch), ("upstream", "repo", "main"))
                return upstream_sha
            return state[branch]

        def fake_update_branch(token, owner, repo, branch, sha, force=False):
            update_calls.append((branch, sha, force))
            if update_side_effect is not None:
                update_side_effect(branch, sha, force)
            state[branch] = sha

        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = Path(tmpdir) / "input.json"
            output_path = Path(tmpdir) / "output.json"
            input_path.write_text(
                json.dumps(
                    {
                        "repo_full_name": "forkorg/repo",
                        "job_type": "polling",
                        "repo_is_fork": True,
                        "repo_default_branch": "main",
                        "repo_parent_full_name": "upstream/repo",
                        "repo_parent_default_branch": "main",
                        "event_id": "evt-1",
                    }
                ),
                encoding="utf-8",
            )
            env = {
                "INPUT_PATH": str(input_path),
                "OUTPUT_PATH": str(output_path),
                "TARGET_ORG": "forkorg",
                "GH_ORG_SHARED_APP_PEM_FILE": "/tmp/pem",
            }
            with mock.patch.dict(os.environ, env, clear=False):
                with mock.patch.object(branch_ops, "load_branch_policy", return_value=make_policy()):
                    with mock.patch.object(branch_ops, "get_installation_token_for_org", return_value="fork-token"):
                        with mock.patch.object(branch_ops, "parse_installations", return_value={"upstream": 2}):
                            with mock.patch.object(branch_ops, "get_installation_token", return_value="upstream-token"):
                                with mock.patch.object(branch_ops, "get_branch_sha", side_effect=fake_get_branch_sha):
                                    with mock.patch.object(branch_ops, "branch_exists", return_value=True):
                                        with mock.patch.object(branch_ops, "create_branch"):
                                            with mock.patch.object(
                                                branch_ops,
                                                "require_secret",
                                                side_effect=lambda name: "secret",
                                            ):
                                                with mock.patch.object(
                                                    branch_ops,
                                                    "require_env",
                                                    return_value="/tmp/pem",
                                                ):
                                                    with mock.patch.object(
                                                        branch_ops,
                                                        "update_branch",
                                                        side_effect=fake_update_branch,
                                                    ):
                                                        result = branch_ops.main()
            return result, json.loads(output_path.read_text(encoding="utf-8")), update_calls

    def test_polling_force_updates_default_and_managed_branches(self):
        result, output, update_calls = self.run_branch_ops(update_side_effect=None)

        self.assertEqual(result, 0)
        self.assertEqual(
            update_calls,
            [
                ("main", "u" * 40, True),
                ("mcr/main", "u" * 40, True),
                ("mcr/staging", "u" * 40, True),
                ("mcr/release", "u" * 40, True),
            ],
        )
        self.assertEqual(
            output["results"]["updated"],
            ["main", "mcr/main", "mcr/staging", "mcr/release"],
        )

    def test_polling_skips_skippable_rewrite_failures(self):
        def reject_updates(branch, _sha, _force):
            raise branch_ops.ApiError(422 if branch == "main" else 403, "blocked")

        result, output, update_calls = self.run_branch_ops(update_side_effect=reject_updates)

        self.assertEqual(result, 0)
        self.assertEqual(
            update_calls,
            [
                ("main", "u" * 40, True),
                ("mcr/main", "u" * 40, True),
                ("mcr/staging", "a" * 40, True),
                ("mcr/release", "a" * 40, True),
            ],
        )
        self.assertEqual(
            output["results"]["skipped"][-4:],
            ["main", "mcr/main", "mcr/staging", "mcr/release"],
        )


if __name__ == "__main__":
    unittest.main()
