import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from protocol.v2.e2e_protocol import (
    ExtensionRegistry,
    ExtensionSupport,
    ProtocolError,
    extension_issues,
    initialize_manifest,
    new_manifest,
    save_manifest,
    validate_manifest,
)


def web_extension(data):
    return {
        "id": "extension-web", "namespace": "e2e.web", "version": "1.0",
        "owner": "e2e-web", "data": data,
    }


def validate_service_data(data):
    if not isinstance(data, dict) or data.get("driver") not in {"rest", "grpc"}:
        return ["extensions[e2e.service].data.driver is invalid"]
    return []


class ProtocolV2ExtensionTests(unittest.TestCase):
    def setUp(self):
        self.manifest = new_manifest("/workspace/app", timestamp="2026-07-21T00:00:00Z")
        self.manifest["extensions"] = [{
            "id": "extension-service",
            "namespace": "e2e.service",
            "version": "1.1",
            "owner": "e2e-service",
            "data": {"driver": "rest"},
        }]

    def test_known_compatible_extension_uses_its_typed_validator(self):
        registry = ExtensionRegistry()
        registry.register(ExtensionSupport("e2e.service", "1.0", "1.9", validate_service_data))
        self.assertEqual(extension_issues(self.manifest, registry), [])
        self.assertEqual(validate_manifest(self.manifest, registry), [])

        self.manifest["extensions"][0]["data"]["driver"] = "database"
        self.assertIn(
            "extensions[e2e.service].data.driver is invalid",
            validate_manifest(self.manifest, registry),
        )

    def test_unknown_namespace_is_capability_unavailable_not_invalid(self):
        registry = ExtensionRegistry()
        before = copy.deepcopy(self.manifest["extensions"][0])

        self.assertEqual(extension_issues(self.manifest, registry), [{
            "extension_id": "extension-service",
            "namespace": "e2e.service",
            "version": "1.1",
            "status": "capability-unavailable",
        }])
        self.assertEqual(validate_manifest(self.manifest, registry), [])
        self.assertEqual(self.manifest["extensions"][0], before)

    def test_known_namespace_outside_range_is_extension_incompatible(self):
        registry = ExtensionRegistry()
        registry.register(ExtensionSupport("e2e.service", "2.0", "2.9", validate_service_data))
        self.assertEqual(extension_issues(self.manifest, registry)[0]["status"], "extension-incompatible")
        self.assertEqual(validate_manifest(self.manifest, registry), [])

    def test_duplicate_namespace_range_is_rejected(self):
        registry = ExtensionRegistry()
        support = ExtensionSupport("e2e.service", "1.0", "1.9", validate_service_data)
        registry.register(support)
        with self.assertRaisesRegex(ValueError, "overlapping extension support"):
            registry.register(support)

    def test_malformed_extension_version_reports_incompatible_without_crashing(self):
        registry = ExtensionRegistry()
        registry.register(ExtensionSupport("e2e.service", "1.0", "1.9", validate_service_data))
        self.manifest["extensions"][0]["version"] = "bad"
        self.assertEqual(extension_issues(self.manifest, registry)[0]["status"], "extension-incompatible")
        self.assertIn("extensions[0].version is invalid", validate_manifest(self.manifest, registry))

    def test_unknown_extension_cannot_be_changed_or_removed_during_save(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "manifest.json"
            saved = save_manifest(path, self.manifest, None, timestamp="2026-07-21T00:00:01Z")
            changed = json.loads(json.dumps(saved))
            changed["extensions"][0]["data"]["driver"] = "grpc"
            with self.assertRaisesRegex(ProtocolError, "unknown extension changed: extension-service"):
                save_manifest(path, changed, 1)
            removed = json.loads(json.dumps(saved))
            removed["extensions"] = []
            with self.assertRaisesRegex(ProtocolError, "unknown extension changed: extension-service"):
                save_manifest(path, removed, 1)

    def test_registered_extension_may_change_within_its_supported_range(self):
        registry = ExtensionRegistry()
        registry.register(ExtensionSupport("e2e.service", "1.0", "1.9", validate_service_data))
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "manifest.json"
            saved = save_manifest(path, self.manifest, None, registry, "2026-07-21T00:00:01Z")
            changed = json.loads(json.dumps(saved))
            changed["extensions"][0]["data"]["driver"] = "grpc"
            updated = save_manifest(path, changed, 1, registry, "2026-07-21T00:00:02Z")
            self.assertEqual(updated["extensions"][0]["data"]["driver"], "grpc")

    def test_bundled_web_schema_is_used_without_a_registry_argument(self):
        manifest = new_manifest("/workspace/app", timestamp="2026-07-24T00:00:00Z")
        manifest["extensions"] = [web_extension({})]
        self.assertIn("extension data missing required property: driver", validate_manifest(manifest))

    def test_bundled_web_extension_can_change_across_revisions(self):
        manifest = new_manifest("/workspace/app", timestamp="2026-07-24T00:00:00Z")
        manifest["extensions"] = [web_extension({"driver": None, "project": {}, "target": {}})]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "manifest.json"
            saved = save_manifest(path, manifest, None, timestamp="2026-07-24T00:00:01Z")
            changed = copy.deepcopy(saved)
            changed["extensions"][0]["data"]["driver"] = "playwright"
            updated = save_manifest(path, changed, 1, timestamp="2026-07-24T00:00:02Z")
            self.assertEqual(updated["extensions"][0]["data"]["driver"], "playwright")

    def test_bundled_registry_reports_unsupported_web_version(self):
        manifest = new_manifest("/workspace/app", timestamp="2026-07-24T00:00:00Z")
        manifest["extensions"] = [web_extension({"driver": None, "project": {}, "target": {}})]
        manifest["extensions"][0]["version"] = "1.1"
        self.assertEqual(extension_issues(manifest)[0]["status"], "extension-incompatible")

    def test_explicit_empty_registry_still_models_an_uninstalled_capability(self):
        manifest = new_manifest("/workspace/app", timestamp="2026-07-24T00:00:00Z")
        manifest["extensions"] = [web_extension({"driver": None, "project": {}, "target": {}})]
        self.assertEqual(extension_issues(manifest, ExtensionRegistry())[0]["status"], "capability-unavailable")

    def test_catalog_failure_precedes_manifest_mutation(self):
        manifest = new_manifest("/workspace/app", timestamp="2026-07-24T00:00:00Z")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / "manifest.json"
            saved = save_manifest(path, manifest, None, timestamp="2026-07-24T00:00:01Z")
            before = path.read_bytes()
            candidate = copy.deepcopy(saved)
            broken_catalog = root / "catalog.json"
            broken_catalog.write_text("{}", encoding="utf-8")
            with mock.patch(
                "protocol.v2.e2e_protocol._default_catalog_path",
                return_value=broken_catalog,
            ):
                with self.assertRaisesRegex(ProtocolError, "extension catalog unavailable"):
                    save_manifest(path, candidate, 1, timestamp="2026-07-24T00:00:02Z")
            self.assertEqual(path.read_bytes(), before)
            uninitialized = root / "new-manifest.json"
            with mock.patch(
                "protocol.v2.e2e_protocol._default_catalog_path",
                return_value=broken_catalog,
            ):
                with self.assertRaisesRegex(ProtocolError, "extension catalog unavailable"):
                    initialize_manifest(uninitialized, str(root))
            self.assertFalse(uninitialized.exists())
