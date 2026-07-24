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
