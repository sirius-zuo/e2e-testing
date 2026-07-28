"""Contract tests for the e2e-mobile portable skill bundle."""

from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MOBILE = ROOT / "skills/e2e-mobile"


class MobileSkillContractTests(unittest.TestCase):
    def test_mobile_skill_public_contract(self):
        text = (MOBILE / "SKILL.md").read_text()
        self.assertIn("name: e2e-mobile", text)
        self.assertIn("default to `generate`", text)
        self.assertIn("`plan`, `generate`, `verify`, or `repair`", text)
        self.assertIn("e2e.mobile@1.0", text)
        self.assertIn("one logical system and one installed application", text)
        self.assertIn("Appium", text)
        self.assertIn("Maestro", text)
        self.assertIn("generated-unverified", text)
        self.assertIn("Never modify application source", text)
        self.assertLess(len(text.splitlines()), 500)

    def test_orchestrator_routes_installed_apps(self):
        text = (ROOT / "skills/e2e-testing/SKILL.md").read_text()
        self.assertIn("confirmed installed mobile application only → `e2e-mobile`", text)
        self.assertIn("`e2e-mobile`", text)
        self.assertIn("embedded WebView", text)
        self.assertIn("standalone mobile-browser", text)
        self.assertIn("one primary surface", text)

    def test_shared_workflow_is_driver_neutral(self):
        text = (MOBILE / "references/workflow.md").read_text()
        self.assertIn("read-only mobile discovery", text)
        self.assertLess(text.index("read-only mobile discovery"), text.index("validate or initialize Protocol 2"))
        self.assertIn("existing Appium or Maestro", text)
        self.assertIn("never migrate", text)
        self.assertIn("host-level prerequisite", text)
        self.assertIn("selected check IDs", text)
        self.assertIn("cleanup failure blocks completion", text)

    def test_driver_contracts(self):
        appium = (MOBILE / "references/appium.md").read_text()
        maestro = (MOBILE / "references/maestro.md").read_text()
        for text in (appium, maestro):
            self.assertIn("preserve existing", text)
            self.assertIn("repository-local bootstrap", text)
            self.assertIn("selected check IDs", text)
            self.assertIn("capability-unavailable", text)
        self.assertIn("XCUITest", appium)
        self.assertIn("UiAutomator2", appium)
        self.assertIn("remote Appium endpoint", appium)
        self.assertIn("accessibility", maestro)
        self.assertIn("never claim real-device support from the driver name", maestro)

    def test_platform_and_lifecycle_contracts(self):
        ios = (MOBILE / "references/ios.md").read_text()
        android = (MOBILE / "references/android.md").read_text()
        lifecycle = (MOBILE / "references/lifecycle.md").read_text()
        self.assertIn("macOS", ios)
        self.assertIn("whole-device wipe", ios)
        self.assertIn("Android SDK", android)
        self.assertIn("whole-device wipe", android)
        for operation in (
            "install", "launch", "reset", "background", "foreground",
            "deep link", "permission", "upgrade", "cleanup",
        ):
            self.assertIn(operation, lifecycle.lower())
        self.assertIn("prior", lifecycle)
        self.assertIn("candidate", lifecycle)
        self.assertIn("not automatically retried", lifecycle)

    def test_mobile_safety_and_evidence_contracts(self):
        safety = (MOBILE / "references/safety.md").read_text()
        evidence = (MOBILE / "references/evidence.md").read_text()
        for required in (
            "app-scoped reset", "dedicated device", "synthetic",
            "production", "non-destructive observation", "categorically prohibited",
        ):
            self.assertIn(required, safety)
        self.assertIn("network capture is disabled by default", evidence)
        self.assertIn("diagnostic", evidence)
        self.assertIn("fixture", evidence)
        for field in (
            "driver", "driver_version", "platform", "os_version", "target_kind",
            "application_build_ref", "target_reference", "target_tier",
            "evidence_origin",
        ):
            self.assertIn(f"`{field}`", evidence)


if __name__ == "__main__":
    unittest.main()
