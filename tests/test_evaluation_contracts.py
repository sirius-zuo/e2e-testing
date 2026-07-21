"""Deterministic acceptance contracts for the E2E skill fixtures."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from evals.evaluate_result import evaluate
from protocol.v1.e2e_protocol import new_manifest


ROOT = Path(__file__).resolve().parents[1]
CASES = ROOT / "evals" / "cases"
FIXTURES = ROOT / "evals" / "fixtures"
REQUIRED_CASE_FIELDS = {"id", "entry_skill", "mode", "prompt", "fixture", "expect"}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _manifest(workspace: Path, status: str = "generated-unverified") -> dict:
    data = new_manifest(str(workspace))
    data["status"] = status
    data["journeys"] = [{"id": "journey-checkout", "status": "covered"}]
    data["tests"] = [{"id": "test-checkout", "journey_id": "journey-checkout", "status": "generated"}]
    data["evidence"] = [{"id": "evidence-source", "kind": "source-derived"}]
    return data


class FixtureContractTests(unittest.TestCase):
    def test_cases_have_required_fields_and_existing_fixtures(self):
        case_paths = sorted(CASES.glob("*.json"))
        self.assertEqual(len(case_paths), 10)
        self.assertEqual({path.stem for path in case_paths}, {
            "greenfield-source", "live-assisted-generation", "existing-playwright",
            "unsupported-cypress", "conflicting-evidence", "verify-pass",
            "repair-test-defect", "product-defect-handoff", "missing-credentials", "auto-budget",
        })
        for path in case_paths:
            with self.subTest(case=path.stem):
                case = json.loads(path.read_text())
                self.assertTrue(REQUIRED_CASE_FIELDS <= set(case))
                self.assertTrue((FIXTURES / case["fixture"]).is_dir())

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
        manifest["tests"] = []
        self._write_manifest(manifest)
        self.assertIn(
            "missing journey traceability: journey-checkout",
            evaluate(self.case, self.workspace),
        )

    def test_detects_missing_evidence(self):
        manifest = _manifest(self.workspace)
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
        (target / "manifest.json").write_text(json.dumps(_manifest(workspace, "unsupported-framework")))
        self.assertEqual(evaluate(case, workspace), [])
        (target / "manifest.json").unlink()
        self.assertIn("missing manifest: manifest.json", evaluate(case, workspace))
        (target / "manifest.json").write_text("{}")
        self.assertTrue(any(item.startswith("invalid manifest:") for item in evaluate(case, workspace)))

    def test_existing_playwright_requires_a_new_checkout_artifact(self):
        workspace = Path(self.tmp.name) / "existing"
        shutil.copytree(FIXTURES / "existing-playwright", workspace)
        manifest = _manifest(workspace)
        manifest["evidence"] = [{"id": "evidence-existing-suite"}]
        target = workspace / ".e2e"
        target.mkdir()
        (target / "manifest.json").write_text(json.dumps(manifest))
        self.assertIn(
            "required new path missing: tests/checkout.generated.spec.ts",
            evaluate(CASES / "existing-playwright.json", workspace),
        )
        (workspace / "tests" / "checkout.generated.spec.ts").write_text("// newly generated checkout coverage\n")
        self.assertEqual(evaluate(CASES / "existing-playwright.json", workspace), [])

    def test_repair_case_requires_the_precise_stale_locator_repair(self):
        workspace = Path(self.tmp.name) / "repair-contract"
        shutil.copytree(FIXTURES / "repairable-test-defect", workspace)
        manifest = _manifest(workspace, "verified")
        manifest["evidence"] = [{"id": "evidence-repair"}, {"id": "evidence-reverification"}]
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

    def test_product_defect_resume_allows_only_the_authorized_source_patch(self):
        workspace = Path(self.tmp.name) / "product"
        shutil.copytree(FIXTURES / "product-defect", workspace)
        manifest = _manifest(workspace, status="handoff-required")
        manifest["run_id"] = "run-product-defect"
        manifest["revision"] = 7
        manifest["evidence"] = [
            {"id": "evidence-product-defect"},
        ]
        manifest["handoffs"] = [{"id": "handoff-product-defect", "owner": "product-team"}]
        target = workspace / ".e2e"
        target.mkdir()
        (target / "manifest.json").write_text(json.dumps(manifest))
        self.assertEqual(
            evaluate(CASES / "product-defect-handoff.json", workspace, phase="handoff"), [],
        )
        self.assertTrue((target / ".eval-checkpoint-product-defect-handoff-handoff.json").is_file())
        subprocess.run(
            ["git", "apply", str(ROOT / "evals" / "patches" / "product-defect-fix.patch")],
            cwd=workspace, check=True,
        )
        manifest["status"] = "verified"
        manifest["revision"] = 8
        manifest["evidence"].append({"id": "evidence-reverification"})
        (target / "manifest.json").write_text(json.dumps(manifest))
        self.assertEqual(
            evaluate(CASES / "product-defect-handoff.json", workspace, phase="resume"), [],
        )

    def test_product_defect_resume_rejects_a_fresh_run_without_handoff_checkpoint(self):
        workspace = Path(self.tmp.name) / "fresh-product"
        shutil.copytree(FIXTURES / "product-defect", workspace)
        subprocess.run(
            ["git", "apply", str(ROOT / "evals" / "patches" / "product-defect-fix.patch")],
            cwd=workspace, check=True,
        )
        manifest = _manifest(workspace, status="verified")
        manifest["run_id"] = "run-fresh-product"
        manifest["revision"] = 8
        manifest["evidence"] = [
            {"id": "evidence-product-defect"}, {"id": "evidence-reverification"},
        ]
        manifest["handoffs"] = [{"id": "handoff-product-defect", "owner": "product-team"}]
        target = workspace / ".e2e"
        target.mkdir()
        (target / "manifest.json").write_text(json.dumps(manifest))
        self.assertIn(
            "missing phase checkpoint: handoff",
            evaluate(CASES / "product-defect-handoff.json", workspace, phase="resume"),
        )

    def test_product_defect_resume_rejects_an_unapplied_declared_patch(self):
        workspace = Path(self.tmp.name) / "unpatched-product"
        shutil.copytree(FIXTURES / "product-defect", workspace)
        manifest = _manifest(workspace, status="handoff-required")
        manifest["run_id"] = "run-unpatched-product"
        manifest["revision"] = 7
        manifest["evidence"] = [{"id": "evidence-product-defect"}]
        manifest["handoffs"] = [{"id": "handoff-product-defect"}]
        target = workspace / ".e2e"
        target.mkdir()
        (target / "manifest.json").write_text(json.dumps(manifest))
        self.assertEqual(evaluate(CASES / "product-defect-handoff.json", workspace, "handoff"), [])
        manifest["status"] = "verified"
        manifest["revision"] = 8
        manifest["evidence"].append({"id": "evidence-reverification"})
        (target / "manifest.json").write_text(json.dumps(manifest))
        self.assertIn(
            "authorized patch not applied: src/checkout.js",
            evaluate(CASES / "product-defect-handoff.json", workspace, "resume"),
        )

    def test_product_defect_resume_rejects_a_discontinuous_run_id(self):
        workspace = Path(self.tmp.name) / "discontinuous-product"
        shutil.copytree(FIXTURES / "product-defect", workspace)
        manifest = _manifest(workspace, status="handoff-required")
        manifest["run_id"] = "run-original-product"
        manifest["revision"] = 7
        manifest["evidence"] = [{"id": "evidence-product-defect"}]
        manifest["handoffs"] = [{"id": "handoff-product-defect"}]
        target = workspace / ".e2e"
        target.mkdir()
        (target / "manifest.json").write_text(json.dumps(manifest))
        self.assertEqual(evaluate(CASES / "product-defect-handoff.json", workspace, "handoff"), [])
        subprocess.run(
            ["git", "apply", str(ROOT / "evals" / "patches" / "product-defect-fix.patch")],
            cwd=workspace, check=True,
        )
        manifest["status"] = "verified"
        manifest["run_id"] = "run-restarted-product"
        manifest["revision"] = 8
        manifest["evidence"].append({"id": "evidence-reverification"})
        (target / "manifest.json").write_text(json.dumps(manifest))
        self.assertIn(
            "run continuity: expected run-original-product, found run-restarted-product",
            evaluate(CASES / "product-defect-handoff.json", workspace, "resume"),
        )

    def test_runnable_defect_fixtures_expose_the_repair_outcomes(self):
        repair = Path(self.tmp.name) / "repair"
        product = Path(self.tmp.name) / "product-runnable"
        shutil.copytree(FIXTURES / "repairable-test-defect", repair)
        shutil.copytree(FIXTURES / "product-defect", product)
        self.assertNotEqual(subprocess.run(["node", "--test"], cwd=repair, capture_output=True).returncode, 0)
        self.assertNotEqual(subprocess.run(["node", "--test"], cwd=product, capture_output=True).returncode, 0)
        (repair / "tests" / "checkout.logic.test.js").write_text(
            (repair / "tests" / "checkout.logic.test.js").read_text().replace("Submit now", "Place order")
        )
        subprocess.run(
            ["git", "apply", str(ROOT / "evals" / "patches" / "product-defect-fix.patch")],
            cwd=product, check=True,
        )
        self.assertEqual(subprocess.run(["node", "--test"], cwd=repair, capture_output=True).returncode, 0)
        self.assertEqual(subprocess.run(["node", "--test"], cwd=product, capture_output=True).returncode, 0)


if __name__ == "__main__":
    unittest.main()
