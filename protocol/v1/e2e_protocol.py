"""Version 1 manifest protocol for end-to-end testing runs."""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import re
import sys
import tempfile
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any


class ProtocolError(Exception):
    """Raised when a manifest cannot be safely created or updated."""


TRANSITIONS = {
    "initialized": {"planned", "needs-clarification", "unsupported-framework", "protocol-incompatible"},
    "planned": {"ready-for-adapter", "needs-clarification", "blocked"},
    "ready-for-adapter": {"generated-unverified", "unsupported-framework", "blocked"},
    "generated-unverified": {"verifying", "needs-authorization", "blocked"},
    "verifying": {"verified", "repair-ready", "handoff-required", "needs-clarification", "needs-authorization", "blocked"},
    "repair-ready": {"generated-unverified", "blocked"},
    "handoff-required": {"verifying", "blocked"},
    "needs-authorization": {"verifying", "blocked"},
    "needs-clarification": {"planned", "blocked"},
    "verified": set(),
    "blocked": set(),
    "unsupported-framework": set(),
    "protocol-incompatible": set(),
}

MODES = {"plan", "generate", "verify", "repair"}
AUTONOMY_MODES = {"explicit", "auto"}
TARGET_TIERS = {"local", "ephemeral", "staging", "production", "unspecified"}
FORBIDDEN_SECRET_KEYS = {"password", "token", "api_key", "secret", "secret_value"}
ID_COLLECTIONS = (
    "journeys", "tests", "evidence", "conflicts", "attempt_history",
    "handoffs", "authorizations", "next_actions",
)
REQUIRED_FIELDS = (
    "protocol_version", "run_id", "revision", "mode", "autonomy", "status",
    "project", "target", "journeys", "tests", "evidence", "conflicts",
    "attempt_budget", "attempt_history", "handoffs", "authorizations", "next_actions",
)


def new_manifest(project_root: str, mode: str = "generate", autonomy: str = "explicit") -> dict[str, Any]:
    """Create a new, revision-zero manifest with safe defaults."""
    manifest = {
        "protocol_version": "1.0",
        "run_id": f"run-{uuid.uuid4()}",
        "revision": 0,
        "mode": mode,
        "autonomy": {"mode": autonomy, "auto_repair": autonomy == "auto"},
        "status": "initialized",
        "project": {"root": str(project_root), "framework": None},
        "target": {"tier": "unspecified", "base_url_ref": None, "credentials_ref": None},
        "journeys": [],
        "tests": [],
        "evidence": [],
        "conflicts": [],
        "attempt_budget": {"repair": 0, "verification": 1, "wall_clock_seconds": 1},
        "attempt_history": [],
        "handoffs": [],
        "authorizations": [],
        "next_actions": [],
    }
    errors = validate_manifest(manifest)
    if errors:
        raise ProtocolError("invalid input: " + "; ".join(errors))
    return manifest


def validate_manifest(data: Any) -> list[str]:
    """Return protocol-validation errors, without mutating *data*."""
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["manifest must be an object"]

    for field in REQUIRED_FIELDS:
        if field not in data:
            errors.append(f"missing required field: {field}")
    unexpected = set(data) - set(REQUIRED_FIELDS)
    errors.extend(f"unexpected top-level field: {field}" for field in sorted(unexpected))

    if data.get("protocol_version") != "1.0":
        errors.append("protocol_version must be 1.0")
    run_id = data.get("run_id")
    if not isinstance(run_id, str) or not re.fullmatch(r"run-[a-z0-9-]+", run_id):
        errors.append("run_id must match ^run-[a-z0-9-]+$")
    _integer_at_least(data.get("revision"), 0, "revision", errors)
    if data.get("mode") not in MODES:
        errors.append("mode is invalid")
    if data.get("status") not in TRANSITIONS:
        errors.append("status is invalid")

    _validate_autonomy(data.get("autonomy"), errors)
    _validate_project(data.get("project"), errors)
    _validate_target(data.get("target"), errors)
    _validate_budget(data.get("attempt_budget"), errors)
    _validate_collections(data, errors)
    _find_secret_keys(data, errors)
    return errors


def save_manifest(path: str | Path, data: dict[str, Any], expected_revision: int | None) -> dict[str, Any]:
    """Validate and atomically save *data* if its stored revision matches."""
    manifest_path = Path(path)
    with _manifest_lock(manifest_path):
        existing = _read_manifest(manifest_path) if manifest_path.exists() else None
        _check_revision(existing, expected_revision)

        saved = dict(data)
        saved["revision"] = 1 if existing is None else existing["revision"] + 1
        errors = validate_manifest(saved)
        if errors:
            raise ProtocolError("invalid input: " + "; ".join(errors))
        _atomic_write(manifest_path, saved)
    return saved


def transition(
    path: str | Path,
    expected_revision: int,
    status: str,
    next_actions: list[dict[str, Any]],
) -> dict[str, Any]:
    """Atomically move an existing manifest to an allowed next status."""
    manifest_path = Path(path)
    if not manifest_path.exists():
        raise ProtocolError("invalid input: manifest does not exist")
    existing = _read_manifest(manifest_path)
    _check_revision(existing, expected_revision)
    current_status = existing.get("status")
    if status not in TRANSITIONS.get(current_status, set()):
        raise ProtocolError(f"invalid transition: {current_status} -> {status}")

    updated = dict(existing)
    updated["status"] = status
    updated["next_actions"] = next_actions
    return save_manifest(manifest_path, updated, expected_revision)


def _integer_at_least(value: Any, minimum: int, name: str, errors: list[str]) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        errors.append(f"{name} must be an integer >= {minimum}")


def _validate_autonomy(value: Any, errors: list[str]) -> None:
    if not isinstance(value, dict):
        errors.append("autonomy must be an object")
        return
    if set(value) != {"mode", "auto_repair"}:
        errors.append("autonomy must contain only mode and auto_repair")
    if value.get("mode") not in AUTONOMY_MODES:
        errors.append("autonomy.mode is invalid")
    if not isinstance(value.get("auto_repair"), bool):
        errors.append("autonomy.auto_repair must be a boolean")


def _validate_project(value: Any, errors: list[str]) -> None:
    if not isinstance(value, dict):
        errors.append("project must be an object")
        return
    if not isinstance(value.get("root"), str):
        errors.append("project.root must be a string")
    if "framework" in value and value["framework"] is not None and not isinstance(value["framework"], str):
        errors.append("project.framework must be a string or null")


def _validate_target(value: Any, errors: list[str]) -> None:
    if not isinstance(value, dict):
        errors.append("target must be an object")
        return
    allowed = {"tier", "base_url_ref", "credentials_ref"}
    if set(value) - allowed:
        errors.append("target contains unsupported fields")
    if value.get("tier") not in TARGET_TIERS:
        errors.append("target.tier is invalid")
    for key in ("base_url_ref", "credentials_ref"):
        if key in value and value[key] is not None and not isinstance(value[key], str):
            errors.append(f"target.{key} must be a string or null")
    if "base_url_ref" not in value:
        errors.append("missing required field: target.base_url_ref")


def _validate_budget(value: Any, errors: list[str]) -> None:
    if not isinstance(value, dict):
        errors.append("attempt_budget must be an object")
        return
    if set(value) != {"repair", "verification", "wall_clock_seconds"}:
        errors.append("attempt_budget must contain repair, verification, and wall_clock_seconds")
    _integer_at_least(value.get("repair"), 0, "attempt_budget.repair", errors)
    _integer_at_least(value.get("verification"), 1, "attempt_budget.verification", errors)
    _integer_at_least(value.get("wall_clock_seconds"), 1, "attempt_budget.wall_clock_seconds", errors)


def _validate_collections(data: dict[str, Any], errors: list[str]) -> None:
    for name in ID_COLLECTIONS:
        items = data.get(name)
        if not isinstance(items, list):
            errors.append(f"{name} must be an array")
            continue
        ids: set[str] = set()
        for index, item in enumerate(items):
            if not isinstance(item, dict) or not isinstance(item.get("id"), str):
                errors.append(f"{name}[{index}] must have a string id")
                continue
            item_id = item["id"]
            if item_id in ids:
                errors.append(f"duplicate id in {name}: {item_id}")
            ids.add(item_id)
            if name == "journeys" and not isinstance(item.get("status"), str):
                errors.append(f"journeys[{index}] must have a string status")
            if name == "tests":
                if not isinstance(item.get("journey_id"), str):
                    errors.append(f"tests[{index}] must have a string journey_id")
                if not isinstance(item.get("status"), str):
                    errors.append(f"tests[{index}] must have a string status")
            if name == "next_actions":
                if not isinstance(item.get("capability"), str):
                    errors.append(f"next_actions[{index}] must have a string capability")
                if not isinstance(item.get("journey_ids"), list) or not all(isinstance(v, str) for v in item.get("journey_ids", [])):
                    errors.append(f"next_actions[{index}] must have string journey_ids")


def _find_secret_keys(value: Any, errors: list[str]) -> None:
    if isinstance(value, dict):
        for key, nested in value.items():
            if key.lower() in FORBIDDEN_SECRET_KEYS:
                errors.append(f"secret value key is forbidden: {key}")
            _find_secret_keys(nested, errors)
    elif isinstance(value, list):
        for nested in value:
            _find_secret_keys(nested, errors)


def _read_manifest(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ProtocolError(f"invalid input: cannot read manifest: {exc}") from exc
    if not isinstance(value, dict):
        raise ProtocolError("invalid input: manifest must be an object")
    return value


def _check_revision(existing: dict[str, Any] | None, expected_revision: int | None) -> None:
    actual = None if existing is None else existing.get("revision")
    if actual != expected_revision:
        raise ProtocolError(f"revision conflict: expected {expected_revision}, found {actual}")


def _atomic_write(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=path.parent, prefix=f".{path.name}.", suffix=".tmp", delete=False
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
    with lock_path.open("w", encoding="utf-8") as lock_file:
        fcntl.flock(lock_file, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock_file, fcntl.LOCK_UN)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="e2e_protocol.py")
    commands = parser.add_subparsers(dest="command", required=True)
    init = commands.add_parser("init")
    init.add_argument("--project-root", required=True)
    init.add_argument("--mode", default="generate")
    init.add_argument("--autonomy", default="explicit")
    init.add_argument("--output")
    validate = commands.add_parser("validate")
    validate.add_argument("manifest")
    move = commands.add_parser("transition")
    move.add_argument("manifest")
    move.add_argument("--expected-revision", type=int, required=True)
    move.add_argument("--status", required=True)
    move.add_argument("--next-actions")
    args = parser.parse_args(argv)

    try:
        if args.command == "init":
            manifest = new_manifest(args.project_root, args.mode, args.autonomy)
            output = Path(args.output) if args.output else Path(args.project_root) / ".e2e" / "manifest.json"
            result = save_manifest(output, manifest, None)
        elif args.command == "validate":
            result = {"errors": validate_manifest(_read_manifest(Path(args.manifest)))}
            if result["errors"]:
                print(json.dumps(result))
                return 2
        else:
            actions = []
            if args.next_actions:
                with open(args.next_actions, encoding="utf-8") as action_file:
                    actions = json.load(action_file)
            result = transition(args.manifest, args.expected_revision, args.status, actions)
    except ProtocolError as exc:
        print(str(exc), file=sys.stderr)
        return 3 if str(exc).startswith("revision conflict") else 2
    except (OSError, json.JSONDecodeError) as exc:
        print(f"invalid input: {exc}", file=sys.stderr)
        return 2

    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
