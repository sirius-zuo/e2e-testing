import importlib.util
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGETS = [
    ROOT / "skills/e2e-testing",
    ROOT / "skills/e2e-web",
    ROOT / "skills/e2e-service",
    ROOT / "skills/e2e-mobile",
    ROOT / "skills/e2e-desktop",
]
EXPECTED_NAMESPACES = {
    "e2e-testing": {"e2e.web", "e2e.service", "e2e.mobile", "e2e.desktop"},
    "e2e-web": {"e2e.web"},
    "e2e-service": {"e2e.service"},
    "e2e-mobile": {"e2e.mobile"},
    "e2e-desktop": {"e2e.desktop"},
}


class PackagingTests(unittest.TestCase):
    def test_each_bundle_has_filtered_catalog_and_referenced_schemas(self):
        canonical = json.loads((ROOT / "protocol/v2/extensions/catalog.json").read_text())
        for target in TARGETS:
            bundled = json.loads((target / "references/extensions/catalog.json").read_text())
            namespaces = {entry["namespace"] for entry in bundled["extensions"]}
            self.assertEqual(namespaces, EXPECTED_NAMESPACES[target.name])
            expected = [
                entry for entry in canonical["extensions"]
                if entry["namespace"] in EXPECTED_NAMESPACES[target.name]
            ]
            self.assertEqual(bundled, {"catalog_version": "1.0", "extensions": expected})
            for entry in bundled["extensions"]:
                for support in entry["versions"]:
                    relative = Path(support["schema"])
                    self.assertEqual(
                        (target / "references/extensions" / relative).read_bytes(),
                        (ROOT / "protocol/v2/extensions" / relative).read_bytes(),
                    )

    def test_each_bundle_imports_runtime_with_only_release_owned_siblings(self):
        for target in TARGETS:
            script = target / "scripts/e2e_protocol.py"
            spec = importlib.util.spec_from_file_location(f"portable_{target.name.replace('-', '_')}", script)
            self.assertIsNotNone(spec)
            module = importlib.util.module_from_spec(spec)
            sys.modules[spec.name] = module
            spec.loader.exec_module(module)
            manifest = module.new_manifest("/workspace/app", timestamp="2026-07-24T00:00:00Z")
            if target.name == "e2e-service":
                manifest["extensions"] = [{
                    "id": "extension-service", "namespace": "e2e.service", "version": "1.0",
                    "owner": "e2e-service", "data": {},
                }]
                self.assertIn("extension data missing required property: http", module.validate_manifest(manifest))
            elif target.name == "e2e-mobile":
                manifest["extensions"] = [{
                    "id": "extension-mobile", "namespace": "e2e.mobile", "version": "1.0",
                    "owner": "e2e-mobile", "data": {},
                }]
                self.assertIn(
                    "extension data missing required property: application",
                    module.validate_manifest(manifest),
                )
            elif target.name == "e2e-desktop":
                manifest["extensions"] = [{
                    "id": "extension-desktop", "namespace": "e2e.desktop", "version": "1.0",
                    "owner": "e2e-desktop", "data": {},
                }]
                self.assertIn(
                    "extension data missing required property: applications",
                    module.validate_manifest(manifest),
                )
            else:
                manifest["extensions"] = [{
                    "id": "extension-web", "namespace": "e2e.web", "version": "1.0",
                    "owner": "e2e-web", "data": {},
                }]
                self.assertIn("extension data missing required property: driver", module.validate_manifest(manifest))

    def test_each_bundled_utility_needs_no_site_packages(self):
        for target in TARGETS:
            result = subprocess.run(
                [sys.executable, "-I", "-S", str(target / "scripts/e2e_protocol.py"), "--help"],
                text=True, capture_output=True, check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("transition", result.stdout)

    def test_old_web_skill_directory_is_absent(self):
        self.assertFalse((ROOT / "skills/e2e-web-playwright").exists())


if __name__ == "__main__":
    unittest.main()
