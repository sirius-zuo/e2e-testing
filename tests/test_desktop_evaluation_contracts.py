"""Contract tests for the desktop evaluation evaluator."""

from __future__ import annotations

import unittest

from evals.desktop_contract import check_desktop_contract
from protocol.v2.e2e_protocol import new_manifest
from tests.test_protocol_v2_extensions import desktop_data, desktop_extension


PASS_EXPECT = {
    "manifest_status": "verified", "mode": "verify",
    "allow_fixture_evidence": True,
    "required_check_ids": ["check-desktop-launch"],
    "required_execution_evidence_ids": ["evidence-desktop-execution"],
    "required_cleanup_outcome": "successful",
}


def desktop_manifest():
    from datetime import datetime, timedelta, timezone
    future = (datetime.now(timezone.utc) + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    manifest = new_manifest("/workspace/app", mode="verify", timestamp="2026-08-01T00:00:00Z")
    manifest["run"].update(status="verified", revision=1)
    manifest["systems"][0]["primary_surface"] = "desktop"
    manifest["systems"][0]["boundary"]["status"] = "declared"
    manifest["systems"][0]["target"]["tier"] = "local"
    manifest["journeys"] = [{
        "id": "journey-desktop", "system_id": "system-primary", "status": "verified",
    }]
    manifest["execution_units"] = [{
        "id": "unit-desktop", "system_id": "system-primary", "surface": "desktop",
        "capability": "installed-desktop-ui", "extension_id": "extension-desktop",
        "status": "verified",
    }]
    manifest["checks"] = [{
        "id": "check-desktop-launch", "journey_id": "journey-desktop",
        "execution_unit_id": "unit-desktop", "status": "passed",
    }]
    environment = {
        "driver": "appium-mac2", "driver_version": "2.0",
        "adapter_version": "3.0", "backend_version": "xctest",
        "platform": "macos", "os_version": "fixture-os",
        "target_reference": "target-macos", "target_kind": "local", "target_tier": "local",
        "session_reference": "session-macos", "session_kind": "dedicated-user",
        "session_isolated": True, "application_id": "app-native-macos",
        "application_kind": "native", "artifact_reference": "artifact-native-macos",
        "artifact_format": "app", "lifecycle_phase": "verify",
        "authorization_refs": ["authorization-desktop"], "evidence_origin": "fixture",
    }
    manifest["evidence"] = [{
        "id": "evidence-target",
    }, {
        "id": "evidence-desktop-execution", "command": "npm run e2e:desktop:macos",
        "exit_code": 0, "duration_ms": 10, "phase": "verify",
        "manifest_revision_consumed": 0, "check_ids": ["check-desktop-launch"],
        "outcomes": [{"check_id": "check-desktop-launch", "status": "passed"}],
        "execution_environment": environment, "real_os_evidence": True,
    }, {
        "id": "evidence-desktop-cleanup", "cleanup_action_id": "action-desktop-cleanup",
        "lifecycle_id": "lifecycle-macos", "session_id": "session-macos",
        "baseline_ref": "baseline-macos", "restoration_ref": "restore-macos",
        "phase": "cleanup", "manifest_revision_consumed": 0,
        "cleanup_successful": True, "restored_baseline": True,
    }]
    manifest["actions"] = [{
        "id": "action-desktop-cleanup", "capability": "desktop-cleanup",
        "journey_ids": ["journey-desktop"],
    }]
    manifest["authorizations"] = [{
        "id": "authorization-desktop", "capability": "desktop-lifecycle",
        "target_id": "target-macos", "session_id": "session-macos",
        "manifest_revision": 0,
    }]
    extension_data = desktop_data()
    extension_data["sessions"][0]["expires_at"] = future
    manifest["extensions"] = [desktop_extension(extension_data)]
    return manifest


FORMAT_PLATFORMS = {
    "app": "macos", "dmg": "macos", "pkg": "macos",
    "portable-exe": "windows", "installer-exe": "windows",
    "msi": "windows", "msix": "windows",
}


class DesktopEvaluatorContractTests(unittest.TestCase):
    def test_complete_desktop_manifest_passes(self):
        manifest = desktop_manifest()
        self.assertEqual(check_desktop_contract(manifest, PASS_EXPECT, "desktop"), [])

    def test_desktop_case_requires_desktop_unit(self):
        manifest = desktop_manifest()
        manifest["execution_units"][0]["surface"] = "web"
        self.assertEqual(
            check_desktop_contract(manifest, PASS_EXPECT, "desktop"),
            ["desktop case requires at least one desktop execution unit"],
        )

    def test_graph_corruption_rejects_unknown_references(self):
        for path, expected in (
            (("targets", 0, "driver_id"), "references unknown driver"),
            (("sessions", 0, "target_id"), "references unknown target"),
            (("artifacts", 0, "application_id"), "references unknown application"),
            (("lifecycle_profiles", 0, "interaction_boundary_id"), "references unknown boundary"),
        ):
            with self.subTest(path=path):
                manifest = desktop_manifest()
                collection, index, field = path
                manifest["extensions"][0]["data"][collection][index][field] = "missing"
                self.assertTrue(
                    any(expected in item for item in check_desktop_contract(manifest, PASS_EXPECT, "desktop")),
                )

    def test_session_refusal_rejects_non_isolated_or_expired(self):
        manifest = desktop_manifest()
        for field in ("interactive", "unlocked", "connected", "isolated"):
            with self.subTest(field=field):
                candidate = desktop_manifest()
                candidate["extensions"][0]["data"]["sessions"][0][field] = False
                errors = check_desktop_contract(candidate, PASS_EXPECT, "desktop")
                self.assertTrue(
                    any("session" in item.lower() for item in errors),
                    f"Expected session refusal for {field}=False",
                )

    def test_expired_session_rejected(self):
        manifest = desktop_manifest()
        manifest["extensions"][0]["data"]["sessions"][0]["expires_at"] = "2020-01-01T00:00:00Z"
        errors = check_desktop_contract(manifest, PASS_EXPECT, "desktop")
        self.assertTrue(any("expired" in item.lower() or "session" in item.lower() for item in errors))

    def test_empty_allowlist_rejected(self):
        manifest = desktop_manifest()
        manifest["extensions"][0]["data"]["sessions"][0]["application_allowlist"] = []
        errors = check_desktop_contract(manifest, PASS_EXPECT, "desktop")
        self.assertTrue(any("allowlist" in item.lower() for item in errors))

    def test_platform_format_mismatch_rejected(self):
        manifest = desktop_manifest()
        manifest["extensions"][0]["data"]["artifacts"][0]["format"] = "msi"
        errors = check_desktop_contract(manifest, PASS_EXPECT, "desktop")
        self.assertTrue(
            any("format" in item.lower() and "incompatible" in item.lower() for item in errors),
            f"Expected format/platform mismatch, got: {errors}",
        )

    def test_wrong_application_in_artifact_rejected(self):
        manifest = desktop_manifest()
        manifest["extensions"][0]["data"]["artifacts"][0]["application_id"] = "wrong-app"
        errors = check_desktop_contract(manifest, PASS_EXPECT, "desktop")
        self.assertTrue(any("references unknown application" in item for item in errors))

    def test_wrong_application_in_boundary_rejected(self):
        manifest = desktop_manifest()
        manifest["extensions"][0]["data"]["interaction_boundaries"][0]["application_id"] = "wrong-app"
        errors = check_desktop_contract(manifest, PASS_EXPECT, "desktop")
        self.assertTrue(any("references unknown application" in item for item in errors))

    def test_wrong_application_in_session_allowlist_rejected(self):
        manifest = desktop_manifest()
        manifest["extensions"][0]["data"]["sessions"][0]["application_allowlist"] = ["wrong-app"]
        errors = check_desktop_contract(manifest, PASS_EXPECT, "desktop")
        self.assertTrue(any("allowlists unknown application" in item for item in errors))

    def test_wrong_boundary_in_session_allowlist_rejected(self):
        manifest = desktop_manifest()
        manifest["extensions"][0]["data"]["sessions"][0]["os_interaction_allowlist"] = ["wrong-boundary"]
        errors = check_desktop_contract(manifest, PASS_EXPECT, "desktop")
        self.assertTrue(any("allowlists unknown boundary" in item for item in errors))

    def test_lifecycle_missing_action_ref_rejected(self):
        manifest = desktop_manifest()
        manifest["extensions"][0]["data"]["lifecycle_profiles"][0]["cleanup_action_refs"] = ["missing"]
        errors = check_desktop_contract(manifest, PASS_EXPECT, "desktop")
        self.assertTrue(any("references unknown action" in item for item in errors))

    def test_lifecycle_missing_authorization_ref_rejected(self):
        manifest = desktop_manifest()
        manifest["extensions"][0]["data"]["lifecycle_profiles"][0]["authorization_refs"] = ["missing"]
        errors = check_desktop_contract(manifest, PASS_EXPECT, "desktop")
        self.assertTrue(any("references unknown authorization" in item for item in errors))

    def test_lifecycle_missing_artifact_ref_rejected(self):
        manifest = desktop_manifest()
        manifest["extensions"][0]["data"]["lifecycle_profiles"][0]["artifact_ids"] = ["missing"]
        errors = check_desktop_contract(manifest, PASS_EXPECT, "desktop")
        self.assertTrue(any("references unknown artifact" in item for item in errors))

    def test_evidence_stale_revision_rejected(self):
        manifest = desktop_manifest()
        manifest["evidence"][1]["manifest_revision_consumed"] = 99
        errors = check_desktop_contract(manifest, PASS_EXPECT, "desktop")
        self.assertTrue(any("stale revision" in item.lower() for item in errors))

    def test_evidence_missing_outcome_rejected(self):
        manifest = desktop_manifest()
        manifest["evidence"][1]["outcomes"] = []
        errors = check_desktop_contract(manifest, PASS_EXPECT, "desktop")
        self.assertTrue(any("missing outcome" in item.lower() for item in errors))

    def test_evidence_wrong_check_rejected(self):
        manifest = desktop_manifest()
        manifest["evidence"][1]["check_ids"] = ["wrong-check"]
        errors = check_desktop_contract(manifest, PASS_EXPECT, "desktop")
        self.assertTrue(any("missing required check_id" in item for item in errors))

    def test_evidence_mocked_os_rejected(self):
        manifest = desktop_manifest()
        manifest["evidence"][1]["real_os_evidence"] = False
        errors = check_desktop_contract(manifest, PASS_EXPECT, "desktop")
        self.assertTrue(any("not real OS evidence" in item for item in errors))

    def test_evidence_invalid_duration_rejected(self):
        manifest = desktop_manifest()
        manifest["evidence"][1]["duration_ms"] = -1
        errors = check_desktop_contract(manifest, PASS_EXPECT, "desktop")
        self.assertTrue(any("invalid duration" in item.lower() for item in errors))

    def test_cleanup_incomplete_rejected(self):
        manifest = desktop_manifest()
        manifest["evidence"][2]["cleanup_successful"] = False
        errors = check_desktop_contract(manifest, PASS_EXPECT, "desktop")
        self.assertTrue(any("cleanup" in item.lower() and "failed" in item.lower() for item in errors))

    def test_cleanup_missing_restoration_rejected(self):
        manifest = desktop_manifest()
        manifest["evidence"][2]["restored_baseline"] = False
        errors = check_desktop_contract(manifest, PASS_EXPECT, "desktop")
        self.assertTrue(any("did not restore baseline" in item for item in errors))

    def test_cleanup_missing_fields_rejected(self):
        manifest = desktop_manifest()
        manifest["evidence"][2].pop("lifecycle_id")
        errors = check_desktop_contract(manifest, PASS_EXPECT, "desktop")
        self.assertTrue(any("missing lifecycle_id" in item for item in errors))

    def test_lifecycle_no_cleanup_action_rejected(self):
        manifest = desktop_manifest()
        manifest["extensions"][0]["data"]["lifecycle_profiles"][0]["cleanup_action_refs"] = []
        errors = check_desktop_contract(manifest, PASS_EXPECT, "desktop")
        self.assertTrue(any("no cleanup_action_refs" in item for item in errors))

    def test_lifecycle_no_artifact_rejected(self):
        manifest = desktop_manifest()
        manifest["extensions"][0]["data"]["lifecycle_profiles"][0]["artifact_ids"] = []
        errors = check_desktop_contract(manifest, PASS_EXPECT, "desktop")
        self.assertTrue(any("no artifact_ids" in item for item in errors))

    def test_lifecycle_update_requires_distinct_artifacts(self):
        manifest = desktop_manifest()
        manifest["extensions"][0]["data"]["lifecycle_profiles"][0]["update"] = True
        manifest["extensions"][0]["data"]["lifecycle_profiles"][0]["artifact_ids"] = ["artifact-native-macos"]
        manifest["extensions"][0]["data"]["artifacts"][0]["role"] = "candidate"
        errors = check_desktop_contract(manifest, PASS_EXPECT, "desktop")
        self.assertTrue(
            any("prior" in item.lower() for item in errors),
            f"Expected prior artifact error: {errors}",
        )

    def test_extension_version_mismatch_rejected(self):
        manifest = desktop_manifest()
        manifest["extensions"][0]["version"] = "2.0"
        errors = check_desktop_contract(manifest, PASS_EXPECT, "desktop")
        self.assertIn(
            "desktop execution unit does not reference e2e.desktop@1.0 owned by e2e-desktop",
            errors,
        )

    def test_non_desktop_surface_ignored(self):
        manifest = desktop_manifest()
        self.assertEqual(check_desktop_contract(manifest, PASS_EXPECT, "web"), [])


if __name__ == "__main__":
    unittest.main()
