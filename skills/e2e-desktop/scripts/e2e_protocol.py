"""Protocol 2 kernel for portable end-to-end testing runs."""

from __future__ import annotations

import argparse
import importlib
import importlib.util
import json
import os
import re
import sys
import tempfile
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

if os.name == "nt":
    import msvcrt
else:
    import fcntl


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

_AUTO_REGISTRY = object()


class ProtocolError(Exception):
    """Raised when a Protocol 2 manifest cannot be safely handled."""


PROTOCOL_VERSION = "2.0"
MODES = {"plan", "generate", "verify", "repair"}
AUTONOMY_MODES = {"explicit", "auto"}
TARGET_TIERS = {"local", "ephemeral", "staging", "production", "unspecified"}
SURFACES = {"web", "service", "mobile", "desktop"}
BOUNDARY_STATUSES = {"unresolved", "declared", "needs-clarification"}
REQUIRED_FIELDS = (
    "protocol_version", "run", "systems", "journeys", "execution_units",
    "checks", "evidence", "actions", "handoffs", "authorizations",
    "attempts", "extensions",
)
COLLECTION_FIELDS = REQUIRED_FIELDS[2:]
PUBLIC_INTERFACE_KINDS = {"web", "rest", "graphql", "grpc", "websocket", "queue", "stream"}
ID_COLLECTIONS = (
    "systems", "journeys", "execution_units", "checks", "evidence",
    "actions", "handoffs", "authorizations", "attempts", "extensions",
)
REFERENCE_KEY_SUFFIXES = ("_ref", "_reference", "_id", "_identifier")
COMPACT_REFERENCE_SUFFIXES = ("ref", "reference", "id", "identifier")
RAW_SECRET_KEY_SUFFIX = re.compile(
    r"(?:^|_)(?:password|passphrase|token|secret(?:_value)?|api_key|private_key|credentials?)$"
)
RAW_SECRET_COMPACT_SUFFIXES = (
    "password", "passphrase", "token", "accesstoken", "refreshtoken", "secret",
    "clientsecret", "apikey", "privatekey", "credential", "credentials", "secretvalue",
)
TRANSITIONS = {
    "initialized": {"planned", "needs-clarification", "capability-unavailable", "extension-incompatible"},
    "planned": {"ready-for-adapter", "needs-clarification", "blocked"},
    "ready-for-adapter": {"generated-unverified", "capability-unavailable", "extension-incompatible", "blocked"},
    "generated-unverified": {"verifying", "needs-authorization", "blocked"},
    "verifying": {"verified", "repair-ready", "handoff-required", "needs-clarification", "needs-authorization", "blocked"},
    "repair-ready": {"generated-unverified", "blocked"},
    "handoff-required": {"verifying", "blocked"},
    "needs-authorization": {"verifying", "blocked"},
    "needs-clarification": {"planned", "blocked"},
    "verified": set(),
    "blocked": set(),
    "capability-unavailable": set(),
    "extension-incompatible": set(),
}
APPEND_ONLY_COLLECTIONS = ("evidence", "attempts")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def new_manifest(
    project_root: str,
    mode: str = "generate",
    autonomy: str = "explicit",
    timestamp: str | None = None,
    registry: Any = _AUTO_REGISTRY,
) -> dict[str, Any]:
    resolved_registry = _resolve_registry(registry)
    now = timestamp or _utc_now()
    manifest = {
        "protocol_version": PROTOCOL_VERSION,
        "run": {
            "id": f"run-{uuid.uuid4()}",
            "revision": 0,
            "mode": mode,
            "autonomy": {"mode": autonomy, "auto_repair": False},
            "status": "initialized",
            "created_at": now,
            "updated_at": now,
            "attempt_budget": {"repair": 0, "verification": 1, "wall_clock_seconds": 300},
        },
        "systems": [{
            "id": "system-primary",
            "project_root": str(project_root),
            "primary_surface": None,
            "boundary": {
                "status": "unresolved",
                "actors": [],
                "public_interfaces": [],
                "evidence_ids": [],
            },
            "target": {
                "tier": "unspecified",
                "endpoint_refs": [],
                "credential_refs": [],
                "mutation_policy": {"namespace_ref": None, "allowed_classes": []},
            },
        }],
        "journeys": [],
        "execution_units": [],
        "checks": [],
        "evidence": [],
        "actions": [],
        "handoffs": [],
        "authorizations": [],
        "attempts": [],
        "extensions": [],
    }
    errors = validate_manifest(manifest, resolved_registry) + validate_v2_policy(manifest)
    if errors:
        raise ProtocolError("invalid input: " + "; ".join(errors))
    return manifest


def validate_manifest(data: Any, registry: Any = _AUTO_REGISTRY) -> list[str]:
    resolved_registry = _resolve_registry(registry)
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["manifest must be an object"]
    for field in REQUIRED_FIELDS:
        if field not in data:
            errors.append(f"missing required field: {field}")
    errors.extend(
        f"unexpected top-level field: {field}"
        for field in sorted(set(data) - set(REQUIRED_FIELDS))
    )
    if data.get("protocol_version") != PROTOCOL_VERSION:
        errors.append("protocol_version must be 2.0")
    _validate_run(data.get("run"), errors)
    _validate_systems(data.get("systems"), errors)
    for field in COLLECTION_FIELDS[1:]:
        if not isinstance(data.get(field), list):
            errors.append(f"{field} must be an array")
    _validate_collections_and_references(data, errors)
    _validate_boundary_references(data, errors)
    _validate_evidence_references(data, errors)
    _validate_extension_envelopes(data, errors, resolved_registry)
    _find_secret_keys(data, errors)
    return errors


def _integer_at_least(value: Any, minimum: int, name: str, errors: list[str]) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        errors.append(f"{name} must be an integer >= {minimum}")


def _validate_run(value: Any, errors: list[str]) -> None:
    required = {"id", "revision", "mode", "autonomy", "status", "created_at", "updated_at", "attempt_budget"}
    if not isinstance(value, dict):
        errors.append("run must be an object")
        return
    if set(value) != required:
        errors.append("run fields are invalid")
    if not isinstance(value.get("id"), str) or not re.fullmatch(r"run-[a-z0-9-]+", value["id"]):
        errors.append("run.id must match ^run-[a-z0-9-]+$")
    _integer_at_least(value.get("revision"), 0, "run.revision", errors)
    if value.get("mode") not in MODES:
        errors.append("run.mode is invalid")
    if value.get("status") not in TRANSITIONS:
        errors.append("run.status is invalid")
    autonomy = value.get("autonomy")
    if not isinstance(autonomy, dict) or set(autonomy) != {"mode", "auto_repair"}:
        errors.append("run.autonomy fields are invalid")
    else:
        if autonomy.get("mode") not in AUTONOMY_MODES:
            errors.append("run.autonomy.mode is invalid")
        if not isinstance(autonomy.get("auto_repair"), bool):
            errors.append("run.autonomy.auto_repair must be a boolean")
    budget = value.get("attempt_budget")
    if not isinstance(budget, dict) or set(budget) != {"repair", "verification", "wall_clock_seconds"}:
        errors.append("run.attempt_budget fields are invalid")
    else:
        _integer_at_least(budget.get("repair"), 0, "run.attempt_budget.repair", errors)
        _integer_at_least(budget.get("verification"), 1, "run.attempt_budget.verification", errors)
        _integer_at_least(budget.get("wall_clock_seconds"), 1, "run.attempt_budget.wall_clock_seconds", errors)
    for field in ("created_at", "updated_at"):
        timestamp = value.get(field)
        if timestamp is not None and (
            not isinstance(timestamp, str)
            or not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[^ ]+Z", timestamp)
        ):
            errors.append(f"run.{field} must be an RFC3339 string or null")


def _validate_systems(value: Any, errors: list[str]) -> None:
    if not isinstance(value, list):
        errors.append("systems must be an array")
        return
    if not value:
        errors.append("systems must contain at least one system")
        return
    for index, system in enumerate(value):
        label = f"systems[{index}]"
        if not isinstance(system, dict):
            errors.append(f"{label} must be an object")
            continue
        if not isinstance(system.get("id"), str):
            errors.append(f"{label}.id must be a string")
        if not isinstance(system.get("project_root"), str):
            errors.append(f"{label}.project_root must be a string")
        if system.get("primary_surface") is not None and system.get("primary_surface") not in SURFACES:
            errors.append(f"{label}.primary_surface is invalid")
        boundary = system.get("boundary")
        if not isinstance(boundary, dict):
            errors.append(f"{label}.boundary must be an object")
        elif boundary.get("status") not in BOUNDARY_STATUSES:
            errors.append(f"{label}.boundary.status is invalid")
        target = system.get("target")
        if not isinstance(target, dict):
            errors.append(f"{label}.target must be an object")
        elif target.get("tier") not in TARGET_TIERS:
            errors.append(f"{label}.target.tier is invalid")
        if set(system) != {"id", "project_root", "primary_surface", "boundary", "target"}:
            errors.append(f"{label} fields are invalid")
        if isinstance(boundary, dict):
            if set(boundary) != {"status", "actors", "public_interfaces", "evidence_ids"}:
                errors.append(f"{label}.boundary fields are invalid")
            if not isinstance(boundary.get("actors"), list) or not all(isinstance(actor, str) for actor in boundary.get("actors", [])):
                errors.append(f"{label}.boundary.actors must be an array of strings")
        if isinstance(target, dict):
            if set(target) != {"tier", "endpoint_refs", "credential_refs", "mutation_policy"}:
                errors.append(f"{label}.target fields are invalid")
            for field in ("endpoint_refs", "credential_refs"):
                refs = target.get(field)
                if not isinstance(refs, list) or not all(isinstance(ref, str) for ref in refs):
                    errors.append(f"{label}.target.{field} must be an array of strings")
            mutation = target.get("mutation_policy")
            if not isinstance(mutation, dict):
                errors.append(f"{label}.target.mutation_policy must be an object")
            else:
                if set(mutation) != {"namespace_ref", "allowed_classes"}:
                    errors.append(f"{label}.target.mutation_policy fields are invalid")
                if mutation.get("namespace_ref") is not None and not isinstance(mutation.get("namespace_ref"), str):
                    errors.append(f"{label}.target.mutation_policy.namespace_ref must be a string or null")
                allowed = mutation.get("allowed_classes")
                if not isinstance(allowed, list) or not all(isinstance(item, str) for item in allowed):
                    errors.append(f"{label}.target.mutation_policy.allowed_classes must be an array of strings")


def _id_map(data: dict[str, Any], name: str, errors: list[str]) -> set[str]:
    items = data.get(name)
    if not isinstance(items, list):
        return set()
    result: set[str] = set()
    for index, item in enumerate(items):
        if not isinstance(item, dict) or not isinstance(item.get("id"), str):
            errors.append(f"{name}[{index}] must have a string id")
            continue
        if item["id"] in result:
            errors.append(f"duplicate id in {name}: {item['id']}")
        result.add(item["id"])
    return result


def _unknown_refs(
    values: Any,
    known: set[str],
    label: str,
    errors: list[str],
) -> None:
    if not isinstance(values, list) or not all(isinstance(value, str) for value in values):
        errors.append(f"{label} must be an array of strings")
        return
    for value in values:
        if value not in known:
            errors.append(f"{label} contains an unknown evidence ID: {value}")


def _validate_collections_and_references(data: dict[str, Any], errors: list[str]) -> None:
    ids = {name: _id_map(data, name, errors) for name in ID_COLLECTIONS}
    systems = data.get("systems") if isinstance(data.get("systems"), list) else []
    journeys = data.get("journeys") if isinstance(data.get("journeys"), list) else []
    units = data.get("execution_units") if isinstance(data.get("execution_units"), list) else []
    checks = data.get("checks") if isinstance(data.get("checks"), list) else []

    for index, journey in enumerate(journeys):
        if not isinstance(journey, dict):
            continue
        system_id = journey.get("system_id")
        if system_id not in ids["systems"]:
            errors.append(
                f"journeys[{index}].system_id does not reference a registered system: {system_id}"
            )

    for index, unit in enumerate(units):
        if not isinstance(unit, dict):
            continue
        if unit.get("system_id") not in ids["systems"]:
            errors.append(f"execution_units[{index}].system_id is unknown")
        if unit.get("surface") not in SURFACES:
            errors.append(f"execution_units[{index}].surface is invalid")
        if not isinstance(unit.get("capability"), str):
            errors.append(f"execution_units[{index}].capability must be a string")
        extension_id = unit.get("extension_id")
        if extension_id is not None and extension_id not in ids["extensions"]:
            errors.append(f"execution_units[{index}].extension_id is unknown")
    for index, check in enumerate(checks):
        if not isinstance(check, dict):
            continue
        journey_id = check.get("journey_id")
        unit_id = check.get("execution_unit_id")
        if journey_id not in ids["journeys"]:
            errors.append(
                f"checks[{index}].journey_id does not reference a registered journey: {journey_id}"
            )
        if unit_id not in ids["execution_units"]:
            errors.append(
                f"checks[{index}].execution_unit_id does not reference a registered execution unit: {unit_id}"
            )

    for index, action in enumerate(data.get("actions", [])):
        if not isinstance(action, dict):
            continue
        if not isinstance(action.get("capability"), str):
            errors.append(f"actions[{index}].capability must be a string")
        values = action.get("journey_ids")
        if not isinstance(values, list) or not all(isinstance(value, str) for value in values):
            errors.append(f"actions[{index}].journey_ids must be an array of strings")
        else:
            for value in values:
                if value not in ids["journeys"]:
                    errors.append(f"actions[{index}].journey_ids contains an unknown journey: {value}")
    for index, handoff in enumerate(data.get("handoffs", [])):
        if not isinstance(handoff, dict) or "journey_ids" not in handoff:
            continue
        values = handoff["journey_ids"]
        if not isinstance(values, list) or not all(isinstance(value, str) for value in values):
            errors.append(f"handoffs[{index}].journey_ids must be an array of strings")
        else:
            for value in values:
                if value not in ids["journeys"]:
                    errors.append(f"handoffs[{index}].journey_ids contains an unknown journey: {value}")


def _validate_boundary_references(data: dict[str, Any], errors: list[str]) -> None:
    evidence_ids = _id_map(data, "evidence", [])
    systems = data.get("systems") if isinstance(data.get("systems"), list) else []
    for system_index, system in enumerate(systems):
        if not isinstance(system, dict):
            continue
        boundary = system.get("boundary")
        if not isinstance(boundary, dict):
            continue
        boundary_label = f"systems[{system_index}].boundary"
        _unknown_refs(boundary.get("evidence_ids"), evidence_ids, f"{boundary_label}.evidence_ids", errors)
        interfaces = boundary.get("public_interfaces")
        if not isinstance(interfaces, list):
            errors.append(f"{boundary_label}.public_interfaces must be an array")
            continue
        for interface_index, interface in enumerate(interfaces):
            label = f"{boundary_label}.public_interfaces[{interface_index}]"
            if not isinstance(interface, dict):
                errors.append(f"{label} must be an object")
                continue
            if interface.get("kind") not in PUBLIC_INTERFACE_KINDS:
                errors.append(f"{label}.kind is invalid")
            _unknown_refs(interface.get("evidence_ids"), evidence_ids, f"{label}.evidence_ids", errors)


def _validate_evidence_references(data: dict[str, Any], errors: list[str]) -> None:
    evidence = data.get("evidence") if isinstance(data.get("evidence"), list) else []
    handoffs = data.get("handoffs") if isinstance(data.get("handoffs"), list) else []
    evidence_ids = {item.get("id") for item in evidence if isinstance(item, dict) and isinstance(item.get("id"), str)}
    artifact_ids = {
        artifact.get("id") for item in evidence if isinstance(item, dict)
        for artifact in item.get("artifacts", []) if isinstance(artifact, dict) and isinstance(artifact.get("id"), str)
    }
    for index, item in enumerate(evidence):
        classification = item.get("classification") if isinstance(item, dict) else None
        if isinstance(classification, dict) and "evidence_ids" in classification:
            _unknown_refs(classification["evidence_ids"], evidence_ids, f"evidence[{index}].classification.evidence_ids", errors)
    for index, item in enumerate(handoffs):
        if not isinstance(item, dict):
            continue
        if "evidence_ids" in item:
            _unknown_refs(item["evidence_ids"], evidence_ids, f"handoffs[{index}].evidence_ids", errors)
        if "artifact_refs" in item:
            refs = item["artifact_refs"]
            if not isinstance(refs, list) or not all(isinstance(ref, str) for ref in refs):
                errors.append(f"handoffs[{index}].artifact_refs must be an array of strings")
            else:
                for ref in refs:
                    if ref not in artifact_ids:
                        errors.append(f"handoffs[{index}].artifact_refs contains an unknown artifact ID: {ref}")


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


def extension_issues(data: dict[str, Any], registry: Any = _AUTO_REGISTRY) -> list[dict[str, str]]:
    resolved_registry = _resolve_registry(registry)
    issues = []
    for extension in data.get("extensions", []):
        if not isinstance(extension, dict):
            continue
        namespace = extension.get("namespace")
        version = extension.get("version")
        if not isinstance(namespace, str) or not isinstance(version, str):
            continue
        status, _ = resolved_registry.resolve(namespace, version)
        if status != "supported":
            issues.append({
                "extension_id": extension.get("id", ""),
                "namespace": namespace,
                "version": version,
                "status": status,
            })
    return issues


def _validate_extension_envelopes(
    data: dict[str, Any],
    errors: list[str],
    registry: ExtensionRegistry | None,
) -> None:
    extensions = data.get("extensions")
    if not isinstance(extensions, list):
        return
    required = {"id", "namespace", "version", "owner", "data"}
    for index, extension in enumerate(extensions):
        if not isinstance(extension, dict):
            continue
        if set(extension) != required:
            errors.append(f"extensions[{index}] fields are invalid")
        namespace = extension.get("namespace")
        version = extension.get("version")
        if not isinstance(namespace, str) or not re.fullmatch(r"[a-z][a-z0-9]*(?:\.[a-z][a-z0-9-]*)+", namespace):
            errors.append(f"extensions[{index}].namespace is invalid")
        if not isinstance(version, str) or not re.fullmatch(r"[0-9]+\.[0-9]+", version):
            errors.append(f"extensions[{index}].version is invalid")
        if not isinstance(extension.get("owner"), str):
            errors.append(f"extensions[{index}].owner must be a string")
        if not isinstance(extension.get("data"), dict):
            errors.append(f"extensions[{index}].data must be an object")
        elif registry is not None and isinstance(namespace, str) and isinstance(version, str):
            errors.extend(registry.validate(extension))


def _find_secret_keys(value: Any, errors: list[str]) -> None:
    if isinstance(value, dict):
        for key, nested in value.items():
            normalized = re.sub(r"[^A-Za-z0-9]+", "_", key)
            normalized = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", normalized)
            normalized = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", normalized).lower().strip("_")
            compact = normalized.replace("_", "")
            is_reference = normalized.endswith(REFERENCE_KEY_SUFFIXES) or compact.endswith(COMPACT_REFERENCE_SUFFIXES)
            is_secret = bool(RAW_SECRET_KEY_SUFFIX.search(normalized)) or compact.endswith(RAW_SECRET_COMPACT_SUFFIXES)
            if is_secret and not is_reference:
                errors.append(f"secret value key is forbidden: {key}")
            _find_secret_keys(nested, errors)
    elif isinstance(value, list):
        for nested in value:
            _find_secret_keys(nested, errors)


def validate_v2_policy(data: Any) -> list[str]:
    if not isinstance(data, dict):
        return ["manifest must be an object"]
    errors: list[str] = []
    systems = data.get("systems")
    if not isinstance(systems, list) or len(systems) != 1:
        errors.append("systems must contain exactly one system in V2")
        return errors
    units = data.get("execution_units") if isinstance(data.get("execution_units"), list) else []
    surfaces = {unit.get("surface") for unit in units if isinstance(unit, dict) and unit.get("surface") in SURFACES}
    if len(surfaces) > 1:
        errors.append("execution_units use more than one primary surface in V2")
    if surfaces and isinstance(systems[0], dict) and systems[0].get("primary_surface") != next(iter(surfaces)):
        errors.append("systems[0].primary_surface does not match execution unit surface")
    return errors


def load_manifest(path: str | Path) -> dict[str, Any]:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ProtocolError(f"invalid input: cannot read manifest: {exc}") from exc
    if not isinstance(value, dict):
        raise ProtocolError("invalid input: manifest must be an object")
    return value


def _revision(data: dict[str, Any] | None) -> int | None:
    if data is None or not isinstance(data.get("run"), dict):
        return None
    return data["run"].get("revision")


def _validate_append_only(existing: dict[str, Any], candidate: dict[str, Any]) -> None:
    for name in APPEND_ONLY_COLLECTIONS:
        old = existing.get(name, [])
        new = candidate.get(name, [])
        if not isinstance(new, list) or new[:len(old)] != old:
            raise ProtocolError(f"append-only collection changed: {name}")


def _validate_unknown_extensions_preserved(
    existing: dict[str, Any],
    candidate: dict[str, Any],
    registry: ExtensionRegistry | None,
) -> None:
    candidate_by_id = {
        item.get("id"): item for item in candidate.get("extensions", []) if isinstance(item, dict)
    }
    for item in existing.get("extensions", []):
        if not isinstance(item, dict):
            continue
        supported = False
        if registry is not None:
            status, _ = registry.resolve(item.get("namespace"), item.get("version"))
            supported = status == "supported"
        if not supported and candidate_by_id.get(item.get("id")) != item:
            raise ProtocolError(f"unknown extension changed: {item.get('id')}")


PolicyValidator = Callable[[Any], list[str]]


def initialize_manifest(
    path: str | Path,
    project_root: str,
    mode: str = "generate",
    autonomy: str = "explicit",
    replace_protocol_1: bool = False,
    timestamp: str | None = None,
    registry: Any = _AUTO_REGISTRY,
) -> dict[str, Any]:
    """Create fresh Protocol 2 state, optionally replacing exact Protocol 1 state."""
    resolved_registry = _resolve_registry(registry)
    manifest_path = Path(path)
    fresh = new_manifest(project_root, mode, autonomy, timestamp, resolved_registry)
    with _manifest_lock(manifest_path):
        if manifest_path.exists():
            existing = json.loads(manifest_path.read_text(encoding="utf-8"))
            if not isinstance(existing, dict):
                raise ProtocolError("existing manifest must be an object")
            version = existing.get("protocol_version")
            if version == "1.0":
                if not replace_protocol_1:
                    raise ProtocolError("existing Protocol 1 manifest requires replacement")
            else:
                raise ProtocolError(f"refusing to replace existing manifest with protocol_version {version!r}")

        saved = json.loads(json.dumps(fresh))
        saved["run"]["revision"] = 1
        saved["run"]["updated_at"] = timestamp or _utc_now()
        errors = validate_manifest(saved, resolved_registry) + validate_v2_policy(saved)
        if errors:
            raise ProtocolError("invalid input: " + "; ".join(errors))
        _atomic_write(manifest_path, saved)
        return saved


def save_manifest(
    path: str | Path,
    data: dict[str, Any],
    expected_revision: int | None,
    registry: Any = _AUTO_REGISTRY,
    timestamp: str | None = None,
    policy_validator: PolicyValidator | None = validate_v2_policy,
) -> dict[str, Any]:
    resolved_registry = _resolve_registry(registry)
    manifest_path = Path(path)
    with _manifest_lock(manifest_path):
        existing = load_manifest(manifest_path) if manifest_path.exists() else None
        if existing is not None:
            existing_errors = validate_manifest(existing, resolved_registry)
            if existing_errors:
                raise ProtocolError("invalid input: existing manifest: " + "; ".join(existing_errors))
        actual = _revision(existing)
        if actual != expected_revision:
            raise ProtocolError(f"revision conflict: expected {expected_revision}, found {actual}")
        supplied = _revision(data)
        required_supplied = 0 if existing is None else expected_revision
        if supplied != required_supplied:
            raise ProtocolError(f"candidate revision conflict: expected {required_supplied}, found {supplied}")
        candidate = json.loads(json.dumps(data))
        if existing is not None:
            _validate_append_only(existing, candidate)
            _validate_unknown_extensions_preserved(existing, candidate, resolved_registry)
        candidate["run"]["revision"] = 1 if existing is None else actual + 1
        candidate["run"]["updated_at"] = timestamp or _utc_now()
        errors = validate_manifest(candidate, resolved_registry)
        if policy_validator is not None:
            errors.extend(policy_validator(candidate))
        if errors:
            raise ProtocolError("invalid input: " + "; ".join(errors))
        _atomic_write(manifest_path, candidate)
        return candidate


def transition(
    path: str | Path,
    expected_revision: int,
    status: str,
    actions: list[dict[str, Any]],
    registry: Any = _AUTO_REGISTRY,
    timestamp: str | None = None,
) -> dict[str, Any]:
    resolved_registry = _resolve_registry(registry)
    existing = load_manifest(path)
    current = existing["run"]["status"]
    if status not in TRANSITIONS.get(current, set()):
        raise ProtocolError(f"invalid transition: {current} -> {status}")
    candidate = json.loads(json.dumps(existing))
    candidate["run"]["status"] = status
    candidate["actions"] = actions
    return save_manifest(path, candidate, expected_revision, resolved_registry, timestamp, validate_v2_policy)


def _atomic_write(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=path.parent,
        prefix=f".{path.name}.", suffix=".tmp", delete=False,
    ) as temporary:
        json.dump(data, temporary, indent=2, sort_keys=True)
        temporary.write("\n")
        temporary_path = temporary.name
    try:
        os.replace(temporary_path, path)
    except OSError:
        try:
            os.unlink(temporary_path)
        except OSError:
            pass
        raise


@contextmanager
def _manifest_lock(path: Path):
    lock_path = path.with_name(f".{path.name}.lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+b") as lock_file:
        _acquire_lock(lock_file)
        try:
            yield
        finally:
            _release_lock(lock_file)


def _acquire_lock(lock_file: Any) -> None:
    if os.name == "nt":
        lock_file.seek(0)
        lock_file.write(b"\0")
        lock_file.flush()
        lock_file.seek(0)
        msvcrt.locking(lock_file.fileno(), msvcrt.LK_LOCK, 1)
    else:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)


def _release_lock(lock_file: Any) -> None:
    if os.name == "nt":
        lock_file.seek(0)
        msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
    else:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="e2e_protocol.py")
    commands = parser.add_subparsers(dest="command", required=True)
    init = commands.add_parser("init")
    init.add_argument("--project-root", required=True)
    init.add_argument("--mode", default="generate")
    init.add_argument("--autonomy", default="explicit")
    init.add_argument("--output")
    init.add_argument(
        "--replace-protocol-1",
        action="store_true",
        help="atomically discard an existing Protocol 1 manifest and initialize Protocol 2",
    )
    validate = commands.add_parser("validate")
    validate.add_argument("manifest")
    move = commands.add_parser("transition")
    move.add_argument("manifest")
    move.add_argument("--expected-revision", type=int, required=True)
    move.add_argument("--status", required=True)
    move.add_argument("--actions")
    args = parser.parse_args(argv)
    try:
        if args.command == "init":
            output = Path(args.output) if args.output else Path(args.project_root) / ".e2e" / "manifest.json"
            result = initialize_manifest(
                output,
                args.project_root,
                args.mode,
                args.autonomy,
                replace_protocol_1=args.replace_protocol_1,
            )
        elif args.command == "validate":
            manifest = load_manifest(args.manifest)
            errors = validate_manifest(manifest) + validate_v2_policy(manifest)
            result = {"errors": errors}
            print(json.dumps(result))
            return 2 if errors else 0
        else:
            actions = []
            if args.actions:
                actions = json.loads(Path(args.actions).read_text(encoding="utf-8"))
            result = transition(args.manifest, args.expected_revision, args.status, actions)
    except ProtocolError as exc:
        print(str(exc), file=sys.stderr)
        return 3 if str(exc).startswith("revision conflict") else 2
    except (OSError, json.JSONDecodeError) as exc:
        print(f"invalid input: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
