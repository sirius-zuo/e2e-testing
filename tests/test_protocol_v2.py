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


if __name__ == "__main__":
    unittest.main()
