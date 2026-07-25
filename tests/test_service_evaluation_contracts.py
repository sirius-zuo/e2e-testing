"""Service-surface evaluation contract tests."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from evals.evaluate_result import evaluate
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
            # Write case without surface (defaults to web)
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
