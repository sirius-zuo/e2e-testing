# Protocol 2 Extension Catalog Stabilization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Protocol 2 surface extensions automatically typed, safely mutable, and portable through a standard-library catalog, while correcting the active web evidence vocabulary.

**Architecture:** A new surface-neutral `extension_catalog.py` owns catalog parsing, version registration, and the named `draft2020-12-subset-1` validator. The existing `e2e_protocol.py` remains the public façade and automatically resolves the single release-native catalog unless a caller explicitly supplies a registry. The sync tool projects the canonical catalog into independently installable skill bundles.

**Tech Stack:** Python 3 standard library, JSON, `unittest`, portable Agent Skill Markdown.

## Global Constraints

- Work only in `/Users/jinzuo/projects/skills/e2e-testing`; never read from, write to, or modify `generate-e2e` as part of implementation.
- Before implementation, use `superpowers:using-git-worktrees` and create an isolated `codex/` branch from the current committed baseline.
- At execution start, run `git rev-parse HEAD`, record that exact SHA as `BASE_SHA` in the implementation notes, and substitute that literal SHA in the protected-file comparison in Task 5.
- Use `superpowers:test-driven-development` for every runtime or behavioral change: add one failing test, run it and confirm the expected failure, implement the minimum, then rerun.
- Use `superpowers:writing-skills` for the `e2e-web` reference edit: run the application scenario against the current guidance before editing it, then rerun the same scenario with corrected guidance.
- The runtime and bundled utilities must use only the Python standard library; do not add `jsonschema`, package manifests, dependency installation, or target-repository dependencies.
- Do not change the Protocol 2 manifest schema or any existing core-field meaning.
- Do not add service, mobile, desktop, composition, or resilience recognition or routing.
- Do not restore Protocol 1 runtime compatibility or active migration. Exact Protocol 1 project manifests are replaced with fresh Protocol 2 state only through the existing explicit flag.
- Keep `protocol/v1/`, `protocol/v2/migrate_v1.py`, migration tests, and historical specs/plans unchanged.
- Unknown extensions remain valid, preserved, and immutable unless an explicitly installed registry supports them.
- Do not run paid Codex or Claude host evaluations without separate authorization.
- Run `superpowers:requesting-code-review` after the implementation and `superpowers:verification-before-completion` before any completion claim.

---

### Task 1: Add the portable schema dialect and catalog loader

**Files:**
- Create: `protocol/v2/extension_catalog.py`
- Create: `protocol/v2/extensions/catalog.json`
- Create: `tests/test_protocol_v2_catalog.py`

**Interfaces:**
- Consumes: release-owned catalog JSON and extension schemas.
- Produces: `ExtensionCatalogError`, `ExtensionSupport`, `ExtensionRegistry`, `compile_schema(schema, dialect, source)`, and `load_extension_registry(catalog_path)` for Task 2.

- [ ] **Step 1: Write failing catalog and dialect tests**

Create `tests/test_protocol_v2_catalog.py` with focused real-code tests:

```python
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
```

- [ ] **Step 2: Run the tests to verify RED**

Run:

```bash
python3 -m unittest tests.test_protocol_v2_catalog -v
```

Expected: import failure because `protocol.v2.extension_catalog` does not exist.

- [ ] **Step 3: Add the canonical catalog**

Create `protocol/v2/extensions/catalog.json` exactly as:

```json
{
  "catalog_version": "1.0",
  "extensions": [
    {
      "namespace": "e2e.web",
      "owner": "e2e-web",
      "versions": [
        {
          "minimum": "1.0",
          "maximum": "1.0",
          "dialect": "draft2020-12-subset-1",
          "schema": "web.schema.json"
        }
      ]
    }
  ]
}
```

- [ ] **Step 4: Implement the standard-library helper**

Create `protocol/v2/extension_catalog.py`. Keep it surface-neutral. Its public structure must be:

```python
"""Portable extension catalog and schema-subset validation."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


class ExtensionCatalogError(ValueError):
    """Raised when release-owned extension metadata is unsafe or invalid."""


ExtensionValidator = Callable[[Any], list[str]]
SUPPORTED_DIALECT = "draft2020-12-subset-1"
JSON_TYPES = {"null", "boolean", "integer", "number", "string", "array", "object"}
SCHEMA_KEYS = {
    "$schema", "$id", "title", "description", "type", "required", "properties",
    "additionalProperties", "enum", "const", "pattern", "minimum", "maximum",
    "minLength", "maxLength", "items", "minItems", "maxItems",
}


def _version_tuple(value: str) -> tuple[int, int]:
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]+\.[0-9]+", value):
        raise ExtensionCatalogError(f"invalid extension version: {value}")
    major, minor = value.split(".")
    return int(major), int(minor)


def _json_type_matches(value: Any, expected: str) -> bool:
    if expected == "null":
        return value is None
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "string":
        return isinstance(value, str)
    if expected == "array":
        return isinstance(value, list)
    return isinstance(value, dict)


def _json_equal(left: Any, right: Any) -> bool:
    if isinstance(left, bool) or isinstance(right, bool):
        return isinstance(left, bool) and isinstance(right, bool) and left == right
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        return left == right
    if type(left) is not type(right):
        return False
    if isinstance(left, list):
        return len(left) == len(right) and all(_json_equal(a, b) for a, b in zip(left, right))
    if isinstance(left, dict):
        return set(left) == set(right) and all(_json_equal(left[key], right[key]) for key in left)
    return left == right


def _validate_schema_node(schema: Any, source: str) -> None:
    if not isinstance(schema, dict):
        raise ExtensionCatalogError(f"invalid schema object: {source}")
    unknown = sorted(set(schema) - SCHEMA_KEYS)
    if unknown:
        raise ExtensionCatalogError(f"unsupported schema keyword: {unknown[0]}")
    for annotation in ("$schema", "$id", "title", "description"):
        if annotation in schema and not isinstance(schema[annotation], str):
            raise ExtensionCatalogError(f"schema keyword {annotation} must be a string: {source}")
    declared_type = schema.get("type")
    if declared_type is not None:
        values = [declared_type] if isinstance(declared_type, str) else declared_type
        if (
            not isinstance(values, list) or not values
            or not all(isinstance(value, str) and value in JSON_TYPES for value in values)
            or len(values) != len(set(values))
        ):
            raise ExtensionCatalogError(f"schema type is invalid: {source}")
    required = schema.get("required", [])
    if not isinstance(required, list) or not all(isinstance(value, str) for value in required) or len(required) != len(set(required)):
        raise ExtensionCatalogError(f"schema required is invalid: {source}")
    properties = schema.get("properties", {})
    if not isinstance(properties, dict) or not all(isinstance(name, str) for name in properties):
        raise ExtensionCatalogError(f"schema properties is invalid: {source}")
    for name, child in properties.items():
        _validate_schema_node(child, f"{source}.properties.{name}")
    if "additionalProperties" in schema and not isinstance(schema["additionalProperties"], bool):
        raise ExtensionCatalogError(f"schema additionalProperties must be boolean: {source}")
    if "enum" in schema and (not isinstance(schema["enum"], list) or not schema["enum"]):
        raise ExtensionCatalogError(f"schema enum is invalid: {source}")
    if "enum" in schema and any(
        _json_equal(value, other)
        for index, value in enumerate(schema["enum"])
        for other in schema["enum"][index + 1:]
    ):
        raise ExtensionCatalogError(f"schema enum values must be unique: {source}")
    if "pattern" in schema:
        if not isinstance(schema["pattern"], str):
            raise ExtensionCatalogError(f"schema pattern must be a string: {source}")
        try:
            re.compile(schema["pattern"])
        except re.error as exc:
            raise ExtensionCatalogError(f"schema pattern is invalid: {source}") from exc
    for minimum, maximum in (("minimum", "maximum"), ("minLength", "maxLength"), ("minItems", "maxItems")):
        for key in (minimum, maximum):
            if key in schema:
                value = schema[key]
                integer_bound = key.startswith("minL") or key.startswith("maxL") or key.startswith("minI") or key.startswith("maxI")
                valid = isinstance(value, int) and not isinstance(value, bool) and value >= 0 if integer_bound else isinstance(value, (int, float)) and not isinstance(value, bool)
                if not valid:
                    raise ExtensionCatalogError(f"schema {key} is invalid: {source}")
        if minimum in schema and maximum in schema and schema[minimum] > schema[maximum]:
            raise ExtensionCatalogError(f"schema {minimum} exceeds {maximum}: {source}")
    if "items" in schema:
        _validate_schema_node(schema["items"], f"{source}.items")


def _validate_value(schema: dict[str, Any], value: Any, path: str, errors: list[str]) -> None:
    declared = schema.get("type")
    types = [declared] if isinstance(declared, str) else declared
    if types is not None and not any(_json_type_matches(value, expected) for expected in types):
        errors.append(f"{path} has invalid type")
        return
    if "enum" in schema and not any(_json_equal(value, allowed) for allowed in schema["enum"]):
        errors.append(f"{path} is not an allowed value")
    if "const" in schema and not _json_equal(value, schema["const"]):
        errors.append(f"{path} does not match const")
    if isinstance(value, dict):
        properties = schema.get("properties", {})
        for required in schema.get("required", []):
            if required not in value:
                errors.append(f"{path} missing required property: {required}")
        if schema.get("additionalProperties") is False:
            for name in sorted(set(value) - set(properties)):
                errors.append(f"{path} contains unexpected property: {name}")
        for name, child in properties.items():
            if name in value:
                _validate_value(child, value[name], f"{path}.{name}", errors)
    if isinstance(value, list):
        if len(value) < schema.get("minItems", 0):
            errors.append(f"{path} has too few items")
        if "maxItems" in schema and len(value) > schema["maxItems"]:
            errors.append(f"{path} has too many items")
        if "items" in schema:
            for index, item in enumerate(value):
                _validate_value(schema["items"], item, f"{path}[{index}]", errors)
    if isinstance(value, str):
        if len(value) < schema.get("minLength", 0):
            errors.append(f"{path} is too short")
        if "maxLength" in schema and len(value) > schema["maxLength"]:
            errors.append(f"{path} is too long")
        if "pattern" in schema and re.search(schema["pattern"], value) is None:
            errors.append(f"{path} does not match pattern")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            errors.append(f"{path} is below minimum")
        if "maximum" in schema and value > schema["maximum"]:
            errors.append(f"{path} is above maximum")


def compile_schema(schema: Any, dialect: str, source: str) -> ExtensionValidator:
    if dialect != SUPPORTED_DIALECT:
        raise ExtensionCatalogError(f"unsupported runtime schema dialect: {dialect}")
    _validate_schema_node(schema, source)

    def validate(value: Any) -> list[str]:
        errors: list[str] = []
        _validate_value(schema, value, "extension data", errors)
        return errors

    return validate


@dataclass(frozen=True)
class ExtensionSupport:
    namespace: str
    minimum_version: str
    maximum_version: str
    validator: ExtensionValidator
    owner: str | None = None

    def contains(self, version: str) -> bool:
        return _version_tuple(self.minimum_version) <= _version_tuple(version) <= _version_tuple(self.maximum_version)


class ExtensionRegistry:
    def __init__(self) -> None:
        self._supports: dict[str, list[ExtensionSupport]] = {}

    def register(self, support: ExtensionSupport) -> None:
        minimum = _version_tuple(support.minimum_version)
        maximum = _version_tuple(support.maximum_version)
        if minimum > maximum:
            raise ExtensionCatalogError("extension support minimum exceeds maximum")
        entries = self._supports.setdefault(support.namespace, [])
        for existing in entries:
            if minimum <= _version_tuple(existing.maximum_version) and _version_tuple(existing.minimum_version) <= maximum:
                raise ExtensionCatalogError(f"overlapping extension support: {support.namespace}")
        entries.append(support)

    def resolve(self, namespace: str, version: str) -> tuple[str, ExtensionSupport | None]:
        entries = self._supports.get(namespace)
        if not entries:
            return "capability-unavailable", None
        try:
            for support in entries:
                if support.contains(version):
                    return "supported", support
        except ExtensionCatalogError:
            return "extension-incompatible", None
        return "extension-incompatible", None

    def validate(self, extension: dict[str, Any]) -> list[str]:
        status, support = self.resolve(extension["namespace"], extension["version"])
        if status != "supported" or support is None:
            return []
        errors = []
        if support.owner is not None and extension.get("owner") != support.owner:
            errors.append(f"extension owner must be {support.owner}")
        errors.extend(support.validator(extension["data"]))
        return errors


def load_extension_registry(catalog_path: str | Path) -> ExtensionRegistry:
    path = Path(catalog_path)
    try:
        catalog = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ExtensionCatalogError(f"invalid extension catalog: {path.name}") from exc
    if not isinstance(catalog, dict) or set(catalog) != {"catalog_version", "extensions"}:
        raise ExtensionCatalogError("invalid extension catalog fields")
    if catalog["catalog_version"] != "1.0":
        raise ExtensionCatalogError(f"unsupported catalog version: {catalog['catalog_version']}")
    if not isinstance(catalog["extensions"], list):
        raise ExtensionCatalogError("catalog extensions must be an array")
    root = path.parent.resolve()
    namespaces: set[str] = set()
    registry = ExtensionRegistry()
    for entry in catalog["extensions"]:
        if not isinstance(entry, dict) or set(entry) != {"namespace", "owner", "versions"}:
            raise ExtensionCatalogError("invalid catalog extension entry")
        namespace, owner, versions = entry["namespace"], entry["owner"], entry["versions"]
        if not isinstance(namespace, str) or not re.fullmatch(r"[a-z][a-z0-9]*(?:\.[a-z][a-z0-9-]*)+", namespace):
            raise ExtensionCatalogError("invalid catalog namespace")
        if namespace in namespaces:
            raise ExtensionCatalogError(f"duplicate catalog namespace: {namespace}")
        namespaces.add(namespace)
        if not isinstance(owner, str) or not re.fullmatch(r"[a-z][a-z0-9]*(?:-[a-z0-9]+)*", owner):
            raise ExtensionCatalogError(f"invalid catalog owner: {namespace}")
        if not isinstance(versions, list) or not versions:
            raise ExtensionCatalogError(f"catalog versions must be non-empty: {namespace}")
        for version in versions:
            if not isinstance(version, dict) or set(version) != {"minimum", "maximum", "dialect", "schema"}:
                raise ExtensionCatalogError(f"invalid catalog version entry: {namespace}")
            if not isinstance(version["dialect"], str):
                raise ExtensionCatalogError(f"invalid catalog dialect: {namespace}")
            if not isinstance(version["schema"], str) or not version["schema"]:
                raise ExtensionCatalogError(f"invalid catalog schema path: {namespace}")
            _version_tuple(version["minimum"])
            _version_tuple(version["maximum"])
            relative = Path(version["schema"])
            if relative.is_absolute():
                raise ExtensionCatalogError("schema path must be relative")
            schema_path = (root / relative).resolve()
            try:
                schema_path.relative_to(root)
            except ValueError as exc:
                raise ExtensionCatalogError("schema path escapes extension directory") from exc
            try:
                schema = json.loads(schema_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                raise ExtensionCatalogError(f"invalid extension schema: {relative.as_posix()}") from exc
            validator = compile_schema(schema, version["dialect"], relative.as_posix())
            registry.register(ExtensionSupport(
                namespace, version["minimum"], version["maximum"], validator, owner,
            ))
    return registry
```

During implementation, keep error messages stable enough for the tests and do not add schema keywords outside the approved dialect.

- [ ] **Step 5: Run focused tests to verify GREEN**

Run:

```bash
python3 -m unittest tests.test_protocol_v2_catalog -v
```

Expected: every catalog and subset test passes.

- [ ] **Step 6: Commit the portable catalog engine**

```bash
git add protocol/v2/extension_catalog.py protocol/v2/extensions/catalog.json tests/test_protocol_v2_catalog.py
git commit -m "feat: add portable extension catalog engine"
```

---

### Task 2: Make bundled registry loading the safe public default

**Files:**
- Modify: `protocol/v2/e2e_protocol.py`
- Modify: `protocol/v2/__init__.py`
- Modify: `tests/test_protocol_v2_extensions.py`
- Modify: `tests/test_protocol_v2.py`

**Interfaces:**
- Consumes: Task 1 `ExtensionRegistry`, `ExtensionSupport`, `ExtensionCatalogError`, and `load_extension_registry`.
- Produces: automatic catalog-backed `new_manifest`, `validate_manifest`, `initialize_manifest`, `save_manifest`, `transition`, and `extension_issues`; keeps explicit registry injection available.

- [ ] **Step 1: Write failing automatic-registration tests**

Add `from unittest import mock` and add `initialize_manifest` to the imports from `protocol.v2.e2e_protocol`. Keep `web_extension` at module scope and add the following `test_...` functions as methods of `ProtocolV2ExtensionTests` (indent each method body one class level):

```python
def web_extension(data):
    return {
        "id": "extension-web", "namespace": "e2e.web", "version": "1.0",
        "owner": "e2e-web", "data": data,
    }


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
```

Add a CLI regression to `tests/test_protocol_v2.py` that writes a manifest with empty web data, invokes canonical `main(["validate", path])`, and expects exit code `2` plus `missing required property: driver`.

- [ ] **Step 2: Run the focused tests to verify RED**

Run:

```bash
python3 -m unittest tests.test_protocol_v2_extensions tests.test_protocol_v2.ProtocolV2PersistenceTests -v
```

Expected failures:

- malformed web data currently validates;
- the owned web extension is treated as unknown during save;
- `extension_issues(manifest)` currently requires a registry.
- a corrupt default catalog is not yet resolved before persistence.

- [ ] **Step 3: Load the helper safely in package, direct-script, and importlib modes**

In `protocol/v2/e2e_protocol.py`, remove the local `ExtensionSupport`, `ExtensionRegistry`, and `_version_tuple` definitions. Add a release-owned helper loader near the imports:

```python
import importlib
import importlib.util


def _load_catalog_module():
    if __package__:
        return importlib.import_module(".extension_catalog", __package__)
    helper_path = Path(__file__).resolve().with_name("extension_catalog.py")
    module_name = f"{__name__}_extension_catalog"
    spec = importlib.util.spec_from_file_location(module_name, helper_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load extension catalog helper: {helper_path.name}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


_CATALOG_MODULE = _load_catalog_module()
ExtensionCatalogError = _CATALOG_MODULE.ExtensionCatalogError
ExtensionRegistry = _CATALOG_MODULE.ExtensionRegistry
ExtensionSupport = _CATALOG_MODULE.ExtensionSupport
load_extension_registry = _CATALOG_MODULE.load_extension_registry
```

Remove the now-unused `dataclass` import. This explicit sibling load is required because active documentation imports the bundled runtime with `spec_from_file_location`, which does not add the skill's `scripts/` directory to `sys.path`.

- [ ] **Step 4: Add deterministic release-native catalog resolution**

Add:

```python
_AUTO_REGISTRY = object()


def _default_catalog_path(runtime_file: str | Path | None = None) -> Path:
    runtime = Path(runtime_file or __file__).resolve()
    directory = runtime.parent
    if directory.name == "v2" and directory.parent.name == "protocol":
        return directory / "extensions" / "catalog.json"
    if directory.name == "scripts":
        return directory.parent / "references" / "extensions" / "catalog.json"
    raise ProtocolError("extension catalog unavailable: unsupported runtime layout")


def _resolve_registry(registry: Any = _AUTO_REGISTRY) -> ExtensionRegistry | None:
    if registry is not _AUTO_REGISTRY:
        return registry
    try:
        return load_extension_registry(_default_catalog_path())
    except ExtensionCatalogError as exc:
        raise ProtocolError(f"extension catalog unavailable: {exc}") from exc
```

Do not search the current working directory, target repository, environment variables, or user paths.

- [ ] **Step 5: Resolve once per public operation**

Change the public signatures to use `_AUTO_REGISTRY` and resolve it once:

```python
def new_manifest(..., timestamp: str | None = None, registry: Any = _AUTO_REGISTRY) -> dict[str, Any]:
    resolved_registry = _resolve_registry(registry)
    # Build as today, then call validate_manifest(manifest, resolved_registry).

def validate_manifest(data: Any, registry: Any = _AUTO_REGISTRY) -> list[str]:
    resolved_registry = _resolve_registry(registry)
    # Pass resolved_registry to _validate_extension_envelopes.

def extension_issues(data: dict[str, Any], registry: Any = _AUTO_REGISTRY) -> list[dict[str, str]]:
    resolved_registry = _resolve_registry(registry)
    # Resolve each extension with resolved_registry.

def initialize_manifest(..., timestamp: str | None = None, registry: Any = _AUTO_REGISTRY) -> dict[str, Any]:
    resolved_registry = _resolve_registry(registry)
    fresh = new_manifest(project_root, mode, autonomy, timestamp, resolved_registry)
    # Reuse resolved_registry for final validation before _atomic_write.

def save_manifest(..., registry: Any = _AUTO_REGISTRY, timestamp: str | None = None, ...) -> dict[str, Any]:
    resolved_registry = _resolve_registry(registry)
    # Reuse it for existing validation, unknown-extension preservation, and candidate validation.

def transition(..., registry: Any = _AUTO_REGISTRY, timestamp: str | None = None) -> dict[str, Any]:
    resolved_registry = _resolve_registry(registry)
    # Pass resolved_registry to save_manifest.
```

Preserve existing positional argument order. In particular, `registry` remains before `timestamp` in `save_manifest` and `transition`; `new_manifest` and `initialize_manifest` add it only after `timestamp`.

Catalog resolution must happen before acquiring the manifest lock or writing files. `validate_manifest(data, None)` remains an explicit advanced opt-out for existing low-level tests; active callers omit the argument and therefore cannot accidentally bypass the bundled catalog.

- [ ] **Step 6: Re-export the catalog API**

Update `protocol/v2/__init__.py` to export `ExtensionCatalogError` and `load_extension_registry` alongside the existing registry types.

- [ ] **Step 7: Run focused tests to verify GREEN and existing registry compatibility**

Run:

```bash
python3 -m unittest tests.test_protocol_v2_catalog tests.test_protocol_v2_extensions tests.test_protocol_v2 -v
```

Expected: all focused tests pass, including existing explicit custom-registry and unknown-extension tests.

- [ ] **Step 8: Commit automatic registration**

```bash
git add protocol/v2/e2e_protocol.py protocol/v2/__init__.py tests/test_protocol_v2_extensions.py tests/test_protocol_v2.py
git commit -m "fix: register bundled protocol extensions by default"
```

---

### Task 3: Package filtered catalogs and validate bundled execution

**Files:**
- Modify: `scripts/sync_protocol.py`
- Modify: `tests/test_packaging.py`
- Modify: `tests/test_evaluation_contracts.py`
- Generate: `skills/e2e-testing/references/extensions/catalog.json`
- Generate: `skills/e2e-testing/scripts/extension_catalog.py`
- Generate: `skills/e2e-web/references/extensions/catalog.json`
- Generate: `skills/e2e-web/scripts/extension_catalog.py`
- Generate: synchronized existing runtime and schema files in both skills.

**Interfaces:**
- Consumes: canonical catalog, schemas, runtime, and helper from Tasks 1-2.
- Produces: independently importable bundles whose catalogs contain exactly `e2e.web`, plus evaluator validation through the bundled registry.

- [ ] **Step 1: Write failing packaging projection tests**

Replace the hard-coded `CANONICAL_FILES` model in `tests/test_packaging.py`. Keep `EXPECTED_NAMESPACES` at module scope and add the following `test_...` functions as methods of `PackagingTests` (indent each method body one class level):

```python
EXPECTED_NAMESPACES = {
    "e2e-testing": {"e2e.web"},
    "e2e-web": {"e2e.web"},
}

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
```

Add `import importlib.util`, `import json`, and ensure `sys` is already imported.

Add an evaluator regression to `tests/test_evaluation_contracts.py`:

```python
def test_evaluator_rejects_malformed_registered_web_extension(self):
    manifest = _manifest(Path("/workspace"))
    manifest["extensions"][0]["data"] = {}
    self.assertIn(
        "extension data missing required property: driver",
        evaluate_result._validate_manifest(manifest),
    )
```

- [ ] **Step 2: Run packaging tests to verify RED**

Run:

```bash
python3 -m unittest tests.test_packaging tests.test_evaluation_contracts.EvaluatorTests.test_evaluator_rejects_malformed_registered_web_extension -v
```

Expected: catalog/helper bundle files are missing and the currently bundled evaluator runtime accepts malformed web data.

- [ ] **Step 3: Implement deterministic filtered synchronization**

Refactor `scripts/sync_protocol.py` around this structure:

```python
import json

ROOT = Path(__file__).resolve().parents[1]
STATIC_FILES = (
    (ROOT / "protocol/v2/manifest.schema.json", Path("references/manifest.schema.json")),
    (ROOT / "protocol/v2/e2e_protocol.py", Path("scripts/e2e_protocol.py")),
    (ROOT / "protocol/v2/extension_catalog.py", Path("scripts/extension_catalog.py")),
)
TARGETS = {
    ROOT / "skills/e2e-testing": frozenset({"e2e.web"}),
    ROOT / "skills/e2e-web": frozenset({"e2e.web"}),
}
CATALOG_PATH = ROOT / "protocol/v2/extensions/catalog.json"


def _catalog_projection(namespaces: frozenset[str]) -> dict:
    catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    return {
        "catalog_version": catalog["catalog_version"],
        "extensions": [
            entry for entry in catalog["extensions"] if entry["namespace"] in namespaces
        ],
    }


def _expected_files(namespaces: frozenset[str]) -> dict[Path, bytes]:
    expected = {relative: source.read_bytes() for source, relative in STATIC_FILES}
    projection = _catalog_projection(namespaces)
    expected[Path("references/extensions/catalog.json")] = (
        json.dumps(projection, indent=2, sort_keys=False) + "\n"
    ).encode()
    for entry in projection["extensions"]:
        for support in entry["versions"]:
            relative = Path(support["schema"])
            expected[Path("references/extensions") / relative] = (
                ROOT / "protocol/v2/extensions" / relative
            ).read_bytes()
    return expected


def sync(check: bool) -> list[str]:
    stale = []
    for target, namespaces in TARGETS.items():
        for relative, content in _expected_files(namespaces).items():
            destination = target / relative
            if not destination.exists() or destination.read_bytes() != content:
                stale.append(str(destination.relative_to(ROOT)))
                if not check:
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    destination.write_bytes(content)
    return stale
```

Retain the existing CLI behavior and deterministic stale-file reporting. Do not delete inert files during sync; the catalog alone controls recognition.

- [ ] **Step 4: Synchronize the bundles**

Run:

```bash
python3 scripts/sync_protocol.py
python3 scripts/sync_protocol.py --check
```

Expected: first command writes release copies; second command has no output and exits `0`.

- [ ] **Step 5: Run packaging and evaluator tests to verify GREEN**

Run:

```bash
python3 -m unittest tests.test_packaging tests.test_evaluation_contracts -v
```

Expected: bundled importlib loading, automatic typed validation, evaluator contracts, and existing harness tests pass.

- [ ] **Step 6: Commit portable packaging**

```bash
git add scripts/sync_protocol.py tests/test_packaging.py tests/test_evaluation_contracts.py skills/e2e-testing skills/e2e-web
git commit -m "feat: package filtered protocol extension catalogs"
```

---

### Task 4: Correct the active execution-evidence skill contract with skill TDD

**Files:**
- Modify: `skills/e2e-web/references/workflow.md`
- Modify: `tests/test_skill_contracts.py`
- Modify: `tests/test_evaluation_contracts.py`

**Interfaces:**
- Consumes: Protocol 2 evaluator fields `check_ids` and `outcomes[].check_id`.
- Produces: active web guidance that generates evaluator-compatible execution evidence and deterministic tests binding documentation to behavior.

- [ ] **Step 1: Run the reference-skill baseline scenario before editing**

Following `superpowers:writing-skills`, dispatch a fresh subagent with access to the current `skills/e2e-web` directory but without explaining the known defect. Use this exact application scenario:

```text
You are executing e2e-web in verify mode under time pressure. The manifest selects
check-login at revision 4, the authorized local Playwright command passed, and you
must now return only the single execution-evidence JSON object required by the
installed e2e-web guidance. Use concrete sanitized placeholder values for every
required field. Do not discuss the task.
```

Record the response verbatim in the implementation notes. The expected current failure is a `test_ids` field or omission of `check_ids`. If the baseline unexpectedly emits the complete correct `check_ids`/`outcomes[].check_id` shape, stop and report that the behavioral control did not reproduce; retain the deterministic RED test below as the defect proof and do not invent pressure-test conclusions.

- [ ] **Step 2: Write the failing contract tests**

Add to `SkillContractTests.test_web_reference_safety_contract`:

```python
self.assertIn("| `check_ids` | immutable selected check IDs |", workflow)
self.assertIn("`outcomes[].check_id`", workflow)
self.assertNotIn("`test_ids`", workflow)
```

Add a deterministic documentation-to-evaluator test to `tests/test_evaluation_contracts.py`:

```python
def test_published_web_evidence_vocabulary_matches_evaluator(self):
    workflow = (ROOT / "skills/e2e-web/references/workflow.md").read_text()
    self.assertIn("| `check_ids` | immutable selected check IDs |", workflow)
    self.assertIn("`outcomes[].check_id`", workflow)
    evidence = _verification_evidence(
        "check-checkout", revision_consumed=4, phase="verify",
    )
    self.assertEqual(evidence["check_ids"], ["check-checkout"])
    self.assertEqual(evidence["outcomes"][0]["check_id"], "check-checkout")
    self.assertTrue(evaluate_result._is_execution_evidence(evidence, {"check-checkout"}))
```

- [ ] **Step 3: Run the contract tests to verify RED**

Run:

```bash
python3 -m unittest tests.test_skill_contracts.SkillContractTests.test_web_reference_safety_contract tests.test_evaluation_contracts.EvaluatorTests.test_published_web_evidence_vocabulary_matches_evaluator -v
```

Expected: both tests fail because the workflow still documents `test_ids` and does not name `outcomes[].check_id`.

- [ ] **Step 4: Make the smallest positive contract correction**

In `skills/e2e-web/references/workflow.md`, replace the two affected table descriptions with:

```markdown
| `check_ids` | immutable selected check IDs |
...
| `outcomes` | per-check pass/fail/blocked results, each keyed by `outcomes[].check_id` |
```

Also change surrounding prose from “selected test IDs/tests” to “selected check IDs/checks” only where it refers to Protocol 2 manifest records. Do not rename repository-native test files, Playwright tests, or the `test-defect` classification.

- [ ] **Step 5: Run the deterministic tests to verify GREEN**

Run:

```bash
python3 -m unittest tests.test_skill_contracts.SkillContractTests.test_web_reference_safety_contract tests.test_evaluation_contracts.EvaluatorTests.test_published_web_evidence_vocabulary_matches_evaluator -v
```

Expected: both tests pass.

- [ ] **Step 6: Rerun the same skill application scenario**

Dispatch a new fresh subagent with the exact Step 1 prompt and the corrected skill directory. Expected: the evidence object uses `check_ids`, every outcome uses `check_id`, and `test_ids` is absent. Record the response verbatim in implementation notes. If it still produces the wrong shape, refine only the positive evidence-record recipe and repeat the same scenario before proceeding.

- [ ] **Step 7: Commit the evidence contract correction**

```bash
git add skills/e2e-web/references/workflow.md tests/test_skill_contracts.py tests/test_evaluation_contracts.py
git commit -m "fix: align web evidence with protocol 2 checks"
```

---

### Task 5: Align active documentation and enforce the release boundary

**Files:**
- Modify: `docs/roadmap.md`
- Modify: `protocol/v2/README.md`
- Modify: `tests/test_readmes.py`
- Modify: `tests/test_skill_contracts.py`

**Interfaces:**
- Consumes: completed catalog/runtime/packaging/evidence work from Tasks 1-4.
- Produces: active documentation consistent with explicit fresh Protocol 2 replacement and a release gate preventing catalog, dependency, or evidence regressions.

- [ ] **Step 1: Write failing active-documentation and release-gate tests**

Add to `tests/test_readmes.py`:

```python
def test_active_protocol_and_roadmap_do_not_publish_runtime_migration(self):
    roadmap = (ROOT / "docs/roadmap.md").read_text()
    protocol = (ROOT / "protocol/v2/README.md").read_text()
    self.assertIn("fresh Protocol 2", roadmap)
    self.assertIn("offline historical utility", roadmap)
    self.assertNotIn("Lossless Protocol 1 migration", roadmap)
    self.assertNotIn("V1 web history migrates losslessly", roadmap)
    self.assertIn("Offline historical utility", protocol)
    self.assertIn("--replace-protocol-1", protocol)
    self.assertNotIn("Migration is explicit and lossless", protocol)
```

Add to `tests/test_skill_contracts.py`:

```python
def test_protocol_kernel_is_surface_neutral_and_portable(self):
    runtime = (ROOT / "protocol/v2/e2e_protocol.py").read_text()
    helper = (ROOT / "protocol/v2/extension_catalog.py").read_text()
    for forbidden in ("e2e.web", "e2e.service", "jsonschema"):
        self.assertNotIn(forbidden, runtime)
        self.assertNotIn(forbidden, helper)

def test_active_bundles_publish_registered_web_catalogs(self):
    for skill in ("e2e-testing", "e2e-web"):
        root = ROOT / "skills" / skill
        catalog = json.loads((root / "references/extensions/catalog.json").read_text())
        self.assertEqual(
            {entry["namespace"] for entry in catalog["extensions"]},
            {"e2e.web"},
        )
        support = catalog["extensions"][0]["versions"]
        self.assertEqual(support, [{
            "minimum": "1.0", "maximum": "1.0",
            "dialect": "draft2020-12-subset-1", "schema": "web.schema.json",
        }])
        self.assertTrue((root / "scripts/extension_catalog.py").is_file())
```

- [ ] **Step 2: Run the new gates to verify RED**

Run:

```bash
python3 -m unittest tests.test_readmes.ReadmeContractTests.test_active_protocol_and_roadmap_do_not_publish_runtime_migration tests.test_skill_contracts.SkillContractTests.test_protocol_kernel_is_surface_neutral_and_portable tests.test_skill_contracts.SkillContractTests.test_active_bundles_publish_registered_web_catalogs -v
```

Expected: the active roadmap and protocol README still promote lossless migration; catalog gates pass only after Tasks 1-3.

- [ ] **Step 3: Correct only active roadmap migration language**

In `docs/roadmap.md`, update V2 as follows:

- prerequisite: replace “sufficient history for lossless migration testing” with deterministic fresh Protocol 2 replacement behavior;
- deliverable: replace “Lossless Protocol 1 migration” with explicit replacement of an exact Protocol 1 manifest by fresh Protocol 2 state, while retaining the old migrator as an offline historical utility;
- exclusion: state “Protocol 1 runtime compatibility or active history migration”;
- exit criterion: state that active skills never invoke the offline migrator and replace exact Protocol 1 state only with explicit authorization;
- delivery decomposition: name “Protocol 2 kernel and offline historical migration utility” rather than an active migration phase.

Do not change the V3-V6 responsibilities, prerequisites, or ordering.

- [ ] **Step 4: Correct the active Protocol 2 README**

In `protocol/v2/README.md`:

- keep `init` and `validate` under canonical commands;
- add the existing `init ... --replace-protocol-1` command;
- move `migrate_v1` out of canonical commands into an `## Offline historical utility` section;
- state that active skills never invoke it and that project manifests use explicit fresh replacement instead;
- document that the bundled catalog supplies typed extension validation automatically and unknown extensions remain preserved.

Do not modify `protocol/v2/migrate_v1.py` or its tests.

- [ ] **Step 5: Run focused documentation and release gates to verify GREEN**

Run:

```bash
python3 -m unittest tests.test_readmes tests.test_skill_contracts tests.test_packaging -v
```

Expected: all active-documentation, skill, and packaging contracts pass.

- [ ] **Step 6: Run complete release verification**

Run each command separately and inspect its complete output:

```bash
python3 scripts/sync_protocol.py --check
python3 scripts/validate_skills.py
python3 -m unittest discover -s tests -v
git diff --check
```

Expected:

- sync check has no output and exits `0`;
- skill validation reports `validated: 2 skills`;
- the complete deterministic suite ends `OK` with zero failures and errors;
- whitespace check exits `0`.

- [ ] **Step 7: Verify protected historical/offline files are unchanged**

Record the execution baseline before Task 1, then run:

```bash
git diff "$BASE_SHA" -- protocol/v1 protocol/v2/migrate_v1.py tests/test_protocol_v2_migration.py docs/superpowers/specs/2026-07-21-e2e-testing-v2-design.md docs/superpowers/plans/2026-07-21-protocol-2-kernel-migration.md
```

Expected: no output. The approved stabilization spec and this plan are not protected historical documents.

- [ ] **Step 8: Commit release alignment and gates**

```bash
git add -f docs/roadmap.md
git add protocol/v2/README.md tests/test_readmes.py tests/test_skill_contracts.py
git commit -m "docs: stabilize the protocol 2 extension boundary"
```

- [ ] **Step 9: Re-run full verification after the final commit**

```bash
python3 scripts/sync_protocol.py --check
python3 scripts/validate_skills.py
python3 -m unittest discover -s tests -v
git status --short --branch
```

Expected: all checks remain green and the worktree contains no unstaged implementation changes.

## Execution Notes

- Task order is intentional. Task 1 creates the dependency-free engine; Task 2 makes it the public default; Task 3 makes active portable bundles and the evaluator consume it; Task 4 repairs the skill-produced evidence contract; Task 5 aligns active documentation and locks the release boundary.
- The default registry sentinel distinguishes an omitted argument from an explicit low-level override. Active callers always omit the argument and therefore load release-owned metadata.
- The helper is a release sibling, not a target-repository module. Dynamic import must never search or import from the current project.
- A catalog infrastructure error raises `ProtocolError` before mutation. It is never persisted as `capability-unavailable`.
- If implementation reveals that a schema keyword outside `draft2020-12-subset-1` is required, stop and amend the design rather than silently widening the dialect.
- After all tasks pass, use `superpowers:requesting-code-review`, resolve Critical and Important findings, then use `superpowers:finishing-a-development-branch` for the merge/PR choice.
