"""Contract tests for the mobile evaluation fixture, evaluator gates, and behavioral cases."""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unittest
from collections.abc import Callable
from pathlib import Path
from typing import Any

from evals.evaluate_result import _check_files, evaluate
from protocol.v2.e2e_protocol import new_manifest


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "evals/fixtures/mobile-contract"
ManifestMutation = Callable[[dict[str, Any]], None]


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
        mutate_manifest: ManifestMutation | None = None,
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
                        "id": "target-ios-sim",
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
                        "target_id": "target-ios-sim",
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
            if mutate_manifest is not None:
                mutate_manifest(manifest)
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

    def test_unknown_mobile_evidence_origin_is_rejected(self):
        environment = {**MOBILE_ENVIRONMENT, "evidence_origin": "shim"}
        diagnostics = self._evaluate(
            environment=environment,
            cleanup_successful=True,
            expect={"manifest_status": "verified", "allow_fixture_evidence": False},
        )
        self.assertIn(
            "mobile execution evidence has invalid evidence origin: shim",
            diagnostics,
        )

    def test_required_mobile_check_must_have_passing_execution_evidence(self):
        def make_required_check_fail_with_decoy_pass(manifest):
            manifest["checks"][0]["status"] = "failed"
            manifest["checks"].append({
                "id": "check-decoy",
                "journey_id": "journey-mobile",
                "execution_unit_id": "unit-mobile",
                "status": "passed",
            })
            execution = manifest["evidence"][0]
            execution["check_ids"] = ["check-decoy"]
            execution["outcomes"] = [{
                "check_id": "check-decoy",
                "status": "passed",
            }]

        diagnostics = self._evaluate(
            environment=MOBILE_ENVIRONMENT,
            cleanup_successful=True,
            expect={
                "manifest_status": "verified",
                "allow_fixture_evidence": True,
                "required_check_ids": ["check-mobile"],
            },
            mutate_manifest=make_required_check_fail_with_decoy_pass,
        )
        self.assertIn(
            "required mobile check lacks passing execution evidence: check-mobile",
            diagnostics,
        )

    def test_required_mobile_check_must_be_manifest_passed(self):
        def mark_matching_required_check_failed(manifest):
            manifest["checks"][0]["status"] = "failed"

        diagnostics = self._evaluate(
            environment=MOBILE_ENVIRONMENT,
            cleanup_successful=True,
            expect={
                "manifest_status": "verified",
                "allow_fixture_evidence": True,
                "required_check_ids": ["check-mobile"],
            },
            mutate_manifest=mark_matching_required_check_failed,
        )
        self.assertIn(
            "required mobile check lacks passing execution evidence: check-mobile",
            diagnostics,
        )

    def test_mobile_execution_target_must_match_bound_lifecycle(self):
        environment = {**MOBILE_ENVIRONMENT, "target_reference": "target-other"}
        diagnostics = self._evaluate(
            environment=environment,
            cleanup_successful=True,
            expect={"manifest_status": "verified", "allow_fixture_evidence": True},
        )
        self.assertIn(
            "mobile execution evidence references unknown target: target-other",
            diagnostics,
        )

    def test_mobile_execution_artifact_must_match_bound_lifecycle(self):
        environment = {
            **MOBILE_ENVIRONMENT,
            "application_build_ref": "artifact-other",
        }
        diagnostics = self._evaluate(
            environment=environment,
            cleanup_successful=True,
            expect={"manifest_status": "verified", "allow_fixture_evidence": True},
        )
        self.assertIn(
            "mobile execution evidence references unknown artifact: artifact-other",
            diagnostics,
        )

    def test_mobile_execution_driver_and_platform_must_match_target(self):
        environment = {
            **MOBILE_ENVIRONMENT,
            "driver": "maestro",
            "platform": "android",
        }
        diagnostics = self._evaluate(
            environment=environment,
            cleanup_successful=True,
            expect={"manifest_status": "verified", "allow_fixture_evidence": True},
        )
        self.assertIn(
            "mobile execution evidence does not match target target-ios-sim",
            diagnostics,
        )

    def test_mobile_cleanup_failure_blocks_verified(self):
        diagnostics = self._evaluate(
            environment=MOBILE_ENVIRONMENT,
            cleanup_successful=False,
            expect={"manifest_status": "verified", "allow_fixture_evidence": True},
        )
        self.assertIn("cleanup incomplete: mobile-cleanup action lacks successful evidence", diagnostics)

    def test_cleanup_failure_requires_failed_cleanup_and_inconclusive_classification(self):
        def make_label_only_cleanup_failure(manifest):
            manifest["run"]["status"] = "blocked"
            manifest["evidence"] = [{"id": "evidence-cleanup-failed"}]
            manifest["actions"] = []

        diagnostics = self._evaluate(
            environment=MOBILE_ENVIRONMENT,
            cleanup_successful=False,
            expect={
                "manifest_status": "blocked",
                "required_evidence_ids": ["evidence-cleanup-failed"],
                "required_action_capabilities": ["mobile-cleanup"],
                "required_classifications": ["inconclusive"],
                "required_cleanup_outcome": "failed",
            },
            mutate_manifest=make_label_only_cleanup_failure,
        )
        self.assertIn("missing action capability: mobile-cleanup", diagnostics)
        self.assertIn("missing evidence classification: inconclusive", diagnostics)
        self.assertIn("mobile cleanup failure lacks explicit failed evidence", diagnostics)

    def test_production_refusal_forbids_execution(self):
        diagnostics = self._evaluate(
            environment={**MOBILE_ENVIRONMENT, "target_tier": "production"},
            cleanup_successful=True,
            expect={
                "manifest_status": "verified",
                "allow_fixture_evidence": True,
                "forbid_execution": True,
            },
        )
        self.assertIn("mobile case forbids execution evidence", diagnostics)

    def test_bootstrap_authorization_requires_two_distinct_capabilities(self):
        def make_unrelated_authorization(manifest):
            manifest["run"]["status"] = "needs-authorization"
            manifest["actions"] = [{
                "id": "action-unrelated",
                "capability": "unrelated",
                "journey_ids": [],
            }]
            manifest["evidence"].append({
                "id": "evidence-authorization",
                "classification": {
                    "primary": "authorization-required",
                    "confidence": 1.0,
                    "rationale": "authorization is required",
                    "evidence_ids": ["evidence-mobile"],
                },
            })

        diagnostics = self._evaluate(
            environment=MOBILE_ENVIRONMENT,
            cleanup_successful=True,
            expect={
                "manifest_status": "needs-authorization",
                "required_action_capabilities": [
                    "mobile-repository-bootstrap",
                    "mobile-host-prerequisite",
                ],
                "required_classifications": ["authorization-required"],
                "forbid_execution": True,
            },
            mutate_manifest=make_unrelated_authorization,
        )
        self.assertIn(
            "missing action capability: mobile-repository-bootstrap",
            diagnostics,
        )
        self.assertIn(
            "missing action capability: mobile-host-prerequisite",
            diagnostics,
        )

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

    def test_mobile_surface_requires_a_mobile_execution_unit(self):
        def remove_mobile_unit(manifest):
            manifest["execution_units"] = []
            manifest["checks"] = []

        diagnostics = self._evaluate(
            environment=MOBILE_ENVIRONMENT,
            cleanup_successful=True,
            expect={"manifest_status": "verified", "allow_fixture_evidence": True},
            mutate_manifest=remove_mobile_unit,
        )
        self.assertIn(
            "mobile case requires at least one mobile execution unit",
            diagnostics,
        )

    def test_mobile_target_driver_reference_must_resolve(self):
        def break_driver_reference(manifest):
            mobile = manifest["extensions"][0]["data"]
            mobile["targets"][0]["driver_id"] = "driver-missing"

        diagnostics = self._evaluate(
            environment=MOBILE_ENVIRONMENT,
            cleanup_successful=True,
            expect={"manifest_status": "verified", "allow_fixture_evidence": True},
            mutate_manifest=break_driver_reference,
        )
        self.assertIn(
            "mobile target target-ios-sim references unknown driver driver-missing",
            diagnostics,
        )

    def test_mobile_lifecycle_references_must_resolve(self):
        mutations = (
            ("execution_unit_id", "unit-missing", "execution unit"),
            ("target_id", "target-missing", "target"),
        )
        for field, value, label in mutations:
            with self.subTest(field=field):
                def break_reference(manifest, field=field, value=value):
                    profile = manifest["extensions"][0]["data"]["lifecycle_profiles"][0]
                    profile[field] = value

                diagnostics = self._evaluate(
                    environment=MOBILE_ENVIRONMENT,
                    cleanup_successful=True,
                    expect={"manifest_status": "verified", "allow_fixture_evidence": True},
                    mutate_manifest=break_reference,
                )
                self.assertIn(
                    f"mobile lifecycle lifecycle-ios references unknown {label} {value}",
                    diagnostics,
                )

    def test_mobile_lifecycle_artifact_reference_must_resolve(self):
        def break_artifact_reference(manifest):
            profile = manifest["extensions"][0]["data"]["lifecycle_profiles"][0]
            profile["artifact_ids"] = ["artifact-missing"]

        diagnostics = self._evaluate(
            environment=MOBILE_ENVIRONMENT,
            cleanup_successful=True,
            expect={"manifest_status": "verified", "allow_fixture_evidence": True},
            mutate_manifest=break_artifact_reference,
        )
        self.assertIn(
            "mobile lifecycle lifecycle-ios references unknown artifact artifact-missing",
            diagnostics,
        )

    def test_mobile_artifact_must_reference_the_declared_application(self):
        def break_application_reference(manifest):
            artifact = manifest["extensions"][0]["data"]["artifacts"][0]
            artifact["application_id"] = "app-other"

        diagnostics = self._evaluate(
            environment=MOBILE_ENVIRONMENT,
            cleanup_successful=True,
            expect={"manifest_status": "verified", "allow_fixture_evidence": True},
            mutate_manifest=break_application_reference,
        )
        self.assertIn(
            "mobile artifact artifact-candidate-ios does not reference application app-mobile",
            diagnostics,
        )

    def test_upgrade_requires_exactly_one_prior_and_candidate(self):
        def make_invalid_upgrade(manifest):
            profile = manifest["extensions"][0]["data"]["lifecycle_profiles"][0]
            profile["upgrade"] = True
            profile["install_policy"] = "upgrade"

        diagnostics = self._evaluate(
            environment=MOBILE_ENVIRONMENT,
            cleanup_successful=True,
            expect={"manifest_status": "verified", "allow_fixture_evidence": True},
            mutate_manifest=make_invalid_upgrade,
        )
        self.assertIn(
            "mobile lifecycle lifecycle-ios upgrade requires one prior and one candidate artifact",
            diagnostics,
        )

    def test_upgrade_requires_prior_artifact_before_candidate(self):
        def reverse_upgrade_artifacts(manifest):
            mobile = manifest["extensions"][0]["data"]
            mobile["artifacts"].append({
                **mobile["artifacts"][0],
                "id": "artifact-prior-ios",
                "role": "prior",
                "artifact_ref": "prior-ios",
                "build_ref": "prior-1",
            })
            profile = mobile["lifecycle_profiles"][0]
            profile.update(
                artifact_ids=["artifact-candidate-ios", "artifact-prior-ios"],
                upgrade=True,
                install_policy="upgrade",
            )

        diagnostics = self._evaluate(
            environment=MOBILE_ENVIRONMENT,
            cleanup_successful=True,
            expect={"manifest_status": "verified", "allow_fixture_evidence": True},
            mutate_manifest=reverse_upgrade_artifacts,
        )
        self.assertIn(
            "mobile lifecycle lifecycle-ios upgrade requires artifacts ordered prior then candidate",
            diagnostics,
        )

    def test_mobile_extension_duplicate_driver_ids_are_rejected(self):
        def duplicate_driver(manifest):
            mobile = manifest["extensions"][0]["data"]
            mobile["drivers"].append(dict(mobile["drivers"][0]))

        diagnostics = self._evaluate(
            environment=MOBILE_ENVIRONMENT,
            cleanup_successful=True,
            expect={"manifest_status": "verified", "allow_fixture_evidence": True},
            mutate_manifest=duplicate_driver,
        )
        self.assertIn("duplicate mobile driver id: driver-appium", diagnostics)

    def test_mobile_extension_duplicate_target_ids_are_rejected(self):
        def duplicate_target(manifest):
            mobile = manifest["extensions"][0]["data"]
            mobile["targets"].append(dict(mobile["targets"][0]))

        diagnostics = self._evaluate(
            environment=MOBILE_ENVIRONMENT,
            cleanup_successful=True,
            expect={"manifest_status": "verified", "allow_fixture_evidence": True},
            mutate_manifest=duplicate_target,
        )
        self.assertIn("duplicate mobile target id: target-ios-sim", diagnostics)

    def test_mobile_extension_duplicate_artifact_ids_are_rejected(self):
        def duplicate_artifact(manifest):
            mobile = manifest["extensions"][0]["data"]
            mobile["artifacts"].append(dict(mobile["artifacts"][0]))

        diagnostics = self._evaluate(
            environment=MOBILE_ENVIRONMENT,
            cleanup_successful=True,
            expect={"manifest_status": "verified", "allow_fixture_evidence": True},
            mutate_manifest=duplicate_artifact,
        )
        self.assertIn("duplicate mobile artifact id: artifact-candidate-ios", diagnostics)

    def test_mobile_extension_duplicate_lifecycle_ids_are_rejected(self):
        def duplicate_lifecycle(manifest):
            mobile = manifest["extensions"][0]["data"]
            mobile["lifecycle_profiles"].append(
                dict(mobile["lifecycle_profiles"][0])
            )

        diagnostics = self._evaluate(
            environment=MOBILE_ENVIRONMENT,
            cleanup_successful=True,
            expect={"manifest_status": "verified", "allow_fixture_evidence": True},
            mutate_manifest=duplicate_lifecycle,
        )
        self.assertIn("duplicate mobile lifecycle id: lifecycle-ios", diagnostics)

    def test_virtual_snapshot_requires_a_disposable_virtual_target(self):
        def make_real_snapshot(manifest):
            target = manifest["extensions"][0]["data"]["targets"][0]
            target.update(kind="real", disposable=False)
            profile = manifest["extensions"][0]["data"]["lifecycle_profiles"][0]
            profile["reset_policy"] = "virtual-snapshot"

        diagnostics = self._evaluate(
            environment=MOBILE_ENVIRONMENT,
            cleanup_successful=True,
            expect={"manifest_status": "verified", "allow_fixture_evidence": True},
            mutate_manifest=make_real_snapshot,
        )
        self.assertIn(
            "mobile lifecycle lifecycle-ios virtual-snapshot requires a disposable virtual target",
            diagnostics,
        )

    def test_real_or_remote_target_must_be_provisioned(self):
        def make_unprovisioned_real_target(manifest):
            target = manifest["extensions"][0]["data"]["targets"][0]
            target.update(kind="real", provisioning_status="unknown")

        diagnostics = self._evaluate(
            environment=MOBILE_ENVIRONMENT,
            cleanup_successful=True,
            expect={"manifest_status": "verified", "allow_fixture_evidence": True},
            mutate_manifest=make_unprovisioned_real_target,
        )
        self.assertIn("mobile target target-ios-sim is not provisioned", diagnostics)


class MobileCaseContractTests(unittest.TestCase):
    def _case(self, case_id):
        return json.loads(
            (ROOT / "evals/cases" / f"{case_id}.json").read_text()
        )

    def test_mobile_cases_declare_their_durable_acceptance_contracts(self):
        expected = {
            "mobile-generate-appium": {
                "allowed_change_globs": ["**/appium/**", "**/appium*.js"],
                "forbid_execution": True,
            },
            "mobile-generate-maestro": {
                "allowed_change_globs": ["**/.maestro/**"],
                "forbid_execution": True,
            },
            "mobile-verify-lifecycle": {
                "required_cleanup_outcome": "successful",
            },
            "mobile-upgrade": {
                "required_artifact_roles": ["prior", "candidate"],
                "required_lifecycle_sequence": [
                    "target",
                    "prior-install",
                    "prior-state",
                    "candidate-upgrade",
                    "launch",
                    "cleanup",
                ],
                "required_cleanup_outcome": "successful",
            },
            "mobile-production-refusal": {
                "required_action_capabilities": [
                    "authorize-production-mobile-observation",
                ],
                "required_classifications": ["authorization-required"],
                "forbid_execution": True,
            },
            "mobile-capability-unavailable": {
                "required_capability_target_evidence": True,
            },
            "mobile-cleanup-failure": {
                "required_action_capabilities": ["mobile-cleanup"],
                "required_classifications": ["inconclusive"],
                "required_cleanup_outcome": "failed",
            },
            "mobile-bootstrap-authorization": {
                "required_action_capabilities": [
                    "mobile-repository-bootstrap",
                    "mobile-host-prerequisite",
                ],
                "required_classifications": ["authorization-required"],
                "forbid_execution": True,
            },
            "mobile-bootstrap-authorized": {
                "required_driver_bootstrap": {
                    "kind": "appium",
                    "status": "authorized",
                    "authorization_ref": "authorization-mobile-bootstrap",
                },
                "allowed_change_globs": [
                    "**/appium/**",
                    "**/appium*.js",
                    "package.json",
                    "package-lock.json",
                ],
                "forbid_execution": True,
            },
            "mobile-missing-credentials": {
                "required_action_capabilities": ["provide-mobile-credentials"],
                "required_classifications": ["authorization-required"],
                "require_empty_credential_refs": True,
                "forbid_execution": True,
            },
            "mobile-missing-artifact": {
                "forbidden_artifact_roles": ["candidate"],
                "forbidden_command_terms": ["build", "install"],
                "forbid_execution": True,
            },
        }
        for case_id, requirements in expected.items():
            with self.subTest(case_id=case_id):
                expect = self._case(case_id)["expect"]
                for key, value in requirements.items():
                    self.assertEqual(expect.get(key), value)

    def test_allowed_mobile_changes_reject_unrelated_workspace_edits(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "workspace"
            shutil.copytree(FIXTURE, workspace)
            app = workspace / "mobile/app.json"
            app.write_text(app.read_text() + "\n", encoding="utf-8")

            diagnostics = _check_files(
                workspace,
                FIXTURE,
                {"allowed_change_globs": ["**/appium/**", "**/appium*.js"]},
            )

        self.assertIn("unauthorized mobile case change: mobile/app.json", diagnostics)


if __name__ == "__main__":
    unittest.main()
