"""Contract tests for the mobile evaluation fixture, evaluator gates, and behavioral cases."""

from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from evals.evaluate_result import evaluate
from protocol.v2.e2e_protocol import new_manifest


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "evals/fixtures/mobile-contract"


MOBILE_ENVIRONMENT = {
    "driver": "appium",
    "driver_version": "fixture-1.0",
    "platform": "ios",
    "os_version": "fixture-os",
    "target_kind": "simulator",
    "application_build_ref": "artifact-candidate-ios",
    "target_reference": "target-ios-sim",
    "target_tier": "local",
    "evidence_origin": "fixture",
}


class MobileFixtureContractTests(unittest.TestCase):
    def test_mobile_fixture_has_required_repository_evidence(self):
        for relative in (
            "mobile/app.json",
            "mobile/targets.json",
            "mobile/artifacts/prior-ios.json",
            "mobile/artifacts/candidate-ios.json",
            "mobile/artifacts/prior-android.json",
            "mobile/artifacts/candidate-android.json",
            "repositories/native-ios/project.json",
            "repositories/native-android/project.json",
            "repositories/cross-platform/project.json",
            "appium.config.js",
            ".maestro/login.yaml",
            "test-support/mobile-driver.js",
            "tests/fixture-contract.test.js",
            "package.json",
            ".fixture-baseline.json",
        ):
            self.assertTrue((FIXTURE / relative).is_file(), relative)

    def test_fixture_runs_every_driver_platform_baseline(self):
        for driver in ("appium", "maestro"):
            for platform in ("ios", "android"):
                result = subprocess.run(
                    [
                        "node", "test-support/mobile-driver.js",
                        "--driver", driver,
                        "--platform", platform,
                        "--scenario", "pass",
                    ],
                    cwd=FIXTURE,
                    text=True,
                    capture_output=True,
                    check=False,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                payload = json.loads(result.stdout)
                self.assertEqual(payload["evidence_origin"], "fixture")
                self.assertEqual(payload["driver"], driver)
                self.assertEqual(payload["platform"], platform)
                self.assertTrue(payload["cleanup_successful"])
                self.assertEqual(payload["outcomes"][0]["status"], "passed")


class MobileEvaluatorGateTests(unittest.TestCase):
    def _evaluate(
        self,
        *,
        environment,
        cleanup_successful,
        expect,
        extension_id="extension-mobile",
    ):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            (workspace / ".e2e").mkdir()
            manifest = new_manifest(
                str(workspace),
                mode="verify",
                timestamp="2026-07-27T00:00:00Z",
            )
            manifest["run"].update(status="verified", revision=1)
            manifest["systems"][0]["primary_surface"] = "mobile"
            manifest["systems"][0]["boundary"]["status"] = "declared"
            manifest["systems"][0]["target"]["tier"] = environment["target_tier"]
            manifest["journeys"] = [{
                "id": "journey-mobile",
                "system_id": "system-primary",
                "status": "verified",
            }]
            manifest["execution_units"] = [{
                "id": "unit-mobile",
                "system_id": "system-primary",
                "surface": "mobile",
                "capability": "installed-app-ui",
                "extension_id": extension_id,
                "status": "verified",
            }]
            manifest["checks"] = [{
                "id": "check-mobile",
                "journey_id": "journey-mobile",
                "execution_unit_id": "unit-mobile",
                "status": "passed",
            }]
            manifest["evidence"] = [{
                "id": "evidence-mobile",
                "command": "node test-support/mobile-driver.js",
                "exit_code": 0,
                "duration_ms": 10,
                "phase": "verify",
                "manifest_revision_consumed": 0,
                "check_ids": ["check-mobile"],
                "outcomes": [{"check_id": "check-mobile", "status": "passed"}],
                "execution_environment": environment,
            }, {
                "id": "evidence-cleanup",
                "cleanup_action_id": "action-mobile-cleanup",
                "cleanup_successful": cleanup_successful,
            }]
            manifest["actions"] = [{
                "id": "action-mobile-cleanup",
                "capability": "mobile-cleanup",
                "journey_ids": ["journey-mobile"],
            }]
            manifest["extensions"] = [{
                "id": "extension-mobile",
                "namespace": "e2e.mobile",
                "version": "1.0",
                "owner": "e2e-mobile",
                "data": {
                    "application": {
                        "id": "app-mobile",
                        "ios_bundle_id": "com.example.mobile",
                        "android_package_id": "",
                        "source_refs": [],
                        "config_refs": [],
                        "build_command_refs": [],
                        "entry_points": ["native"],
                        "framework_evidence": [],
                    },
                    "drivers": [{
                        "id": "driver-appium",
                        "kind": "appium",
                        "version": "fixture-1.0",
                        "adapter_version": "fixture-1.0",
                        "config_refs": [],
                        "command_ref": "fixture-mobile",
                        "capabilities": ["install", "launch", "cleanup"],
                        "host_platforms": ["test"],
                        "remote_endpoint_ref": "",
                        "bootstrap_status": "existing",
                        "authorization_ref": "",
                    }],
                    "targets": [{
                        "id": "target-ios",
                        "platform": "ios",
                        "kind": "simulator",
                        "device_ref": "fixture-ios",
                        "os_version": "fixture-os",
                        "driver_id": "driver-appium",
                        "provisioning_status": "ready",
                        "disposable": True,
                        "capabilities": ["install", "launch", "cleanup"],
                        "evidence_refs": ["evidence-mobile"],
                    }],
                    "artifacts": [{
                        "id": "artifact-candidate-ios",
                        "platform": "ios",
                        "role": "candidate",
                        "artifact_ref": "candidate-ios",
                        "build_command_ref": "",
                        "application_id": "app-mobile",
                        "build_ref": "candidate-1",
                        "provisioning_ref": "",
                    }],
                    "lifecycle_profiles": [{
                        "id": "lifecycle-ios",
                        "execution_unit_id": "unit-mobile",
                        "target_id": "target-ios",
                        "artifact_ids": ["artifact-candidate-ios"],
                        "install_policy": "fresh",
                        "launch_policy": "cold",
                        "reset_policy": "app-scoped",
                        "background_foreground": False,
                        "orientation": "portrait",
                        "deep_link_refs": [],
                        "permission_profile_refs": [],
                        "upgrade": False,
                        "setup_action_refs": [],
                        "cleanup_action_refs": ["action-mobile-cleanup"],
                    }],
                },
            }]
            (workspace / ".e2e/manifest.json").write_text(
                json.dumps(manifest, indent=2),
                encoding="utf-8",
            )
            case = {
                "id": "mobile-evaluator-test",
                "entry_skill": "e2e-mobile",
                "surface": "mobile",
                "mode": "verify",
                "prompt": "verify selected mobile check",
                "fixture": "mobile-contract",
                "expect": expect,
            }
            case_path = workspace / "case.json"
            case_path.write_text(json.dumps(case), encoding="utf-8")
            return evaluate(case_path, workspace)

    def test_valid_mobile_fixture_execution_and_cleanup_pass(self):
        diagnostics = self._evaluate(
            environment=MOBILE_ENVIRONMENT,
            cleanup_successful=True,
            expect={"manifest_status": "verified", "allow_fixture_evidence": True},
        )
        self.assertEqual(diagnostics, [])

    def test_fixture_evidence_cannot_claim_live_platform_acceptance(self):
        diagnostics = self._evaluate(
            environment=MOBILE_ENVIRONMENT,
            cleanup_successful=True,
            expect={"manifest_status": "verified", "allow_fixture_evidence": False},
        )
        self.assertIn("fixture evidence cannot satisfy live mobile acceptance", diagnostics)

    def test_mobile_cleanup_failure_blocks_verified(self):
        diagnostics = self._evaluate(
            environment=MOBILE_ENVIRONMENT,
            cleanup_successful=False,
            expect={"manifest_status": "verified", "allow_fixture_evidence": True},
        )
        self.assertIn("cleanup incomplete: mobile-cleanup action lacks successful evidence", diagnostics)

    def test_production_external_effect_is_rejected(self):
        environment = {
            **MOBILE_ENVIRONMENT,
            "target_tier": "production",
            "external_effect_performed": True,
        }
        diagnostics = self._evaluate(
            environment=environment,
            cleanup_successful=True,
            expect={"manifest_status": "verified", "allow_fixture_evidence": True},
        )
        self.assertIn("production external effects are not allowed in mobile verification", diagnostics)

    def test_mobile_unit_requires_single_bound_extension(self):
        diagnostics = self._evaluate(
            environment=MOBILE_ENVIRONMENT,
            cleanup_successful=True,
            extension_id=None,
            expect={"manifest_status": "verified", "allow_fixture_evidence": True},
        )
        self.assertIn(
            "execution_unit unit-mobile does not reference the e2e.mobile@1.0 extension",
            diagnostics,
        )


class MobileCaseContractTests(unittest.TestCase):
    CASES = (
        "mobile-generate-appium",
        "mobile-generate-maestro",
        "mobile-verify-lifecycle",
        "mobile-upgrade",
        "mobile-production-refusal",
        "mobile-capability-unavailable",
        "mobile-product-defect",
        "mobile-cleanup-failure",
        "mobile-bootstrap-authorization",
        "mobile-bootstrap-authorized",
        "mobile-missing-credentials",
        "mobile-missing-artifact",
    )

    def test_mobile_cases_exist_and_use_mobile_contract(self):
        for case_id in self.CASES:
            path = ROOT / "evals/cases" / f"{case_id}.json"
            self.assertTrue(path.is_file(), case_id)
            case = json.loads(path.read_text())
            self.assertEqual(case["id"], case_id)
            self.assertEqual(case["entry_skill"], "e2e-mobile")
            self.assertEqual(case["surface"], "mobile")
            self.assertEqual(case["fixture"], "mobile-contract")

    def test_verified_mobile_cases_explicitly_allow_fixture_evidence(self):
        for case_id in ("mobile-verify-lifecycle", "mobile-upgrade"):
            case = json.loads(
                (ROOT / "evals/cases" / f"{case_id}.json").read_text()
            )
            self.assertTrue(case["expect"]["allow_fixture_evidence"])


if __name__ == "__main__":
    unittest.main()
