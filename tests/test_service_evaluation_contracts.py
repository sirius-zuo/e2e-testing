"""Service-surface evaluation contract tests."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from evals.evaluate_result import evaluate, SERVICE_PROTOCOLS, DATABASE_CAPABILITIES
from evals.evaluate_result import ROOT


SERVICE_ENVIRONMENT = {
    "protocol": "grpc",
    "client": "repository-native",
    "client_version": "1.0",
    "os_platform": "test",
    "runtime": "node",
    "application_build_ref": "build-local",
    "target_reference": "target-local",
    "target_tier": "local",
}

WEB_ENVIRONMENT = {
    "browser_project": "chromium",
    "os_platform": "test",
    "runtime": "node",
    "application_build_ref": "build-local",
    "target_reference": "target-local",
    "target_tier": "local",
}


def _json_write(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2))


def _copy_fixture_baseline(workspace: Path) -> None:
    """Copy a minimal fixture baseline so the evaluator doesn't fail on file checks."""
    fixture_baseline = ROOT / "evals" / "fixtures" / "login-journey" / ".fixture-baseline.json"
    if fixture_baseline.exists():
        (workspace / ".fixture-baseline.json").write_text(
            fixture_baseline.read_text(), encoding="utf-8"
        )
    else:
        (workspace / ".fixture-baseline.json").write_text("{}", encoding="utf-8")


class ServiceEvaluationTests(unittest.TestCase):
    def _manifest(self, surface: str, mode: str = "verify") -> dict:
        primary = "service" if surface == "service" else "web"
        return {
            "protocol_version": "2.0",
            "run": {"id": "run-test", "revision": 1, "mode": mode,
                    "autonomy": {"mode": "explicit", "auto_repair": False},
                    "status": "verified",
                    "created_at": "2026-07-25T00:00:00Z", "updated_at": "2026-07-25T00:00:00Z",
                    "attempt_budget": {"repair": 0, "verification": 1, "wall_clock_seconds": 300}},
            "systems": [{"id": "system-primary", "project_root": "/test", "primary_surface": primary,
                         "boundary": {"status": "declared", "actors": [], "public_interfaces": [],
                                      "evidence_ids": []},
                         "target": {"tier": "local", "endpoint_refs": [], "credential_refs": [],
                                    "mutation_policy": {"namespace_ref": None, "allowed_classes": []}}}],
            "journeys": [], "execution_units": [{"id": "unit-1", "system_id": "system-primary",
                                                 "surface": surface, "capability": "query",
                                                 "extension_id": None}],
            "checks": [], "evidence": [], "actions": [], "handoffs": [],
            "authorizations": [], "attempts": [], "extensions": [],
        }

    def _setup_workspace(self, workspace: Path, manifest: dict, surface: str) -> Path:
        """Set up workspace with manifest, fixture baseline, and case file."""
        e2e_dir = workspace / ".e2e"
        e2e_dir.mkdir()
        _copy_fixture_baseline(workspace)

        # Add journey to manifest
        manifest["journeys"] = [{"id": "journey-1", "system_id": "system-primary", "status": "planned"}]

        # Build checks list
        checks = [{"id": "check-1", "journey_id": "journey-1",
                   "execution_unit_id": "unit-1", "status": "passed"}]
        manifest["checks"] = checks

        # Build evidence with execution_environment
        if surface == "service":
            env = SERVICE_ENVIRONMENT
        else:
            env = WEB_ENVIRONMENT
        manifest["evidence"] = [{
            "id": "exec-1", "command": f"e2e-{surface} verify", "exit_code": 0, "duration_ms": 100,
            "check_ids": ["check-1"], "outcomes": [{"check_id": "check-1", "status": "passed"}],
            "execution_environment": env,
        }]

        _json_write(e2e_dir / "manifest.json", manifest)
        return e2e_dir

    def test_service_execution_environment_passes_for_service_surface(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            manifest = self._manifest("service")
            self._setup_workspace(workspace, manifest, "service")
            case = {
                "id": "case-svc", "entry_skill": "e2e-service", "mode": "verify", "prompt": "verify",
                "fixture": "login-journey", "surface": "service",
                "expect": {"manifest_status": "verified", "required_journey_ids": ["journey-1"]},
            }
            _json_write(workspace / "case.json", case)
            diagnostics = evaluate(workspace / "case.json", workspace)
            self.assertEqual(diagnostics, [])

    def test_service_execution_environment_fails_for_web_surface(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            manifest = self._manifest("service")
            self._setup_workspace(workspace, manifest, "service")
            case = {
                "id": "case-svc", "entry_skill": "e2e-service", "mode": "verify", "prompt": "verify",
                "fixture": "login-journey",
                "expect": {"manifest_status": "verified", "required_journey_ids": ["journey-1"]},
            }
            _json_write(workspace / "case.json", case)
            diagnostics = evaluate(workspace / "case.json", workspace)
            self.assertIn(
                "verified status requires successful selected-check execution evidence",
                diagnostics,
            )

    def test_web_execution_environment_passes_for_omitted_surface(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            manifest = self._manifest("web")
            self._setup_workspace(workspace, manifest, "web")
            case = {
                "id": "case-web", "entry_skill": "e2e-web", "mode": "verify", "prompt": "verify",
                "fixture": "login-journey",
                "expect": {"manifest_status": "verified", "required_journey_ids": ["journey-1"]},
            }
            _json_write(workspace / "case.json", case)
            diagnostics = evaluate(workspace / "case.json", workspace)
            self.assertEqual(diagnostics, [])

    def test_service_environment_fails_for_web_surface(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            e2e_dir = workspace / ".e2e"
            e2e_dir.mkdir()
            _copy_fixture_baseline(workspace)
            manifest = self._manifest("web")
            checks = [{"id": "check-1", "journey_id": "journey-1",
                       "execution_unit_id": "unit-1", "status": "passed"}]
            manifest["checks"] = checks
            manifest["evidence"] = [{
                "id": "exec-1", "command": "e2e-service verify", "exit_code": 0, "duration_ms": 100,
                "check_ids": ["check-1"], "outcomes": [{"check_id": "check-1", "status": "passed"}],
                "execution_environment": SERVICE_ENVIRONMENT,
            }]
            manifest["journeys"] = [{"id": "journey-1", "system_id": "system-primary", "status": "planned"}]
            _json_write(e2e_dir / "manifest.json", manifest)
            case = {
                "id": "case-web", "entry_skill": "e2e-web", "mode": "verify", "prompt": "verify",
                "fixture": "login-journey",
                "expect": {"manifest_status": "verified", "required_journey_ids": ["journey-1"]},
            }
            _json_write(workspace / "case.json", case)
            diagnostics = evaluate(workspace / "case.json", workspace)
            self.assertIn(
                "verified status requires successful selected-check execution evidence",
                diagnostics,
            )

    def test_service_capability_evidence_accepted_as_read_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            e2e_dir = workspace / ".e2e"
            e2e_dir.mkdir()
            _copy_fixture_baseline(workspace)
            manifest = self._manifest("service", mode="generate")
            manifest["evidence"] = [{
                "id": "cap-1",
                "framework": "queue",
                "source_locations": ["contracts/queue.md"],
                "read_only": True,
            }]
            manifest["run"]["status"] = "capability-unavailable"
            _json_write(e2e_dir / "manifest.json", manifest)
            case = {
                "id": "case-cap", "entry_skill": "e2e-service", "mode": "generate", "prompt": "test",
                "fixture": "login-journey", "surface": "service",
                "expect": {"manifest_status": "capability-unavailable"},
            }
            _json_write(workspace / "case.json", case)
            diagnostics = evaluate(workspace / "case.json", workspace)
            self.assertEqual(diagnostics, [])


class ServiceCaseContractTests(unittest.TestCase):
    def test_service_cases_exist_and_have_required_fields(self):
        cases_dir = ROOT / "evals" / "cases"
        service_case_ids = (
            "service-generate-all", "service-verify-all", "service-multi-protocol",
            "service-production-refusal", "service-capability-unavailable",
            "service-product-defect", "service-database-support",
        )
        for case_id in service_case_ids:
            case_path = cases_dir / f"{case_id}.json"
            self.assertTrue(case_path.exists(), f"missing case: {case_path}")
            case = json.loads(case_path.read_text())
            self.assertEqual(case["surface"], "service")
            self.assertIn(case["mode"], {"generate", "verify", "repair", "plan"})
            self.assertEqual(case["fixture"], "service-contract")

    def test_multi_protocol_requires_all_six_check_ids(self):
        cases_dir = ROOT / "evals" / "cases"
        multi = json.loads((cases_dir / "service-multi-protocol.json").read_text())
        self.assertEqual(
            set(multi["expect"]["required_check_ids"]),
            {"check-http", "check-graphql", "check-grpc", "check-websocket", "check-queue", "check-stream"},
        )


class ServiceEvaluationGateTests(unittest.TestCase):
    def _manifest(self, surface: str, mode: str = "verify") -> dict:
        primary = "service" if surface == "service" else "web"
        return {
            "protocol_version": "2.0",
            "run": {"id": "run-test", "revision": 1, "mode": "verify",
                    "autonomy": {"mode": "explicit", "auto_repair": False},
                    "status": "verified",
                    "created_at": "2026-07-25T00:00:00Z", "updated_at": "2026-07-25T00:00:00Z",
                    "attempt_budget": {"repair": 0, "verification": 1, "wall_clock_seconds": 300}},
            "systems": [{"id": "system-primary", "project_root": "/test", "primary_surface": primary,
                         "boundary": {"status": "declared", "actors": [], "public_interfaces": [],
                                      "evidence_ids": []},
                         "target": {"tier": "local", "endpoint_refs": [], "credential_refs": [],
                                    "mutation_policy": {"namespace_ref": None, "allowed_classes": []}}}],
            "journeys": [], "execution_units": [{"id": "unit-1", "system_id": "system-primary",
                                                 "surface": surface, "capability": "query",
                                                 "extension_id": None}],
            "checks": [], "evidence": [], "actions": [], "handoffs": [],
            "authorizations": [], "attempts": [], "extensions": [],
        }

    def test_missing_service_module_outcome_prevents_verified(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            e2e_dir = workspace / ".e2e"
            e2e_dir.mkdir()
            _copy_fixture_baseline(workspace)
            manifest = self._manifest("service")
            manifest["evidence"] = [{
                "id": "exec-1", "command": "e2e-service verify", "exit_code": 0, "duration_ms": 100,
                "check_ids": ["check-http"], "outcomes": [{"check_id": "check-http", "status": "passed"}],
                "execution_environment": SERVICE_ENVIRONMENT,
            }]
            manifest["checks"] = [
                {"id": "check-http", "journey_id": "journey-1", "execution_unit_id": "unit-1",
                 "status": "passed"},
                {"id": "check-graphql", "journey_id": "journey-1", "execution_unit_id": "unit-1",
                 "status": "pending"},
            ]
            manifest["journeys"] = [{"id": "journey-1", "system_id": "system-primary", "status": "planned"}]
            _json_write(e2e_dir / "manifest.json", manifest)
            case = {
                "id": "case-multi", "entry_skill": "e2e-service", "mode": "verify", "prompt": "test",
                "fixture": "login-journey", "surface": "service",
                "expect": {
                    "manifest_status": "verified",
                    "required_check_ids": ["check-http", "check-graphql"],
                },
            }
            _json_write(workspace / "case.json", case)
            diagnostics = evaluate(workspace / "case.json", workspace)
            self.assertIn("missing check ID: check-graphql", diagnostics)

    def test_production_mutation_rejected_in_service(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            e2e_dir = workspace / ".e2e"
            e2e_dir.mkdir()
            _copy_fixture_baseline(workspace)
            manifest = self._manifest("service")
            manifest["evidence"] = [{
                "id": "exec-1", "command": "e2e-service verify", "exit_code": 0, "duration_ms": 100,
                "check_ids": ["check-1"], "outcomes": [{"check_id": "check-1", "status": "passed"}],
                "execution_environment": {
                    **SERVICE_ENVIRONMENT, "mutation_performed": True,
                },
            }]
            manifest["checks"] = [{"id": "check-1", "journey_id": "journey-1",
                                   "execution_unit_id": "unit-1", "status": "passed"}]
            manifest["journeys"] = [{"id": "journey-1", "system_id": "system-primary", "status": "planned"}]
            _json_write(e2e_dir / "manifest.json", manifest)
            case = {
                "id": "case-prod", "entry_skill": "e2e-service", "mode": "verify", "prompt": "test",
                "fixture": "login-journey", "surface": "service",
                "expect": {"manifest_status": "verified"},
            }
            _json_write(workspace / "case.json", case)
            diagnostics = evaluate(workspace / "case.json", workspace)
            self.assertTrue(any("mutation" in d.lower() for d in diagnostics))

    def test_database_row_cannot_substitute_for_execution_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            e2e_dir = workspace / ".e2e"
            e2e_dir.mkdir()
            _copy_fixture_baseline(workspace)
            manifest = self._manifest("service")
            manifest["evidence"] = [{
                "id": "db-row", "classification": {"primary": "test-passed", "confidence": 0.9,
                     "rationale": "db row exists", "evidence_ids": []},
            }]
            manifest["run"]["status"] = "verified"
            manifest["checks"] = [{"id": "check-1", "journey_id": "journey-1",
                                   "execution_unit_id": "unit-1", "status": "passed"}]
            manifest["journeys"] = [{"id": "journey-1", "system_id": "system-primary", "status": "planned"}]
            _json_write(e2e_dir / "manifest.json", manifest)
            case = {
                "id": "case-db", "entry_skill": "e2e-service", "mode": "verify", "prompt": "test",
                "fixture": "login-journey", "surface": "service",
                "expect": {"manifest_status": "verified"},
            }
            _json_write(workspace / "case.json", case)
            diagnostics = evaluate(workspace / "case.json", workspace)
            self.assertIn(
                "verified status requires successful selected-check execution evidence",
                diagnostics,
            )

    def test_cleanup_failure_blocks_completion(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            e2e_dir = workspace / ".e2e"
            e2e_dir.mkdir()
            _copy_fixture_baseline(workspace)
            manifest = self._manifest("service")
            manifest["evidence"] = [{
                "id": "exec-1", "command": "e2e-service verify", "exit_code": 0, "duration_ms": 100,
                "check_ids": ["check-1"], "outcomes": [{"check_id": "check-1", "status": "passed"}],
                "execution_environment": SERVICE_ENVIRONMENT,
            }]
            manifest["checks"] = [{"id": "check-1", "journey_id": "journey-1",
                                   "execution_unit_id": "unit-1", "status": "passed"}]
            manifest["actions"] = [{
                "id": "action-db-cleanup", "capability": "database-cleanup",
                "journey_ids": ["journey-1"], "command_ref": "cmd-cleanup",
            }]
            manifest["journeys"] = [{"id": "journey-1", "system_id": "system-primary", "status": "planned"}]
            _json_write(e2e_dir / "manifest.json", manifest)
            case = {
                "id": "case-cleanup", "entry_skill": "e2e-service", "mode": "verify", "prompt": "test",
                "fixture": "login-journey", "surface": "service",
                "expect": {
                    "manifest_status": "verified",
                    "required_action_ids": ["action-db-cleanup"],
                },
            }
            _json_write(workspace / "case.json", case)
            diagnostics = evaluate(workspace / "case.json", workspace)
            self.assertTrue(any("cleanup" in d.lower() for d in diagnostics))

    def test_capability_evidence_is_read_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            e2e_dir = workspace / ".e2e"
            e2e_dir.mkdir()
            _copy_fixture_baseline(workspace)
            manifest = self._manifest("service", mode="generate")
            manifest["evidence"] = [{
                "id": "cap-1", "framework": "stream",
                "source_locations": ["contracts/stream.md"],
                "read_only": False,
            }]
            manifest["run"]["status"] = "capability-unavailable"
            _json_write(e2e_dir / "manifest.json", manifest)
            case = {
                "id": "case-cap", "entry_skill": "e2e-service", "mode": "generate", "prompt": "test",
                "fixture": "login-journey", "surface": "service",
                "expect": {"manifest_status": "capability-unavailable"},
            }
            _json_write(workspace / "case.json", case)
            diagnostics = evaluate(workspace / "case.json", workspace)
            self.assertIn("missing capability-unavailable framework detection evidence", diagnostics)


class ServiceFixtureContractTests(unittest.TestCase):
    def test_service_fixture_has_required_files(self):
        fixture = ROOT / "evals" / "fixtures" / "service-contract"
        self.assertTrue((fixture / "package.json").exists())
        self.assertTrue((fixture / "src/server.js").exists())
        self.assertTrue((fixture / "contracts/http-api.json").exists())
        self.assertTrue((fixture / "contracts/schema.graphql").exists())
        self.assertTrue((fixture / "contracts/service.proto").exists())
        self.assertTrue((fixture / "contracts/websocket-messages.json").exists())
        self.assertTrue((fixture / "contracts/queue-contract.json").exists())
        self.assertTrue((fixture / "contracts/stream-contract.json").exists())
        self.assertTrue((fixture / "test-support/http-client.js").exists())
        self.assertTrue((fixture / "test-support/graphql-client.js").exists())
        self.assertTrue((fixture / "test-support/grpc-client.js").exists())
        self.assertTrue((fixture / "test-support/websocket-client.js").exists())
        self.assertTrue((fixture / "test-support/queue-client.js").exists())
        self.assertTrue((fixture / "test-support/stream-client.js").exists())
        self.assertTrue((fixture / "tests/fixture-contract.test.js").exists())

    def test_service_fixture_package_json(self):
        pkg = json.loads((ROOT / "evals/fixtures/service-contract/package.json").read_text())
        self.assertEqual(pkg["name"], "service-contract-fixture")
        self.assertEqual(pkg["type"], "module")
        self.assertIn("start", pkg.get("scripts", {}))
        self.assertIn("test", pkg.get("scripts", {}))

    def test_service_fixture_server_exposes_health(self):
        """Verify server exposes /health with expected response."""
        import http.client
        conn = http.client.HTTPConnection("127.0.0.1", 43170, timeout=5)
        try:
            conn.request("GET", "/health")
            resp = conn.getresponse()
            self.assertEqual(resp.status, 200)
            body = json.loads(resp.read())
            self.assertEqual(body["status"], "ok")
        finally:
            conn.close()


if __name__ == "__main__":
    unittest.main()
