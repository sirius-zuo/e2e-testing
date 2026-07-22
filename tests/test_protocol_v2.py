import copy
import unittest

from protocol.v2.e2e_protocol import new_manifest, validate_manifest, validate_v2_policy


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
            "data": {"token_ref": "vault://service-token", "credentials_ref": "vault://credentials"},
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


if __name__ == "__main__":
    unittest.main()
