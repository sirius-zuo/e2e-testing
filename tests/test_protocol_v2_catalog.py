import copy
import json
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
        self.assertEqual(registry.resolve("e2e.service", "1.0")[0], "capability-unavailable")
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
