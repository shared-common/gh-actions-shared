import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / ".github" / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from json_schema import load_json, validate  # noqa: E402


class SchemaTests(unittest.TestCase):
    def test_inputs_schema_accepts_worker_polling_payload(self):
        schema = load_json(str(ROOT / "configs" / "inputs.schema.json"))
        payload = {
            "event_name": "polling",
            "delivery_id": "inventory-1773473445000",
            "org_login": "xf-secops",
            "repo_id": 1179011526,
            "event_id": "inventory-1773473445000",
            "job_type": "polling",
            "repo_full_name": "xf-secops/UAC-Bypass-FUD",
            "gitlab_group_path": "derived/gh-xf-secops",
            "action": "polling",
            "ref": None,
            "after": None,
            "repo_default_branch": "main",
            "repo_is_fork": True,
            "repo_parent_full_name": "Stendrmatm/UAC-Bypass-FUD",
            "repo_parent_default_branch": "main",
            "source_repo_full_name": "Stendrmatm/UAC-Bypass-FUD",
        }
        validate(payload, schema)

    def test_summary_schema_accepts_branch_ops_summary_with_worker_event_id(self):
        schema = load_json(str(ROOT / "configs" / "summary.schema.json"))
        payload = {
            "repo": "xf-secops/UAC-Bypass-FUD",
            "job_type": "polling",
            "event_id": "inventory-1773473445000",
            "results": {
                "created": [],
                "updated": ["main", "mcr/main", "mcr/staging", "mcr/release"],
                "skipped": [],
            },
            "errors": [],
        }
        validate(payload, schema)

    def test_discover_schema_accepts_repo_with_parent_metadata(self):
        schema = load_json(str(ROOT / "configs" / "discover.schema.json"))
        payload = [
            {
                "name": "UAC-Bypass-FUD",
                "full_name": "xf-secops/UAC-Bypass-FUD",
                "fork": True,
                "default_branch": "main",
                "archived": False,
                "private": False,
                "parent": {
                    "full_name": "Stendrmatm/UAC-Bypass-FUD",
                    "default_branch": "main",
                },
            }
        ]
        validate(payload, schema)

    def test_org_allowlist_schema_rejects_invalid_org_name(self):
        schema = load_json(str(ROOT / "configs" / "org-allowlist.schema.json"))
        with self.assertRaises(ValueError):
            validate({"orgs": ["xf-secops", "bad/org"]}, schema)

    def test_targets_schema_accepts_repo_list(self):
        schema = load_json(str(ROOT / "configs" / "targets.schema.json"))
        payload = [{"repo_full_name": "xf-secops/UAC-Bypass-FUD"}]
        validate(payload, schema)


if __name__ == "__main__":
    unittest.main()
