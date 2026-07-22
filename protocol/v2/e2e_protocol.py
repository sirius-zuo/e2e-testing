"""Protocol 2 kernel for portable end-to-end testing runs."""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from typing import Any


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


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def new_manifest(
    project_root: str,
    mode: str = "generate",
    autonomy: str = "explicit",
    timestamp: str | None = None,
) -> dict[str, Any]:
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
    errors = validate_manifest(manifest) + validate_v2_policy(manifest)
    if errors:
        raise ProtocolError("invalid input: " + "; ".join(errors))
    return manifest


def validate_manifest(data: Any, registry: Any = None) -> list[str]:
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
