"""Contract tests for the mobile evaluation fixture, evaluator gates, and behavioral cases."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import tempfile
import unittest
from collections.abc import Callable
from pathlib import Path
from typing import Any

from evals import run_host_eval
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

    def test_required_mobile_execution_rejects_boolean_or_non_integer_exit_code(self):
        for exit_code in (False, 0.0):
            with self.subTest(exit_code=exit_code):
                def make_invalid_exit_code(manifest, exit_code=exit_code):
                    manifest["evidence"][0]["exit_code"] = exit_code

                diagnostics = self._evaluate(
                    environment=MOBILE_ENVIRONMENT,
                    cleanup_successful=True,
                    expect={
                        "manifest_status": "verified",
                        "allow_fixture_evidence": True,
                        "required_check_ids": ["check-mobile"],
                        "required_execution_evidence_ids": ["evidence-mobile"],
                    },
                    mutate_manifest=make_invalid_exit_code,
                )
                self.assertIn(
                    "required mobile check lacks passing execution evidence: "
                    "check-mobile",
                    diagnostics,
                )

    def test_required_mobile_execution_rejects_boolean_or_negative_duration(self):
        for duration in (True, -1):
            with self.subTest(duration=duration):
                def make_invalid_duration(manifest, duration=duration):
                    manifest["evidence"][0]["duration_ms"] = duration

                diagnostics = self._evaluate(
                    environment=MOBILE_ENVIRONMENT,
                    cleanup_successful=True,
                    expect={
                        "manifest_status": "verified",
                        "allow_fixture_evidence": True,
                        "required_check_ids": ["check-mobile"],
                        "required_execution_evidence_ids": ["evidence-mobile"],
                    },
                    mutate_manifest=make_invalid_duration,
                )
                self.assertIn(
                    "required mobile check lacks passing execution evidence: "
                    "check-mobile",
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

    def test_non_upgrade_execution_selects_unique_lifecycle_independent_of_order(self):
        for insert_at_start in (False, True):
            with self.subTest(insert_at_start=insert_at_start):
                def add_distinct_same_unit_profile(
                    manifest,
                    insert_at_start=insert_at_start,
                ):
                    mobile = manifest["extensions"][0]["data"]
                    mobile["targets"].append({
                        **mobile["targets"][0],
                        "id": "target-ios-other",
                    })
                    mobile["artifacts"].append({
                        **mobile["artifacts"][0],
                        "id": "artifact-candidate-other",
                        "artifact_ref": "candidate-other",
                        "build_ref": "candidate-other-1",
                    })
                    profile = {
                        **mobile["lifecycle_profiles"][0],
                        "id": "lifecycle-ios-other",
                        "target_id": "target-ios-other",
                        "artifact_ids": ["artifact-candidate-other"],
                    }
                    if insert_at_start:
                        mobile["lifecycle_profiles"].insert(0, profile)
                    else:
                        mobile["lifecycle_profiles"].append(profile)

                diagnostics = self._evaluate(
                    environment=MOBILE_ENVIRONMENT,
                    cleanup_successful=True,
                    expect={
                        "manifest_status": "verified",
                        "allow_fixture_evidence": True,
                        "required_check_ids": ["check-mobile"],
                        "required_execution_evidence_ids": ["evidence-mobile"],
                    },
                    mutate_manifest=add_distinct_same_unit_profile,
                )
                self.assertNotIn(
                    "mobile execution evidence is not bound to lifecycle for "
                    "unit-mobile",
                    diagnostics,
                )

    def test_non_upgrade_execution_rejects_ambiguous_same_unit_lifecycle(self):
        def add_ambiguous_same_unit_profile(manifest):
            mobile = manifest["extensions"][0]["data"]
            mobile["lifecycle_profiles"].append({
                **mobile["lifecycle_profiles"][0],
                "id": "lifecycle-ios-ambiguous",
            })

        diagnostics = self._evaluate(
            environment=MOBILE_ENVIRONMENT,
            cleanup_successful=True,
            expect={
                "manifest_status": "verified",
                "allow_fixture_evidence": True,
                "required_check_ids": ["check-mobile"],
                "required_execution_evidence_ids": ["evidence-mobile"],
            },
            mutate_manifest=add_ambiguous_same_unit_profile,
        )
        self.assertIn(
            "mobile execution evidence is not bound to lifecycle for unit-mobile",
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

    def test_production_refusal_rejects_invalid_bound_classification_confidence(self):
        for confidence in (True, float("inf"), 1.1):
            with self.subTest(confidence=confidence):
                def make_bound_production_refusal(
                    manifest,
                    confidence=confidence,
                ):
                    manifest["run"]["status"] = "needs-authorization"
                    manifest["evidence"] = [{
                        "id": "evidence-production-authorization",
                        "surface": "mobile",
                        "read_only": True,
                    }, {
                        "id": "evidence-production-classification",
                        "classification": {
                            "primary": "authorization-required",
                            "confidence": confidence,
                            "rationale": "production access is not authorized",
                            "evidence_ids": [
                                "evidence-production-authorization"
                            ],
                        },
                    }]
                    manifest["actions"] = [{
                        "id": "action-production-authorization",
                        "capability":
                            "authorize-production-mobile-observation",
                        "journey_ids": ["journey-mobile"],
                        "evidence_ids": [
                            "evidence-production-authorization"
                        ],
                    }]

                expect = json.loads(
                    (
                        ROOT / "evals/cases/mobile-production-refusal.json"
                    ).read_text()
                )["expect"]
                diagnostics = self._evaluate(
                    environment={
                        **MOBILE_ENVIRONMENT,
                        "target_tier": "production",
                    },
                    cleanup_successful=True,
                    expect=expect,
                    mutate_manifest=make_bound_production_refusal,
                )
                self.assertIn(
                    "missing evidence classification: "
                    "authorization-required",
                    diagnostics,
                )

    def test_cleanup_failure_rejects_invalid_bound_classification_confidence(self):
        for confidence in (True, float("inf"), 1.1):
            with self.subTest(confidence=confidence):
                def make_bound_cleanup_failure(
                    manifest,
                    confidence=confidence,
                ):
                    manifest["run"]["status"] = "blocked"
                    manifest["checks"][0]["id"] = "check-cleanup-passed"
                    execution = manifest["evidence"][0]
                    execution.update(
                        check_ids=["check-cleanup-passed"],
                        outcomes=[{
                            "check_id": "check-cleanup-passed",
                            "status": "passed",
                        }],
                    )
                    manifest["evidence"] = [execution, {
                        "id": "evidence-cleanup-failed",
                        "cleanup_action_id": "action-mobile-cleanup",
                        "cleanup_successful": False,
                    }, {
                        "id": "evidence-cleanup-classification",
                        "classification": {
                            "primary": "inconclusive",
                            "confidence": confidence,
                            "rationale": "cleanup could not be restored",
                            "evidence_ids": ["evidence-cleanup-failed"],
                        },
                    }]

                expect = json.loads(
                    (
                        ROOT / "evals/cases/mobile-cleanup-failure.json"
                    ).read_text()
                )["expect"]
                diagnostics = self._evaluate(
                    environment=MOBILE_ENVIRONMENT,
                    cleanup_successful=False,
                    expect=expect,
                    mutate_manifest=make_bound_cleanup_failure,
                )
                self.assertIn(
                    "missing evidence classification: inconclusive",
                    diagnostics,
                )

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

    def test_cleanup_requirements_reject_unbound_action_and_self_referential_classification(self):
        def make_unbound_cleanup_records(manifest):
            manifest["run"]["status"] = "blocked"
            manifest["evidence"] = [{
                "id": "evidence-cleanup-failed",
                "cleanup_action_id": "action-other",
                "cleanup_successful": False,
            }, {
                "id": "evidence-classification",
                "classification": {
                    "primary": "inconclusive",
                    "confidence": 1.0,
                    "rationale": "cleanup could not be restored",
                    "evidence_ids": ["evidence-classification"],
                },
            }]
            manifest["actions"] = [{
                "id": "action-mobile-cleanup",
                "capability": "mobile-cleanup",
                "journey_ids": ["journey-mobile"],
                "evidence_ids": ["evidence-classification"],
            }]

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
            mutate_manifest=make_unbound_cleanup_records,
        )
        self.assertIn("missing action capability: mobile-cleanup", diagnostics)
        self.assertIn("missing evidence classification: inconclusive", diagnostics)

    def test_cleanup_action_must_cover_each_required_check_journey(self):
        for journey_ids in ([], ["journey-unrelated"]):
            with self.subTest(journey_ids=journey_ids):
                def scope_cleanup_to_wrong_journey(manifest, journey_ids=journey_ids):
                    manifest["journeys"].append({
                        "id": "journey-unrelated",
                        "system_id": "system-primary",
                        "status": "verified",
                    })
                    manifest["actions"][0]["journey_ids"] = journey_ids

                diagnostics = self._evaluate(
                    environment=MOBILE_ENVIRONMENT,
                    cleanup_successful=True,
                    expect={
                        "manifest_status": "verified",
                        "allow_fixture_evidence": True,
                        "required_check_ids": ["check-mobile"],
                        "required_evidence_ids": ["evidence-cleanup"],
                        "required_action_capabilities": ["mobile-cleanup"],
                        "required_cleanup_outcome": "successful",
                    },
                    mutate_manifest=scope_cleanup_to_wrong_journey,
                )
                self.assertIn("missing action capability: mobile-cleanup", diagnostics)

    def test_case_cleanup_outcome_must_cover_required_check_journey_without_required_capability(self):
        cases = {
            "mobile-verify-lifecycle": {
                "journey_id": "journey-mobile-lifecycle",
                "check_ids": ["check-ios-login", "check-android-login"],
                "evidence_id": "evidence-mobile-execution",
            },
            "mobile-upgrade": {
                "journey_id": "journey-mobile-upgrade",
                "check_ids": ["check-upgrade-visible"],
                "evidence_id": "evidence-mobile-upgrade",
            },
        }
        for case_id, scope in cases.items():
            with self.subTest(case_id=case_id):
                def bind_cleanup_only_to_unrelated_journey(
                    manifest,
                    case_id=case_id,
                    scope=scope,
                ):
                    manifest["journeys"][0]["id"] = scope["journey_id"]
                    manifest["journeys"].append({
                        "id": "journey-unrelated",
                        "system_id": "system-primary",
                        "status": "verified",
                    })
                    manifest["checks"][0].update(
                        id=scope["check_ids"][0],
                        journey_id=scope["journey_id"],
                    )
                    for check_id in scope["check_ids"][1:]:
                        manifest["checks"].append({
                            "id": check_id,
                            "journey_id": scope["journey_id"],
                            "execution_unit_id": "unit-mobile",
                            "status": "passed",
                        })
                    execution = manifest["evidence"][0]
                    execution["id"] = scope["evidence_id"]
                    execution["check_ids"] = scope["check_ids"]
                    execution["outcomes"] = [
                        {"check_id": check_id, "status": "passed"}
                        for check_id in scope["check_ids"]
                    ]
                    manifest["actions"][0]["journey_ids"] = [
                        "journey-unrelated"
                    ]
                    if case_id == "mobile-upgrade":
                        sequence = [
                            "target",
                            "prior-install",
                            "prior-state",
                            "candidate-upgrade",
                            "launch",
                            "cleanup",
                        ]
                        execution["lifecycle"] = sequence
                        mobile = manifest["extensions"][0]["data"]
                        mobile["artifacts"].insert(0, {
                            **mobile["artifacts"][0],
                            "id": "artifact-prior-ios",
                            "role": "prior",
                            "artifact_ref": "prior-ios",
                            "build_ref": "prior-1",
                        })
                        mobile["lifecycle_profiles"][0].update(
                            upgrade=True,
                            artifact_ids=[
                                "artifact-prior-ios",
                                "artifact-candidate-ios",
                            ],
                        )

                expect = json.loads(
                    (
                        ROOT / "evals/cases" / f"{case_id}.json"
                    ).read_text()
                )["expect"]
                diagnostics = self._evaluate(
                    environment=MOBILE_ENVIRONMENT,
                    cleanup_successful=True,
                    expect=expect,
                    mutate_manifest=bind_cleanup_only_to_unrelated_journey,
                )
                self.assertIn(
                    "mobile cleanup success lacks explicit evidence",
                    diagnostics,
                )

    def test_authorization_requirements_reject_records_unbound_to_expected_evidence(self):
        def make_unbound_authorization_records(manifest):
            manifest["run"]["status"] = "needs-authorization"
            manifest["evidence"] = [{
                "id": "evidence-authorization-context",
                "surface": "mobile",
                "read_only": True,
            }, {
                "id": "evidence-unrelated",
                "surface": "mobile",
                "read_only": True,
            }, {
                "id": "evidence-authorization-classification",
                "classification": {
                    "primary": "authorization-required",
                    "confidence": 1.0,
                    "rationale": "some authorization is required",
                    "evidence_ids": ["evidence-unrelated"],
                },
            }]
            manifest["actions"] = [{
                "id": "action-authorization",
                "capability": "provide-mobile-credentials",
                "journey_ids": ["journey-mobile"],
                "evidence_ids": ["evidence-unrelated"],
            }]

        diagnostics = self._evaluate(
            environment=MOBILE_ENVIRONMENT,
            cleanup_successful=True,
            expect={
                "manifest_status": "needs-authorization",
                "required_evidence_ids": ["evidence-authorization-context"],
                "required_action_capabilities": ["provide-mobile-credentials"],
                "required_classifications": ["authorization-required"],
                "forbid_execution": True,
            },
            mutate_manifest=make_unbound_authorization_records,
        )
        self.assertIn("missing action capability: provide-mobile-credentials", diagnostics)
        self.assertIn(
            "missing evidence classification: authorization-required",
            diagnostics,
        )

    def test_forbid_execution_rejects_command_evidence_without_selected_checks(self):
        for check_ids in (None, []):
            with self.subTest(check_ids=check_ids):
                def make_forbidden_attempt(manifest, check_ids=check_ids):
                    manifest["run"]["status"] = "generated-unverified"
                    attempt = {
                        "id": "evidence-driver-attempt",
                        "command": "appium driver install xcuitest",
                        "exit_code": 1,
                        "duration_ms": 5,
                        "execution_environment": {
                            "driver": "appium",
                        },
                    }
                    if check_ids is not None:
                        attempt["check_ids"] = check_ids
                    manifest["evidence"] = [attempt]
                    manifest["actions"] = []

                diagnostics = self._evaluate(
                    environment=MOBILE_ENVIRONMENT,
                    cleanup_successful=True,
                    expect={
                        "manifest_status": "generated-unverified",
                        "forbid_execution": True,
                    },
                    mutate_manifest=make_forbidden_attempt,
                )
                self.assertIn("mobile case forbids execution evidence", diagnostics)

    def test_forbid_execution_does_not_reject_pure_operation_labels(self):
        def make_label_only_records(manifest):
            manifest["run"]["status"] = "generated-unverified"
            manifest["evidence"] = [{
                "id": "evidence-plan",
                "kind": "plan",
                "operations": ["build", "install", "launch", "driver"],
            }]
            manifest["actions"] = []

        diagnostics = self._evaluate(
            environment=MOBILE_ENVIRONMENT,
            cleanup_successful=True,
            expect={
                "manifest_status": "generated-unverified",
                "forbid_execution": True,
            },
            mutate_manifest=make_label_only_records,
        )
        self.assertNotIn("mobile case forbids execution evidence", diagnostics)

    def test_upgrade_expectations_bind_to_selected_upgrade_lifecycle_and_evidence(self):
        required_sequence = [
            "target",
            "prior-install",
            "prior-state",
            "candidate-upgrade",
            "launch",
            "cleanup",
        ]

        def add_unbound_upgrade_records(manifest):
            mobile = manifest["extensions"][0]["data"]
            mobile["artifacts"].append({
                **mobile["artifacts"][0],
                "id": "artifact-prior-unused",
                "role": "prior",
                "artifact_ref": "prior-unused",
                "build_ref": "prior-unused-1",
            })
            manifest["evidence"].append({
                "id": "evidence-unrelated-upgrade",
                "lifecycle": required_sequence,
            })

        diagnostics = self._evaluate(
            environment=MOBILE_ENVIRONMENT,
            cleanup_successful=True,
            expect={
                "manifest_status": "verified",
                "allow_fixture_evidence": True,
                "required_execution_evidence_ids": ["evidence-mobile"],
                "required_artifact_roles": ["prior", "candidate"],
                "required_lifecycle_sequence": required_sequence,
            },
            mutate_manifest=add_unbound_upgrade_records,
        )
        self.assertIn("mobile required lifecycle is not an upgrade", diagnostics)
        self.assertIn("missing mobile artifact role: prior", diagnostics)
        self.assertIn(
            "mobile lifecycle evidence is missing the required sequence",
            diagnostics,
        )

    def test_upgrade_expectations_ignore_extra_checks_on_an_unrelated_upgrade_unit(self):
        required_sequence = [
            "target",
            "prior-install",
            "prior-state",
            "candidate-upgrade",
            "launch",
            "cleanup",
        ]

        def add_extra_upgrade_unit(manifest):
            manifest["execution_units"].append({
                **manifest["execution_units"][0],
                "id": "unit-extra",
            })
            manifest["checks"].append({
                "id": "check-extra",
                "journey_id": "journey-mobile",
                "execution_unit_id": "unit-extra",
                "status": "passed",
            })
            execution = manifest["evidence"][0]
            execution["check_ids"].append("check-extra")
            execution["outcomes"].append({
                "check_id": "check-extra",
                "status": "passed",
            })
            execution["lifecycle"] = required_sequence
            mobile = manifest["extensions"][0]["data"]
            mobile["artifacts"].append({
                **mobile["artifacts"][0],
                "id": "artifact-prior-extra",
                "role": "prior",
                "artifact_ref": "prior-extra",
                "build_ref": "prior-extra-1",
            })
            mobile["lifecycle_profiles"].append({
                **mobile["lifecycle_profiles"][0],
                "id": "lifecycle-extra",
                "execution_unit_id": "unit-extra",
                "artifact_ids": [
                    "artifact-prior-extra",
                    "artifact-candidate-ios",
                ],
                "install_policy": "upgrade",
                "upgrade": True,
            })

        diagnostics = self._evaluate(
            environment=MOBILE_ENVIRONMENT,
            cleanup_successful=True,
            expect={
                "manifest_status": "verified",
                "allow_fixture_evidence": True,
                "required_check_ids": ["check-mobile"],
                "required_execution_evidence_ids": ["evidence-mobile"],
                "required_artifact_roles": ["prior", "candidate"],
                "required_lifecycle_sequence": required_sequence,
            },
            mutate_manifest=add_extra_upgrade_unit,
        )
        self.assertIn("mobile required lifecycle is not an upgrade", diagnostics)
        self.assertIn("missing mobile artifact role: prior", diagnostics)
        self.assertIn(
            "mobile lifecycle evidence is missing the required sequence",
            diagnostics,
        )

    def test_case_upgrade_rejects_same_unit_decoy_upgrade_lifecycle(self):
        sequence = [
            "target",
            "prior-install",
            "prior-state",
            "candidate-upgrade",
            "launch",
            "cleanup",
        ]

        def add_decoy_upgrade_profile(manifest):
            manifest["journeys"][0]["id"] = "journey-mobile-upgrade"
            manifest["checks"][0].update(
                id="check-upgrade-visible",
                journey_id="journey-mobile-upgrade",
            )
            execution = manifest["evidence"][0]
            execution.update(
                id="evidence-mobile-upgrade",
                check_ids=["check-upgrade-visible"],
                outcomes=[{
                    "check_id": "check-upgrade-visible",
                    "status": "passed",
                }],
                lifecycle=sequence,
            )
            manifest["actions"][0]["journey_ids"] = [
                "journey-mobile-upgrade"
            ]
            mobile = manifest["extensions"][0]["data"]
            mobile["artifacts"].insert(0, {
                **mobile["artifacts"][0],
                "id": "artifact-prior-ios",
                "role": "prior",
                "artifact_ref": "prior-ios",
                "build_ref": "prior-1",
            })
            mobile["lifecycle_profiles"].append({
                **mobile["lifecycle_profiles"][0],
                "id": "lifecycle-decoy-upgrade",
                "artifact_ids": [
                    "artifact-prior-ios",
                    "artifact-candidate-ios",
                ],
                "install_policy": "upgrade",
                "upgrade": True,
            })

        expect = json.loads(
            (ROOT / "evals/cases/mobile-upgrade.json").read_text()
        )["expect"]
        diagnostics = self._evaluate(
            environment=MOBILE_ENVIRONMENT,
            cleanup_successful=True,
            expect=expect,
            mutate_manifest=add_decoy_upgrade_profile,
        )
        self.assertIn(
            "mobile required lifecycle selection is ambiguous or unbound",
            diagnostics,
        )

    def test_required_bootstrap_is_checked_on_selected_target_driver(self):
        def authorize_unused_driver(manifest):
            mobile = manifest["extensions"][0]["data"]
            mobile["drivers"].append({
                **mobile["drivers"][0],
                "id": "driver-appium-unused",
                "bootstrap_status": "authorized",
                "authorization_ref": "authorization-mobile-bootstrap",
            })

        diagnostics = self._evaluate(
            environment=MOBILE_ENVIRONMENT,
            cleanup_successful=True,
            expect={
                "manifest_status": "verified",
                "allow_fixture_evidence": True,
                "required_driver_bootstrap": {
                    "kind": "appium",
                    "status": "authorized",
                    "authorization_ref": "authorization-mobile-bootstrap",
                },
            },
            mutate_manifest=authorize_unused_driver,
        )
        self.assertIn(
            "mobile driver lacks required bootstrap authorization",
            diagnostics,
        )

    def test_required_bootstrap_ignores_another_bound_mobile_unit(self):
        def authorize_another_bound_unit(manifest):
            manifest["execution_units"].append({
                **manifest["execution_units"][0],
                "id": "unit-extra",
            })
            mobile = manifest["extensions"][0]["data"]
            mobile["drivers"].append({
                **mobile["drivers"][0],
                "id": "driver-appium-extra",
                "bootstrap_status": "authorized",
                "authorization_ref": "authorization-mobile-bootstrap",
            })
            mobile["targets"].append({
                **mobile["targets"][0],
                "id": "target-extra",
                "driver_id": "driver-appium-extra",
            })
            mobile["lifecycle_profiles"].append({
                **mobile["lifecycle_profiles"][0],
                "id": "lifecycle-extra",
                "execution_unit_id": "unit-extra",
                "target_id": "target-extra",
            })

        diagnostics = self._evaluate(
            environment=MOBILE_ENVIRONMENT,
            cleanup_successful=True,
            expect={
                "manifest_status": "verified",
                "allow_fixture_evidence": True,
                "required_check_ids": ["check-mobile"],
                "required_driver_bootstrap": {
                    "kind": "appium",
                    "status": "authorized",
                    "authorization_ref": "authorization-mobile-bootstrap",
                },
            },
            mutate_manifest=authorize_another_bound_unit,
        )
        self.assertIn(
            "mobile driver lacks required bootstrap authorization",
            diagnostics,
        )

    def test_case_bootstrap_ignores_unevidenced_extra_passed_unit(self):
        def authorize_unevidenced_extra_unit(manifest):
            manifest["run"].update(
                status="generated-unverified",
                mode="generate",
            )
            manifest["execution_units"].append({
                **manifest["execution_units"][0],
                "id": "unit-extra",
            })
            manifest["checks"].append({
                "id": "check-extra",
                "journey_id": "journey-mobile",
                "execution_unit_id": "unit-extra",
                "status": "passed",
            })
            mobile = manifest["extensions"][0]["data"]
            mobile["drivers"].append({
                **mobile["drivers"][0],
                "id": "driver-appium-extra",
                "bootstrap_status": "authorized",
                "authorization_ref": "authorization-mobile-bootstrap",
            })
            mobile["targets"].append({
                **mobile["targets"][0],
                "id": "target-extra",
                "driver_id": "driver-appium-extra",
            })
            mobile["lifecycle_profiles"].append({
                **mobile["lifecycle_profiles"][0],
                "id": "lifecycle-extra",
                "execution_unit_id": "unit-extra",
                "target_id": "target-extra",
            })

        expect = json.loads(
            (
                ROOT / "evals/cases/mobile-bootstrap-authorized.json"
            ).read_text()
        )["expect"]
        diagnostics = self._evaluate(
            environment=MOBILE_ENVIRONMENT,
            cleanup_successful=True,
            expect=expect,
            mutate_manifest=authorize_unevidenced_extra_unit,
        )
        self.assertIn(
            "mobile driver lacks required bootstrap authorization",
            diagnostics,
        )

    def test_case_bootstrap_accepts_single_unambiguous_no_execution_lifecycle(self):
        def authorize_only_bound_driver_without_execution(manifest):
            manifest["run"].update(
                status="generated-unverified",
                mode="generate",
            )
            manifest["journeys"][0]["status"] = "planned"
            manifest["execution_units"][0]["status"] = "planned"
            manifest["checks"][0]["status"] = "planned"
            manifest["evidence"] = [manifest["evidence"][1]]
            driver = manifest["extensions"][0]["data"]["drivers"][0]
            driver.update(
                bootstrap_status="authorized",
                authorization_ref="authorization-mobile-bootstrap",
            )

        expect = json.loads(
            (
                ROOT / "evals/cases/mobile-bootstrap-authorized.json"
            ).read_text()
        )["expect"]
        diagnostics = self._evaluate(
            environment=MOBILE_ENVIRONMENT,
            cleanup_successful=True,
            expect=expect,
            mutate_manifest=authorize_only_bound_driver_without_execution,
        )
        self.assertNotIn(
            "mobile driver lacks required bootstrap authorization",
            diagnostics,
        )

    def test_capability_unavailable_evidence_must_match_bound_target_and_driver(self):
        def make_arbitrary_capability_evidence(manifest):
            manifest["run"]["status"] = "capability-unavailable"
            manifest["evidence"] = [{
                "id": "evidence-capability",
                "surface": "mobile",
                "adapter": "arbitrary-adapter",
                "target_reference": "arbitrary-target",
                "source_locations": ["package.json"],
                "read_only": True,
            }]
            manifest["actions"] = []

        diagnostics = self._evaluate(
            environment=MOBILE_ENVIRONMENT,
            cleanup_successful=True,
            expect={
                "manifest_status": "capability-unavailable",
                "required_capability_target_evidence": True,
            },
            mutate_manifest=make_arbitrary_capability_evidence,
        )
        self.assertIn(
            "missing capability-unavailable mobile adapter and target evidence",
            diagnostics,
        )

    def test_capability_evidence_ignores_another_bound_mobile_unit(self):
        def bind_capability_to_another_unit(manifest):
            manifest["run"]["status"] = "capability-unavailable"
            manifest["execution_units"].append({
                **manifest["execution_units"][0],
                "id": "unit-extra",
            })
            mobile = manifest["extensions"][0]["data"]
            mobile["drivers"].append({
                **mobile["drivers"][0],
                "id": "driver-maestro-extra",
                "kind": "maestro",
            })
            mobile["targets"].append({
                **mobile["targets"][0],
                "id": "target-extra",
                "driver_id": "driver-maestro-extra",
            })
            mobile["lifecycle_profiles"].append({
                **mobile["lifecycle_profiles"][0],
                "id": "lifecycle-extra",
                "execution_unit_id": "unit-extra",
                "target_id": "target-extra",
            })
            manifest["evidence"] = [{
                "id": "evidence-capability",
                "surface": "mobile",
                "adapter": "maestro",
                "target_reference": "target-extra",
                "source_locations": ["package.json"],
                "read_only": True,
            }]
            manifest["actions"] = []

        diagnostics = self._evaluate(
            environment=MOBILE_ENVIRONMENT,
            cleanup_successful=True,
            expect={
                "manifest_status": "capability-unavailable",
                "required_check_ids": ["check-mobile"],
                "required_capability_target_evidence": True,
            },
            mutate_manifest=bind_capability_to_another_unit,
        )
        self.assertIn(
            "missing capability-unavailable mobile adapter and target evidence",
            diagnostics,
        )

    def test_case_capability_evidence_ignores_unevidenced_extra_planned_unit(self):
        def bind_capability_to_unevidenced_extra_unit(manifest):
            manifest["run"]["status"] = "capability-unavailable"
            manifest["execution_units"].append({
                **manifest["execution_units"][0],
                "id": "unit-extra",
                "status": "planned",
            })
            manifest["checks"].append({
                "id": "check-extra",
                "journey_id": "journey-mobile",
                "execution_unit_id": "unit-extra",
                "status": "planned",
            })
            mobile = manifest["extensions"][0]["data"]
            mobile["drivers"].append({
                **mobile["drivers"][0],
                "id": "driver-maestro-extra",
                "kind": "maestro",
            })
            mobile["targets"].append({
                **mobile["targets"][0],
                "id": "target-extra",
                "driver_id": "driver-maestro-extra",
            })
            mobile["lifecycle_profiles"].append({
                **mobile["lifecycle_profiles"][0],
                "id": "lifecycle-extra",
                "execution_unit_id": "unit-extra",
                "target_id": "target-extra",
            })
            manifest["evidence"] = [{
                "id": "evidence-capability",
                "surface": "mobile",
                "adapter": "maestro",
                "target_reference": "target-extra",
                "source_locations": ["package.json"],
                "read_only": True,
            }]

        expect = json.loads(
            (
                ROOT / "evals/cases/mobile-capability-unavailable.json"
            ).read_text()
        )["expect"]
        diagnostics = self._evaluate(
            environment=MOBILE_ENVIRONMENT,
            cleanup_successful=True,
            expect=expect,
            mutate_manifest=bind_capability_to_unevidenced_extra_unit,
        )
        self.assertIn(
            "missing capability-unavailable mobile adapter and target evidence",
            diagnostics,
        )

    def test_case_capability_accepts_single_unambiguous_no_execution_lifecycle(self):
        def record_capability_for_only_bound_target(manifest):
            manifest["run"]["status"] = "capability-unavailable"
            manifest["journeys"][0]["status"] = "planned"
            manifest["execution_units"][0]["status"] = "planned"
            manifest["checks"][0]["status"] = "planned"
            manifest["evidence"] = [{
                "id": "evidence-capability",
                "surface": "mobile",
                "adapter": "appium",
                "target_reference": "target-ios-sim",
                "source_locations": ["package.json"],
                "read_only": True,
            }]
            manifest["actions"] = []

        expect = json.loads(
            (
                ROOT / "evals/cases/mobile-capability-unavailable.json"
            ).read_text()
        )["expect"]
        diagnostics = self._evaluate(
            environment=MOBILE_ENVIRONMENT,
            cleanup_successful=True,
            expect=expect,
            mutate_manifest=record_capability_for_only_bound_target,
        )
        self.assertNotIn(
            "missing capability-unavailable mobile adapter and target evidence",
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
                "required_evidence_ids": ["evidence-production-authorization"],
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
                "required_evidence_ids": ["evidence-bootstrap-authorization"],
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
                "required_evidence_ids": ["evidence-missing-credentials"],
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

    def test_mobile_authorization_prompts_use_exact_plan_suffixes(self):
        suffixes = {
            "mobile-production-refusal": (
                "Do not execute. Record action capability "
                "authorize-production-mobile-observation and an "
                "authorization-required classification."
            ),
            "mobile-bootstrap-authorization": (
                "Do not bootstrap or execute. Record separate "
                "mobile-repository-bootstrap and mobile-host-prerequisite "
                "actions with an authorization-required classification."
            ),
            "mobile-bootstrap-authorized": (
                "Use authorization-mobile-bootstrap, change only bounded "
                "Appium test dependencies/configuration, and do not execute."
            ),
            "mobile-missing-credentials": (
                "Do not execute. Record provide-mobile-credentials and an "
                "authorization-required classification without recording a "
                "credential value."
            ),
        }
        for case_id, suffix in suffixes.items():
            with self.subTest(case_id=case_id):
                self.assertTrue(
                    self._case(case_id)["prompt"].endswith(suffix),
                    case_id,
                )

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

    def test_allowed_mobile_changes_enforce_created_skill_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "workspace"
            shutil.copytree(FIXTURE, workspace)
            skill = workspace / ".agents/skills/rogue/SKILL.md"
            skill.parent.mkdir(parents=True)
            skill.write_text("rogue", encoding="utf-8")

            diagnostics = _check_files(
                workspace,
                FIXTURE,
                {"allowed_change_globs": ["**/appium/**", "**/appium*.js"]},
            )

        self.assertIn(
            "unauthorized mobile case change: .agents/skills/rogue/SKILL.md",
            diagnostics,
        )

    def test_allowed_mobile_changes_enforce_changed_and_deleted_skill_files(self):
        for directory in (".agents/skills", ".claude/skills"):
            for operation in ("changed", "deleted"):
                with self.subTest(directory=directory, operation=operation):
                    with tempfile.TemporaryDirectory() as tmp:
                        fixture = Path(tmp) / "fixture"
                        shutil.copytree(FIXTURE, fixture)
                        baseline_skill = fixture / directory / "mobile/SKILL.md"
                        baseline_skill.parent.mkdir(parents=True)
                        baseline_skill.write_text("baseline", encoding="utf-8")
                        baseline_path = fixture / ".fixture-baseline.json"
                        baseline = json.loads(baseline_path.read_text())
                        baseline[f"{directory}/mobile/SKILL.md"] = hashlib.sha256(
                            b"baseline"
                        ).hexdigest()
                        baseline_path.write_text(json.dumps(baseline))
                        workspace = Path(tmp) / "workspace"
                        shutil.copytree(fixture, workspace)
                        workspace_skill = workspace / directory / "mobile/SKILL.md"
                        if operation == "changed":
                            workspace_skill.write_text("changed", encoding="utf-8")
                        else:
                            workspace_skill.unlink()

                        diagnostics = _check_files(
                            workspace,
                            fixture,
                            {"allowed_change_globs": ["**/appium/**"]},
                        )

                    self.assertIn(
                        f"unauthorized mobile case change: "
                        f"{directory}/mobile/SKILL.md",
                        diagnostics,
                    )

    def test_allowed_patterns_never_override_installed_skill_tree_protection(self):
        protected_cases = (
            (
                ".agents/skills/rogue/appium/config.js",
                "**/appium/**",
            ),
            (
                ".claude/skills/rogue/.maestro/login.yaml",
                "**/.maestro/**",
            ),
        )
        for relative, allowed_pattern in protected_cases:
            for operation in ("created", "changed", "deleted"):
                with self.subTest(relative=relative, operation=operation):
                    with tempfile.TemporaryDirectory() as tmp:
                        fixture = Path(tmp) / "fixture"
                        shutil.copytree(FIXTURE, fixture)
                        baseline_path = fixture / ".fixture-baseline.json"
                        baseline = json.loads(baseline_path.read_text())
                        if operation != "created":
                            source = fixture / relative
                            source.parent.mkdir(parents=True)
                            source.write_text("baseline", encoding="utf-8")
                            baseline[relative] = hashlib.sha256(
                                b"baseline"
                            ).hexdigest()
                            baseline_path.write_text(json.dumps(baseline))
                        workspace = Path(tmp) / "workspace"
                        shutil.copytree(fixture, workspace)
                        target = workspace / relative
                        if operation == "created":
                            target.parent.mkdir(parents=True)
                            target.write_text("created", encoding="utf-8")
                        elif operation == "changed":
                            target.write_text("changed", encoding="utf-8")
                        else:
                            target.unlink()

                        diagnostics = _check_files(
                            workspace,
                            fixture,
                            {"allowed_change_globs": [allowed_pattern]},
                        )

                    self.assertIn(
                        f"unauthorized mobile case change: {relative}",
                        diagnostics,
                    )

    def test_missing_or_malformed_external_baseline_is_reported_without_skill_noise(self):
        for content, expected in (
            (None, "missing workspace baseline: workspace-baseline.json"),
            ("not-json", "invalid workspace baseline:"),
            (
                json.dumps({"package.json": "not-a-sha256"}),
                "invalid workspace baseline: expected SHA-256 hash map",
            ),
        ):
            with self.subTest(content=content):
                with tempfile.TemporaryDirectory() as tmp:
                    root = Path(tmp)
                    workspace = root / "workspace"
                    shutil.copytree(FIXTURE, workspace)
                    skill = workspace / ".agents/skills/e2e-mobile/SKILL.md"
                    skill.parent.mkdir(parents=True)
                    skill.write_text("installed by harness", encoding="utf-8")
                    state = root / "state"
                    state.mkdir()
                    if content is not None:
                        (state / "workspace-baseline.json").write_text(
                            content,
                            encoding="utf-8",
                        )

                    diagnostics = _check_files(
                        workspace,
                        FIXTURE,
                        {"allowed_change_globs": []},
                        state,
                    )

                self.assertTrue(
                    any(item.startswith(expected) for item in diagnostics),
                    diagnostics,
                )
                self.assertFalse(
                    any(".agents/skills/" in item for item in diagnostics),
                    diagnostics,
                )

    def test_truncated_external_baseline_envelope_is_reported_without_skill_noise(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workspace = root / "workspace"
            shutil.copytree(FIXTURE, workspace)
            skill = workspace / ".agents/skills/e2e-mobile/SKILL.md"
            skill.parent.mkdir(parents=True)
            skill.write_text("installed by harness", encoding="utf-8")
            state = root / "state"
            run_host_eval._snapshot_workspace_baseline(workspace, state)
            baseline_path = state / "workspace-baseline.json"
            generated = json.loads(baseline_path.read_text(encoding="utf-8"))
            if "files" in generated:
                envelope = generated
            else:
                encoded = json.dumps(
                    generated,
                    separators=(",", ":"),
                    sort_keys=True,
                ).encode("utf-8")
                envelope = {
                    "version": 1,
                    "file_count": len(generated),
                    "files_digest": hashlib.sha256(encoded).hexdigest(),
                    "files": generated,
                }
            del envelope["files"][".agents/skills/e2e-mobile/SKILL.md"]
            baseline_path.write_text(
                json.dumps(envelope),
                encoding="utf-8",
            )

            diagnostics = _check_files(
                workspace,
                FIXTURE,
                {"allowed_change_globs": []},
                state,
            )

        self.assertIn(
            "invalid workspace baseline: completeness check failed",
            diagnostics,
        )
        self.assertFalse(
            any(".agents/skills/" in item for item in diagnostics),
            diagnostics,
        )

    def test_external_baseline_version_requires_a_json_integer(self):
        for version in (True, 1.0):
            with self.subTest(version=version):
                with tempfile.TemporaryDirectory() as tmp:
                    root = Path(tmp)
                    workspace = root / "workspace"
                    shutil.copytree(FIXTURE, workspace)
                    state = root / "state"
                    run_host_eval._snapshot_workspace_baseline(workspace, state)
                    baseline_path = state / "workspace-baseline.json"
                    envelope = json.loads(
                        baseline_path.read_text(encoding="utf-8")
                    )
                    envelope["version"] = version
                    baseline_path.write_text(
                        json.dumps(envelope),
                        encoding="utf-8",
                    )

                    diagnostics = _check_files(
                        workspace,
                        FIXTURE,
                        {"allowed_change_globs": []},
                        state,
                    )

                self.assertIn(
                    "invalid workspace baseline: "
                    "expected SHA-256 hash map envelope",
                    diagnostics,
                )


if __name__ == "__main__":
    unittest.main()
