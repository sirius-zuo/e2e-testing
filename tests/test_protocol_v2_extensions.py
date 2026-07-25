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


def service_data(**overrides):
    value = {
        name: {"interfaces": []}
        for name in ("http", "graphql", "grpc", "websocket", "queue", "stream")
    }
    value.update(overrides)
    return value


def service_extension(data):
    return {
        "id": "extension-service",
        "namespace": "e2e.service",
        "version": "1.0",
        "owner": "e2e-service",
        "data": data,
    }


def validate_service_data(data):
    if not isinstance(data, dict) or data.get("driver") not in {"rest", "grpc"}:
        return ["extensions[e2e.service].data.driver is invalid"]
    return []


def web_extension(data):
    return {
        "id": "extension-web", "namespace": "e2e.web", "version": "1.0",
        "owner": "e2e-web", "data": data,
    }


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

    def test_service_extension_validates_complete_data(self):
        manifest = new_manifest("/workspace/app", timestamp="2026-07-25T00:00:00Z")
        data = service_data()
        for name in ("http", "graphql", "grpc", "websocket", "queue", "stream"):
            data[name].update({
                "interface_id": "iface-1", "source_refs": ["src.md"],
                "config_refs": ["cfg.md"], "client_ref": "client", "command_ref": "cmd",
                "contract_refs": ["ct.md"],
            })
        data["http"].update({"request_conventions": ["rest-req"], "response_conventions": ["rest-resp"]})
        data["graphql"].update({"schema_refs": ["schema.graphql"], "operation_refs": ["ops.graphql"]})
        data["grpc"].update({"descriptor_refs": ["svc.proto"], "service_method_refs": ["methods.proto"]})
        data["websocket"].update({"handshake_refs": ["ws.md"], "subprotocols": ["e2e-v1"], "message_contract_refs": ["msg.md"]})
        data["queue"].update({"destination_ref": "q-ref", "role": "consume", "acknowledgement_policy": "manual", "delivery_contract_refs": ["del.md"]})
        data["stream"].update({"channel_ref": "ch-ref", "role": "produce", "cursor_policy": "auto", "event_contract_refs": ["evt.md"]})
        manifest["extensions"] = [service_extension(data)]
        self.assertEqual(validate_manifest(manifest), [])

    def test_service_extension_rejects_missing_required_module(self):
        manifest = new_manifest("/workspace/app", timestamp="2026-07-25T00:00:00Z")
        missing = service_data()
        missing.pop("grpc")
        manifest["extensions"] = [service_extension(missing)]
        self.assertIn("extension data missing required property: grpc", validate_manifest(manifest))

    def test_service_extension_rejects_unknown_property_in_module(self):
        manifest = new_manifest("/workspace/app", timestamp="2026-07-25T00:00:00Z")
        data = service_data()
        data["http"]["unexpected_field"] = True
        manifest["extensions"] = [service_extension(data)]
        self.assertIn("extension data.http contains unexpected property: unexpected_field", validate_manifest(manifest))

    def test_service_extension_requires_common_fields(self):
        manifest = new_manifest("/workspace/app", timestamp="2026-07-25T00:00:00Z")
        data = service_data()
        for name in ("http", "graphql", "grpc", "websocket", "queue", "stream"):
            data[name].update({
                "interfaces": ["i1"], "interface_id": 42, "source_refs": [],
                "config_refs": [], "client_ref": "c", "command_ref": "cmd",
                "contract_refs": [],
            })
            data[name].pop("request_conventions", None)
            data[name].pop("response_conventions", None)
            data[name].pop("schema_refs", None)
            data[name].pop("operation_refs", None)
            data[name].pop("descriptor_refs", None)
            data[name].pop("service_method_refs", None)
            data[name].pop("handshake_refs", None)
            data[name].pop("subprotocols", None)
            data[name].pop("message_contract_refs", None)
            data[name].pop("destination_ref", None)
            data[name].pop("role", None)
            data[name].pop("acknowledgement_policy", None)
            data[name].pop("delivery_contract_refs", None)
            data[name].pop("channel_ref", None)
            data[name].pop("cursor_policy", None)
            data[name].pop("event_contract_refs", None)
        manifest["extensions"] = [service_extension(data)]
        errors = validate_manifest(manifest)
        self.assertIn("extension data.http.interface_id has invalid type", errors)

    def test_service_extension_with_protocol_specific_fields(self):
        manifest = new_manifest("/workspace/app", timestamp="2026-07-25T00:00:00Z")
        data = service_data()
        for name in ("http", "graphql", "grpc", "websocket", "queue", "stream"):
            data[name].update({
                "interface_id": "iface-1", "source_refs": ["src.md"],
                "config_refs": ["cfg.md"], "client_ref": "client", "command_ref": "cmd",
                "contract_refs": ["ct.md"],
            })
        data["http"].update({
            "request_conventions": ["rest-conventions"], "response_conventions": ["rest-response"]
        })
        data["graphql"].update({
            "schema_refs": ["schema.graphql"], "operation_refs": ["ops.graphql"]
        })
        data["grpc"].update({
            "descriptor_refs": ["svc.proto"], "service_method_refs": ["methods.proto"]
        })
        data["websocket"].update({
            "handshake_refs": ["ws.md"], "subprotocols": ["e2e-v1"],
            "message_contract_refs": ["msg-contract.md"]
        })
        data["queue"].update({
            "destination_ref": "q-ref", "role": "consume",
            "acknowledgement_policy": "manual", "delivery_contract_refs": ["del.md"]
        })
        data["stream"].update({
            "channel_ref": "ch-ref", "role": "consume",
            "cursor_policy": "auto", "event_contract_refs": ["evt.md"]
        })
        manifest["extensions"] = [service_extension(data)]
        self.assertEqual(validate_manifest(manifest), [])

    def test_service_extension_rejects_invalid_queue_role(self):
        manifest = new_manifest("/workspace/app", timestamp="2026-07-25T00:00:00Z")
        data = service_data()
        for name in ("http", "graphql", "grpc", "websocket", "queue", "stream"):
            data[name].update({
                "interface_id": "i1", "source_refs": [], "config_refs": [],
                "client_ref": "c", "command_ref": "cmd", "contract_refs": [],
            })
        data["queue"].update({"role": "invalid"})
        manifest["extensions"] = [service_extension(data)]
        errors = validate_manifest(manifest)
        self.assertTrue(any("queue.role is not an allowed value" in e for e in errors))

    def test_service_extension_rejects_invalid_stream_role(self):
        manifest = new_manifest("/workspace/app", timestamp="2026-07-25T00:00:00Z")
        data = service_data()
        for name in ("http", "graphql", "grpc", "websocket", "queue", "stream"):
            data[name].update({
                "interface_id": "i1", "source_refs": [], "config_refs": [],
                "client_ref": "c", "command_ref": "cmd", "contract_refs": [],
            })
        data["stream"].update({"role": "invalid"})
        manifest["extensions"] = [service_extension(data)]
        errors = validate_manifest(manifest)
        self.assertTrue(any("stream.role is not an allowed value" in e for e in errors))
