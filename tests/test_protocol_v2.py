import copy
import json
import multiprocessing
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from protocol.v2.e2e_protocol import (
    ProtocolError,
    _manifest_lock,
    initialize_manifest,
    load_manifest,
    new_manifest,
    save_manifest,
    transition,
    validate_manifest,
    validate_v2_policy,
)

PROTOCOL_V2_SCRIPT = Path(__file__).parents[1] / "protocol" / "v2" / "e2e_protocol.py"
ROOT = Path(__file__).parents[1]


def _transition_v2_in_process(path, started, result):
    started.put(None)
    try:
        result.put(("saved", transition(path, 1, "planned", [])))
    except ProtocolError as error:
        result.put(("error", str(error)))


class ProtocolV2ShapeTests(unittest.TestCase):
    def test_new_manifest_has_strict_safe_defaults(self):
        manifest = new_manifest(
            "/workspace/app",
            timestamp="2026-07-21T00:00:00Z",
        )

        self.assertEqual(manifest["protocol_version"], "2.0")
        self.assertEqual(manifest["run"], {
            "id": manifest["run"]["id"],
            "revision": 0,
            "mode": "generate",
            "autonomy": {"mode": "explicit", "auto_repair": False},
            "status": "initialized",
            "created_at": "2026-07-21T00:00:00Z",
            "updated_at": "2026-07-21T00:00:00Z",
            "attempt_budget": {"repair": 0, "verification": 1, "wall_clock_seconds": 300},
        })
        self.assertEqual(len(manifest["systems"]), 1)
        self.assertEqual(manifest["systems"][0]["id"], "system-primary")
        self.assertEqual(manifest["systems"][0]["project_root"], "/workspace/app")
        self.assertIsNone(manifest["systems"][0]["primary_surface"])
        self.assertEqual(validate_manifest(manifest), [])
        self.assertEqual(validate_v2_policy(manifest), [])

    def test_invalid_mode_autonomy_and_top_level_field_are_rejected(self):
        manifest = new_manifest("/workspace/app", timestamp="2026-07-21T00:00:00Z")
        manifest["run"]["mode"] = "deploy"
        manifest["run"]["autonomy"]["mode"] = "unbounded"
        manifest["unexpected"] = True

        errors = validate_manifest(manifest)

        self.assertIn("unexpected top-level field: unexpected", errors)
        self.assertIn("run.mode is invalid", errors)
        self.assertIn("run.autonomy.mode is invalid", errors)

    def test_core_allows_multiple_systems_but_v2_policy_requires_one(self):
        manifest = new_manifest("/workspace/app", timestamp="2026-07-21T00:00:00Z")
        second = copy.deepcopy(manifest["systems"][0])
        second["id"] = "system-secondary"
        manifest["systems"].append(second)
        self.assertEqual(validate_manifest(manifest), [])
        self.assertIn("systems must contain exactly one system in V2", validate_v2_policy(manifest))

    def test_cross_record_references_and_single_surface_are_enforced(self):
        manifest = new_manifest("/workspace/app", timestamp="2026-07-21T00:00:00Z")
        manifest["systems"][0]["primary_surface"] = "service"
        manifest["journeys"] = [{"id": "journey-order", "system_id": "missing", "status": "planned"}]
        manifest["execution_units"] = [
            {
                "id": "unit-service",
                "system_id": "system-primary",
                "surface": "service",
                "capability": "e2e-service",
                "extension_id": "extension-service",
                "status": "planned",
            },
            {
                "id": "unit-web",
                "system_id": "system-primary",
                "surface": "web",
                "capability": "e2e-web",
                "extension_id": "extension-web",
                "status": "planned",
            },
        ]
        manifest["checks"] = [{
            "id": "check-order",
            "journey_id": "journey-missing",
            "execution_unit_id": "unit-missing",
            "status": "generated",
        }]

        errors = validate_manifest(manifest) + validate_v2_policy(manifest)

        self.assertIn("journeys[0].system_id does not reference a registered system: missing", errors)
        self.assertIn("execution_units use more than one primary surface in V2", errors)
        self.assertIn("checks[0].journey_id does not reference a registered journey: journey-missing", errors)
        self.assertIn("checks[0].execution_unit_id does not reference a registered execution unit: unit-missing", errors)

    def test_public_interfaces_require_boundary_evidence_and_external_kind(self):
        manifest = new_manifest("/workspace/app", timestamp="2026-07-21T00:00:00Z")
        manifest["systems"][0]["boundary"] = {
            "status": "declared",
            "actors": ["consumer"],
            "public_interfaces": [{
                "id": "interface-orders",
                "kind": "database",
                "endpoint_ref": "db-ref",
                "evidence_ids": ["missing"],
            }],
            "evidence_ids": ["missing"],
        }

        errors = validate_manifest(manifest)

        self.assertIn("systems[0].boundary.public_interfaces[0].kind is invalid", errors)
        self.assertIn("systems[0].boundary.evidence_ids contains an unknown evidence ID: missing", errors)

    def test_duplicate_ids_and_raw_secrets_are_rejected_everywhere(self):
        manifest = new_manifest("/workspace/app", timestamp="2026-07-21T00:00:00Z")
        manifest["journeys"] = [
            {"id": "journey-a", "system_id": "system-primary", "status": "planned"},
            {"id": "journey-a", "system_id": "system-primary", "status": "planned"},
        ]
        manifest["extensions"] = [{
            "id": "extension-service",
            "namespace": "e2e.service",
            "version": "1.0",
            "owner": "e2e-service",
            "data": {"accessToken": "plaintext"},
        }]

        errors = validate_manifest(manifest)

        self.assertIn("duplicate id in journeys: journey-a", errors)
        self.assertIn("secret value key is forbidden: accessToken", errors)

    def test_reference_keys_are_allowed(self):
        manifest = new_manifest("/workspace/app", timestamp="2026-07-21T00:00:00Z")
        manifest["extensions"] = [{
            "id": "extension-service",
            "namespace": "e2e.service",
            "version": "1.0",
            "owner": "e2e-service",
            "data": {
                "http": {"interfaces": [], "interface_id": "i1", "source_refs": [], "config_refs": [],
                         "client_ref": "vault://client", "command_ref": "vault://cmd", "contract_refs": [],
                         "request_conventions": [], "response_conventions": []},
                "graphql": {"interfaces": [], "interface_id": "i1", "source_refs": [], "config_refs": [],
                            "client_ref": "vault://client", "command_ref": "vault://cmd", "contract_refs": [],
                            "schema_refs": [], "operation_refs": []},
                "grpc": {"interfaces": [], "interface_id": "i1", "source_refs": [], "config_refs": [],
                         "client_ref": "vault://client", "command_ref": "vault://cmd", "contract_refs": [],
                         "descriptor_refs": [], "service_method_refs": []},
                "websocket": {"interfaces": [], "interface_id": "i1", "source_refs": [], "config_refs": [],
                              "client_ref": "vault://client", "command_ref": "vault://cmd", "contract_refs": [],
                              "handshake_refs": [], "subprotocols": [], "message_contract_refs": []},
                "queue": {"interfaces": [], "interface_id": "i1", "source_refs": [], "config_refs": [],
                          "client_ref": "vault://client", "command_ref": "vault://cmd", "contract_refs": [],
                          "destination_ref": "vault://dest", "role": "consume", "acknowledgement_policy": "manual",
                          "delivery_contract_refs": []},
                "stream": {"interfaces": [], "interface_id": "i1", "source_refs": [], "config_refs": [],
                           "client_ref": "vault://client", "command_ref": "vault://cmd", "contract_refs": [],
                           "channel_ref": "vault://ch", "role": "produce", "cursor_policy": "auto",
                           "event_contract_refs": []},
            },
        }]
        self.assertEqual(validate_manifest(manifest), [])

    def test_system_boundary_target_and_timestamps_are_strict(self):
        manifest = new_manifest("/workspace/app", timestamp="2026-07-21T00:00:00Z")
        manifest["run"]["created_at"] = 42
        manifest["systems"][0]["extra"] = True
        manifest["systems"][0]["boundary"]["extra"] = True
        manifest["systems"][0]["target"]["extra"] = True
        manifest["systems"][0]["target"]["mutation_policy"]["extra"] = True
        errors = validate_manifest(manifest)
        self.assertIn("run.created_at must be an RFC3339 string or null", errors)
        self.assertIn("systems[0] fields are invalid", errors)
        self.assertIn("systems[0].boundary fields are invalid", errors)
        self.assertIn("systems[0].target fields are invalid", errors)
        self.assertIn("systems[0].target.mutation_policy fields are invalid", errors)

    def test_migrated_runs_may_preserve_unknown_legacy_timestamps_as_null(self):
        manifest = new_manifest("/workspace/app", timestamp="2026-07-21T00:00:00Z")
        manifest["run"]["created_at"] = None
        manifest["run"]["updated_at"] = None
        self.assertEqual(validate_manifest(manifest), [])

    def test_evidence_classification_and_handoff_references_resolve(self):
        manifest = new_manifest("/workspace/app", timestamp="2026-07-21T00:00:00Z")
        manifest["journeys"] = [{"id": "journey-a", "system_id": "system-primary", "status": "failed"}]
        manifest["evidence"] = [{
            "id": "evidence-classification",
            "classification": {"evidence_ids": ["evidence-missing"]},
            "artifacts": [{"id": "artifact-log"}],
        }]
        manifest["handoffs"] = [{
            "id": "handoff-a", "journey_ids": ["journey-a"],
            "evidence_ids": ["evidence-missing"], "artifact_refs": ["artifact-missing"],
        }]
        errors = validate_manifest(manifest)
        self.assertIn("evidence[0].classification.evidence_ids contains an unknown evidence ID: evidence-missing", errors)
        self.assertIn("handoffs[0].evidence_ids contains an unknown evidence ID: evidence-missing", errors)
        self.assertIn("handoffs[0].artifact_refs contains an unknown artifact ID: artifact-missing", errors)


class ProtocolV2PersistenceTests(unittest.TestCase):
    def test_save_increments_nested_revision_and_rejects_stale_writer(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / ".e2e" / "manifest.json"
            saved = save_manifest(
                path,
                new_manifest(tmp, timestamp="2026-07-21T00:00:00Z"),
                expected_revision=None,
                timestamp="2026-07-21T00:00:01Z",
            )
            self.assertEqual(saved["run"]["revision"], 1)
            moved = transition(
                path, 1, "planned", [], timestamp="2026-07-21T00:00:02Z",
            )
            self.assertEqual(moved["run"]["revision"], 2)
            with self.assertRaisesRegex(ProtocolError, "revision conflict"):
                transition(path, 1, "ready-for-adapter", [])

    def test_evidence_and_attempts_cannot_be_rewritten_or_removed(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "manifest.json"
            initial = new_manifest(tmp, timestamp="2026-07-21T00:00:00Z")
            initial["evidence"] = [{"id": "evidence-a", "kind": "source-derived"}]
            initial["attempts"] = [{"id": "attempt-a", "status": "recorded"}]
            saved = save_manifest(path, initial, None, timestamp="2026-07-21T00:00:01Z")
            candidate = json.loads(json.dumps(saved))
            candidate["evidence"][0]["kind"] = "rewritten"
            candidate["attempts"] = []

            with self.assertRaisesRegex(ProtocolError, "append-only collection changed: evidence"):
                save_manifest(path, candidate, 1)

            attempts_only = json.loads(json.dumps(saved))
            attempts_only["attempts"] = []
            with self.assertRaisesRegex(ProtocolError, "append-only collection changed: attempts"):
                save_manifest(path, attempts_only, 1)

    def test_candidate_revision_must_match_the_revision_it_consumed(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "manifest.json"
            saved = save_manifest(path, new_manifest(tmp, timestamp="2026-07-21T00:00:00Z"), None)
            candidate = json.loads(json.dumps(saved))
            candidate["run"]["revision"] = 0
            with self.assertRaisesRegex(ProtocolError, "candidate revision conflict"):
                save_manifest(path, candidate, expected_revision=1)

    def test_cli_init_validate_and_transition(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "manifest.json"
            initialized = subprocess.run(
                [sys.executable, str(PROTOCOL_V2_SCRIPT), "init", "--project-root", tmp, "--output", str(path)],
                text=True, capture_output=True, check=False,
            )
            self.assertEqual(initialized.returncode, 0, initialized.stderr)
            self.assertEqual(json.loads(initialized.stdout)["protocol_version"], "2.0")

            validated = subprocess.run(
                [sys.executable, str(PROTOCOL_V2_SCRIPT), "validate", str(path)],
                text=True, capture_output=True, check=False,
            )
            self.assertEqual(validated.returncode, 0, validated.stderr)
            self.assertEqual(json.loads(validated.stdout), {"errors": []})

    def test_cli_validate_rejects_malformed_web_extension(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "manifest.json"
            manifest = json.loads((Path(tmp) / "manifest.json").read_text()) if (Path(tmp) / "manifest.json").exists() else {}
            manifest = {
                "protocol_version": "2.0",
                "run": {"id": "run-test", "revision": 0, "mode": "generate", "autonomy": {"mode": "explicit", "auto_repair": False}, "status": "initialized", "created_at": "2026-07-24T00:00:00Z", "updated_at": "2026-07-24T00:00:00Z", "attempt_budget": {"repair": 0, "verification": 1, "wall_clock_seconds": 300}},
                "systems": [{"id": "system-primary", "project_root": tmp, "primary_surface": None, "boundary": {"status": "unresolved", "actors": [], "public_interfaces": [], "evidence_ids": []}, "target": {"tier": "unspecified", "endpoint_refs": [], "credential_refs": [], "mutation_policy": {"namespace_ref": None, "allowed_classes": []}}}],
                "journeys": [], "execution_units": [], "checks": [], "evidence": [], "actions": [], "handoffs": [], "authorizations": [], "attempts": [],
                "extensions": [{"id": "extension-web", "namespace": "e2e.web", "version": "1.0", "owner": "e2e-web", "data": {}}],
            }
            path.write_text(json.dumps(manifest), encoding="utf-8")
            validated = subprocess.run(
                [sys.executable, str(PROTOCOL_V2_SCRIPT), "validate", str(path)],
                text=True, capture_output=True, check=False,
            )
            self.assertEqual(validated.returncode, 2, validated.stderr)
            result = json.loads(validated.stdout)
            self.assertIn("extension data missing required property: driver", result["errors"])

    def test_save_waits_for_the_manifest_lock(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "manifest.json"
            save_manifest(path, new_manifest(tmp, timestamp="2026-07-21T00:00:00Z"), None)
            with _manifest_lock(path):
                context = multiprocessing.get_context("spawn")
                started = context.Queue()
                result = context.Queue()
                process = context.Process(target=_transition_v2_in_process, args=(str(path), started, result))
                process.start()
                started.get(timeout=5)
                time.sleep(0.2)
                self.assertEqual(load_manifest(path)["run"]["revision"], 1)
            outcome, value = result.get(timeout=5)
            process.join(timeout=5)
            self.assertEqual(process.exitcode, 0)
            self.assertEqual(outcome, "saved")
            self.assertEqual(value["run"]["revision"], 2)


class Protocol2InitializationTests(unittest.TestCase):
    def test_initializes_when_manifest_does_not_exist(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = root / ".e2e" / "manifest.json"
            saved = initialize_manifest(path, str(root), timestamp="2026-07-22T00:00:00Z")
            self.assertEqual(saved["protocol_version"], "2.0")
            self.assertEqual(saved["run"]["revision"], 1)
            self.assertEqual(load_manifest(path), saved)

    def test_replaces_exact_protocol_1_without_migrating_history(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = root / ".e2e" / "manifest.json"
            path.parent.mkdir()
            path.write_text(json.dumps({
                "protocol_version": "1.0",
                "run_id": "run-legacy",
                "evidence": [{"id": "evidence-legacy"}],
            }))
            saved = initialize_manifest(
                path,
                str(root),
                replace_protocol_1=True,
                timestamp="2026-07-22T00:00:00Z",
            )
            self.assertEqual(saved["protocol_version"], "2.0")
            self.assertEqual(saved["run"]["revision"], 1)
            self.assertNotEqual(saved["run"]["id"], "run-legacy")
            self.assertNotIn("evidence-legacy", json.dumps(saved))
            self.assertEqual(validate_manifest(saved) + validate_v2_policy(saved), [])

    def test_refuses_protocol_1_without_explicit_replacement_flag(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = root / "manifest.json"
            original = b'{"protocol_version":"1.0"}\n'
            path.write_bytes(original)
            with self.assertRaisesRegex(ProtocolError, "existing Protocol 1 manifest requires replacement"):
                initialize_manifest(path, str(root))
            self.assertEqual(path.read_bytes(), original)

    def test_preserves_malformed_and_unknown_manifests(self):
        for original in (b"{not-json\n", b'{"protocol_version":"9.0"}\n'):
            with self.subTest(original=original):
                with tempfile.TemporaryDirectory() as temporary:
                    root = Path(temporary)
                    path = root / "manifest.json"
                    path.write_bytes(original)
                    with self.assertRaises((json.JSONDecodeError, ProtocolError)):
                        initialize_manifest(path, str(root), replace_protocol_1=True)
                    self.assertEqual(path.read_bytes(), original)

    def test_atomic_write_failure_preserves_protocol_1_source(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = root / "manifest.json"
            original = b'{"protocol_version":"1.0"}\n'
            path.write_bytes(original)
            with mock.patch("protocol.v2.e2e_protocol._atomic_write", side_effect=OSError("disk full")):
                with self.assertRaisesRegex(OSError, "disk full"):
                    initialize_manifest(path, str(root), replace_protocol_1=True)
            self.assertEqual(path.read_bytes(), original)

    def test_cli_replaces_protocol_1_only_with_flag(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = root / ".e2e" / "manifest.json"
            path.parent.mkdir()
            path.write_text('{"protocol_version":"1.0"}\n')
            completed = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "protocol/v2/e2e_protocol.py"),
                    "init",
                    "--project-root", str(root),
                    "--output", str(path),
                    "--replace-protocol-1",
                ],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertEqual(json.loads(completed.stdout)["protocol_version"], "2.0")


if __name__ == "__main__":
    unittest.main()
