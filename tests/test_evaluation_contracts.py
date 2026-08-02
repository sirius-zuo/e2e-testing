"""Deterministic acceptance contracts for the E2E skill fixtures."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest import mock

from evals.evaluate_result import evaluate
from evals import evaluate_result, run_host_eval
from protocol.v2.e2e_protocol import new_manifest, save_manifest


ROOT = Path(__file__).resolve().parents[1]
CASES = ROOT / "evals" / "cases"
FIXTURES = ROOT / "evals" / "fixtures"
REQUIRED_CASE_FIELDS = {"id", "entry_skill", "mode", "autonomy", "prompt", "fixture", "expect"}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _source_evidence() -> dict:
    # The Protocol 2 system boundary in ``_manifest`` references this source
    # evidence, so replacing a manifest's evidence must keep it to stay valid.
    return {"id": "evidence-source", "kind": "source-derived"}


def _manifest(workspace: Path, status: str = "generated-unverified") -> dict:
    data = new_manifest(str(workspace), timestamp="2026-07-22T00:00:00Z")
    data["run"]["status"] = status
    data["systems"][0]["primary_surface"] = "web"
    data["systems"][0]["boundary"] = {
        "status": "declared",
        "actors": ["user"],
        "public_interfaces": [{
            "id": "interface-web-primary",
            "kind": "web",
            "endpoint_ref": None,
            "evidence_ids": ["evidence-source"],
        }],
        "evidence_ids": ["evidence-source"],
    }
    data["journeys"] = [{
        "id": "journey-checkout",
        "system_id": "system-primary",
        "status": "covered",
    }]
    data["execution_units"] = [{
        "id": "execution-web-primary",
        "system_id": "system-primary",
        "surface": "web",
        "capability": "e2e-web",
        "extension_id": "extension-web-primary",
        "status": status,
    }]
    data["checks"] = [{
        "id": "check-checkout",
        "journey_id": "journey-checkout",
        "execution_unit_id": "execution-web-primary",
        "status": "generated",
    }]
    data["evidence"] = [{"id": "evidence-source", "kind": "source-derived"}]
    data["extensions"] = [{
        "id": "extension-web-primary",
        "namespace": "e2e.web",
        "version": "1.0",
        "owner": "e2e-web",
        "data": {"driver": "playwright", "project": {}, "target": {}},
    }]
    return data


def _verification_evidence(check_id: str, *, revision_consumed: int, phase: str) -> dict:
    return {
        "kind": "verification",
        "command": "node --test tests/login.logic.test.js",
        "exit_code": 0,
        "duration_ms": 125,
        "manifest_revision_consumed": revision_consumed,
        "phase": phase,
        "check_ids": [check_id],
        "outcomes": [{"check_id": check_id, "status": "passed"}],
        "execution_environment": {
            "browser_project": "chromium",
            "os_platform": "test-os",
            "runtime": "node 22",
            "application_build_ref": "fixture",
            "target_reference": "local-fixture",
            "target_tier": "local",
        },
    }


def _product_defect_evidence() -> list[dict]:
    return [
        {
            "id": "evidence-product-run",
            "kind": "verification",
            "command": "node --test tests/checkout.logic.test.js",
            "exit_code": 1,
            "duration_ms": 125,
            "check_ids": ["check-checkout"],
            "outcomes": [{"check_id": "check-checkout", "status": "failed"}],
            "execution_environment": {
                "browser_project": "chromium", "os_platform": "test-os", "runtime": "node 22",
                "application_build_ref": "fixture", "target_reference": "local-fixture", "target_tier": "local",
            },
            "artifacts": [{
                "id": "artifact-checkout-log", "path": ".e2e/evidence/checkout.log",
                "sha256": "b6d81b360a5672d80c27430f39153e2c920ca209157884b67866f83ec952ef75",
            }],
        },
        {
            "id": "evidence-product-defect",
            "kind": "classification",
            "classification": {
                "primary": "product-defect", "confidence": 0.9,
                "rationale": "The selected assertion matches the fixture specification.",
                "evidence_ids": ["evidence-product-run"],
            },
        },
    ]


def _product_defect_handoff() -> dict:
    return {
        "id": "handoff-product-defect", "capability": "fix-product-defect",
        "journey_ids": ["journey-checkout"],
        "resume": {"command": "e2e-web verify"},
        "reproduction_steps": ["Run the selected checkout test", "Submit a valid checkout"],
        "expected_behavior": "Checkout succeeds",
        "actual_behavior": "Checkout fails",
        "artifact_refs": ["artifact-checkout-log"],
        "evidence_ids": ["evidence-product-run", "evidence-product-defect"],
    }


def _repair_attempt() -> dict:
    return {
        "id": "attempt-repair-1", "check_ids": ["check-checkout"],
        "allowed_paths": ["tests/checkout.spec.ts"],
        "assertion_comparison": "The checkout assertion remains equally specific.",
    }


class FixtureContractTests(unittest.TestCase):
    def test_cases_have_required_fields_and_existing_fixtures(self):
        case_paths = sorted(CASES.glob("*.json"))
        self.assertEqual(len(case_paths), 44)
        original_cases = {
            "greenfield-source", "live-assisted-generation", "existing-playwright",
            "unsupported-cypress", "conflicting-evidence", "verify-pass",
            "repair-test-defect", "product-defect-handoff", "missing-credentials", "auto-budget",
        }
        service_cases = {
            "service-generate-all", "service-verify-all", "service-multi-protocol",
            "service-production-refusal", "service-capability-unavailable",
            "service-product-defect", "service-database-support",
        }
        mobile_cases = {
            "mobile-generate-appium", "mobile-generate-maestro",
            "mobile-verify-lifecycle", "mobile-upgrade",
            "mobile-production-refusal", "mobile-capability-unavailable",
            "mobile-product-defect", "mobile-cleanup-failure",
            "mobile-bootstrap-authorization", "mobile-bootstrap-authorized",
            "mobile-missing-credentials", "mobile-missing-artifact",
        }
        desktop_cases = {
            "desktop-generate-mac2", "desktop-generate-novawindows",
            "desktop-generate-electron", "desktop-verify-lifecycle", "desktop-update",
            "desktop-production-refusal", "desktop-capability-unavailable",
            "desktop-product-defect", "desktop-cleanup-failure",
            "desktop-bootstrap-authorization", "desktop-bootstrap-authorized",
            "desktop-missing-credentials", "desktop-missing-artifact",
            "desktop-session-refusal", "desktop-mocked-os-refusal",
        }
        self.assertEqual(
            {path.stem for path in case_paths},
            original_cases | service_cases | mobile_cases | desktop_cases,
        )
        for path in case_paths:
            with self.subTest(case=path.stem):
                case = json.loads(path.read_text())
                self.assertTrue(REQUIRED_CASE_FIELDS <= set(case))
                self.assertTrue((FIXTURES / case["fixture"]).is_dir())
                self.assertIn(case["entry_skill"], {"e2e-testing", "e2e-service", "e2e-mobile", "e2e-desktop"})
                self.assertNotIn("e2e-web-playwright", json.dumps(case))

    def test_verified_case_expectations_name_the_execution_evidence_to_bind(self):
        verify = json.loads((CASES / "verify-pass.json").read_text())
        repair = json.loads((CASES / "repair-test-defect.json").read_text())
        product = json.loads((CASES / "product-defect-handoff.json").read_text())
        resume = next(phase for phase in product["phases"] if phase["name"] == "resume")
        self.assertEqual(verify["expect"].get("required_execution_evidence_ids"), ["evidence-verification"])
        self.assertEqual(repair["expect"].get("required_execution_evidence_ids"), ["evidence-reverification"])
        self.assertEqual(resume["expect"].get("required_execution_evidence_ids"), ["evidence-reverification"])

    def test_fixture_baselines_match_pristine_files(self):
        for fixture in sorted(path for path in FIXTURES.iterdir() if path.is_dir()):
            with self.subTest(fixture=fixture.name):
                baseline = json.loads((fixture / ".fixture-baseline.json").read_text())
                files = {
                    path.relative_to(fixture).as_posix()
                    for path in fixture.rglob("*")
                    if path.is_file() and path.name != ".fixture-baseline.json"
                }
                self.assertEqual(set(baseline), files)
                self.assertEqual(
                    {relative: _sha256(fixture / relative) for relative in sorted(files)}, baseline,
                )


class EvaluatorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.workspace = Path(self.tmp.name) / "workspace"
        shutil.copytree(FIXTURES / "greenfield-source", self.workspace)
        self.case = ROOT / "evals" / "cases" / "greenfield-source.json"

    def tearDown(self):
        self.tmp.cleanup()

    def _write_manifest(self, manifest: dict | None = None):
        target = self.workspace / ".e2e"
        target.mkdir()
        (target / "manifest.json").write_text(json.dumps(manifest or _manifest(self.workspace)))

    def _save_verified_manifest(self, name: str, revision_claim: int) -> tuple[Path, dict]:
        workspace = Path(self.tmp.name) / name
        shutil.copytree(FIXTURES / "existing-playwright", workspace)
        path = workspace / ".e2e" / "manifest.json"
        consumed = save_manifest(path, new_manifest(str(workspace), mode="verify"), expected_revision=None)
        final = dict(consumed)
        final["run"]["status"] = "verified"
        final["systems"][0]["primary_surface"] = "web"
        final["journeys"] = [{"id": "journey-login", "system_id": "system-primary", "status": "verified"}]
        final["execution_units"] = [{
            "id": "execution-web-primary", "system_id": "system-primary", "surface": "web",
            "capability": "e2e-web", "extension_id": "extension-web-primary", "status": "verified",
        }]
        final["extensions"] = [{
            "id": "extension-web-primary", "namespace": "e2e.web", "version": "1.0",
            "owner": "e2e-web", "data": {"driver": "playwright", "project": {}, "target": {}},
        }]
        final["checks"] = [{"id": "check-login", "journey_id": "journey-login", "execution_unit_id": "execution-web-primary", "status": "passed"}]
        execution = _verification_evidence(
            "check-login", revision_consumed=revision_claim, phase="verify",
        )
        execution["id"] = "evidence-verification"
        final["evidence"] = [execution]
        return workspace, save_manifest(path, final, expected_revision=consumed["run"]["revision"])

    def _revision_binding_diagnostics(self, final_revision, consumed_revision) -> list[str]:
        manifest = _manifest(self.workspace, "verified")
        manifest["run"]["mode"] = "verify"
        manifest["run"]["revision"] = final_revision
        manifest["journeys"] = [{"id": "journey-checkout", "system_id": "system-primary", "status": "verified"}]
        manifest["checks"] = [
            {"id": "check-checkout", "journey_id": "journey-checkout", "execution_unit_id": "execution-web-primary", "status": "passed"},
        ]
        execution = _verification_evidence(
            "check-checkout", revision_consumed=consumed_revision, phase="verify",
        )
        execution["id"] = "evidence-verification"
        manifest["evidence"] = [execution]
        return evaluate_result._check_status_evidence(manifest, {
            "required_journey_ids": ["journey-checkout"],
            "required_execution_evidence_ids": ["evidence-verification"],
        }, "web")

    def test_detects_forbidden_preserved_file_change(self):
        self._write_manifest()
        (self.workspace / "package.json").write_text('{"changed": true}\n')
        self.assertIn("forbidden change: package.json", evaluate(self.case, self.workspace))

    def test_detects_missing_manifest_status(self):
        self._write_manifest(_manifest(self.workspace, status="planned"))
        self.assertIn(
            "manifest status: expected generated-unverified, found planned",
            evaluate(self.case, self.workspace),
        )

    def test_detects_missing_journey_traceability(self):
        manifest = _manifest(self.workspace)
        manifest["checks"] = []
        self._write_manifest(manifest)
        self.assertIn(
            "missing journey traceability: journey-checkout",
            evaluate(self.case, self.workspace),
        )

    def test_detects_missing_evidence(self):
        manifest = _manifest(self.workspace)
        # Drop the source evidence and the boundary references to it so the
        # manifest stays structurally valid while the required ID is absent.
        manifest["systems"][0]["boundary"]["evidence_ids"] = []
        manifest["systems"][0]["boundary"]["public_interfaces"][0]["evidence_ids"] = []
        manifest["evidence"] = []
        self._write_manifest(manifest)
        self.assertIn("missing evidence ID: evidence-source", evaluate(self.case, self.workspace))

    def test_accepts_a_complete_artifact_set(self):
        self._write_manifest()
        generated = self.workspace / "tests" / "checkout.spec.ts"
        generated.parent.mkdir()
        generated.write_text("// generated checkout coverage\n")
        self.assertEqual(evaluate(self.case, self.workspace), [])

    def test_unsupported_case_requires_a_valid_protocol_manifest(self):
        workspace = Path(self.tmp.name) / "cypress"
        shutil.copytree(FIXTURES / "unsupported-cypress", workspace)
        case = CASES / "unsupported-cypress.json"
        target = workspace / ".e2e"
        target.mkdir()
        manifest = _manifest(workspace, "capability-unavailable")
        manifest["evidence"] = [_source_evidence(), {
            "id": "evidence-framework-detection", "framework": "cypress",
            "source_locations": ["package.json"], "read_only": True,
        }]
        (target / "manifest.json").write_text(json.dumps(manifest))
        self.assertEqual(evaluate(case, workspace), [])
        (target / "manifest.json").unlink()
        self.assertIn("missing manifest: manifest.json", evaluate(case, workspace))
        (target / "manifest.json").write_text("{}")
        self.assertTrue(any(item.startswith("invalid manifest:") for item in evaluate(case, workspace)))

    def test_unsupported_case_requires_the_requested_mode_and_read_only_detection_evidence(self):
        workspace = Path(self.tmp.name) / "cypress-contract"
        shutil.copytree(FIXTURES / "unsupported-cypress", workspace)
        manifest = _manifest(workspace, "capability-unavailable")
        manifest["run"]["mode"] = "verify"
        target = workspace / ".e2e"
        target.mkdir()
        (target / "manifest.json").write_text(json.dumps(manifest))
        diagnostics = evaluate(CASES / "unsupported-cypress.json", workspace)
        self.assertIn("manifest mode: expected generate, found verify", diagnostics)
        self.assertIn("missing capability-unavailable framework detection evidence", diagnostics)

    def test_verified_case_rejects_status_labels_without_execution_evidence(self):
        workspace = Path(self.tmp.name) / "verify-evidence"
        shutil.copytree(FIXTURES / "existing-playwright", workspace)
        manifest = _manifest(workspace, "verified")
        manifest["run"]["mode"] = "verify"
        manifest["journeys"] = [{"id": "journey-login", "system_id": "system-primary", "status": "verified"}]
        manifest["checks"] = [{"id": "check-login", "journey_id": "journey-login", "execution_unit_id": "execution-web-primary", "status": "passed"}]
        manifest["evidence"] = [_source_evidence(), {"id": "evidence-verification", "kind": "verification"}]
        target = workspace / ".e2e"
        target.mkdir()
        (target / "manifest.json").write_text(json.dumps(manifest))
        diagnostics = evaluate(CASES / "verify-pass.json", workspace)
        self.assertIn("verified status requires successful selected-check execution evidence", diagnostics)

    def test_verified_case_rejects_required_label_with_unrelated_successful_execution(self):
        workspace = Path(self.tmp.name) / "verify-unrelated-success"
        shutil.copytree(FIXTURES / "existing-playwright", workspace)
        manifest = _manifest(workspace, "verified")
        manifest["run"]["mode"] = "verify"
        manifest["run"]["revision"] = 3
        manifest["journeys"] = [
            {"id": "journey-login", "system_id": "system-primary", "status": "verified"},
            {"id": "journey-checkout", "system_id": "system-primary", "status": "verified"},
        ]
        manifest["checks"] = [
            {"id": "check-login", "journey_id": "journey-login", "execution_unit_id": "execution-web-primary", "status": "passed"},
            {"id": "check-checkout", "journey_id": "journey-checkout", "execution_unit_id": "execution-web-primary", "status": "passed"},
        ]
        unrelated = _verification_evidence("check-checkout", revision_consumed=3, phase="verify")
        unrelated["id"] = "evidence-unrelated"
        manifest["evidence"] = [
            _source_evidence(),
            {"id": "evidence-verification", "kind": "verification"}, unrelated,
        ]
        target = workspace / ".e2e"
        target.mkdir()
        (target / "manifest.json").write_text(json.dumps(manifest))
        case = json.loads((CASES / "verify-pass.json").read_text())
        case["expect"]["required_execution_evidence_ids"] = ["evidence-verification"]
        case_path = Path(self.tmp.name) / "verify-bound-case.json"
        case_path.write_text(json.dumps(case))
        self.assertIn(
            "required execution evidence is not bound to this phase, revision, and scoped tests: evidence-verification",
            evaluate(case_path, workspace),
        )

    def test_verified_case_accepts_required_execution_bound_to_phase_revision_and_scope(self):
        workspace = Path(self.tmp.name) / "verify-bound-success"
        shutil.copytree(FIXTURES / "existing-playwright", workspace)
        manifest = _manifest(workspace, "verified")
        manifest["run"]["mode"] = "verify"
        manifest["run"]["revision"] = 3
        manifest["journeys"] = [{"id": "journey-login", "system_id": "system-primary", "status": "verified"}]
        manifest["checks"] = [{"id": "check-login", "journey_id": "journey-login", "execution_unit_id": "execution-web-primary", "status": "passed"}]
        execution = _verification_evidence("check-login", revision_consumed=2, phase="verify")
        execution["id"] = "evidence-verification"
        manifest["evidence"] = [_source_evidence(), execution]
        target = workspace / ".e2e"
        target.mkdir()
        (target / "manifest.json").write_text(json.dumps(manifest))
        case = json.loads((CASES / "verify-pass.json").read_text())
        case["expect"]["required_execution_evidence_ids"] = ["evidence-verification"]
        case_path = Path(self.tmp.name) / "verify-bound-success-case.json"
        case_path.write_text(json.dumps(case))
        self.assertEqual(evaluate(case_path, workspace), [])

    def test_verified_case_accepts_execution_that_consumed_the_pre_save_revision(self):
        workspace, saved = self._save_verified_manifest("verify-consumed-revision", revision_claim=1)
        self.assertEqual(saved["run"]["revision"], 2)
        self.assertEqual(evaluate(CASES / "verify-pass.json", workspace), [])

    def test_verified_case_rejects_final_or_unrelated_consumed_revision_claims(self):
        for label, revision_claim in (("final", 2), ("unrelated", 7)):
            with self.subTest(claim=label):
                workspace, saved = self._save_verified_manifest(
                    f"verify-{label}-revision", revision_claim=revision_claim,
                )
                self.assertEqual(saved["run"]["revision"], 2)
                self.assertIn(
                    "required execution evidence is not bound to this phase, revision, and scoped tests: "
                    "evidence-verification",
                    evaluate(CASES / "verify-pass.json", workspace),
                )

    def test_verified_binding_rejects_non_integer_boolean_or_non_positive_final_revision(self):
        expected = "verified status requires final manifest revision to be a non-boolean integer >= 1"
        for revision in (2.0, True, -1, 0):
            with self.subTest(revision=revision):
                self.assertIn(expected, self._revision_binding_diagnostics(revision, 0))

    def test_verified_binding_rejects_non_integer_boolean_or_negative_consumed_revision(self):
        expected = (
            "required execution evidence manifest_revision_consumed must be a non-boolean integer >= 0: "
            "evidence-verification"
        )
        for revision in (1.0, True, -1):
            with self.subTest(revision=revision):
                self.assertIn(expected, self._revision_binding_diagnostics(2, revision))

    def test_verified_binding_rejects_impossible_zero_and_negative_revision_pair(self):
        diagnostics = self._revision_binding_diagnostics(0, -1)
        self.assertIn(
            "verified status requires final manifest revision to be a non-boolean integer >= 1",
            diagnostics,
        )
        self.assertIn(
            "required execution evidence manifest_revision_consumed must be a non-boolean integer >= 0: "
            "evidence-verification",
            diagnostics,
        )

    def test_budget_blocked_case_rejects_an_evidence_label_without_budget_details(self):
        workspace = Path(self.tmp.name) / "budget-evidence"
        shutil.copytree(FIXTURES / "auto-budget", workspace)
        manifest = _manifest(workspace, "blocked")
        manifest["run"]["mode"] = "repair"
        manifest["run"]["autonomy"] = {"mode": "auto", "auto_repair": True}
        manifest["evidence"] = [_source_evidence(), {"id": "evidence-budget-exhausted"}]
        manifest["attempts"] = [{"id": "attempt-repair-1"}]
        target = workspace / ".e2e"
        target.mkdir()
        (target / "manifest.json").write_text(json.dumps(manifest))
        diagnostics = evaluate(CASES / "auto-budget.json", workspace)
        self.assertIn("blocked budget outcome requires budget and attempt evidence", diagnostics)

    def test_existing_playwright_requires_a_new_checkout_artifact(self):
        workspace = Path(self.tmp.name) / "existing"
        shutil.copytree(FIXTURES / "existing-playwright", workspace)
        manifest = _manifest(workspace)
        manifest["evidence"] = [_source_evidence(), {"id": "evidence-existing-suite"}]
        target = workspace / ".e2e"
        target.mkdir()
        (target / "manifest.json").write_text(json.dumps(manifest))
        self.assertIn(
            "required new path missing: tests/**/*checkout*.spec.*",
            evaluate(CASES / "existing-playwright.json", workspace),
        )
        (workspace / "tests" / "checkout.purchase.spec.ts").write_text("// newly generated checkout coverage\n")
        self.assertEqual(evaluate(CASES / "existing-playwright.json", workspace), [])

    def test_verify_pass_contract_targets_the_runnable_existing_login_journey(self):
        case = json.loads((CASES / "verify-pass.json").read_text())
        fixture = FIXTURES / "existing-playwright"
        self.assertIn("login", case["prompt"])
        self.assertEqual(case["expect"]["required_journey_ids"], ["journey-login"])
        self.assertTrue((fixture / "tests" / "login.logic.test.js").is_file())
        self.assertEqual(subprocess.run(["node", "--test"], cwd=fixture, capture_output=True).returncode, 0)

    def test_repair_case_requires_the_precise_stale_locator_repair(self):
        workspace = Path(self.tmp.name) / "repair-contract"
        shutil.copytree(FIXTURES / "repairable-test-defect", workspace)
        manifest = _manifest(workspace, "verified")
        manifest["run"]["mode"] = "repair"
        manifest["run"]["revision"] = 1
        manifest["evidence"] = [
            _source_evidence(),
            {"id": "evidence-repair", "classification": {
                "primary": "test-defect", "confidence": 0.9, "rationale": "stale locator",
                "evidence_ids": ["evidence-repair"],
            }},
            {"id": "evidence-reverification", **_verification_evidence("check-checkout", revision_consumed=0, phase="repair")},
        ]
        manifest["attempts"] = [_repair_attempt()]
        target = workspace / ".e2e"
        target.mkdir()
        (target / "manifest.json").write_text(json.dumps(manifest))
        self.assertIn(
            "required change missing: tests/checkout.spec.ts",
            evaluate(CASES / "repair-test-defect.json", workspace),
        )
        repaired = workspace / "tests" / "checkout.spec.ts"
        repaired.write_text(repaired.read_text().replace("Submit now", "Place order"))
        self.assertEqual(evaluate(CASES / "repair-test-defect.json", workspace), [])

    def test_repair_verified_status_rejects_labels_without_repair_attempt_evidence(self):
        workspace = Path(self.tmp.name) / "repair-evidence"
        shutil.copytree(FIXTURES / "repairable-test-defect", workspace)
        manifest = _manifest(workspace, "verified")
        manifest["run"]["mode"] = "repair"
        manifest["run"]["revision"] = 1
        manifest["evidence"] = [
            _source_evidence(),
            {"id": "evidence-repair", "kind": "repair"},
            {"id": "evidence-reverification", **_verification_evidence("check-checkout", revision_consumed=0, phase="repair")},
        ]
        repaired = workspace / "tests" / "checkout.spec.ts"
        repaired.write_text(repaired.read_text().replace("Submit now", "Place order"))
        target = workspace / ".e2e"
        target.mkdir()
        (target / "manifest.json").write_text(json.dumps(manifest))
        diagnostics = evaluate(CASES / "repair-test-defect.json", workspace)
        self.assertIn("repair verification requires classified repair and bounded attempt evidence", diagnostics)

    def test_product_handoff_requires_failed_selected_execution_and_linked_evidence(self):
        workspace = Path(self.tmp.name) / "incomplete-product-evidence"
        shutil.copytree(FIXTURES / "product-defect", workspace)
        manifest = _manifest(workspace, status="handoff-required")
        manifest["run"]["mode"] = "verify"
        manifest["evidence"] = [*_product_defect_evidence(), _source_evidence()]
        manifest["evidence"][0]["exit_code"] = 0
        manifest["handoffs"] = [_product_defect_handoff()]
        target = workspace / ".e2e"
        state = Path(self.tmp.name) / "incomplete-evidence-state"
        target.mkdir()
        (target / "manifest.json").write_text(json.dumps(manifest))
        self.assertIn(
            "handoff-required status requires failed selected-test execution and linked product-defect classification evidence",
            evaluate(CASES / "product-defect-handoff.json", workspace, "handoff", state),
        )

    def test_failed_execution_evidence_rejects_invalid_duration(self):
        for duration in (True, -1, "125", float("nan"), float("inf")):
            with self.subTest(duration=duration):
                evidence = _product_defect_evidence()[0]
                evidence["duration_ms"] = duration
                self.assertFalse(
                    evaluate_result._is_failed_execution_evidence(
                        evidence,
                        {"check-checkout"},
                        "web",
                    )
                )

    def test_product_handoff_rejects_non_finite_failed_execution_duration(self):
        for duration in (float("nan"), float("inf")):
            with self.subTest(duration=duration):
                workspace = Path(self.tmp.name) / f"non-finite-{duration}"
                shutil.copytree(FIXTURES / "product-defect", workspace)
                manifest = _manifest(workspace, status="handoff-required")
                manifest["run"]["mode"] = "verify"
                manifest["evidence"] = [
                    *_product_defect_evidence(),
                    _source_evidence(),
                ]
                manifest["evidence"][0]["duration_ms"] = duration
                manifest["handoffs"] = [_product_defect_handoff()]
                target = workspace / ".e2e"
                state = Path(self.tmp.name) / f"non-finite-state-{duration}"
                target.mkdir()
                (target / "manifest.json").write_text(json.dumps(manifest))
                self.assertIn(
                    "handoff-required status requires failed selected-test "
                    "execution and linked product-defect classification "
                    "evidence",
                    evaluate(
                        CASES / "product-defect-handoff.json",
                        workspace,
                        "handoff",
                        state,
                    ),
                )

    def test_product_handoff_requires_complete_defect_details_and_valid_refs(self):
        workspace = Path(self.tmp.name) / "incomplete-product-handoff"
        shutil.copytree(FIXTURES / "product-defect", workspace)
        manifest = _manifest(workspace, status="handoff-required")
        manifest["run"]["mode"] = "verify"
        manifest["evidence"] = [_source_evidence(), *_product_defect_evidence()]
        handoff = _product_defect_handoff()
        handoff.pop("reproduction_steps")
        manifest["handoffs"] = [handoff]
        target = workspace / ".e2e"
        state = Path(self.tmp.name) / "incomplete-handoff-state"
        target.mkdir()
        (target / "manifest.json").write_text(json.dumps(manifest))
        self.assertIn(
            "handoff-required status requires complete product-defect handoff details with valid evidence and artifact refs",
            evaluate(CASES / "product-defect-handoff.json", workspace, "handoff", state),
        )

    def test_product_defect_resume_allows_only_the_authorized_source_patch(self):
        workspace = Path(self.tmp.name) / "product"
        shutil.copytree(FIXTURES / "product-defect", workspace)
        manifest = _manifest(workspace, status="handoff-required")
        manifest["run"]["mode"] = "verify"
        manifest["run"]["id"] = "run-product-defect"
        manifest["run"]["revision"] = 7
        manifest["evidence"] = [_source_evidence(), *_product_defect_evidence()]
        manifest["handoffs"] = [_product_defect_handoff()]
        target = workspace / ".e2e"
        state = Path(self.tmp.name) / "evaluator-state"
        target.mkdir()
        (target / "manifest.json").write_text(json.dumps(manifest))
        self.assertEqual(
            evaluate(CASES / "product-defect-handoff.json", workspace, phase="handoff", state_dir=state), [],
        )
        self.assertFalse((target / ".eval-checkpoint-product-defect-handoff-handoff.json").exists())
        self.assertTrue((state / "product-defect-handoff-handoff.json").is_file())
        subprocess.run(
            ["git", "apply", str(ROOT / "evals" / "patches" / "product-defect-fix.patch")],
            cwd=workspace, check=True,
        )
        manifest["run"]["status"] = "verified"
        manifest["run"]["revision"] = 8
        manifest["evidence"].append({
            "id": "evidence-reverification",
            **_verification_evidence("check-checkout", revision_consumed=7, phase="resume"),
        })
        (target / "manifest.json").write_text(json.dumps(manifest))
        self.assertEqual(
            evaluate(CASES / "product-defect-handoff.json", workspace, phase="resume", state_dir=state), [],
        )

    def test_product_defect_resume_rejects_a_fresh_run_without_handoff_checkpoint(self):
        workspace = Path(self.tmp.name) / "fresh-product"
        shutil.copytree(FIXTURES / "product-defect", workspace)
        subprocess.run(
            ["git", "apply", str(ROOT / "evals" / "patches" / "product-defect-fix.patch")],
            cwd=workspace, check=True,
        )
        manifest = _manifest(workspace, status="verified")
        manifest["run"]["mode"] = "verify"
        manifest["run"]["id"] = "run-fresh-product"
        manifest["run"]["revision"] = 8
        manifest["evidence"] = [_source_evidence(), *_product_defect_evidence()] + [
            {"id": "evidence-reverification", **_verification_evidence("check-checkout", revision_consumed=7, phase="resume")},
        ]
        manifest["handoffs"] = [_product_defect_handoff()]
        target = workspace / ".e2e"
        state = Path(self.tmp.name) / "fresh-state"
        target.mkdir()
        (target / "manifest.json").write_text(json.dumps(manifest))
        self.assertIn(
            "missing phase checkpoint: handoff",
            evaluate(CASES / "product-defect-handoff.json", workspace, phase="resume", state_dir=state),
        )

    def test_product_defect_resume_rejects_unapproved_application_additions(self):
        workspace = Path(self.tmp.name) / "product-extra-source"
        shutil.copytree(FIXTURES / "product-defect", workspace)
        manifest = _manifest(workspace, status="handoff-required")
        manifest["run"]["mode"] = "verify"
        manifest["run"]["id"] = "run-product-extra-source"
        manifest["run"]["revision"] = 7
        manifest["evidence"] = [_source_evidence(), *_product_defect_evidence()]
        manifest["handoffs"] = [_product_defect_handoff()]
        target = workspace / ".e2e"
        state = Path(self.tmp.name) / "extra-source-state"
        target.mkdir()
        (target / "manifest.json").write_text(json.dumps(manifest))
        self.assertEqual(evaluate(CASES / "product-defect-handoff.json", workspace, "handoff", state), [])
        subprocess.run(["git", "apply", str(ROOT / "evals" / "patches" / "product-defect-fix.patch")], cwd=workspace, check=True)
        (workspace / "src" / "unapproved.js").write_text("export const unsafe = true;\n")
        manifest["run"]["status"] = "verified"
        manifest["run"]["revision"] = 8
        manifest["evidence"].append({
            "id": "evidence-reverification",
            **_verification_evidence("check-checkout", revision_consumed=7, phase="resume"),
        })
        (target / "manifest.json").write_text(json.dumps(manifest))
        self.assertIn(
            "unauthorized resume change: src/unapproved.js",
            evaluate(CASES / "product-defect-handoff.json", workspace, "resume", state),
        )

    def test_product_defect_resume_rejects_a_malformed_external_checkpoint(self):
        workspace = Path(self.tmp.name) / "malformed-product"
        shutil.copytree(FIXTURES / "product-defect", workspace)
        subprocess.run(
            ["git", "apply", str(ROOT / "evals" / "patches" / "product-defect-fix.patch")],
            cwd=workspace, check=True,
        )
        manifest = _manifest(workspace, status="verified")
        manifest["run"]["mode"] = "verify"
        manifest["run"]["id"] = "run-malformed-product"
        manifest["run"]["revision"] = 8
        manifest["evidence"] = [_source_evidence(), *_product_defect_evidence()] + [
            {"id": "evidence-reverification", **_verification_evidence("check-checkout", revision_consumed=7, phase="resume")},
        ]
        manifest["handoffs"] = [_product_defect_handoff()]
        target = workspace / ".e2e"
        state = Path(self.tmp.name) / "malformed-state"
        target.mkdir()
        state.mkdir()
        (target / "manifest.json").write_text(json.dumps(manifest))
        (state / "product-defect-handoff-handoff.json").write_text(
            json.dumps({"run_id": "run-malformed-product", "revision": "eight", "handoff_ids": []})
        )
        self.assertEqual(
            evaluate(CASES / "product-defect-handoff.json", workspace, "resume", state),
            ["invalid phase checkpoint: handoff"],
        )

    def test_product_defect_resume_rejects_an_unapplied_declared_patch(self):
        workspace = Path(self.tmp.name) / "unpatched-product"
        shutil.copytree(FIXTURES / "product-defect", workspace)
        manifest = _manifest(workspace, status="handoff-required")
        manifest["run"]["mode"] = "verify"
        manifest["run"]["id"] = "run-unpatched-product"
        manifest["run"]["revision"] = 7
        manifest["evidence"] = [_source_evidence(), *_product_defect_evidence()]
        manifest["handoffs"] = [_product_defect_handoff()]
        target = workspace / ".e2e"
        state = Path(self.tmp.name) / "unpatched-state"
        target.mkdir()
        (target / "manifest.json").write_text(json.dumps(manifest))
        self.assertEqual(evaluate(CASES / "product-defect-handoff.json", workspace, "handoff", state), [])
        manifest["run"]["status"] = "verified"
        manifest["run"]["revision"] = 8
        manifest["evidence"].append({
            "id": "evidence-reverification",
            **_verification_evidence("check-checkout", revision_consumed=7, phase="resume"),
        })
        (target / "manifest.json").write_text(json.dumps(manifest))
        self.assertIn(
            "authorized patch not applied: src/checkout.js",
            evaluate(CASES / "product-defect-handoff.json", workspace, "resume", state),
        )

    def test_product_defect_resume_rejects_a_discontinuous_run_id(self):
        workspace = Path(self.tmp.name) / "discontinuous-product"
        shutil.copytree(FIXTURES / "product-defect", workspace)
        manifest = _manifest(workspace, status="handoff-required")
        manifest["run"]["mode"] = "verify"
        manifest["run"]["id"] = "run-original-product"
        manifest["run"]["revision"] = 7
        manifest["evidence"] = [_source_evidence(), *_product_defect_evidence()]
        manifest["handoffs"] = [_product_defect_handoff()]
        target = workspace / ".e2e"
        state = Path(self.tmp.name) / "discontinuous-state"
        target.mkdir()
        (target / "manifest.json").write_text(json.dumps(manifest))
        self.assertEqual(evaluate(CASES / "product-defect-handoff.json", workspace, "handoff", state), [])
        subprocess.run(
            ["git", "apply", str(ROOT / "evals" / "patches" / "product-defect-fix.patch")],
            cwd=workspace, check=True,
        )
        manifest["run"]["status"] = "verified"
        manifest["run"]["id"] = "run-restarted-product"
        manifest["run"]["revision"] = 8
        manifest["evidence"].append({
            "id": "evidence-reverification",
            **_verification_evidence("check-checkout", revision_consumed=7, phase="resume"),
        })
        (target / "manifest.json").write_text(json.dumps(manifest))
        self.assertIn(
            "run continuity: expected run-original-product, found run-restarted-product",
            evaluate(CASES / "product-defect-handoff.json", workspace, "resume", state),
        )

    def test_runnable_defect_fixtures_expose_the_repair_outcomes(self):
        repair = Path(self.tmp.name) / "repair"
        product = Path(self.tmp.name) / "product-runnable"
        shutil.copytree(FIXTURES / "repairable-test-defect", repair)
        shutil.copytree(FIXTURES / "product-defect", product)
        self.assertNotEqual(subprocess.run(["node", "--test"], cwd=repair, capture_output=True).returncode, 0)
        self.assertNotEqual(subprocess.run(["node", "--test"], cwd=product, capture_output=True).returncode, 0)
        (repair / "tests" / "checkout.spec.ts").write_text(
            (repair / "tests" / "checkout.spec.ts").read_text().replace("Submit now", "Place order")
        )
        subprocess.run(
            ["git", "apply", str(ROOT / "evals" / "patches" / "product-defect-fix.patch")],
            cwd=product, check=True,
        )
        self.assertEqual(subprocess.run(["node", "--test"], cwd=repair, capture_output=True).returncode, 0)
        self.assertEqual(subprocess.run(["node", "--test"], cwd=product, capture_output=True).returncode, 0)

    def test_evaluator_rejects_malformed_registered_web_extension(self):
        manifest = _manifest(Path("/workspace"))
        manifest["extensions"][0]["data"] = {}
        self.assertIn(
            "extension data missing required property: driver",
            evaluate_result._validate_manifest(manifest),
        )

    def test_published_web_evidence_vocabulary_matches_evaluator(self):
        workflow = (ROOT / "skills/e2e-web/references/workflow.md").read_text()
        self.assertIn("| `check_ids` | immutable selected check IDs |", workflow)
        self.assertIn("`outcomes[].check_id`", workflow)
        evidence = _verification_evidence(
            "check-checkout", revision_consumed=4, phase="verify",
        )
        self.assertEqual(evidence["check_ids"], ["check-checkout"])
        self.assertEqual(evidence["outcomes"][0]["check_id"], "check-checkout")
        self.assertTrue(evaluate_result._is_execution_evidence(evidence, {"check-checkout"}, "web"))


class HostHarnessTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.results = Path(self.tmp.name) / "results"

    def tearDown(self):
        self.tmp.cleanup()

    def _run(self, host="codex", case="greenfield-source", *, diagnostics=None, returncode=0, keep_results=False, timeout=30):
        process = mock.Mock(pid=4321, returncode=returncode)
        process.communicate.return_value = ("host prose", "host stderr")
        completed = subprocess.CompletedProcess([], 0, stdout="", stderr="")
        with (
            mock.patch.object(run_host_eval, "RESULTS", self.results),
            mock.patch("evals.run_host_eval.shutil.which", return_value=f"/usr/bin/{host}"),
            mock.patch("evals.run_host_eval.subprocess.run", return_value=completed),
            mock.patch("evals.run_host_eval._spawn_host", return_value=process) as popen,
            mock.patch("evals.run_host_eval.evaluate", return_value=diagnostics or []) as evaluator,
        ):
            status = run_host_eval.run_case(host, case, keep_results=keep_results, host_timeout=timeout)
        return status, popen, evaluator, process

    def test_two_phase_product_resume_allows_harness_skills_and_all_e2e_artifacts_only(self):
        case_path, case = run_host_eval._read_case("product-defect-handoff")
        for host in ("codex", "claude"):
            with self.subTest(host=host), run_host_eval._workspace(case) as (_, workspace, state):
                run_host_eval._install_skills(workspace, host)
                target = workspace / ".e2e"
                evidence_dir = target / "evidence"
                evidence_dir.mkdir(parents=True)
                (target / "test-plan.md").write_text("# Checkout verification plan\n")
                (evidence_dir / "checkout.log").write_text("sanitized checkout failure\n")
                manifest = _manifest(workspace, status="handoff-required")
                manifest["run"]["mode"] = "verify"
                manifest["run"]["id"] = f"run-{host}-product-resume"
                manifest["run"]["revision"] = 7
                manifest["evidence"] = [_source_evidence(), *_product_defect_evidence()]
                manifest["handoffs"] = [_product_defect_handoff()]
                (target / "manifest.json").write_text(json.dumps(manifest))
                self.assertEqual(evaluate(case_path, workspace, "handoff", state), [])

                run_host_eval._apply_declared_patch(
                    workspace, ROOT / "evals" / "patches" / "product-defect-fix.patch",
                )
                manifest["run"]["status"] = "verified"
                manifest["run"]["revision"] = 8
                manifest["evidence"].append(
                    {
                        "id": "evidence-reverification",
                        **_verification_evidence("check-checkout", revision_consumed=7, phase="resume"),
                    }
                )
                (target / "manifest.json").write_text(json.dumps(manifest))
                self.assertEqual(evaluate(case_path, workspace, "resume", state), [])

                (workspace / "src" / "unapproved.js").write_text("export const unsafe = true;\n")
                self.assertIn(
                    "unauthorized resume change: src/unapproved.js",
                    evaluate(case_path, workspace, "resume", state),
                )

    def test_refuses_a_missing_host_executable_before_creating_a_process(self):
        with (
            mock.patch("evals.run_host_eval.shutil.which", return_value=None),
            mock.patch("evals.run_host_eval._spawn_host") as popen,
        ):
            with self.assertRaisesRegex(run_host_eval.HostUnavailableError, "codex executable"):
                run_host_eval.run_case("codex", "greenfield-source")
        popen.assert_not_called()

    def test_uses_the_exact_codex_command_prefix_and_case_prompt(self):
        status, popen, evaluator, process = self._run("codex")
        self.assertEqual(status, 0)
        command = popen.call_args.args[0]
        self.assertEqual(command[:4], ["codex", "exec", "--full-auto", "-"])
        prompt = process.communicate.call_args.kwargs["input"]
        self.assertEqual(prompt, json.loads((CASES / "greenfield-source.json").read_text())["prompt"])
        self.assertNotIn("generated-unverified", prompt)
        self.assertNotIn("required_evidence_ids", prompt)
        evaluator.assert_called_once()

    def test_uses_the_exact_claude_command_prefix(self):
        status, popen, _, _ = self._run("claude")
        self.assertEqual(status, 0)
        self.assertEqual(
            popen.call_args.args[0][:5],
            ["claude", "-p", "--permission-mode", "acceptEdits", "--no-session-persistence"],
        )

    def test_installs_all_skills_in_the_host_specific_directory(self):
        for host, skill_root in (("codex", ".agents/skills"), ("claude", ".claude/skills")):
            with self.subTest(host=host):
                self._run(host, keep_results=True)
                workspace = next((self.results / host / "greenfield-source").glob("*/workspace"))
                for skill in ("e2e-testing", "e2e-web", "e2e-service", "e2e-mobile", "e2e-desktop"):
                    self.assertTrue((workspace / skill_root / skill / "SKILL.md").is_file())
                self.assertFalse((workspace / skill_root / "e2e-web-playwright").exists())

    def test_snapshots_harness_installed_skills_deterministically_before_host_evaluation(self):
        snapshots: list[str] = []

        def evaluator(_case_path, workspace, _phase, state_dir):
            snapshot = Path(state_dir) / "workspace-baseline.json"
            self.assertTrue(snapshot.is_file())
            text = snapshot.read_text(encoding="utf-8")
            envelope = json.loads(text)
            self.assertEqual(envelope.get("version"), 1)
            baseline = envelope["files"]
            self.assertEqual(envelope["file_count"], len(baseline))
            self.assertRegex(envelope["files_digest"], r"^[0-9a-f]{64}$")
            self.assertIn(".git/HEAD", baseline)
            self.assertIn("package.json", baseline)
            self.assertIn(".agents/skills/e2e-mobile/SKILL.md", baseline)
            self.assertEqual(
                baseline[".agents/skills/e2e-mobile/SKILL.md"],
                _sha256(Path(workspace) / ".agents/skills/e2e-mobile/SKILL.md"),
            )
            diagnostics = evaluate_result._check_files(
                Path(workspace),
                FIXTURES / "greenfield-source",
                {"allowed_change_globs": []},
                Path(state_dir),
            )
            self.assertFalse(
                any(".agents/skills/" in item for item in diagnostics),
                diagnostics,
            )
            snapshots.append(text)
            return []

        process = mock.Mock(pid=4321, returncode=0)
        process.communicate.return_value = ("", "")
        with (
            mock.patch("evals.run_host_eval.shutil.which", return_value="/usr/bin/codex"),
            mock.patch("evals.run_host_eval._spawn_host", return_value=process),
            mock.patch("evals.run_host_eval.evaluate", side_effect=evaluator),
        ):
            self.assertEqual(run_host_eval.run_case("codex", "greenfield-source"), 0)
            self.assertEqual(run_host_eval.run_case("codex", "greenfield-source"), 0)

        self.assertEqual(len(snapshots), 2)
        self.assertEqual(snapshots[0], snapshots[1])

    def test_each_run_uses_a_fresh_fixture_copy_and_never_the_source_fixture(self):
        _, first, _, _ = self._run(keep_results=True)
        _, second, _, _ = self._run(keep_results=True)
        first_workspace = Path(first.call_args.args[1])
        second_workspace = Path(second.call_args.args[1])
        self.assertNotEqual(first_workspace, second_workspace)
        self.assertNotEqual(first_workspace, FIXTURES / "greenfield-source")
        self.assertNotEqual(second_workspace, FIXTURES / "greenfield-source")
        self.assertEqual(_sha256(FIXTURES / "greenfield-source" / "package.json"), json.loads(
            (FIXTURES / "greenfield-source" / ".fixture-baseline.json").read_text()
        )["package.json"])

    def test_runs_optional_setup_for_the_host_invocation_and_closes_it_afterward(self):
        events: list[str] = []

        @contextmanager
        def setup(case, workspace):
            events.append(f"start:{case['setup']['ready_url']}")
            yield
            events.append("stop")

        process = mock.Mock(pid=4321, returncode=0)
        process.communicate.return_value = ("", "")
        completed = subprocess.CompletedProcess([], 0, stdout="", stderr="")
        with (
            mock.patch("evals.run_host_eval.shutil.which", return_value="/usr/bin/codex"),
            mock.patch("evals.run_host_eval.subprocess.run", return_value=completed),
            mock.patch("evals.run_host_eval._spawn_host", return_value=process),
            mock.patch("evals.run_host_eval.evaluate", return_value=[]),
            mock.patch("evals.run_host_eval.running_setup", side_effect=setup),
        ):
            self.assertEqual(run_host_eval.run_case("codex", "live-assisted-generation"), 0)
        self.assertEqual(events, ["start:http://127.0.0.1:8765/", "stop"])

    def test_evaluates_each_phase_before_applying_the_declared_patch(self):
        events: list[str] = []
        process = mock.Mock(pid=4321, returncode=0)
        process.communicate.return_value = ("", "")
        completed = subprocess.CompletedProcess([], 0, stdout="", stderr="")

        def evaluator(case_path, workspace, phase, state_dir):
            events.append(f"evaluate:{phase}")
            self.assertNotEqual(Path(state_dir).parent, Path(workspace))
            return []

        def patch(workspace, patch_path):
            events.append(f"patch:{patch_path.name}")

        with (
            mock.patch("evals.run_host_eval.shutil.which", return_value="/usr/bin/codex"),
            mock.patch("evals.run_host_eval.subprocess.run", return_value=completed),
            mock.patch("evals.run_host_eval._spawn_host", return_value=process),
            mock.patch("evals.run_host_eval.evaluate", side_effect=evaluator),
            mock.patch("evals.run_host_eval._apply_declared_patch", side_effect=patch),
        ):
            self.assertEqual(run_host_eval.run_case("codex", "product-defect-handoff"), 0)
        self.assertEqual(events, [
            "evaluate:handoff",
            "patch:product-defect-fix.patch",
            "evaluate:resume",
        ])

    def test_returns_evaluator_status_instead_of_host_prose_or_process_exit_code(self):
        self.assertEqual(self._run(diagnostics=["missing manifest"], returncode=0)[0], 1)
        self.assertEqual(self._run(diagnostics=[], returncode=9)[0], 0)

    def test_retains_transcript_and_workspace_only_when_requested(self):
        self._run(keep_results=True)
        result = next((self.results / "codex" / "greenfield-source").iterdir())
        self.assertTrue((result / "stdout.txt").is_file())
        self.assertTrue((result / "stderr.txt").is_file())
        self.assertTrue((result / "workspace").is_dir())
        self._run(keep_results=False)
        self.assertEqual(len(list((self.results / "codex" / "greenfield-source").iterdir())), 1)

    def test_writes_unretained_transcript_to_the_temporary_run_directory(self):
        temporary_root = Path(self.tmp.name) / "ephemeral"
        temporary_root.mkdir()
        process = mock.Mock(pid=4321, returncode=0)
        process.communicate.return_value = ("temporary prose", "temporary stderr")
        completed = subprocess.CompletedProcess([], 0, stdout="", stderr="")
        temporary_directory = mock.MagicMock()
        temporary_directory.__enter__.return_value = str(temporary_root)
        with (
            mock.patch("evals.run_host_eval.shutil.which", return_value="/usr/bin/codex"),
            mock.patch("evals.run_host_eval.tempfile.TemporaryDirectory", return_value=temporary_directory),
            mock.patch("evals.run_host_eval.subprocess.run", return_value=completed),
            mock.patch("evals.run_host_eval._spawn_host", return_value=process),
            mock.patch("evals.run_host_eval.evaluate", return_value=[]),
        ):
            self.assertEqual(run_host_eval.run_case("codex", "greenfield-source"), 0)
        self.assertEqual((temporary_root / "stdout.txt").read_text(), "temporary prose")
        self.assertEqual((temporary_root / "stderr.txt").read_text(), "temporary stderr")

    def test_retains_host_transcript_when_a_between_phase_patch_fails(self):
        process = mock.Mock(pid=4321, returncode=0)
        process.communicate.return_value = ("handoff prose", "")
        completed = subprocess.CompletedProcess([], 0, stdout="", stderr="")
        with (
            mock.patch.object(run_host_eval, "RESULTS", self.results),
            mock.patch("evals.run_host_eval.shutil.which", return_value="/usr/bin/codex"),
            mock.patch("evals.run_host_eval.subprocess.run", return_value=completed),
            mock.patch("evals.run_host_eval._spawn_host", return_value=process),
            mock.patch("evals.run_host_eval.evaluate", return_value=[]),
            mock.patch("evals.run_host_eval._apply_declared_patch", side_effect=RuntimeError("patch failed")),
        ):
            with self.assertRaisesRegex(RuntimeError, "patch failed"):
                run_host_eval.run_case("codex", "product-defect-handoff", keep_results=True)
        result = next((self.results / "codex" / "product-defect-handoff").iterdir())
        self.assertEqual((result / "stdout.txt").read_text(), "handoff prose")

    def test_executes_outside_the_repository_then_copies_results_afterward(self):
        status, popen, _, _ = self._run(keep_results=True)
        self.assertEqual(status, 0)
        execution_workspace = Path(popen.call_args.args[1]).resolve()
        self.assertFalse(execution_workspace.is_relative_to(ROOT.resolve()))
        retained = next((self.results / "codex" / "greenfield-source").glob("*/workspace"))
        self.assertTrue((retained / "package.json").is_file())
        self.assertNotEqual(retained.resolve(), execution_workspace)

    def test_rejects_traversal_and_case_id_mismatch_as_untrusted_metadata(self):
        with self.assertRaisesRegex(ValueError, "invalid case ID"):
            run_host_eval._read_case("../greenfield-source")
        with self.assertRaisesRegex(ValueError, "invalid fixture path"):
            run_host_eval._fixture_path({"fixture": "../fixtures"})
        with self.assertRaisesRegex(ValueError, "invalid patch path"):
            run_host_eval._phase_runs({"id": "case", "prompt": "x", "phases": [
                {"name": "resume", "prompt": "x", "apply_patch": "../../outside.patch"},
            ]})
        case_root = Path(self.tmp.name) / "cases"
        case_root.mkdir()
        (case_root / "case.json").write_text(json.dumps({"id": "different"}))
        with mock.patch.object(run_host_eval, "CASES", case_root):
            with self.assertRaisesRegex(ValueError, "case ID mismatch"):
                run_host_eval._read_case("case")

    def test_host_timeout_terminates_the_process_tree_and_retains_partial_output(self):
        timeout = subprocess.TimeoutExpired("codex", 3, output="partial stdout", stderr="partial stderr")
        process = mock.Mock(pid=4321, returncode=None)
        process.communicate.side_effect = [timeout, ("partial stdout", "partial stderr")]
        process.wait.side_effect = [subprocess.TimeoutExpired("codex", 2), None]
        completed = subprocess.CompletedProcess([], 0, stdout="", stderr="")
        with (
            mock.patch.object(run_host_eval, "RESULTS", self.results),
            mock.patch("evals.run_host_eval.shutil.which", return_value="/usr/bin/codex"),
            mock.patch("evals.run_host_eval.subprocess.run", return_value=completed),
            mock.patch("evals.run_host_eval._spawn_host", return_value=process),
            mock.patch("evals.run_host_eval.os.killpg") as killpg,
            mock.patch("evals.run_host_eval.evaluate", return_value=[]),
        ):
            with self.assertRaisesRegex(run_host_eval.HostTimeoutError, "3 seconds"):
                run_host_eval.run_case("codex", "greenfield-source", keep_results=True, host_timeout=3)
        self.assertEqual(killpg.call_count, 2)
        result = next((self.results / "codex" / "greenfield-source").iterdir())
        self.assertEqual((result / "stdout.txt").read_text(), "partial stdout")
        self.assertEqual((result / "stderr.txt").read_text(), "partial stderr")

    def test_process_tree_cleanup_stops_waiting_after_the_kill_grace_period(self):
        process = mock.Mock(pid=4321)
        process.wait.side_effect = [
            subprocess.TimeoutExpired("codex", 2),
            subprocess.TimeoutExpired("codex", 2),
        ]
        with mock.patch("evals.run_host_eval.os.killpg") as killpg:
            run_host_eval._terminate_process_tree(process)
        self.assertEqual(killpg.call_count, 2)

    def test_process_tree_cleanup_does_not_mask_timeout_with_a_wait_os_error(self):
        process = mock.Mock(pid=4321)
        process.wait.side_effect = OSError("already reaped")
        with mock.patch("evals.run_host_eval.os.killpg"):
            run_host_eval._terminate_process_tree(process)

    def test_windows_process_tree_cleanup_uses_taskkill_tree_then_forced_escalation(self):
        process = mock.Mock(pid=4321)
        process.wait.side_effect = [subprocess.TimeoutExpired("codex", 2), None]
        completed = subprocess.CompletedProcess([], 0, stdout="", stderr="")
        with (
            mock.patch.object(run_host_eval.os, "name", "nt"),
            mock.patch("evals.run_host_eval.subprocess.run", return_value=completed) as run,
        ):
            run_host_eval._terminate_process_tree(process)
        self.assertEqual(
            [call.args[0] for call in run.call_args_list],
            [["taskkill", "/PID", "4321", "/T"], ["taskkill", "/PID", "4321", "/T", "/F"]],
        )
        self.assertTrue(all(call.kwargs["shell"] is False for call in run.call_args_list))
        process.terminate.assert_not_called()
        process.kill.assert_not_called()

    def test_windows_tree_cleanup_does_not_require_sigkill_to_exist(self):
        process = mock.Mock(pid=4321)
        process.wait.side_effect = [subprocess.TimeoutExpired("codex", 2), None]
        completed = subprocess.CompletedProcess([], 0, stdout="", stderr="")
        original_sigkill = run_host_eval.signal.SIGKILL
        try:
            delattr(run_host_eval.signal, "SIGKILL")
            with (
                mock.patch.object(run_host_eval.os, "name", "nt"),
                mock.patch("evals.run_host_eval.subprocess.run", return_value=completed) as run,
            ):
                run_host_eval._terminate_process_tree(process)
        finally:
            setattr(run_host_eval.signal, "SIGKILL", original_sigkill)
        self.assertEqual(
            [call.args[0] for call in run.call_args_list],
            [["taskkill", "/PID", "4321", "/T"], ["taskkill", "/PID", "4321", "/T", "/F"]],
        )

    def test_timeout_concatenates_distinct_partial_and_drained_output(self):
        timeout = subprocess.TimeoutExpired("codex", 3, output="partial stdout", stderr="partial stderr")
        process = mock.Mock(pid=4321)
        process.communicate.side_effect = [timeout, ("drained stdout", "drained stderr")]
        process.wait.return_value = None
        with (
            mock.patch("evals.run_host_eval._spawn_host", return_value=process),
            mock.patch("evals.run_host_eval.os.killpg"),
        ):
            with self.assertRaises(run_host_eval.HostTimeoutError) as raised:
                run_host_eval._run_host(["codex"], Path(self.tmp.name), "prompt", 3)
        self.assertEqual(raised.exception.stdout, "partial stdoutdrained stdout")
        self.assertEqual(raised.exception.stderr, "partial stderrdrained stderr")

    def test_timeout_overlap_merge_preserves_repeats_and_blank_lines(self):
        partial = "first\n\nrepeat\n"
        drained = "repeat\n\nsecond\nrepeat\n"
        self.assertEqual(
            run_host_eval._combine_output(partial, drained),
            "first\n\nrepeat\n\nsecond\nrepeat\n",
        )
        self.assertEqual(
            run_host_eval._combine_output("repeat\n", "other\nrepeat\n"),
            "repeat\nother\nrepeat\n",
        )

    def test_timeout_preserves_primary_error_when_killpg_and_drain_fail(self):
        timeout = subprocess.TimeoutExpired("codex", 3, output="partial stdout", stderr="partial stderr")
        process = mock.Mock(pid=4321)
        process.communicate.side_effect = [timeout, OSError("drain failed")]
        process.wait.return_value = None
        with (
            mock.patch("evals.run_host_eval._spawn_host", return_value=process),
            mock.patch("evals.run_host_eval.os.killpg", side_effect=OSError("killpg failed")),
        ):
            with self.assertRaises(run_host_eval.HostTimeoutError) as raised:
                run_host_eval._run_host(["codex"], Path(self.tmp.name), "prompt", 3)
        self.assertEqual(raised.exception.stdout, "partial stdout")
        self.assertEqual(raised.exception.stderr, "partial stderr")

    def test_real_git_boundary_is_external_and_retention_runs_after_evaluation(self):
        process = mock.Mock(pid=4321, returncode=0)
        events: list[str] = []

        def communicate(*, input, timeout):
            events.append("host")
            return "host prose", ""

        process.communicate.side_effect = communicate
        original_retain = run_host_eval._retain_artifacts

        def retain(source, host, case_id):
            events.append("retain")
            self.assertEqual(events[:2], ["host", "evaluate"])
            return original_retain(source, host, case_id)

        def launch(command, workspace):
            workspace = Path(workspace)
            top = subprocess.run(
                ["git", "rev-parse", "--show-toplevel"], cwd=workspace, text=True, capture_output=True, check=True,
            ).stdout.strip()
            self.assertEqual(Path(top).resolve(), workspace.resolve())
            self.assertFalse(Path(top).resolve().is_relative_to(ROOT.resolve()))
            return process

        def evaluator(*_args):
            events.append("evaluate")
            return []

        with (
            mock.patch.object(run_host_eval, "RESULTS", self.results),
            mock.patch("evals.run_host_eval.shutil.which", return_value="/usr/bin/codex"),
            mock.patch("evals.run_host_eval._spawn_host", side_effect=launch),
            mock.patch("evals.run_host_eval.evaluate", side_effect=evaluator),
            mock.patch("evals.run_host_eval._retain_artifacts", side_effect=retain),
        ):
            self.assertEqual(run_host_eval.run_case("codex", "greenfield-source", keep_results=True), 0)
        self.assertEqual(events, ["host", "evaluate", "retain"])
        retained = next((self.results / "codex" / "greenfield-source").glob("*/workspace"))
        self.assertTrue((retained / ".git").is_dir())

    def test_host_timeout_survives_a_second_setup_kill_wait_timeout(self):
        case = json.loads((CASES / "live-assisted-generation.json").read_text())
        host_timeout = subprocess.TimeoutExpired("codex", 1, output="partial", stderr="")
        host = mock.Mock(pid=4321)
        host.communicate.side_effect = [host_timeout, ("", "")]
        host.wait.return_value = None
        setup = mock.Mock()
        setup.wait.side_effect = [subprocess.TimeoutExpired("setup", 2), subprocess.TimeoutExpired("setup", 2)]
        response = mock.MagicMock(status=200)
        response.__enter__.return_value = response
        with (
            mock.patch("evals.run_host_eval.shutil.which", return_value="/usr/bin/codex"),
            mock.patch("evals.run_host_eval._spawn_host", return_value=host),
            mock.patch("evals.run_host_eval.os.killpg"),
            mock.patch("evals.evaluate_result._spawn_setup", return_value=setup),
            mock.patch("evals.evaluate_result.urllib.request.urlopen", return_value=response),
        ):
            with self.assertRaises(run_host_eval.HostTimeoutError):
                run_host_eval.run_case("codex", case["id"], host_timeout=1)
        setup.terminate.assert_called_once()
        setup.kill.assert_called_once()

    def test_host_timeout_survives_setup_terminate_error_and_still_kills(self):
        case = json.loads((CASES / "live-assisted-generation.json").read_text())
        host_timeout = subprocess.TimeoutExpired("codex", 1, output="partial", stderr="")
        host = mock.Mock(pid=4321)
        host.communicate.side_effect = [host_timeout, ("", "")]
        host.wait.return_value = None
        setup = mock.Mock()
        setup.terminate.side_effect = OSError("terminate failed")
        setup.wait.return_value = None
        response = mock.MagicMock(status=200)
        response.__enter__.return_value = response
        with (
            mock.patch("evals.run_host_eval.shutil.which", return_value="/usr/bin/codex"),
            mock.patch("evals.run_host_eval._spawn_host", return_value=host),
            mock.patch("evals.run_host_eval.os.killpg"),
            mock.patch("evals.evaluate_result._spawn_setup", return_value=setup),
            mock.patch("evals.evaluate_result.urllib.request.urlopen", return_value=response),
        ):
            with self.assertRaises(run_host_eval.HostTimeoutError):
                run_host_eval.run_case("codex", case["id"], host_timeout=1)
        setup.kill.assert_called_once()
        setup.wait.assert_called_once_with(timeout=2)


class SetupLifecycleTests(unittest.TestCase):
    def test_polls_declared_ready_url_and_kills_setup_after_termination_timeout(self):
        case = json.loads((CASES / "live-assisted-generation.json").read_text())
        process = mock.Mock()
        process.wait.side_effect = [subprocess.TimeoutExpired("setup", 2), None]
        response = mock.MagicMock(status=200)
        response.__enter__.return_value = response
        with (
            mock.patch("evals.evaluate_result._spawn_setup", return_value=process),
            mock.patch("evals.evaluate_result.urllib.request.urlopen", side_effect=[OSError("not ready"), response]) as urlopen,
            mock.patch("evals.evaluate_result.time.sleep"),
        ):
            with evaluate_result.running_setup(case, FIXTURES / "live-assisted-generation"):
                pass
        self.assertEqual(urlopen.call_args_list[-1].args[0], case["setup"]["ready_url"])
        process.terminate.assert_called_once()
        process.kill.assert_called_once()


if __name__ == "__main__":
    unittest.main()
