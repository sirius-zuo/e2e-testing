import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DESKTOP = ROOT / "skills/e2e-desktop"


class DesktopSkillContractTests(unittest.TestCase):
    def test_public_contract(self):
        text = (DESKTOP / "SKILL.md").read_text()
        for required in (
            "name: e2e-desktop", "e2e.desktop@1.0", "Default to `generate`",
            "Appium Mac2", "NovaWindows", "WebdriverIO Electron",
            "dedicated OS user session or ephemeral VM", "generated-unverified",
            "Never modify application source",
        ):
            self.assertIn(required, text)
        self.assertLess(len(text.splitlines()), 500)

    def test_orchestrator_routes_installed_desktop_apps(self):
        text = (ROOT / "skills/e2e-testing/SKILL.md").read_text()
        self.assertIn("confirmed installed desktop application only → `e2e-desktop`", text)
        self.assertIn("Electron application", text)
        self.assertIn("browser-rendered site", text)

    def test_driver_and_platform_contracts(self):
        macos = (DESKTOP / "references/macos.md").read_text()
        windows = (DESKTOP / "references/windows.md").read_text()
        electron = (DESKTOP / "references/electron.md").read_text()
        self.assertIn("Appium Mac2", macos)
        self.assertIn("serialized", macos)
        self.assertIn("NovaWindows", windows)
        self.assertIn("WinAppDriver", windows)
        self.assertIn("capability-gated", windows)
        self.assertIn("WebdriverIO Electron", electron)
        self.assertIn("mocked", electron)
        self.assertIn("cannot satisfy", electron)

    def test_lifecycle_and_safety_contracts(self):
        lifecycle = (DESKTOP / "references/lifecycle.md").read_text().lower()
        safety = (DESKTOP / "references/safety.md").read_text().lower()
        for operation in ("install", "launch", "activate", "minimize", "restore", "update", "reset", "uninstall", "teardown"):
            self.assertIn(operation, lifecycle)
        for required in ("dedicated", "interactive", "unlocked", "connected", "isolated", "general-purpose", "production"):
            self.assertIn(required, safety)


if __name__ == "__main__":
    unittest.main()
