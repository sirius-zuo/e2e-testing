import copy
import unittest

from protocol.v2.e2e_protocol import (
    ExtensionRegistry,
    ExtensionSupport,
    extension_issues,
    new_manifest,
    validate_manifest,
)


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
