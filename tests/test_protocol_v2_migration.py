import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from protocol.v1.e2e_protocol import new_manifest as new_v1_manifest
from protocol.v2.e2e_protocol import validate_manifest
from protocol.v2.migrate_v1 import migrate_file, migrate_manifest, source_sha256


def complete_v1_manifest():
    source = new_v1_manifest("/workspace/app", mode="verify", autonomy="auto")
    source["run_id"] = "run-migration-fixture"
    source["revision"] = 7
    source["status"] = "verifying"
    source["project"] = {"root": "/workspace/app", "framework": "playwright", "language": "typescript"}
    source["target"] = {
        "tier": "staging",
        "base_url_ref": "env:E2E_BASE_URL",
        "credentials_ref": "vault://e2e-user",
    }
    source["journeys"] = [{"id": "journey-login", "status": "verifying", "goal": "Sign in"}]
    source["tests"] = [{
        "id": "test-login", "journey_id": "journey-login", "status": "generated",
        "path": "tests/login.spec.ts",
    }]
    source["evidence"] = [{"id": "evidence-source", "kind": "source-derived"}]
    source["conflicts"] = [{"id": "conflict-copy", "status": "resolved"}]
    source["attempt_history"] = [{"id": "attempt-verify", "status": "failed"}]
    source["handoffs"] = [{"id": "handoff-env", "journey_ids": ["journey-login"]}]
    source["authorizations"] = [{"id": "authorization-staging", "status": "approved"}]
    source["next_actions"] = [{
        "id": "action-verify", "capability": "e2e-web-playwright",
        "journey_ids": ["journey-login"],
    }]
    return source


class ProtocolV2MigrationMappingTests(unittest.TestCase):
    def test_complete_v1_manifest_maps_losslessly_and_validates(self):
        source = complete_v1_manifest()
        original = copy.deepcopy(source)
        migrated = migrate_manifest(source)

        self.assertEqual(source, original)
        self.assertEqual(migrated["protocol_version"], "2.0")
        self.assertEqual(migrated["run"]["id"], source["run_id"])
        self.assertEqual(migrated["run"]["revision"], 7)
        self.assertEqual(migrated["run"]["status"], "verifying")
        self.assertEqual(migrated["journeys"][0]["id"], "journey-login")
        self.assertEqual(migrated["checks"][0]["id"], "test-login")
        self.assertEqual(migrated["attempts"], source["attempt_history"])
        self.assertEqual(migrated["actions"][0]["capability"], "e2e-web")
        migration_evidence = next(item for item in migrated["evidence"] if item.get("kind") == "protocol-migration")
        self.assertEqual(migration_evidence["source_revision"], 7)
        self.assertEqual(migration_evidence["source_sha256"], source_sha256(original))
        archive = next(item for item in migrated["extensions"] if item["namespace"] == "e2e.protocol1.archive")
        self.assertEqual(archive["data"]["source_manifest"], original)
        self.assertEqual(archive["data"]["source_sha256"], source_sha256(original))
        self.assertEqual(validate_manifest(migrated), [])

    def test_mapping_is_deterministic(self):
        source = complete_v1_manifest()
        self.assertEqual(migrate_manifest(source), migrate_manifest(copy.deepcopy(source)))

    def test_legacy_terminal_statuses_are_translated_and_recorded(self):
        source = complete_v1_manifest()
        source["status"] = "unsupported-framework"
        migrated = migrate_manifest(source)
        self.assertEqual(migrated["run"]["status"], "capability-unavailable")
        archive = next(item for item in migrated["extensions"] if item["namespace"] == "e2e.protocol1.archive")
        self.assertEqual(archive["data"]["status_translation"], {
            "source": "unsupported-framework", "target": "capability-unavailable",
        })

    def test_invalid_v1_input_is_rejected(self):
        source = complete_v1_manifest()
        source["protocol_version"] = "0.9"
        with self.assertRaisesRegex(ValueError, "invalid Protocol 1 manifest"):
            migrate_manifest(source)


class ProtocolV2MigrationFileTests(unittest.TestCase):
    def test_migration_preserves_source_and_publishes_exact_revision(self):
        with tempfile.TemporaryDirectory() as tmp:
            source_path = Path(tmp) / "v1.json"
            target_path = Path(tmp) / "v2.json"
            source = complete_v1_manifest()
            source_path.write_text(json.dumps(source, indent=2) + "\n")
            source_bytes = source_path.read_bytes()

            migrated = migrate_file(source_path, target_path)

            self.assertEqual(source_path.read_bytes(), source_bytes)
            self.assertEqual(json.loads(target_path.read_text()), migrated)
            self.assertEqual(migrated["run"]["revision"], 7)

    def test_identical_rerun_is_idempotent_but_divergent_target_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            source_path = Path(tmp) / "v1.json"
            target_path = Path(tmp) / "v2.json"
            source_path.write_text(json.dumps(complete_v1_manifest()))
            first = migrate_file(source_path, target_path)
            self.assertEqual(migrate_file(source_path, target_path), first)

            changed = json.loads(target_path.read_text())
            changed["run"]["status"] = "blocked"
            target_path.write_text(json.dumps(changed))
            with self.assertRaisesRegex(ValueError, "migration target already exists with different content"):
                migrate_file(source_path, target_path)

    def test_cli_requires_separate_output_and_returns_clean_errors(self):
        with tempfile.TemporaryDirectory() as tmp:
            source_path = Path(tmp) / "v1.json"
            target_path = Path(tmp) / "v2.json"
            source_path.write_text(json.dumps(complete_v1_manifest()))
            completed = subprocess.run(
                [sys.executable, "-m", "protocol.v2.migrate_v1", str(source_path), "--output", str(target_path)],
                text=True, capture_output=True, check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertEqual(json.loads(completed.stdout)["protocol_version"], "2.0")
            self.assertTrue(target_path.exists())

            invalid = subprocess.run(
                [sys.executable, "-m", "protocol.v2.migrate_v1", str(source_path), "--output", str(source_path)],
                text=True, capture_output=True, check=False,
            )
            self.assertEqual(invalid.returncode, 2)
            self.assertIn("source and output must differ", invalid.stderr)
            self.assertNotIn("Traceback", invalid.stderr)
