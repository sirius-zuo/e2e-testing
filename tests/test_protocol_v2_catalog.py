import copy
import json
import math
import os
import tempfile
import unittest
from pathlib import Path

from protocol.v2.extension_catalog import (
    ExtensionCatalogError,
    compile_schema,
    load_extension_registry,
)


ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "protocol/v2/extensions/catalog.json"


class PortableSchemaDialectTests(unittest.TestCase):
    def _service_data(self, **overrides):
        value = {
            name: {"interfaces": []}
            for name in ("http", "graphql", "grpc", "websocket", "queue", "stream")
        }
        value.update(overrides)
        return value

    def test_service_schema_accepts_complete_data_and_rejects_missing_or_extra_fields(self):
        schema = json.loads((ROOT / "protocol/v2/extensions/service.schema.json").read_text())
        self.assertEqual(schema["$id"], "urn:e2e-testing:extension:service:1.0")
        self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")
        validate = compile_schema(schema, "draft2020-12-subset-1", "service.schema.json")
        service = {
            name: {"interfaces": ["contract-ref"]}
            for name in ("http", "graphql", "grpc", "websocket", "queue", "stream")
        }
        for name in ("http", "graphql", "grpc", "websocket", "queue", "stream"):
            common = {"interface_id": "iface-1", "source_refs": ["src.md"], "config_refs": ["cfg.md"],
                      "client_ref": "client", "command_ref": "cmd", "contract_refs": ["ct.md"]}
            service[name].update(common)
        service["http"].update({"request_conventions": ["rest-req"], "response_conventions": ["rest-resp"]})
        service["graphql"].update({"schema_refs": ["schema.graphql"], "operation_refs": ["ops.graphql"]})
        service["grpc"].update({"descriptor_refs": ["svc.proto"], "service_method_refs": ["methods.proto"]})
        service["websocket"].update({"handshake_refs": ["ws.md"], "subprotocols": ["e2e-v1"], "message_contract_refs": ["msg.md"]})
        service["queue"].update({"destination_ref": "q-ref", "role": "consume", "acknowledgement_policy": "manual", "delivery_contract_refs": ["del.md"]})
        service["stream"].update({"channel_ref": "ch-ref", "role": "produce", "cursor_policy": "auto", "event_contract_refs": ["evt.md"]})
        self.assertEqual(validate(service), [])
        missing = self._service_data()
        missing.pop("grpc")
        self.assertIn("extension data missing required property: grpc", validate(missing))
        extra = self._service_data()
        extra["http"]["unexpected_field"] = True
        self.assertIn("extension data.http contains unexpected property: unexpected_field", validate(extra))

    def test_web_schema_accepts_complete_data_and_rejects_missing_or_extra_fields(self):
        schema = json.loads((ROOT / "protocol/v2/extensions/web.schema.json").read_text())
        validate = compile_schema(schema, "draft2020-12-subset-1", "web.schema.json")
        self.assertEqual(validate({"driver": "playwright", "project": {}, "target": {}}), [])
        self.assertIn("extension data missing required property: target", validate({"driver": None, "project": {}}))
        self.assertIn(
            "extension data contains unexpected property: private_state",
            validate({"driver": None, "project": {}, "target": {}, "private_state": {}}),
        )

    def test_dialect_rejects_unknown_keywords_and_boolean_number_confusion(self):
        with self.assertRaisesRegex(ExtensionCatalogError, "unsupported schema keyword: oneOf"):
            compile_schema({"type": "object", "oneOf": []}, "draft2020-12-subset-1", "bad.json")
        validate = compile_schema({"type": "integer"}, "draft2020-12-subset-1", "integer.json")
        self.assertTrue(validate(True))
        self.assertEqual(validate(2), [])
        enum_validate = compile_schema({"enum": [1]}, "draft2020-12-subset-1", "enum.json")
        self.assertTrue(enum_validate(True), "JSON true must not equal JSON number 1")

    def test_dialect_rejects_non_finite_numeric_bounds(self):
        for value in (math.nan, math.inf, -math.inf):
            with self.subTest(value=value), self.assertRaisesRegex(
                ExtensionCatalogError, "schema minimum is invalid",
            ):
                compile_schema(
                    {"type": "number", "minimum": value},
                    "draft2020-12-subset-1",
                    "number.json",
                )


class ExtensionCatalogTests(unittest.TestCase):
    def _write_catalog(self, directory: Path, catalog: dict, schema: dict | None = None) -> Path:
        path = directory / "catalog.json"
        path.write_text(json.dumps(catalog), encoding="utf-8")
        if schema is not None:
            (directory / "surface.schema.json").write_text(json.dumps(schema), encoding="utf-8")
        return path

    def test_canonical_catalog_registers_exact_web_support_and_owner(self):
        registry = load_extension_registry(CATALOG)
        self.assertEqual(registry.resolve("e2e.web", "1.0")[0], "supported")
        self.assertEqual(registry.resolve("e2e.web", "1.1")[0], "extension-incompatible")
        self.assertEqual(registry.resolve("e2e.service", "1.0")[0], "supported")
        self.assertEqual(registry.resolve("e2e.service", "1.1")[0], "extension-incompatible")
        extension = {
            "namespace": "e2e.web", "version": "1.0", "owner": "wrong-owner",
            "data": {"driver": "playwright", "project": {}, "target": {}},
        }
        self.assertIn("extension owner must be e2e-web", registry.validate(extension))

    def test_catalog_rejects_overlapping_ranges_and_unsafe_paths(self):
        base = {
            "catalog_version": "1.0",
            "extensions": [{
                "namespace": "e2e.web", "owner": "e2e-web",
                "versions": [{
                    "minimum": "1.0", "maximum": "1.1",
                    "dialect": "draft2020-12-subset-1", "schema": "surface.schema.json",
                }, {
                    "minimum": "1.1", "maximum": "1.2",
                    "dialect": "draft2020-12-subset-1", "schema": "surface.schema.json",
                }],
            }],
        }
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = self._write_catalog(root, base, {"type": "object"})
            with self.assertRaisesRegex(ExtensionCatalogError, "overlapping extension support: e2e.web"):
                load_extension_registry(path)

            unsafe = copy.deepcopy(base)
            unsafe["extensions"][0]["versions"] = [{
                "minimum": "1.0", "maximum": "1.0",
                "dialect": "draft2020-12-subset-1", "schema": "../outside.json",
            }]
            path = self._write_catalog(root, unsafe)
            with self.assertRaisesRegex(ExtensionCatalogError, "schema path escapes extension directory"):
                load_extension_registry(path)

    def test_catalog_rejects_bad_versions_dialects_and_missing_schemas(self):
        valid = {
            "catalog_version": "1.0",
            "extensions": [{
                "namespace": "e2e.web", "owner": "e2e-web",
                "versions": [{
                    "minimum": "1.0", "maximum": "1.0",
                    "dialect": "draft2020-12-subset-1", "schema": "surface.schema.json",
                }],
            }],
        }
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.assertRaisesRegex(ExtensionCatalogError, "invalid extension catalog"):
                load_extension_registry(root / "missing-catalog.json")
            for label, mutate, diagnostic in (
                ("catalog-version", lambda item: item.update(catalog_version="9.0"), "unsupported catalog version"),
                ("empty-versions", lambda item: item["extensions"][0].update(versions=[]), "catalog versions must be non-empty"),
                ("reversed", lambda item: item["extensions"][0]["versions"][0].update(minimum="2.0", maximum="1.0"), "minimum exceeds maximum"),
                ("dialect", lambda item: item["extensions"][0]["versions"][0].update(dialect="unknown"), "unsupported runtime schema dialect"),
                ("absolute", lambda item: item["extensions"][0]["versions"][0].update(schema=str(root / "surface.schema.json")), "schema path must be relative"),
            ):
                with self.subTest(label=label):
                    candidate = copy.deepcopy(valid)
                    mutate(candidate)
                    path = self._write_catalog(root, candidate, {"type": "object"})
                    with self.assertRaisesRegex(ExtensionCatalogError, diagnostic):
                        load_extension_registry(path)
            path = self._write_catalog(root, valid)
            (root / "surface.schema.json").unlink()
            with self.assertRaisesRegex(ExtensionCatalogError, "invalid extension schema"):
                load_extension_registry(path)
            path.write_text("{", encoding="utf-8")
            with self.assertRaisesRegex(ExtensionCatalogError, "invalid extension catalog"):
                load_extension_registry(path)

    def test_catalog_rejects_non_standard_json_numbers(self):
        catalog = {
            "catalog_version": "1.0",
            "extensions": [{
                "namespace": "e2e.web", "owner": "e2e-web",
                "versions": [{
                    "minimum": "1.0", "maximum": "1.0",
                    "dialect": "draft2020-12-subset-1", "schema": "surface.schema.json",
                }],
            }],
        }
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = self._write_catalog(root, catalog)
            (root / "surface.schema.json").write_text(
                '{"type":"number","minimum":NaN}', encoding="utf-8",
            )
            with self.assertRaisesRegex(ExtensionCatalogError, "invalid extension schema"):
                load_extension_registry(path)

    def test_catalog_normalizes_invalid_schema_path_errors(self):
        catalog = {
            "catalog_version": "1.0",
            "extensions": [{
                "namespace": "e2e.web", "owner": "e2e-web",
                "versions": [{
                    "minimum": "1.0", "maximum": "1.0",
                    "dialect": "draft2020-12-subset-1", "schema": "bad\0.schema.json",
                }],
            }],
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write_catalog(Path(tmp), catalog)
            with self.assertRaisesRegex(ExtensionCatalogError, "invalid catalog schema path"):
                load_extension_registry(path)

    @unittest.skipIf(os.name == "nt", "symlink creation is not portable on Windows CI")
    def test_catalog_rejects_symlink_escape(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            outside = root.parent / f"{root.name}-outside.json"
            outside.write_text('{"type":"object"}', encoding="utf-8")
            try:
                (root / "surface.schema.json").symlink_to(outside)
                catalog = {
                    "catalog_version": "1.0",
                    "extensions": [{
                        "namespace": "e2e.web", "owner": "e2e-web",
                        "versions": [{
                            "minimum": "1.0", "maximum": "1.0",
                            "dialect": "draft2020-12-subset-1", "schema": "surface.schema.json",
                        }],
                    }],
                }
                path = self._write_catalog(root, catalog)
                with self.assertRaisesRegex(ExtensionCatalogError, "schema path escapes extension directory"):
                    load_extension_registry(path)
            finally:
                outside.unlink(missing_ok=True)
