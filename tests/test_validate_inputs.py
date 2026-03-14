import sys
import unittest
from pathlib import Path
from unittest import mock

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / ".github" / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import validate_inputs  # noqa: E402


class ValidateInputsTests(unittest.TestCase):
    def test_polling_fork_recovers_missing_parent_branch_from_repo_api(self):
        payload = {
            "event_name": "polling",
            "delivery_id": "123e4567-e89b-12d3-a456-426614174000",
            "org_login": "xf-main",
            "repo_id": 77,
            "repo_full_name": "xf-main/drifted-fork",
            "action": "polling",
            "ref": "refs/heads/main",
            "after": None,
            "source_repo_full_name": "openai/openai-dotnet",
            "job_type": "polling",
            "event_id": "123e4567-e89b-12d3-a456-426614174000",
            "repo_default_branch": "main",
            "repo_is_fork": True,
            "repo_parent_full_name": "openai/openai-dotnet",
            "repo_parent_default_branch": None,
        }

        with mock.patch.dict(
            "os.environ",
            {
                "TARGET_ORG": "xf-main",
                "GH_ORG_SHARED_APP_PEM_FILE": "/tmp/pem",
            },
            clear=False,
        ):
            with mock.patch.object(validate_inputs, "require_secret", return_value="secret"):
                with mock.patch.object(
                    validate_inputs,
                    "get_installation_token_for_org",
                    return_value="token",
                ):
                    with mock.patch.object(
                        validate_inputs,
                        "get_repo",
                        return_value={
                            "parent": {
                                "full_name": "openai/openai-dotnet",
                                "default_branch": "main",
                            }
                        },
                    ):
                        validated, org = validate_inputs.validate_payload(payload)

        self.assertEqual(org, "xf-main")
        self.assertEqual(validated["repo_parent_full_name"], "openai/openai-dotnet")
        self.assertEqual(validated["repo_parent_default_branch"], "main")


if __name__ == "__main__":
    unittest.main()
