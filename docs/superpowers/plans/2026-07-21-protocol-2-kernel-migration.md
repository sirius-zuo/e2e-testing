# Protocol 2 Kernel and Lossless Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the canonical Protocol 2 kernel and an explicit, deterministic, lossless Protocol 1 migration utility without changing the current V1 skills or browser behavior.

**Architecture:** Add a new canonical `protocol/v2` package beside the untouched V1 implementation. The V2 kernel owns the strict core manifest, semantic validation, extension compatibility, revision-safe persistence, and CLI; a separate migrator imports the legacy validator only while translating a V1 manifest into the V2 core plus `e2e.web` and immutable archive extensions. This subproject stops before bundling Protocol 2 into skills or renaming the web skill.

**Tech Stack:** Python 3 standard library, JSON Schema Draft 2020-12 documents, `unittest`, cross-platform file locks (`fcntl`/`msvcrt`), atomic `os.replace` writes.

## Global Constraints

- Work only in `/Users/jinzuo/projects/skills/e2e-testing`.
- Do not modify `protocol/v1/`, `skills/`, `evals/`, or the existing V1 tests in this subproject.
- E2E tests treat the system as a black box behind supported external boundaries; internal details cannot become acceptance oracles.
- Protocol 2 core meanings are stable through V6; add surface data through namespaced, versioned extensions.
- Protocol 2 structurally permits multiple systems and surfaces; the separate V2 atomic-run policy requires exactly one system and at most one primary surface.
- Unknown extension records remain byte-for-byte equivalent as JSON values across ordinary saves.
- Evidence and attempt history are append-only.
- Raw secrets are forbidden everywhere, including extension and archived migration data; reference fields remain allowed.
- Protocol 1 runtime compatibility is not required. Migration is explicit, lossless, deterministic, and never overwrites its source.
- Use only the Python standard library; add no runtime dependency.
- Follow TDD: observe every targeted test fail before adding its implementation.
- Run the full existing suite after every task; the verified baseline is 85 passing tests.

---

## File Structure

| Path | Responsibility |
| --- | --- |
| `protocol/v2/__init__.py` | Export the supported Protocol 2 public API. |
| `protocol/v2/e2e_protocol.py` | Core model, semantic validation, extension registry, persistence, transitions, and CLI. |
| `protocol/v2/migrate_v1.py` | Pure V1-to-V2 mapping, exact-source archival, atomic publication, and migration CLI. |
| `protocol/v2/manifest.schema.json` | Machine-readable Protocol 2 core and extension-envelope contract. |
| `protocol/v2/extensions/web.schema.json` | Minimal typed web extension produced by V1 migration and consumed by the later web-migration subproject. |
| `protocol/v2/README.md` | Canonical operating and migration commands plus compatibility rules. |
| `tests/test_protocol_v2.py` | Core creation, semantic validation, references, safety, persistence, transitions, and CLI tests. |
| `tests/test_protocol_v2_extensions.py` | Extension registration, version ranges, typed validation, and unknown-extension preservation tests. |
| `tests/test_protocol_v2_migration.py` | Lossless mapping, status translation, determinism, source preservation, rollback, and migration CLI tests. |
| `tests/test_protocol_v2_schema.py` | JSON Schema document integrity and vocabulary alignment tests without adding a schema-library dependency. |

## Manifest Contract Used by Every Task

The Protocol 2 top-level object has exactly these fields:

```python
REQUIRED_FIELDS = (
    "protocol_version",
    "run",
    "systems",
    "journeys",
    "execution_units",
    "checks",
    "evidence",
    "actions",
    "handoffs",
    "authorizations",
    "attempts",
    "extensions",
)
```

`new_manifest("/workspace/app", timestamp="2026-07-21T00:00:00Z")` returns:

```json
{
  "protocol_version": "2.0",
  "run": {
    "id": "run-<uuid>",
    "revision": 0,
    "mode": "generate",
    "autonomy": {"mode": "explicit", "auto_repair": false},
    "status": "initialized",
    "created_at": "2026-07-21T00:00:00Z",
    "updated_at": "2026-07-21T00:00:00Z",
    "attempt_budget": {"repair": 0, "verification": 1, "wall_clock_seconds": 300}
  },
  "systems": [{
    "id": "system-primary",
    "project_root": "/workspace/app",
    "primary_surface": null,
    "boundary": {
      "status": "unresolved",
      "actors": [],
      "public_interfaces": [],
      "evidence_ids": []
    },
    "target": {
      "tier": "unspecified",
      "endpoint_refs": [],
      "credential_refs": [],
      "mutation_policy": {"namespace_ref": null, "allowed_classes": []}
    }
  }],
  "journeys": [],
  "execution_units": [],
  "checks": [],
  "evidence": [],
  "actions": [],
  "handoffs": [],
  "authorizations": [],
  "attempts": [],
  "extensions": []
}
```

Core record objects require their documented linking fields but may preserve additional non-secret fields. The top-level object, `run`, the initial system boundary, target, mutation policy, and extension envelope are strict.

---

### Task 1: Protocol 2 initializer and core shape validation

**Files:**
- Create: `protocol/v2/__init__.py`
- Create: `protocol/v2/e2e_protocol.py`
- Create: `tests/test_protocol_v2.py`

**Interfaces:**
- Produces: `ProtocolError`, `new_manifest(project_root: str, mode: str = "generate", autonomy: str = "explicit", timestamp: str | None = None) -> dict[str, Any]`
- Produces: `validate_manifest(data: Any, registry: ExtensionRegistry | None = None) -> list[str]` for stable core validation; the `registry` argument is accepted now and implemented in Task 3.
- Produces: `validate_v2_policy(data: Any) -> list[str]` for the V2 one-system/one-surface constraint.
- Consumes: no V1 code.

- [ ] **Step 1: Write failing initializer tests**

Create `tests/test_protocol_v2.py`:

```python
import copy
import unittest

from protocol.v2.e2e_protocol import new_manifest, validate_manifest, validate_v2_policy


class ProtocolV2ShapeTests(unittest.TestCase):
    def test_new_manifest_has_strict_safe_defaults(self):
        manifest = new_manifest(
            "/workspace/app",
            timestamp="2026-07-21T00:00:00Z",
        )

        self.assertEqual(manifest["protocol_version"], "2.0")
        self.assertEqual(manifest["run"], {
            "id": manifest["run"]["id"],
            "revision": 0,
            "mode": "generate",
            "autonomy": {"mode": "explicit", "auto_repair": False},
            "status": "initialized",
            "created_at": "2026-07-21T00:00:00Z",
            "updated_at": "2026-07-21T00:00:00Z",
            "attempt_budget": {"repair": 0, "verification": 1, "wall_clock_seconds": 300},
        })
        self.assertEqual(len(manifest["systems"]), 1)
        self.assertEqual(manifest["systems"][0]["id"], "system-primary")
        self.assertEqual(manifest["systems"][0]["project_root"], "/workspace/app")
        self.assertIsNone(manifest["systems"][0]["primary_surface"])
        self.assertEqual(validate_manifest(manifest), [])
        self.assertEqual(validate_v2_policy(manifest), [])

    def test_invalid_mode_autonomy_and_top_level_field_are_rejected(self):
        manifest = new_manifest("/workspace/app", timestamp="2026-07-21T00:00:00Z")
        manifest["run"]["mode"] = "deploy"
        manifest["run"]["autonomy"]["mode"] = "unbounded"
        manifest["unexpected"] = True

        errors = validate_manifest(manifest)

        self.assertIn("unexpected top-level field: unexpected", errors)
        self.assertIn("run.mode is invalid", errors)
        self.assertIn("run.autonomy.mode is invalid", errors)

    def test_core_allows_multiple_systems_but_v2_policy_requires_one(self):
        manifest = new_manifest("/workspace/app", timestamp="2026-07-21T00:00:00Z")
        second = copy.deepcopy(manifest["systems"][0])
        second["id"] = "system-secondary"
        manifest["systems"].append(second)
        self.assertEqual(validate_manifest(manifest), [])
        self.assertIn("systems must contain exactly one system in V2", validate_v2_policy(manifest))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests and verify the import fails**

Run:

```bash
python3 -m unittest tests.test_protocol_v2 -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'protocol.v2'`.

- [ ] **Step 3: Implement the initializer and shape validator**

Create `protocol/v2/e2e_protocol.py` with the following public constants and functions. Keep validation helpers private.

```python
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
```

Create `protocol/v2/__init__.py`:

```python
"""Public Protocol 2 API."""

from .e2e_protocol import ProtocolError, new_manifest, validate_manifest, validate_v2_policy

__all__ = ["ProtocolError", "new_manifest", "validate_manifest", "validate_v2_policy"]
```

- [ ] **Step 4: Run the targeted and full suites**

Run:

```bash
python3 -m unittest tests.test_protocol_v2 -v
python3 -m unittest discover -s tests -v
```

Expected: 3 V2 tests pass; the full suite reports 88 tests and `OK`.

- [ ] **Step 5: Commit the initializer**

```bash
git add protocol/v2/__init__.py protocol/v2/e2e_protocol.py tests/test_protocol_v2.py
git commit -m "feat: add protocol 2 manifest kernel"
```

---

### Task 2: Cross-record validation, black-box policy, and secret safety

**Files:**
- Modify: `protocol/v2/e2e_protocol.py`
- Modify: `tests/test_protocol_v2.py`

**Interfaces:**
- Extends: `validate_manifest(data, registry=None)` with deterministic collection, reference, surface, and secret diagnostics.
- Produces: a V2 manifest policy that accepts zero or one execution unit, but rejects multiple systems or multiple primary surfaces.
- Consumes: Task 1 constants and manifest shape.

- [ ] **Step 1: Add failing semantic-validation tests**

Add these methods to `ProtocolV2ShapeTests`:

```python
    def test_cross_record_references_and_single_surface_are_enforced(self):
        manifest = new_manifest("/workspace/app", timestamp="2026-07-21T00:00:00Z")
        manifest["systems"][0]["primary_surface"] = "service"
        manifest["journeys"] = [{"id": "journey-order", "system_id": "missing", "status": "planned"}]
        manifest["execution_units"] = [
            {
                "id": "unit-service",
                "system_id": "system-primary",
                "surface": "service",
                "capability": "e2e-service",
                "extension_id": "extension-service",
                "status": "planned",
            },
            {
                "id": "unit-web",
                "system_id": "system-primary",
                "surface": "web",
                "capability": "e2e-web",
                "extension_id": "extension-web",
                "status": "planned",
            },
        ]
        manifest["checks"] = [{
            "id": "check-order",
            "journey_id": "journey-missing",
            "execution_unit_id": "unit-missing",
            "status": "generated",
        }]

        errors = validate_manifest(manifest) + validate_v2_policy(manifest)

        self.assertIn("journeys[0].system_id does not reference a registered system: missing", errors)
        self.assertIn("execution_units use more than one primary surface in V2", errors)
        self.assertIn("checks[0].journey_id does not reference a registered journey: journey-missing", errors)
        self.assertIn("checks[0].execution_unit_id does not reference a registered execution unit: unit-missing", errors)

    def test_public_interfaces_require_boundary_evidence_and_external_kind(self):
        manifest = new_manifest("/workspace/app", timestamp="2026-07-21T00:00:00Z")
        manifest["systems"][0]["boundary"] = {
            "status": "declared",
            "actors": ["consumer"],
            "public_interfaces": [{
                "id": "interface-orders",
                "kind": "database",
                "endpoint_ref": "db-ref",
                "evidence_ids": ["missing"],
            }],
            "evidence_ids": ["missing"],
        }

        errors = validate_manifest(manifest)

        self.assertIn("systems[0].boundary.public_interfaces[0].kind is invalid", errors)
        self.assertIn("systems[0].boundary.evidence_ids contains an unknown evidence ID: missing", errors)

    def test_duplicate_ids_and_raw_secrets_are_rejected_everywhere(self):
        manifest = new_manifest("/workspace/app", timestamp="2026-07-21T00:00:00Z")
        manifest["journeys"] = [
            {"id": "journey-a", "system_id": "system-primary", "status": "planned"},
            {"id": "journey-a", "system_id": "system-primary", "status": "planned"},
        ]
        manifest["extensions"] = [{
            "id": "extension-service",
            "namespace": "e2e.service",
            "version": "1.0",
            "owner": "e2e-service",
            "data": {"accessToken": "plaintext"},
        }]

        errors = validate_manifest(manifest)

        self.assertIn("duplicate id in journeys: journey-a", errors)
        self.assertIn("secret value key is forbidden: accessToken", errors)

    def test_reference_keys_are_allowed(self):
        manifest = new_manifest("/workspace/app", timestamp="2026-07-21T00:00:00Z")
        manifest["extensions"] = [{
            "id": "extension-service",
            "namespace": "e2e.service",
            "version": "1.0",
            "owner": "e2e-service",
            "data": {"token_ref": "vault://service-token", "credentials_ref": "vault://credentials"},
        }]
        self.assertEqual(validate_manifest(manifest), [])

    def test_system_boundary_target_and_timestamps_are_strict(self):
        manifest = new_manifest("/workspace/app", timestamp="2026-07-21T00:00:00Z")
        manifest["run"]["created_at"] = 42
        manifest["systems"][0]["extra"] = True
        manifest["systems"][0]["boundary"]["extra"] = True
        manifest["systems"][0]["target"]["extra"] = True
        manifest["systems"][0]["target"]["mutation_policy"]["extra"] = True
        errors = validate_manifest(manifest)
        self.assertIn("run.created_at must be an RFC3339 string or null", errors)
        self.assertIn("systems[0] fields are invalid", errors)
        self.assertIn("systems[0].boundary fields are invalid", errors)
        self.assertIn("systems[0].target fields are invalid", errors)
        self.assertIn("systems[0].target.mutation_policy fields are invalid", errors)

    def test_migrated_runs_may_preserve_unknown_legacy_timestamps_as_null(self):
        manifest = new_manifest("/workspace/app", timestamp="2026-07-21T00:00:00Z")
        manifest["run"]["created_at"] = None
        manifest["run"]["updated_at"] = None
        self.assertEqual(validate_manifest(manifest), [])

    def test_evidence_classification_and_handoff_references_resolve(self):
        manifest = new_manifest("/workspace/app", timestamp="2026-07-21T00:00:00Z")
        manifest["journeys"] = [{"id": "journey-a", "system_id": "system-primary", "status": "failed"}]
        manifest["evidence"] = [{
            "id": "evidence-classification",
            "classification": {"evidence_ids": ["evidence-missing"]},
            "artifacts": [{"id": "artifact-log"}],
        }]
        manifest["handoffs"] = [{
            "id": "handoff-a", "journey_ids": ["journey-a"],
            "evidence_ids": ["evidence-missing"], "artifact_refs": ["artifact-missing"],
        }]
        errors = validate_manifest(manifest)
        self.assertIn("evidence[0].classification.evidence_ids contains an unknown evidence ID: evidence-missing", errors)
        self.assertIn("handoffs[0].evidence_ids contains an unknown evidence ID: evidence-missing", errors)
        self.assertIn("handoffs[0].artifact_refs contains an unknown artifact ID: artifact-missing", errors)
```

- [ ] **Step 2: Run the new tests and verify semantic failures**

Run:

```bash
python3 -m unittest tests.test_protocol_v2.ProtocolV2ShapeTests -v
```

Expected: the seven new tests FAIL because reference, strict-envelope, timestamp, duplicate-ID, and secret validation do not exist.

- [ ] **Step 3: Implement collection and reference validation**

Add these constants and call the helpers at the end of `validate_manifest`:

```python
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

# At the end of validate_manifest:
    _validate_collections_and_references(data, errors)
    _validate_boundary_references(data, errors)
    _find_secret_keys(data, errors)
```

Implement the helpers with these exact rules:

```python
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

    for name in ("actions", "handoffs"):
        items = data.get(name) if isinstance(data.get(name), list) else []
        for index, item in enumerate(items):
            if isinstance(item, dict) and "journey_ids" in item:
                values = item["journey_ids"]
                if not isinstance(values, list) or not all(isinstance(value, str) for value in values):
                    errors.append(f"{name}[{index}].journey_ids must be an array of strings")
                else:
                    for value in values:
                        if value not in ids["journeys"]:
                            errors.append(f"{name}[{index}].journey_ids contains an unknown journey: {value}")


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
```

Call `_validate_evidence_references(data, errors)` after boundary reference validation. Add these exact strict checks inside `_validate_systems` after `system`, `boundary`, and `target` are resolved:

```python
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
```

Add to `_validate_run`:

```python
    for field in ("created_at", "updated_at"):
        timestamp = value.get(field)
        if timestamp is not None and (
            not isinstance(timestamp, str)
            or not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[^ ]+Z", timestamp)
        ):
            errors.append(f"run.{field} must be an RFC3339 string or null")
```

Replace the combined action/handoff loop with exact per-collection requirements:

```python
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
```

Do not add `database` to `PUBLIC_INTERFACE_KINDS`. Database access is auxiliary and cannot become the public acceptance boundary.

- [ ] **Step 4: Run targeted and full suites**

```bash
python3 -m unittest tests.test_protocol_v2 -v
python3 -m unittest discover -s tests -v
```

Expected: 10 V2 tests pass; full suite reports 95 tests and `OK`.

- [ ] **Step 5: Commit semantic validation**

```bash
git add protocol/v2/e2e_protocol.py tests/test_protocol_v2.py
git commit -m "feat: validate protocol 2 relationships"
```

---

### Task 3: Versioned extension registry and unknown-extension preservation

**Files:**
- Modify: `protocol/v2/e2e_protocol.py`
- Modify: `protocol/v2/__init__.py`
- Create: `tests/test_protocol_v2_extensions.py`

**Interfaces:**
- Produces: `ExtensionSupport(namespace: str, minimum_version: str, maximum_version: str, validator: Callable[[Any], list[str]])`.
- Produces: `ExtensionRegistry.register(support)`, `resolve(namespace, version)`, and `validate(extension)`.
- Produces: `extension_issues(manifest, registry) -> list[dict[str, str]]` with `capability-unavailable` and `extension-incompatible` statuses.
- Extends: `validate_manifest(..., registry)` to validate only recognized compatible extension data.

- [ ] **Step 1: Write failing extension tests**

Create `tests/test_protocol_v2_extensions.py`:

```python
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
```

- [ ] **Step 2: Run and verify missing extension APIs**

```bash
python3 -m unittest tests.test_protocol_v2_extensions -v
```

Expected: FAIL importing `ExtensionRegistry`.

- [ ] **Step 3: Implement extension versions and registry**

Add imports:

```python
from dataclasses import dataclass
from typing import Any, Callable
```

Add the extension types and functions:

```python
ExtensionValidator = Callable[[Any], list[str]]


def _version_tuple(value: str) -> tuple[int, int]:
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]+\.[0-9]+", value):
        raise ValueError(f"invalid extension version: {value}")
    major, minor = value.split(".")
    return int(major), int(minor)


@dataclass(frozen=True)
class ExtensionSupport:
    namespace: str
    minimum_version: str
    maximum_version: str
    validator: ExtensionValidator

    def contains(self, version: str) -> bool:
        return _version_tuple(self.minimum_version) <= _version_tuple(version) <= _version_tuple(self.maximum_version)


class ExtensionRegistry:
    def __init__(self) -> None:
        self._supports: dict[str, list[ExtensionSupport]] = {}

    def register(self, support: ExtensionSupport) -> None:
        minimum = _version_tuple(support.minimum_version)
        maximum = _version_tuple(support.maximum_version)
        if minimum > maximum:
            raise ValueError("extension support minimum exceeds maximum")
        entries = self._supports.setdefault(support.namespace, [])
        for existing in entries:
            if minimum <= _version_tuple(existing.maximum_version) and _version_tuple(existing.minimum_version) <= maximum:
                raise ValueError(f"overlapping extension support: {support.namespace}")
        entries.append(support)

    def resolve(self, namespace: str, version: str) -> tuple[str, ExtensionSupport | None]:
        entries = self._supports.get(namespace)
        if not entries:
            return "capability-unavailable", None
        try:
            for support in entries:
                if support.contains(version):
                    return "supported", support
        except ValueError:
            return "extension-incompatible", None
        return "extension-incompatible", None

    def validate(self, extension: dict[str, Any]) -> list[str]:
        status, support = self.resolve(extension["namespace"], extension["version"])
        return [] if status != "supported" or support is None else support.validator(extension["data"])


def extension_issues(data: dict[str, Any], registry: ExtensionRegistry) -> list[dict[str, str]]:
    issues = []
    for extension in data.get("extensions", []):
        if not isinstance(extension, dict):
            continue
        namespace = extension.get("namespace")
        version = extension.get("version")
        if not isinstance(namespace, str) or not isinstance(version, str):
            continue
        status, _ = registry.resolve(namespace, version)
        if status != "supported":
            issues.append({
                "extension_id": extension.get("id", ""),
                "namespace": namespace,
                "version": version,
                "status": status,
            })
    return issues
```

Add `_validate_extension_envelopes(data, errors, registry)` to core validation:

```python
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
```

Call it before `_find_secret_keys`. Unknown and incompatible extensions remain valid core data and are reported only by `extension_issues`.

Export the new API from `protocol/v2/__init__.py`:

```python
from .e2e_protocol import (
    ExtensionRegistry,
    ExtensionSupport,
    ProtocolError,
    extension_issues,
    new_manifest,
    validate_manifest,
    validate_v2_policy,
)

__all__ = [
    "ExtensionRegistry", "ExtensionSupport", "ProtocolError",
    "extension_issues", "new_manifest", "validate_manifest", "validate_v2_policy",
]
```

- [ ] **Step 4: Run targeted and full suites**

```bash
python3 -m unittest tests.test_protocol_v2_extensions -v
python3 -m unittest discover -s tests -v
```

Expected: 5 extension tests pass; full suite reports 100 tests and `OK`.

- [ ] **Step 5: Commit extension compatibility**

```bash
git add protocol/v2/__init__.py protocol/v2/e2e_protocol.py tests/test_protocol_v2_extensions.py
git commit -m "feat: add protocol 2 extension registry"
```

---

### Task 4: Revision-safe storage, append-only history, transitions, and core CLI

**Files:**
- Modify: `protocol/v2/e2e_protocol.py`
- Modify: `protocol/v2/__init__.py`
- Modify: `tests/test_protocol_v2.py`
- Modify: `tests/test_protocol_v2_extensions.py`

**Interfaces:**
- Produces: `load_manifest(path) -> dict[str, Any]`.
- Produces: `save_manifest(path, data, expected_revision, registry=None, timestamp=None) -> dict[str, Any]`.
- Produces: `transition(path, expected_revision, status, actions, registry=None, timestamp=None) -> dict[str, Any]`.
- Produces CLI commands: `init`, `validate`, and `transition`.
- Preserves: evidence and attempts as immutable sequence prefixes; unknown extensions unless their namespace/version is supported by the supplied registry.

- [ ] **Step 1: Add failing persistence and CLI tests**

Extend imports in `tests/test_protocol_v2.py` with `json`, `multiprocessing`, `subprocess`, `sys`, `tempfile`, `time`, `Path`, and:

```python
from protocol.v2.e2e_protocol import (
    ProtocolError,
    _manifest_lock,
    load_manifest,
    new_manifest,
    save_manifest,
    transition,
    validate_manifest,
)

PROTOCOL_V2_SCRIPT = Path(__file__).parents[1] / "protocol" / "v2" / "e2e_protocol.py"


def _transition_v2_in_process(path, started, result):
    started.put(None)
    try:
        result.put(("saved", transition(path, 1, "planned", [])))
    except ProtocolError as error:
        result.put(("error", str(error)))
```

Add a new `ProtocolV2PersistenceTests` class:

```python
class ProtocolV2PersistenceTests(unittest.TestCase):
    def test_save_increments_nested_revision_and_rejects_stale_writer(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / ".e2e" / "manifest.json"
            saved = save_manifest(
                path,
                new_manifest(tmp, timestamp="2026-07-21T00:00:00Z"),
                expected_revision=None,
                timestamp="2026-07-21T00:00:01Z",
            )
            self.assertEqual(saved["run"]["revision"], 1)
            moved = transition(
                path, 1, "planned", [], timestamp="2026-07-21T00:00:02Z",
            )
            self.assertEqual(moved["run"]["revision"], 2)
            with self.assertRaisesRegex(ProtocolError, "revision conflict"):
                transition(path, 1, "ready-for-adapter", [])

    def test_evidence_and_attempts_cannot_be_rewritten_or_removed(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "manifest.json"
            initial = new_manifest(tmp, timestamp="2026-07-21T00:00:00Z")
            initial["evidence"] = [{"id": "evidence-a", "kind": "source-derived"}]
            initial["attempts"] = [{"id": "attempt-a", "status": "recorded"}]
            saved = save_manifest(path, initial, None, timestamp="2026-07-21T00:00:01Z")
            candidate = json.loads(json.dumps(saved))
            candidate["evidence"][0]["kind"] = "rewritten"
            candidate["attempts"] = []

            with self.assertRaisesRegex(ProtocolError, "append-only collection changed: evidence"):
                save_manifest(path, candidate, 1)

            attempts_only = json.loads(json.dumps(saved))
            attempts_only["attempts"] = []
            with self.assertRaisesRegex(ProtocolError, "append-only collection changed: attempts"):
                save_manifest(path, attempts_only, 1)

    def test_candidate_revision_must_match_the_revision_it_consumed(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "manifest.json"
            saved = save_manifest(path, new_manifest(tmp, timestamp="2026-07-21T00:00:00Z"), None)
            candidate = json.loads(json.dumps(saved))
            candidate["run"]["revision"] = 0
            with self.assertRaisesRegex(ProtocolError, "candidate revision conflict"):
                save_manifest(path, candidate, expected_revision=1)

    def test_cli_init_validate_and_transition(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "manifest.json"
            initialized = subprocess.run(
                [sys.executable, str(PROTOCOL_V2_SCRIPT), "init", "--project-root", tmp, "--output", str(path)],
                text=True, capture_output=True, check=False,
            )
            self.assertEqual(initialized.returncode, 0, initialized.stderr)
            self.assertEqual(json.loads(initialized.stdout)["protocol_version"], "2.0")

            validated = subprocess.run(
                [sys.executable, str(PROTOCOL_V2_SCRIPT), "validate", str(path)],
                text=True, capture_output=True, check=False,
            )
            self.assertEqual(validated.returncode, 0, validated.stderr)
            self.assertEqual(json.loads(validated.stdout), {"errors": []})

    def test_save_waits_for_the_manifest_lock(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "manifest.json"
            save_manifest(path, new_manifest(tmp, timestamp="2026-07-21T00:00:00Z"), None)
            with _manifest_lock(path):
                context = multiprocessing.get_context("spawn")
                started = context.Queue()
                result = context.Queue()
                process = context.Process(target=_transition_v2_in_process, args=(str(path), started, result))
                process.start()
                started.get(timeout=5)
                time.sleep(0.2)
                self.assertEqual(load_manifest(path)["run"]["revision"], 1)
            outcome, value = result.get(timeout=5)
            process.join(timeout=5)
            self.assertEqual(process.exitcode, 0)
            self.assertEqual(outcome, "saved")
            self.assertEqual(value["run"]["revision"], 2)
```

- [ ] **Step 2: Run and verify the missing persistence API**

```bash
python3 -m unittest tests.test_protocol_v2.ProtocolV2PersistenceTests -v
```

Expected: FAIL importing `save_manifest`.

- [ ] **Step 3: Port atomic storage around the nested V2 run record**

Add `argparse`, `json`, `os`, `sys`, `tempfile`, `contextmanager`, and `Path` imports. Import `msvcrt` on Windows and `fcntl` elsewhere. Define V2 transitions:

```python
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
```

Make `_validate_run` reject a status outside `TRANSITIONS`. Add these persistence functions:

```python
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


def save_manifest(
    path: str | Path,
    data: dict[str, Any],
    expected_revision: int | None,
    registry: ExtensionRegistry | None = None,
    timestamp: str | None = None,
    policy_validator: PolicyValidator | None = validate_v2_policy,
) -> dict[str, Any]:
    manifest_path = Path(path)
    with _manifest_lock(manifest_path):
        existing = load_manifest(manifest_path) if manifest_path.exists() else None
        if existing is not None:
            existing_errors = validate_manifest(existing, registry)
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
            _validate_unknown_extensions_preserved(existing, candidate, registry)
        candidate["run"]["revision"] = 1 if existing is None else actual + 1
        candidate["run"]["updated_at"] = timestamp or _utc_now()
        errors = validate_manifest(candidate, registry)
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
    registry: ExtensionRegistry | None = None,
    timestamp: str | None = None,
) -> dict[str, Any]:
    existing = load_manifest(path)
    current = existing["run"]["status"]
    if status not in TRANSITIONS.get(current, set()):
        raise ProtocolError(f"invalid transition: {current} -> {status}")
    candidate = json.loads(json.dumps(existing))
    candidate["run"]["status"] = status
    candidate["actions"] = actions
    return save_manifest(path, candidate, expected_revision, registry, timestamp, validate_v2_policy)
```

Add the exact cross-platform storage primitives to `protocol/v2/e2e_protocol.py`:

```python
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
```

- [ ] **Step 4: Add the core CLI**

Add the complete core CLI:

```python
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
    move.add_argument("--actions")
    args = parser.parse_args(argv)
    try:
        if args.command == "init":
            manifest = new_manifest(args.project_root, args.mode, args.autonomy)
            output = Path(args.output) if args.output else Path(args.project_root) / ".e2e" / "manifest.json"
            result = save_manifest(output, manifest, None)
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
```

Export `load_manifest`, `save_manifest`, and `transition` from `protocol/v2/__init__.py`.

- [ ] **Step 5: Run targeted and full suites**

```bash
python3 -m unittest tests.test_protocol_v2.ProtocolV2PersistenceTests -v
python3 -m unittest discover -s tests -v
```

Before running the suite, extend `tests/test_protocol_v2_extensions.py` imports with `json`, `tempfile`, `Path`, `ProtocolError`, and `save_manifest`, then add:

```python
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
```

Expected: 5 persistence tests and 2 extension-persistence tests pass; full suite reports 107 tests and `OK`.

- [ ] **Step 6: Commit persistence and CLI**

```bash
git add protocol/v2/__init__.py protocol/v2/e2e_protocol.py tests/test_protocol_v2.py tests/test_protocol_v2_extensions.py
git commit -m "feat: persist protocol 2 manifests safely"
```

---

### Task 5: Pure lossless Protocol 1 mapping

**Files:**
- Create: `protocol/v2/migrate_v1.py`
- Create: `protocol/v2/extensions/web.schema.json`
- Create: `tests/test_protocol_v2_migration.py`

**Interfaces:**
- Produces: `migrate_manifest(source: dict[str, Any]) -> dict[str, Any]`, a pure deterministic function.
- Produces: `source_sha256(source) -> str`, using canonical sorted compact JSON.
- Consumes: `protocol.v1.e2e_protocol.validate_manifest` only inside the migration module.
- Produces migration extensions: `e2e.web` version `1.0` and `e2e.protocol1.archive` version `1.0`.

- [ ] **Step 1: Write failing mapping tests**

Create `tests/test_protocol_v2_migration.py`:

```python
import copy
import json
import unittest

from protocol.v1.e2e_protocol import new_manifest as new_v1_manifest
from protocol.v2.e2e_protocol import validate_manifest
from protocol.v2.migrate_v1 import migrate_manifest, source_sha256


def complete_v1_manifest():
    source = new_v1_manifest("/workspace/app", mode="verify", autonomy="auto")
    source["run_id"] = "run-migration-fixture"
    source["revision"] = 7
    source["status"] = "verifying"
    source["project"] = {"root": "/workspace/app", "framework": "playwright", "language": "typescript"}
    source["target"] = {
        "tier": "staging",
        "base_url_ref": "env:E2E_BASE_URL",
        "credentials_ref": "vault://e2e-user",
    }
    source["journeys"] = [{"id": "journey-login", "status": "verifying", "goal": "Sign in"}]
    source["tests"] = [{
        "id": "test-login", "journey_id": "journey-login", "status": "generated",
        "path": "tests/login.spec.ts",
    }]
    source["evidence"] = [{"id": "evidence-source", "kind": "source-derived"}]
    source["conflicts"] = [{"id": "conflict-copy", "status": "resolved"}]
    source["attempt_history"] = [{"id": "attempt-verify", "status": "failed"}]
    source["handoffs"] = [{"id": "handoff-env", "journey_ids": ["journey-login"]}]
    source["authorizations"] = [{"id": "authorization-staging", "status": "approved"}]
    source["next_actions"] = [{
        "id": "action-verify", "capability": "e2e-web-playwright",
        "journey_ids": ["journey-login"],
    }]
    return source


class ProtocolV2MigrationMappingTests(unittest.TestCase):
    def test_complete_v1_manifest_maps_losslessly_and_validates(self):
        source = complete_v1_manifest()
        original = copy.deepcopy(source)
        migrated = migrate_manifest(source)

        self.assertEqual(source, original)
        self.assertEqual(migrated["protocol_version"], "2.0")
        self.assertEqual(migrated["run"]["id"], source["run_id"])
        self.assertEqual(migrated["run"]["revision"], 7)
        self.assertEqual(migrated["run"]["status"], "verifying")
        self.assertEqual(migrated["journeys"][0]["id"], "journey-login")
        self.assertEqual(migrated["checks"][0]["id"], "test-login")
        self.assertEqual(migrated["attempts"], source["attempt_history"])
        self.assertEqual(migrated["actions"][0]["capability"], "e2e-web")
        migration_evidence = next(item for item in migrated["evidence"] if item.get("kind") == "protocol-migration")
        self.assertEqual(migration_evidence["source_revision"], 7)
        self.assertEqual(migration_evidence["source_sha256"], source_sha256(original))
        archive = next(item for item in migrated["extensions"] if item["namespace"] == "e2e.protocol1.archive")
        self.assertEqual(archive["data"]["source_manifest"], original)
        self.assertEqual(archive["data"]["source_sha256"], source_sha256(original))
        self.assertEqual(validate_manifest(migrated), [])

    def test_mapping_is_deterministic(self):
        source = complete_v1_manifest()
        self.assertEqual(migrate_manifest(source), migrate_manifest(copy.deepcopy(source)))

    def test_legacy_terminal_statuses_are_translated_and_recorded(self):
        source = complete_v1_manifest()
        source["status"] = "unsupported-framework"
        migrated = migrate_manifest(source)
        self.assertEqual(migrated["run"]["status"], "capability-unavailable")
        archive = next(item for item in migrated["extensions"] if item["namespace"] == "e2e.protocol1.archive")
        self.assertEqual(archive["data"]["status_translation"], {
            "source": "unsupported-framework", "target": "capability-unavailable",
        })

    def test_invalid_v1_input_is_rejected(self):
        source = complete_v1_manifest()
        source["protocol_version"] = "0.9"
        with self.assertRaisesRegex(ValueError, "invalid Protocol 1 manifest"):
            migrate_manifest(source)
```

- [ ] **Step 2: Run and verify migration import failure**

```bash
python3 -m unittest tests.test_protocol_v2_migration.ProtocolV2MigrationMappingTests -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'protocol.v2.migrate_v1'`.

- [ ] **Step 3: Implement deterministic mapping**

Create `protocol/v2/migrate_v1.py` with these mappings:

```python
"""Explicit lossless migration from Protocol 1 to Protocol 2."""

from __future__ import annotations

import copy
import hashlib
import json
from typing import Any

from protocol.v1.e2e_protocol import validate_manifest as validate_v1_manifest
from protocol.v2.e2e_protocol import ProtocolError, new_manifest, validate_manifest, validate_v2_policy


STATUS_MAP = {
    "unsupported-framework": "capability-unavailable",
    "protocol-incompatible": "extension-incompatible",
}


def source_sha256(source: dict[str, Any]) -> str:
    encoded = json.dumps(source, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def migrate_manifest(source: dict[str, Any]) -> dict[str, Any]:
    source_copy = copy.deepcopy(source)
    source_errors = validate_v1_manifest(source_copy)
    if source_errors:
        raise ValueError("invalid Protocol 1 manifest: " + "; ".join(source_errors))

    project = source_copy["project"]
    target = source_copy["target"]
    result = new_manifest(project["root"], mode=source_copy["mode"], autonomy=source_copy["autonomy"]["mode"], timestamp="1970-01-01T00:00:00Z")
    mapped_status = STATUS_MAP.get(source_copy["status"], source_copy["status"])
    result["run"] = {
        "id": source_copy["run_id"],
        "revision": source_copy["revision"],
        "mode": source_copy["mode"],
        "autonomy": copy.deepcopy(source_copy["autonomy"]),
        "status": mapped_status,
        "created_at": None,
        "updated_at": None,
        "attempt_budget": copy.deepcopy(source_copy["attempt_budget"]),
    }

    interface = {
        "id": "interface-web-primary",
        "kind": "web",
        "endpoint_ref": target.get("base_url_ref"),
        "evidence_ids": [],
    }
    result["systems"] = [{
        "id": "system-primary",
        "project_root": project["root"],
        "primary_surface": "web",
        "boundary": {
            "status": "needs-clarification",
            "actors": [],
            "public_interfaces": [interface],
            "evidence_ids": [],
        },
        "target": {
            "tier": target["tier"],
            "endpoint_refs": [] if target.get("base_url_ref") is None else [target["base_url_ref"]],
            "credential_refs": [] if target.get("credentials_ref") is None else [target["credentials_ref"]],
            "mutation_policy": {"namespace_ref": None, "allowed_classes": []},
        },
    }]
    result["journeys"] = [
        {**copy.deepcopy(item), "system_id": "system-primary"}
        for item in source_copy["journeys"]
    ]
    result["execution_units"] = [{
        "id": "execution-web-primary",
        "system_id": "system-primary",
        "surface": "web",
        "capability": "e2e-web",
        "extension_id": "extension-web-primary",
        "status": mapped_status,
    }]
    result["checks"] = [
        {**copy.deepcopy(item), "execution_unit_id": "execution-web-primary"}
        for item in source_copy["tests"]
    ]
    result["evidence"] = copy.deepcopy(source_copy["evidence"])
    result["actions"] = copy.deepcopy(source_copy["next_actions"])
    for action in result["actions"]:
        if action.get("capability") == "e2e-web-playwright":
            action["capability"] = "e2e-web"
    result["handoffs"] = copy.deepcopy(source_copy["handoffs"])
    for handoff in result["handoffs"]:
        resume = handoff.get("resume")
        if isinstance(resume, dict) and isinstance(resume.get("command"), str):
            resume["command"] = resume["command"].replace("e2e-web-playwright", "e2e-web")
    result["authorizations"] = copy.deepcopy(source_copy["authorizations"])
    result["attempts"] = copy.deepcopy(source_copy["attempt_history"])
    digest = source_sha256(source_copy)
    existing_evidence_ids = {item.get("id") for item in result["evidence"] if isinstance(item, dict)}
    evidence_id = f"evidence-migration-protocol1-{digest}"
    counter = 2
    while evidence_id in existing_evidence_ids:
        evidence_id = f"evidence-migration-protocol1-{digest}-{counter}"
        counter += 1
    result["evidence"].append({
        "id": evidence_id,
        "kind": "protocol-migration",
        "source_protocol": "1.0",
        "source_revision": source_copy["revision"],
        "source_sha256": digest,
        "archive_extension_id": "extension-protocol1-archive",
    })
    result["extensions"] = [
        {
            "id": "extension-web-primary",
            "namespace": "e2e.web",
            "version": "1.0",
            "owner": "e2e-web",
            "data": {
                "driver": project.get("framework"),
                "project": copy.deepcopy(project),
                "target": copy.deepcopy(target),
            },
        },
        {
            "id": "extension-protocol1-archive",
            "namespace": "e2e.protocol1.archive",
            "version": "1.0",
            "owner": "e2e-testing",
            "data": {
                "source_sha256": digest,
                "source_manifest": source_copy,
                "status_translation": {"source": source_copy["status"], "target": mapped_status},
                "capability_translation": {"source": "e2e-web-playwright", "target": "e2e-web"},
                "conflicts": copy.deepcopy(source_copy["conflicts"]),
            },
        },
    ]
    errors = validate_manifest(result) + validate_v2_policy(result)
    if errors:
        raise ProtocolError("invalid migrated manifest: " + "; ".join(errors))
    return result
```

Adjust Task 1 validation so `run.created_at` and `run.updated_at` accept either an RFC3339 string or `None`; migrated manifests must not invent legacy timestamps.

Create `protocol/v2/extensions/web.schema.json`:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "urn:e2e-testing:extension:web:1.0",
  "title": "E2E Web Surface Extension",
  "type": "object",
  "additionalProperties": false,
  "required": ["driver", "project", "target"],
  "properties": {
    "driver": {"type": ["string", "null"]},
    "project": {"type": "object"},
    "target": {"type": "object"}
  }
}
```

- [ ] **Step 4: Run mapping and full tests**

```bash
python3 -m unittest tests.test_protocol_v2_migration.ProtocolV2MigrationMappingTests -v
python3 -m unittest discover -s tests -v
```

Expected: 4 migration mapping tests pass; full suite reports 111 tests and `OK`.

- [ ] **Step 5: Commit pure migration**

```bash
git add protocol/v2/migrate_v1.py protocol/v2/extensions/web.schema.json tests/test_protocol_v2_migration.py
git commit -m "feat: map protocol 1 manifests losslessly"
```

---

### Task 6: Atomic migration publication and explicit CLI

**Files:**
- Modify: `protocol/v2/migrate_v1.py`
- Modify: `tests/test_protocol_v2_migration.py`

**Interfaces:**
- Produces: `migrate_file(source_path: str | Path, target_path: str | Path) -> dict[str, Any]`.
- Produces CLI: `python3 -m protocol.v2.migrate_v1 SOURCE --output TARGET`.
- Guarantees: source bytes unchanged; absent target created atomically with preserved source revision; identical rerun succeeds without rewriting; divergent existing target fails.

- [ ] **Step 1: Add failing file and CLI tests**

Add imports `subprocess`, `sys`, `tempfile`, and `Path`; import `migrate_file`. Add:

```python
class ProtocolV2MigrationFileTests(unittest.TestCase):
    def test_migration_preserves_source_and_publishes_exact_revision(self):
        with tempfile.TemporaryDirectory() as tmp:
            source_path = Path(tmp) / "v1.json"
            target_path = Path(tmp) / "v2.json"
            source = complete_v1_manifest()
            source_path.write_text(json.dumps(source, indent=2) + "\n")
            source_bytes = source_path.read_bytes()

            migrated = migrate_file(source_path, target_path)

            self.assertEqual(source_path.read_bytes(), source_bytes)
            self.assertEqual(json.loads(target_path.read_text()), migrated)
            self.assertEqual(migrated["run"]["revision"], 7)

    def test_identical_rerun_is_idempotent_but_divergent_target_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            source_path = Path(tmp) / "v1.json"
            target_path = Path(tmp) / "v2.json"
            source_path.write_text(json.dumps(complete_v1_manifest()))
            first = migrate_file(source_path, target_path)
            self.assertEqual(migrate_file(source_path, target_path), first)

            changed = json.loads(target_path.read_text())
            changed["run"]["status"] = "blocked"
            target_path.write_text(json.dumps(changed))
            with self.assertRaisesRegex(ValueError, "migration target already exists with different content"):
                migrate_file(source_path, target_path)

    def test_cli_requires_separate_output_and_returns_clean_errors(self):
        with tempfile.TemporaryDirectory() as tmp:
            source_path = Path(tmp) / "v1.json"
            target_path = Path(tmp) / "v2.json"
            source_path.write_text(json.dumps(complete_v1_manifest()))
            completed = subprocess.run(
                [sys.executable, "-m", "protocol.v2.migrate_v1", str(source_path), "--output", str(target_path)],
                text=True, capture_output=True, check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertEqual(json.loads(completed.stdout)["protocol_version"], "2.0")
            self.assertTrue(target_path.exists())

            invalid = subprocess.run(
                [sys.executable, "-m", "protocol.v2.migrate_v1", str(source_path), "--output", str(source_path)],
                text=True, capture_output=True, check=False,
            )
            self.assertEqual(invalid.returncode, 2)
            self.assertIn("source and output must differ", invalid.stderr)
            self.assertNotIn("Traceback", invalid.stderr)
```

- [ ] **Step 2: Run and verify missing file migration**

```bash
python3 -m unittest tests.test_protocol_v2_migration.ProtocolV2MigrationFileTests -v
```

Expected: FAIL importing `migrate_file`.

- [ ] **Step 3: Implement atomic, idempotent publication**

Add `argparse`, `sys`, and `Path`. Import `_atomic_write` and `_manifest_lock` from `protocol.v2.e2e_protocol`; do not call `save_manifest`, because ordinary saves increment the revision and migration must preserve it.

```python
def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read migration source: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError("migration source must be an object")
    return value


def migrate_file(source_path: str | Path, target_path: str | Path) -> dict[str, Any]:
    source = Path(source_path).resolve()
    target = Path(target_path).resolve()
    if source == target:
        raise ValueError("source and output must differ")
    migrated = migrate_manifest(_read_json(source))
    with _manifest_lock(target):
        if target.exists():
            existing = _read_json(target)
            if existing == migrated:
                return existing
            raise ValueError("migration target already exists with different content")
        _atomic_write(target, migrated)
    return migrated
```

Add the complete migration CLI:

```python
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source")
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    try:
        result = migrate_file(args.source, args.output)
    except (ValueError, ProtocolError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run targeted and full suites**

```bash
python3 -m unittest tests.test_protocol_v2_migration -v
python3 -m unittest discover -s tests -v
```

Expected: 7 migration tests pass; full suite reports 114 tests and `OK`.

- [ ] **Step 5: Commit atomic migration**

```bash
git add protocol/v2/migrate_v1.py tests/test_protocol_v2_migration.py
git commit -m "feat: publish protocol 2 migrations atomically"
```

---

### Task 7: JSON Schema contracts and canonical operating guide

**Files:**
- Create: `protocol/v2/manifest.schema.json`
- Create: `protocol/v2/README.md`
- Create: `tests/test_protocol_v2_schema.py`

**Interfaces:**
- Documents: the exact Python-validator vocabulary and CLI commands.
- Validates: schema files are parseable Draft 2020-12 documents with the required strict core fields and open extension `data` object.
- Does not modify: current skill bundles or `scripts/sync_protocol.py`; those change during the web-migration subproject.

- [ ] **Step 1: Write failing schema contract tests**

Create `tests/test_protocol_v2_schema.py`:

```python
import json
import unittest
from pathlib import Path

from protocol.v2.e2e_protocol import REQUIRED_FIELDS, SURFACES, TRANSITIONS


ROOT = Path(__file__).parents[1]


class ProtocolV2SchemaTests(unittest.TestCase):
    def test_core_schema_matches_runtime_vocabulary(self):
        schema = json.loads((ROOT / "protocol/v2/manifest.schema.json").read_text())
        self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")
        self.assertEqual(schema["$id"], "urn:e2e-testing:protocol:2.0")
        self.assertFalse(schema["additionalProperties"])
        self.assertEqual(schema["required"], list(REQUIRED_FIELDS))
        self.assertEqual(set(schema["properties"]["run"]["properties"]["status"]["enum"]), set(TRANSITIONS))
        self.assertEqual(set(schema["$defs"]["surface"]["enum"]), SURFACES)
        self.assertNotIn("maxItems", schema["properties"]["systems"])

    def test_extension_envelope_is_strict_but_data_is_surface_owned(self):
        schema = json.loads((ROOT / "protocol/v2/manifest.schema.json").read_text())
        extension = schema["$defs"]["extension"]
        self.assertFalse(extension["additionalProperties"])
        self.assertEqual(extension["required"], ["id", "namespace", "version", "owner", "data"])
        self.assertEqual(extension["properties"]["data"], {"type": "object"})

    def test_web_migration_extension_has_stable_identity(self):
        schema = json.loads((ROOT / "protocol/v2/extensions/web.schema.json").read_text())
        self.assertEqual(schema["$id"], "urn:e2e-testing:extension:web:1.0")
        self.assertEqual(schema["required"], ["driver", "project", "target"])
```

- [ ] **Step 2: Run and verify the core schema is missing**

```bash
python3 -m unittest tests.test_protocol_v2_schema -v
```

Expected: FAIL with `FileNotFoundError` for `protocol/v2/manifest.schema.json`.

- [ ] **Step 3: Create the Protocol 2 JSON Schema**

Create a Draft 2020-12 schema whose top level is strict and whose `required` order exactly matches `REQUIRED_FIELDS`. Encode:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "urn:e2e-testing:protocol:2.0",
  "title": "E2E Testing Protocol 2 Manifest",
  "type": "object",
  "additionalProperties": false,
  "required": [
    "protocol_version", "run", "systems", "journeys", "execution_units",
    "checks", "evidence", "actions", "handoffs", "authorizations",
    "attempts", "extensions"
  ],
  "properties": {
    "protocol_version": {"const": "2.0"},
    "run": {"$ref": "#/$defs/run"},
    "systems": {"type": "array", "minItems": 1, "items": {"$ref": "#/$defs/system"}},
    "journeys": {"type": "array", "items": {"$ref": "#/$defs/journey"}},
    "execution_units": {"type": "array", "items": {"$ref": "#/$defs/executionUnit"}},
    "checks": {"type": "array", "items": {"$ref": "#/$defs/check"}},
    "evidence": {"type": "array", "items": {"$ref": "#/$defs/idObject"}},
    "actions": {"type": "array", "items": {"$ref": "#/$defs/action"}},
    "handoffs": {"type": "array", "items": {"$ref": "#/$defs/idObject"}},
    "authorizations": {"type": "array", "items": {"$ref": "#/$defs/idObject"}},
    "attempts": {"type": "array", "items": {"$ref": "#/$defs/idObject"}},
    "extensions": {"type": "array", "items": {"$ref": "#/$defs/extension"}}
  },
  "$defs": {
    "surface": {"enum": ["web", "service", "mobile", "desktop"]},
    "run": {
      "type": "object",
      "additionalProperties": false,
      "required": ["id", "revision", "mode", "autonomy", "status", "created_at", "updated_at", "attempt_budget"],
      "properties": {
        "id": {"type": "string", "pattern": "^run-[a-z0-9-]+$"},
        "revision": {"type": "integer", "minimum": 0},
        "mode": {"enum": ["plan", "generate", "verify", "repair"]},
        "autonomy": {
          "type": "object", "additionalProperties": false,
          "required": ["mode", "auto_repair"],
          "properties": {"mode": {"enum": ["explicit", "auto"]}, "auto_repair": {"type": "boolean"}}
        },
        "status": {"enum": [
          "initialized", "planned", "ready-for-adapter", "generated-unverified", "verifying",
          "repair-ready", "handoff-required", "needs-clarification", "needs-authorization",
          "verified", "blocked", "capability-unavailable", "extension-incompatible"
        ]},
        "created_at": {"type": ["string", "null"]},
        "updated_at": {"type": ["string", "null"]},
        "attempt_budget": {
          "type": "object", "additionalProperties": false,
          "required": ["repair", "verification", "wall_clock_seconds"],
          "properties": {
            "repair": {"type": "integer", "minimum": 0},
            "verification": {"type": "integer", "minimum": 1},
            "wall_clock_seconds": {"type": "integer", "minimum": 1}
          }
        }
      }
    },
    "system": {
      "type": "object",
      "required": ["id", "project_root", "primary_surface", "boundary", "target"],
      "properties": {
        "id": {"type": "string"}, "project_root": {"type": "string"},
        "primary_surface": {"anyOf": [{"$ref": "#/$defs/surface"}, {"type": "null"}]},
        "boundary": {"$ref": "#/$defs/boundary"}, "target": {"$ref": "#/$defs/target"}
      },
      "additionalProperties": false
    },
    "boundary": {
      "type": "object", "additionalProperties": false,
      "required": ["status", "actors", "public_interfaces", "evidence_ids"],
      "properties": {
        "status": {"enum": ["unresolved", "declared", "needs-clarification"]},
        "actors": {"type": "array", "items": {"type": "string"}},
        "public_interfaces": {"type": "array", "items": {"$ref": "#/$defs/publicInterface"}},
        "evidence_ids": {"type": "array", "items": {"type": "string"}}
      }
    },
    "publicInterface": {
      "type": "object", "additionalProperties": true,
      "required": ["id", "kind", "evidence_ids"],
      "properties": {
        "id": {"type": "string"},
        "kind": {"enum": ["web", "rest", "graphql", "grpc", "websocket", "queue", "stream"]},
        "endpoint_ref": {"type": ["string", "null"]},
        "evidence_ids": {"type": "array", "items": {"type": "string"}}
      }
    },
    "target": {
      "type": "object", "additionalProperties": false,
      "required": ["tier", "endpoint_refs", "credential_refs", "mutation_policy"],
      "properties": {
        "tier": {"enum": ["local", "ephemeral", "staging", "production", "unspecified"]},
        "endpoint_refs": {"type": "array", "items": {"type": "string"}},
        "credential_refs": {"type": "array", "items": {"type": "string"}},
        "mutation_policy": {"$ref": "#/$defs/mutationPolicy"}
      }
    },
    "mutationPolicy": {
      "type": "object", "additionalProperties": false,
      "required": ["namespace_ref", "allowed_classes"],
      "properties": {
        "namespace_ref": {"type": ["string", "null"]},
        "allowed_classes": {"type": "array", "items": {"type": "string"}}
      }
    },
    "idObject": {"type": "object", "required": ["id"], "properties": {"id": {"type": "string"}}, "additionalProperties": true},
    "journey": {"type": "object", "required": ["id", "system_id", "status"], "properties": {"id": {"type": "string"}, "system_id": {"type": "string"}, "status": {"type": "string"}}, "additionalProperties": true},
    "executionUnit": {"type": "object", "required": ["id", "system_id", "surface", "capability", "status"], "properties": {"id": {"type": "string"}, "system_id": {"type": "string"}, "surface": {"$ref": "#/$defs/surface"}, "capability": {"type": "string"}, "extension_id": {"type": ["string", "null"]}, "status": {"type": "string"}}, "additionalProperties": true},
    "check": {"type": "object", "required": ["id", "journey_id", "execution_unit_id", "status"], "properties": {"id": {"type": "string"}, "journey_id": {"type": "string"}, "execution_unit_id": {"type": "string"}, "status": {"type": "string"}}, "additionalProperties": true},
    "action": {"type": "object", "required": ["id", "capability", "journey_ids"], "properties": {"id": {"type": "string"}, "capability": {"type": "string"}, "journey_ids": {"type": "array", "items": {"type": "string"}}, "resume": {"type": "object"}}, "additionalProperties": true},
    "extension": {
      "type": "object", "additionalProperties": false,
      "required": ["id", "namespace", "version", "owner", "data"],
      "properties": {
        "id": {"type": "string"},
        "namespace": {"type": "string", "pattern": "^[a-z][a-z0-9]*(?:\\.[a-z][a-z0-9-]*)+$"},
        "version": {"type": "string", "pattern": "^[0-9]+\\.[0-9]+$"},
        "owner": {"type": "string"},
        "data": {"type": "object"}
      }
    }
  }
}
```

Keep Python semantic validation authoritative for cross-record references, append-only behavior, and unknown-extension preservation; the JSON Schema documents shape and vocabulary.

- [ ] **Step 4: Write the canonical operating guide**

Create `protocol/v2/README.md` documenting exactly:

````markdown
# Protocol 2

Protocol 2 is the stable manifest kernel for E2E Testing V2 through V6. Surface-specific data belongs in namespaced, versioned extensions.

## Canonical commands

```sh
python3 protocol/v2/e2e_protocol.py init --project-root PROJECT --output PROJECT/.e2e/manifest.json
python3 protocol/v2/e2e_protocol.py validate PROJECT/.e2e/manifest.json
python3 -m protocol.v2.migrate_v1 PROJECT/.e2e/manifest-v1.json --output PROJECT/.e2e/manifest.json
```

Migration is explicit and lossless. It never overwrites its source. An identical rerun is accepted; a divergent existing target is rejected.

## Compatibility

- The core accepts Protocol `2.0` only.
- Adapters declare supported ranges for their extension namespaces.
- Unknown extensions remain valid and unchanged, while routing reports `capability-unavailable`.
- A known namespace outside every supported range reports `extension-incompatible`.
- The core permits multiple systems and surfaces; V2 applies a separate one-system/one-primary-surface policy.

## Authority

`manifest.schema.json` defines core shape. `e2e_protocol.py` additionally enforces references, revisions, append-only evidence and attempts, secret safety, and extension-preservation rules.
````

- [ ] **Step 5: Run schema, protocol, and full verification**

```bash
python3 -m unittest tests.test_protocol_v2_schema -v
python3 -m unittest tests.test_protocol_v2 tests.test_protocol_v2_extensions tests.test_protocol_v2_migration -v
python3 -m unittest discover -s tests -v
python3 scripts/sync_protocol.py --check
python3 scripts/validate_skills.py
git diff --check
```

Expected:

- 3 schema tests pass.
- All Protocol 2 test modules pass.
- Full suite reports 117 tests and `OK`.
- `sync_protocol.py --check`, skill validation, and whitespace checks exit `0` with no output.

- [ ] **Step 6: Commit schema and operating guide**

```bash
git add protocol/v2/manifest.schema.json protocol/v2/README.md tests/test_protocol_v2_schema.py
git commit -m "docs: define protocol 2 schema contract"
```

---

## Final Verification Gate

- [ ] Run the complete deterministic suite:

```bash
python3 -m unittest discover -s tests -v
```

Expected: 117 tests, zero failures, `OK`.

- [ ] Run repository contract checks:

```bash
python3 scripts/sync_protocol.py --check
python3 scripts/validate_skills.py
git diff --check
git status --short
```

Expected: the first three commands exit `0`; `git status --short` shows no implementation changes after the task commits, apart from the pre-existing untracked `.codegraph/` directory.

- [ ] Inspect the subproject history:

```bash
git log --oneline --max-count=7
```

Expected: seven focused commits for the kernel, semantic validation, extension registry, persistence, pure migration, atomic migration, and schema documentation.

Do not update the skills or their bundled protocol copies in this subproject. The next approved design and plan will migrate `e2e-testing` and rename `e2e-web-playwright` to `e2e-web`.
